# AutoGen Dynamic Discussion Routing — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an opt-in `DISCUSSION_MODE=dynamic` that runs the DISCUSSION phase as an AutoGen `SelectorGroupChat` (a moderator LLM picks who speaks next, debate ends early on consensus), surgically — every other phase, the tools, the report, and the three front-ends are untouched.

**Architecture:** All AutoGen knowledge lives in one new module `agentcore/discussion_autogen.py` with **deferred** AutoGen imports (top of file imports only stdlib + our modules), so its pure helpers stay unit-testable and the orchestrator stays importable without AutoGen installed. The orchestrator dispatches the DISCUSSION phase to either the existing round-robin loop (`roundrobin`, default) or `run_dynamic_discussion(...)` (`dynamic`), wrapped in a phase-level try/except fallback. Speaker selection + per-turn round-robin fallback live in our `selector_func`; AutoGen provides the team runtime, message protocol, and termination conditions.

**Tech Stack:** Python 3.12 (`.venv/bin/python`), `autogen-agentchat>=0.4` + `autogen-ext[openai]`, pytest (hand-rolled fakes, `live` marker deselected by default).

**Spec:** `docs/superpowers/specs/2026-06-14-autogen-dynamic-discussion-design.md`

**Conventions:** Test with `.venv/bin/python -m pytest`. Branch `feat/discussion-phase`. Hand-rolled fakes (no `unittest.mock`). Stage only the files each task names (no `git add -A`; untracked `.agents/` + `skills-lock.json` exist). If a `block-no-verify`/GateGuard hook blocks a combined `git add && commit`, split into separate calls; never use `--no-verify`.

---

## File Structure

**Create:**
- `agentcore/discussion_autogen.py` — all AutoGen integration. Pure helpers (`make_selector`, `strip_consensus`, `is_consensus`, `bridge_turn`, `_discussion_system`, `_kickoff`, `_format_messages`) at module top with **no AutoGen import**; `run_dynamic_discussion(...)` imports AutoGen lazily inside the function body.
- `tests/test_discussion_autogen.py` — unit tests for the pure helpers + a `@pytest.mark.live` end-to-end team run.

**Modify:**
- `committee/config.py` — `DISCUSSION_MODE`, `DISCUSSION_MAX_TURNS`.
- `agentcore/orchestrator.py` — `discussion_mode`/`discussion_max_turns` fields; extract `_run_discussion_roundrobin`; dispatch + phase-level fallback.
- `agentcore/llm.py` — store `self.base_url` / `self.api_key` so the AutoGen client can reuse the connection.
- `main.py`, `gui.py`, `committee_web/run.py` — pass `discussion_mode` + `discussion_max_turns`.
- `requirements.txt` — add the two AutoGen packages.
- `CLAUDE.md`, `README.md` — document the new mode + env vars + dependency.
- Tests: `tests/test_config.py`, `tests/test_orchestrator.py`.

---

## Task 1: Config + Orchestrator fields + front-end wiring (no behavior change)

**Files:** Modify `committee/config.py`, `agentcore/orchestrator.py`, `main.py`, `gui.py`, `committee_web/run.py`; Test `tests/test_config.py`, `tests/test_orchestrator.py`

- [ ] **Step 1: Write failing tests.**

Append to `tests/test_config.py`:
```python
def test_discussion_mode_default_and_override(monkeypatch):
    import importlib
    import committee.config as cfg
    monkeypatch.delenv("DISCUSSION_MODE", raising=False)
    importlib.reload(cfg)
    assert cfg.DISCUSSION_MODE == "roundrobin"
    monkeypatch.setenv("DISCUSSION_MODE", "dynamic")
    importlib.reload(cfg)
    assert cfg.DISCUSSION_MODE == "dynamic"
    monkeypatch.delenv("DISCUSSION_MODE", raising=False)
    importlib.reload(cfg)          # restore module to default for later tests


def test_discussion_max_turns_default_and_override(monkeypatch):
    import importlib
    import committee.config as cfg
    monkeypatch.delenv("DISCUSSION_MAX_TURNS", raising=False)
    importlib.reload(cfg)
    assert cfg.DISCUSSION_MAX_TURNS == 12
    monkeypatch.setenv("DISCUSSION_MAX_TURNS", "6")
    importlib.reload(cfg)
    assert cfg.DISCUSSION_MAX_TURNS == 6
    monkeypatch.delenv("DISCUSSION_MAX_TURNS", raising=False)
    importlib.reload(cfg)
```

