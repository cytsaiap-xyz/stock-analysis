"""AutoGen-backed dynamic DISCUSSION phase (opt-in via DISCUSSION_MODE=dynamic).

All AutoGen knowledge lives here. The pure helpers below import NO AutoGen, so they
stay unit-testable and let the orchestrator import this module without the dependency
installed; run_dynamic_discussion (a later task) imports AutoGen lazily inside its body.
"""
from typing import Any, Callable, Dict, List, Sequence, Tuple

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
    state = {"rr": 0}
    roster = "\n".join("- {} ({})".format(n, roles.get(n, n)) for n in names)

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
                if n in text:
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
