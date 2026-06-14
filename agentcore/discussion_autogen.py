"""AutoGen-backed dynamic DISCUSSION phase (opt-in via DISCUSSION_MODE=dynamic).

All AutoGen knowledge lives here. The pure helpers below import NO AutoGen, so they
stay unit-testable and let the orchestrator import this module without the dependency
installed; run_dynamic_discussion (a later task) imports AutoGen lazily inside its body.
"""
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple
import re

from agentcore.events import Event
from agentcore.verify import check_grounding

CONSENSUS = "<CONSENSUS>"


def strip_consensus(text: str) -> str:
    return (text or "").replace(CONSENSUS, "").strip()


def is_consensus(text: str) -> bool:
    return CONSENSUS in (text or "")


def _format_messages(messages: Sequence[Any]) -> str:
    """Render AutoGen messages (objects with .source/.content) or (name, text) tuples
    into a plain transcript the selector prompt can read."""
    lines = []
    for m in messages:
        if isinstance(m, tuple) and len(m) == 2:
            src, content = m
        else:
            src = getattr(m, "source", "?")
            content = getattr(m, "content", "")
        if isinstance(content, str) and content.strip():
            lines.append("[{}] {}".format(src, content))
    return "\n".join(lines)


def make_selector(names: List[str], roles: Dict[str, str], llm: Any,
                  model: str) -> Callable[[Sequence[Any]], str]:
    """Return a selector_func(messages) -> speaker name. Asks `llm` (the reasoner) to
    pick the next speaker; on ANY failure or an unrecognized name, falls back to the
    next round-robin speaker. Never returns None (so AutoGen never runs its own
    internal selector)."""
    if not names:
        raise ValueError("names must be non-empty")
    state = {"rr": 0}
    roster = "\n".join("- {} ({})".format(n, roles.get(n, n)) for n in names)

    # rr counter is independent of LLM picks; the fallback resumes its own sequence.
    def _round_robin() -> str:
        nm = names[state["rr"] % len(names)]
        state["rr"] += 1
        return nm

    def select(messages: Sequence[Any]) -> str:
        try:
            convo = _format_messages(messages)
            ask = ("You are the moderator of a committee debate. Based on the "
                   "conversation so far, choose the single most useful next speaker.\n"
                   "Candidates:\n{}\n\nConversation:\n{}\n\n"
                   "Reply with exactly one candidate name from the list and nothing else."
                   ).format(roster, convo)
            reply = llm.chat(model=model, messages=[{"role": "user", "content": ask}])
            text = (reply.get("content") or "")
            for n in names:                      # first roster name mentioned wins
                if re.search(r"\b{}\b".format(re.escape(n)), text, re.IGNORECASE):
                    return n
            return _round_robin()                # named nobody -> fallback
        except Exception:
            return _round_robin()                # selector error -> fallback

    return select


def bridge_turn(name: str, text: str, bus: Any, ledger: Any) -> str:
    """Emit one discussion turn onto the EventBus exactly like the round-robin path:
    a `message` event, then a deterministic grounding check -> `grounding_flag` for any
    unsourced figure. Returns the consensus-stripped text."""
    clean = strip_consensus(text)
    bus.emit(Event(type="message", agent=name, data={"text": clean}))
    g = check_grounding(clean, ledger)
    if not g["grounded"]:
        bus.emit(Event(type="grounding_flag", agent=name,
                       data={"unsupported": g["unsupported"]}))
    return clean


def _discussion_system(agent: Any, roles: Dict[str, str], stock_no: str) -> str:
    """Per-agent system message: its persona + role anchor + the consensus rule."""
    role = roles.get(agent.name, getattr(agent, "role", agent.name))
    base = getattr(agent, "system_prompt", "")
    return (
        "{}\n\n"
        "You are the {}. In this committee debate about {}, speak ONLY from your own "
        "area of expertise, in one short paragraph, in your own words — do not repeat "
        "other members' wording, and cite only figures already established by the data. "
        "If you believe the committee has converged and you have nothing new to add, "
        "reply with exactly {} and nothing else."
    ).format(base, role, stock_no, CONSENSUS)


def _run_coro(coro: Any) -> None:
    """Run an async coroutine to completion from sync code, safely whether or not the
    calling thread already has a running event loop."""
    import asyncio
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        asyncio.run(coro)            # no loop in this thread (the normal case)
        return
    import concurrent.futures        # a loop is already running -> run in a side thread
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        pool.submit(asyncio.run, coro).result()


def _kickoff(stock_no: str) -> str:
    return ("Begin the committee discussion on {}. Each member argues from its own "
            "perspective; reply {} when the committee has converged."
            ).format(stock_no, CONSENSUS)


def run_dynamic_discussion(debaters: List[Any], stock_no: str,
                           agent_labels: Dict[str, str], max_turns: int,
                           llm: Any, bus: Any, ledger: Any, model: Optional[str]
                           ) -> List[Tuple[str, str]]:
    """Run the DISCUSSION phase as an AutoGen SelectorGroupChat. Bridges each produced
    turn onto the EventBus (message + grounding_flag) and returns [(name, text), ...]
    to append to the synchronous transcript. Raises on import/construction failure so
    the orchestrator can fall back to round-robin."""
    from autogen_agentchat.agents import AssistantAgent
    from autogen_agentchat.teams import SelectorGroupChat
    from autogen_agentchat.conditions import (MaxMessageTermination,
                                              TextMentionTermination)
    from autogen_ext.models.openai import OpenAIChatCompletionClient
    from autogen_core.models import ModelInfo

    names = [d.name for d in debaters]
    roles = {d.name: agent_labels.get(d.name, getattr(d, "role", d.name))
             for d in debaters}

    client = OpenAIChatCompletionClient(
        model=model, base_url=getattr(llm, "base_url", None),
        api_key=getattr(llm, "api_key", None),
        model_info=ModelInfo(vision=False, function_calling=False, json_output=False,
                             family="unknown", structured_output=False))

    agents = [AssistantAgent(name=d.name, model_client=client,
                             system_message=_discussion_system(d, roles, stock_no))
              for d in debaters]

    termination = MaxMessageTermination(max_turns) | TextMentionTermination(CONSENSUS)
    selector = make_selector(names, roles, llm, model)
    # selector_func always returns a name, so AutoGen never runs its own model-based
    # selector (and allow_repeated_speaker, which only applies to that path, is moot).
    team = SelectorGroupChat(agents, model_client=client,
                             termination_condition=termination,
                             selector_func=selector)

    produced: List[Tuple[str, str]] = []

    async def _drive() -> None:
        try:
            async for msg in team.run_stream(task=_kickoff(stock_no)):
                src = getattr(msg, "source", None)
                content = getattr(msg, "content", None)
                if src in names and isinstance(content, str) and content.strip():
                    clean = bridge_turn(src, content, bus, ledger)
                    if clean:
                        produced.append((src, clean))
        finally:
            await client.close()

    _run_coro(_drive())
    return produced