Append to `tests/test_orchestrator.py`:
```python
def test_orchestrator_discussion_mode_defaults_to_roundrobin():
    o = Orchestrator(research=[], challengers=[], chair=None)
    assert o.discussion_mode == "roundrobin"
    assert o.discussion_max_turns == 12
```

- [ ] **Step 2: Run, verify fail** — `.venv/bin/python -m pytest tests/test_config.py -k discussion_mode tests/test_orchestrator.py -k defaults_to_roundrobin -v` → FAIL (`DISCUSSION_MODE` / `discussion_mode` undefined).

- [ ] **Step 3: Add config** in `committee/config.py`, after the `DISCUSSION_ROUNDS = ...` line:
```python
# Discussion engine: "roundrobin" (sequential, default) or "dynamic" (AutoGen SelectorGroupChat).
DISCUSSION_MODE = os.environ.get("DISCUSSION_MODE", "roundrobin")
# Hard cap on dynamic-mode turns (selector may end earlier on consensus).
DISCUSSION_MAX_TURNS = int(os.environ.get("DISCUSSION_MAX_TURNS", "12"))
```

- [ ] **Step 4: Add Orchestrator fields** in `agentcore/orchestrator.py`, immediately after the existing `agent_labels` field:
```python
    discussion_mode: str = "roundrobin"   # "roundrobin" | "dynamic"
    discussion_max_turns: int = 12         # dynamic-mode hard cap
```

- [ ] **Step 5: Wire the three construction sites.** In `main.py`, `committee_web/run.py`, and `gui.py`, add `DISCUSSION_MODE, DISCUSSION_MAX_TURNS` to the existing `from committee.config import ...` line, and add these two kwargs to each `Orchestrator(...)` call right after the existing `agent_labels=profile.labels.agent_names,` line:
```python
                        discussion_mode=DISCUSSION_MODE,
                        discussion_max_turns=DISCUSSION_MAX_TURNS,
```
(Match each file's indentation: `main.py` uses 24 spaces, `committee_web/run.py` 28, `gui.py` 32.)

- [ ] **Step 6: Run, verify pass.**
```bash
cd /Users/steventsai/Documents/Claude_Project/stock-ana/stock-analysis
.venv/bin/python -m pytest tests/test_config.py tests/test_orchestrator.py -v 2>&1 | tail -3
.venv/bin/python -c "import main, gui, committee_web.run; print('imports ok')"
.venv/bin/python -m pytest -q 2>&1 | tail -1
```
Expected: all PASS (fields default to `roundrobin`/12 so behavior is unchanged), `imports ok`, full suite green.

- [ ] **Step 7: Commit**
```bash
git rev-parse HEAD   # report as BASE sha
git add committee/config.py agentcore/orchestrator.py main.py gui.py committee_web/run.py tests/test_config.py tests/test_orchestrator.py
git commit -m "feat: DISCUSSION_MODE/MAX_TURNS config + orchestrator fields (default roundrobin)"
```

---

## Task 2: `discussion_autogen.py` pure helpers (no AutoGen import)

**Files:** Create `agentcore/discussion_autogen.py`, `tests/test_discussion_autogen.py`

- [ ] **Step 1: Write failing tests** — create `tests/test_discussion_autogen.py`:

```python
from agentcore.discussion_autogen import (make_selector, bridge_turn,
                                           strip_consensus, is_consensus)
from agentcore.events import EventBus, Event
from agentcore.evidence import EvidenceLedger


class _FakeLLM:
    """Records calls; returns a scripted reply or raises."""
    def __init__(self, reply=None, raises=False):
        self._reply, self._raises = reply, raises
        self.calls = []

    def chat(self, **kwargs):
        self.calls.append(kwargs)
        if self._raises:
            raise RuntimeError("selector down")
        return {"content": self._reply}


def test_selector_picks_named_speaker():
    names = ["fundamental", "technical", "risk"]
    roles = {"fundamental": "基本面", "technical": "技術面", "risk": "風險"}
    sel = make_selector(names, roles, _FakeLLM(reply="Next: technical."), model="m")
    assert sel([]) == "technical"


def test_selector_falls_back_to_round_robin_on_error():
    names = ["fundamental", "technical"]
    roles = {"fundamental": "基本面", "technical": "技術面"}
    sel = make_selector(names, roles, _FakeLLM(raises=True), model="m")
    assert sel([]) == "fundamental"   # round-robin index 0
    assert sel([]) == "technical"     # index 1
    assert sel([]) == "fundamental"   # wraps


def test_selector_falls_back_when_reply_names_nobody():
    names = ["fundamental", "technical"]
    roles = {"fundamental": "基本面", "technical": "技術面"}
    sel = make_selector(names, roles, _FakeLLM(reply="I am not sure"), model="m")
    assert sel([]) == "fundamental"   # no known name -> round-robin


def test_consensus_helpers_strip_and_detect():
    assert is_consensus("done <CONSENSUS>") is True
    assert is_consensus("still arguing") is False
    assert strip_consensus("agreed <CONSENSUS>") == "agreed"


def test_bridge_turn_emits_message_and_grounding_flag():
    bus, ledger = EventBus(), EvidenceLedger()
    events = []
    bus.subscribe(events.append)
    clean = bridge_turn("fundamental", "PE 約 30.52 偏高 <CONSENSUS>", bus, ledger)
    assert clean == "PE 約 30.52 偏高"                       # sentinel stripped
    msgs = [e for e in events if e.type == "message"]
    assert msgs and msgs[0].agent == "fundamental" and "30.52" in msgs[0].data["text"]
    flags = [e for e in events if e.type == "grounding_flag"]
    assert flags and 30.52 in flags[0].data["unsupported"]   # 30.52 not in (empty) ledger


def test_bridge_turn_grounded_text_has_no_flag():
    bus, ledger = EventBus(), EvidenceLedger()
    events = []
    bus.subscribe(events.append)
    bridge_turn("technical", "維持看多,無新數字", bus, ledger)
    assert not [e for e in events if e.type == "grounding_flag"]
```

- [ ] **Step 2: Run, verify fail** — `.venv/bin/python -m pytest tests/test_discussion_autogen.py -v` → FAIL (module does not exist).

- [ ] **Step 3: Create `agentcore/discussion_autogen.py`** (AutoGen imported only inside `run_dynamic_discussion`, added in Task 3):

```python
"""AutoGen-backed dynamic DISCUSSION phase (opt-in via DISCUSSION_MODE=dynamic).

All AutoGen knowledge lives here. The pure helpers below import NO AutoGen, so they
stay unit-testable and let the orchestrator import this module without the dependency
installed; run_dynamic_discussion (Task 3) imports AutoGen lazily inside its body.
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
```

- [ ] **Step 4: Run, verify pass** — `.venv/bin/python -m pytest tests/test_discussion_autogen.py -v` → all PASS. Full suite `.venv/bin/python -m pytest -q` → PASS.

- [ ] **Step 5: Commit**
```bash
git rev-parse HEAD
git add agentcore/discussion_autogen.py tests/test_discussion_autogen.py
git commit -m "feat: pure helpers for AutoGen dynamic discussion (selector + bridge + consensus)"
```

---

## Task 3: `run_dynamic_discussion` (real AutoGen team) + deps + LLMClient connection

**Files:** Modify `agentcore/discussion_autogen.py`, `agentcore/llm.py`, `requirements.txt`; Test `tests/test_discussion_autogen.py` (live)

> The team-assembly code below targets the `autogen-agentchat` 0.4 API. Its safety net is twofold: the orchestrator's phase-level fallback (Task 4) means a runtime failure here never breaks a committee run, and unit coverage already lives in the pure helpers (Task 2). The one live test is deselected by default. **Verify import paths against the installed version** during Step 4 and adjust if the package moved a symbol.

- [ ] **Step 1: Install the dependencies**
```bash
cd /Users/steventsai/Documents/Claude_Project/stock-ana/stock-analysis
.venv/bin/python -m pip install "autogen-agentchat>=0.4" "autogen-ext[openai]"
.venv/bin/python -c "import autogen_agentchat, autogen_ext; print('autogen import ok')"
```
Expected: `autogen import ok`. Then add to `requirements.txt` (after the `openai>=2.0` line):
```
autogen-agentchat>=0.4
autogen-ext[openai]
```

- [ ] **Step 2: Expose the connection on `LLMClient`.** In `agentcore/llm.py` `__init__`, store the URL/key so the AutoGen client can reuse them. Replace the body from `if client is not None:` through the `OpenAI(...)` construction with:
```python
        if client is not None:
            self._client = client
            self.base_url = base_url
            self.api_key = None
            return
        key = api_key or os.environ.get(api_key_env)
        if not key:
            raise RuntimeError("{} is not set".format(api_key_env))
        from openai import OpenAI

        self.base_url = base_url
        self.api_key = key
        self._client = OpenAI(base_url=base_url, api_key=key)
```

- [ ] **Step 3: Add `run_dynamic_discussion` + prompt builders** to the END of `agentcore/discussion_autogen.py`:

```python
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


def _kickoff(stock_no: str) -> str:
    return ("Begin the committee discussion on {}. Each member argues from its own "
            "perspective; reply {} when the committee has converged."
            ).format(stock_no, CONSENSUS)


def run_dynamic_discussion(debaters: List[Any], stock_no: str,
                           agent_labels: Dict[str, str], max_turns: int,
                           llm: Any, bus: Any, ledger: Any, model: str
                           ) -> List[Tuple[str, str]]:
    """Run the DISCUSSION phase as an AutoGen SelectorGroupChat. Bridges each produced
    turn onto the EventBus (message + grounding_flag) and returns [(name, text), ...]
    to append to the synchronous transcript. Raises on import/construction failure so
    the orchestrator can fall back to round-robin."""
    import asyncio

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
    team = SelectorGroupChat(agents, model_client=client,
                             termination_condition=termination,
                             selector_func=selector, allow_repeated_speaker=False)

    produced: List[Tuple[str, str]] = []

    async def _drive() -> None:
        async for msg in team.run_stream(task=_kickoff(stock_no)):
            src = getattr(msg, "source", None)
            content = getattr(msg, "content", None)
            if src in names and isinstance(content, str) and content.strip():
                clean = bridge_turn(src, content, bus, ledger)
                if clean:
                    produced.append((src, clean))

    asyncio.run(_drive())
    return produced
```

- [ ] **Step 4: Verify (no live network).**
```bash
.venv/bin/python -c "from agentcore.discussion_autogen import run_dynamic_discussion; print('symbol ok')"
.venv/bin/python -m pytest tests/test_discussion_autogen.py tests/test_llm.py -q 2>&1 | tail -2
.venv/bin/python -m pytest -q 2>&1 | tail -1
```
Expected: `symbol ok` (confirms AutoGen import paths resolve at call-definition time and the module still imports), llm + discussion tests PASS, full suite PASS. If `symbol ok` fails on an ImportError, fix the import path to match the installed `autogen-agentchat` version, then re-run.

- [ ] **Step 5: Add a live end-to-end test** to `tests/test_discussion_autogen.py` (deselected by default via the `live` marker):
```python
import os
import pytest


@pytest.mark.live
def test_dynamic_discussion_live_smoke():
    """Real AutoGen team run against the configured endpoint. Needs network + key."""
    from agentcore.discussion_autogen import run_dynamic_discussion
    from agentcore.events import EventBus
    from agentcore.evidence import EvidenceLedger
    from agentcore.llm import LLMClient
    from committee.config import BASE_URL, API_KEY_ENV, MODEL_REASONER
    from committee.agents import build_committee
    from committee.markets.tw import tw_prompts

    if not os.environ.get(API_KEY_ENV):
        pytest.skip("{} not set".format(API_KEY_ENV))
    llm = LLMClient(base_url=BASE_URL, api_key_env=API_KEY_ENV)
    c = build_committee(tw_prompts())
    bus, ledger = EventBus(), EvidenceLedger()
    turns = run_dynamic_discussion(
        debaters=list(c.research) + list(c.challengers), stock_no="2330",
        agent_labels={}, max_turns=6, llm=llm, bus=bus, ledger=ledger,
        model=MODEL_REASONER)
    assert isinstance(turns, list) and turns           # at least one turn produced
    assert all(isinstance(t, tuple) and len(t) == 2 for t in turns)
```

- [ ] **Step 6: Run the live test manually (operator).** With network + key set:
```bash
.venv/bin/python -m pytest tests/test_discussion_autogen.py -m live -k live_smoke -v
```
Expected: PASS — confirms the real AutoGen team runs, the selector routes, and turns come back. (If it fails on AutoGen API drift, adjust `run_dynamic_discussion` per the error and re-run. This is the task's real integration gate.)

- [ ] **Step 7: Commit**
```bash
git rev-parse HEAD
git add agentcore/discussion_autogen.py agentcore/llm.py requirements.txt tests/test_discussion_autogen.py
git commit -m "feat: run_dynamic_discussion (AutoGen SelectorGroupChat) + deps + live smoke"
```

---

## Task 4: Orchestrator dispatch + phase-level fallback

**Files:** Modify `agentcore/orchestrator.py`; Test `tests/test_orchestrator.py`

- [ ] **Step 1: Write failing tests** — append to `tests/test_orchestrator.py`:
```python
def test_dynamic_mode_uses_run_dynamic_discussion(monkeypatch):
    from agentcore import discussion_autogen
    fund = _StubAgent("fundamental", "研究A")
    risk = _StubAgent("risk", "研究B")
    chair = _StubAgent("chair", "建議: 持有")
    captured = {}

    def fake_run(**kwargs):
        captured.update(kwargs)
        return [("fundamental", "動態發言A"), ("risk", "動態發言B")]

    monkeypatch.setattr(discussion_autogen, "run_dynamic_discussion", fake_run)
    orch = _orch([fund], [risk], chair, discussion_rounds=1,
                 discussion_mode="dynamic", discussion_max_turns=8)
    bus, ledger = EventBus(), EvidenceLedger()
    events = []
    bus.subscribe(events.append)

    orch.run(stock_no="2330", llm=None, registry=None, bus=bus, ledger=ledger)

    phases = [e.data.get("phase") for e in events if e.type == "phase" and "phase" in e.data]
    assert phases == ["RESEARCH", "DISCUSSION", "VERDICT"]
    assert captured["max_turns"] == 8                 # field threaded through
    assert "動態發言A" in chair.tasks[0]["task"]        # Chair sees the dynamic turns


def test_dynamic_mode_falls_back_to_roundrobin_on_failure(monkeypatch):
    from agentcore import discussion_autogen

    def boom(**kwargs):
        raise RuntimeError("autogen unavailable")

    monkeypatch.setattr(discussion_autogen, "run_dynamic_discussion", boom)
    fund = _StubAgent("fundamental", "看多")
    risk = _StubAgent("risk", "風險偏高")
    chair = _StubAgent("chair", "建議: 持有")
    orch = _orch([fund], [risk], chair, discussion_rounds=1, discussion_mode="dynamic")
    bus, ledger = EventBus(), EvidenceLedger()
    events = []
    bus.subscribe(events.append)

    orch.run(stock_no="2330", llm=None, registry=None, bus=bus, ledger=ledger)

    phases = [e.data.get("phase") for e in events if e.type == "phase" and "phase" in e.data]
    assert phases == ["RESEARCH", "DISCUSSION", "VERDICT"]
    # fell back to round-robin: the research analyst took an extra (discussion) turn
    assert len(fund.tasks) == 2
```

- [ ] **Step 2: Run, verify fail** — `.venv/bin/python -m pytest tests/test_orchestrator.py -k "dynamic_mode" -v` → FAIL (dispatch not implemented; dynamic mode currently runs the round-robin loop, so `fake_run` is never called and `動態發言A` is absent).

- [ ] **Step 3: Refactor + dispatch in `agentcore/orchestrator.py`.**

(a) Add the import near the top (after `from agentcore.verify import check_grounding`):
```python
from agentcore import discussion_autogen
```

(b) Extract the existing discussion loop into a method. Find the current block inside `run()`:
```python
        if self.discussion_rounds > 0:
            phase("DISCUSSION")
            debaters = list(self.research) + list(self.challengers)
            member_names = {d.name for d in debaters}

            def role_of(agent):
                return self.agent_labels.get(agent.name, getattr(agent, "role", agent.name))

            for _ in range(self.discussion_rounds):
                for a in debaters:
                    # ... role-anchored task build, run_agent, grounding flag ...
```
Replace the whole `if self.discussion_rounds > 0:` body with a dispatch that delegates to one of two helpers, passing the closures it needs:
```python
        if self.discussion_rounds > 0:
            phase("DISCUSSION")
            debaters = list(self.research) + list(self.challengers)
            if self.discussion_mode == "dynamic":
                try:
                    turns = discussion_autogen.run_dynamic_discussion(
                        debaters=debaters, stock_no=stock_no,
                        agent_labels=self.agent_labels,
                        max_turns=self.discussion_max_turns, llm=llm, bus=bus,
                        ledger=ledger, model=getattr(self.chair, "model", None))
                    transcript.extend(turns)
                except Exception as exc:   # import/construction/runtime failure
                    bus.emit(Event(type="message", agent="system",
                                   data={"text": "dynamic discussion unavailable "
                                                 "({}); using round-robin".format(exc)}))
                    self._discussion_roundrobin(debaters, stock_no, transcript,
                                                run_agent, bus, ledger)
            else:
                self._discussion_roundrobin(debaters, stock_no, transcript,
                                            run_agent, bus, ledger)
```

(c) Add the extracted helper as a method on `Orchestrator` (move the original loop body verbatim into it; it keeps the exact role-anchored prompt logic from the current code):
```python
    def _discussion_roundrobin(self, debaters, stock_no, transcript, run_agent,
                               bus, ledger) -> None:
        member_names = {d.name for d in debaters}

        def role_of(agent):
            return self.agent_labels.get(agent.name, getattr(agent, "role", agent.name))

        for _ in range(self.discussion_rounds):
            for a in debaters:
                latest = _latest_points(transcript, a.name, member_names)
                others = "\n".join(
                    "- {}: {}".format(role_of(d), latest[d.name])
                    for d in debaters if d.name in latest)
                task = self.discussion_task_template.format(
                    stock=stock_no, role=role_of(a), others=others,
                    own=_own_stance(transcript, a.name))
                text = run_agent(a, task)
                transcript.append((a.name, text))
                g = check_grounding(text, ledger)
                if not g["grounded"]:
                    bus.emit(Event(type="grounding_flag", agent=a.name,
                                   data={"unsupported": g["unsupported"]}))
```
`_latest_points` and `_own_stance` are the existing module-level helpers in `agentcore/orchestrator.py` (defined near `_join`); this method calls them directly — no new import needed. The body is exactly the original DISCUSSION loop, just relocated into a method.

- [ ] **Step 4: Run, verify pass** — `.venv/bin/python -m pytest tests/test_orchestrator.py -v` → all PASS, including the pre-existing `test_discussion_phase_replaces_challenge_rebuttal_when_enabled`, `test_discussion_turn_with_unsourced_figure_is_flagged`, and `test_discussion_task_is_role_anchored_and_structured` (round-robin behavior unchanged). Full suite `.venv/bin/python -m pytest -q` → PASS.

- [ ] **Step 5: Commit**
```bash
git rev-parse HEAD
git add agentcore/orchestrator.py tests/test_orchestrator.py
git commit -m "feat: orchestrator dispatches DISCUSSION to dynamic/roundrobin with fallback"
```

---

## Task 5: Documentation + final verification

**Files:** Modify `CLAUDE.md`, `README.md`

- [ ] **Step 1: Update `CLAUDE.md`.** READ it first. Make three edits:
  - In the DISCUSSION paragraph (added earlier near the REFLECT paragraph), append: *"A `DISCUSSION_MODE=dynamic` variant runs the phase as an AutoGen `SelectorGroupChat` — a moderator LLM picks the next speaker and the debate stops early on a `<CONSENSUS>` sentinel, bounded by `DISCUSSION_MAX_TURNS` (default 12). It is opt-in (`roundrobin` is the default), confined to `agentcore/discussion_autogen.py` (AutoGen imported lazily), and falls back to round-robin if AutoGen fails. Discussion agents are tool-free in this mode."*
  - In the model/config area, note the new env vars `DISCUSSION_MODE` and `DISCUSSION_MAX_TURNS`.
  - In the "Two layers, strictly separated" section, note that `agentcore/discussion_autogen.py` is the single home of the optional AutoGen dependency.

- [ ] **Step 2: Update `README.md`.** READ it first. Add `DISCUSSION_MODE` / `DISCUSSION_MAX_TURNS` to the environment/config section, with a one-line note that `dynamic` needs `pip install autogen-agentchat autogen-ext[openai]`.

- [ ] **Step 3: Full verification.**
```bash
cd /Users/steventsai/Documents/Claude_Project/stock-ana/stock-analysis
.venv/bin/python -m pytest -q 2>&1 | tail -2
.venv/bin/python -c "import main, gui, committee_web.run; print('imports ok')"
```
Expected: full suite PASS (the `live` AutoGen test deselected), `imports ok`.

- [ ] **Step 4: Manual smoke (operator).** With a key set, run dynamic mode end-to-end and watch the DISCUSSION phase route non-sequentially and (ideally) stop early:
```bash
DISCUSSION_MODE=dynamic DISCUSSION_MAX_TURNS=8 .venv/bin/python main.py 2330
```
Expected: the DISCUSSION phase shows speakers in a non-fixed order chosen by the moderator; turns are distinct; `⚠ unverified figure` flags still appear for unsourced numbers; the run completes a normal VERDICT/VERIFY afterward. Then confirm the default is unchanged: `.venv/bin/python main.py 2330` still runs the sequential round-robin.

- [ ] **Step 5: Commit**
```bash
git rev-parse HEAD
git add CLAUDE.md README.md
git commit -m "docs: document DISCUSSION_MODE=dynamic (AutoGen) + env vars"
```

---

## Self-Review Notes

- **Spec coverage:** surgical scope + opt-in `DISCUSSION_MODE` (T1, T4), AutoGen 0.4 `SelectorGroupChat` with `asyncio.run` at the boundary (T3), reasoner selector model (T2/T3 use `model`), turn budget + `<CONSENSUS>` early stop via `MaxMessageTermination | TextMentionTermination` (T3), per-turn round-robin fallback in `make_selector` (T2) + phase-level fallback (T4), grounding flags preserved via `bridge_turn` (T2), tool-free agents (T3 `AssistantAgent` has no `tools`), config + 3-site wiring (T1), no front-end changes (none in plan — message events flow unchanged), deps (T3), docs + risks (T5). All spec sections map to a task.
- **Deferred-import invariant:** `discussion_autogen.py` imports AutoGen only inside `run_dynamic_discussion`; Tasks 2 and 4 run/pass **before** Task 3 installs the dependency, so the module and the orchestrator must import without AutoGen present — the plan orders the pure helpers (T2) and keeps the AutoGen import inside the function body specifically for this.
- **Type/name consistency:** `run_dynamic_discussion(debaters, stock_no, agent_labels, max_turns, llm, bus, ledger, model)` — same signature in T3 (definition), the T3 live test, and the T4 orchestrator call and `fake_run(**kwargs)` (which reads `kwargs["max_turns"]`). `make_selector(names, roles, llm, model)`, `bridge_turn(name, text, bus, ledger)`, `strip_consensus`/`is_consensus`, and `CONSENSUS = "<CONSENSUS>"` are consistent across T2 and T3. Orchestrator fields `discussion_mode` / `discussion_max_turns` (T1) are read in T4. `_latest_points` / `_own_stance` are the existing orchestrator helpers reused by `_discussion_roundrobin`.
- **Backward-compat:** every field defaults to the round-robin path; all current discussion tests are asserted to stay green in T4 Step 4. The `live` marker keeps the real AutoGen run out of the default suite.
- **Honest limits surfaced:** message-granularity streaming (no token typing in dynamic mode) and gemma `model_info` are documented (spec + CLAUDE.md), not silently assumed.
