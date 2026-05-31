# Agentic Investment Committee — Phase 1 (MVP) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a working, terminal-driven 3-agent committee (Fundamental, Technical, Chair) that pulls real TWSE data via tools and produces a BUY/HOLD/SELL verdict — proving the reusable agent core end-to-end.

**Architecture:** A generic agent core (`agentcore/`: LLMClient, Tool/ToolRegistry, Agent tool-loop, EventBus, EvidenceLedger, Orchestrator) with zero stock knowledge, plus a thin domain layer (`committee/`: TWSE client, indicator math, tool wiring, agent definitions). A terminal renderer subscribes to the EventBus to display the live run.

**Tech Stack:** Python 3.9, `openai` SDK (NVIDIA OpenAI-compatible endpoint), `requests` (TWSE), `pandas` (indicators), `pytest` (TDD), `python-dotenv` (config).

---

## Scope (this plan only)

This plan implements **Phase 1 (MVP) only**. Phases 2–4 (full 7-agent committee + VERIFY step, web UI, HTML report) get their own plans after the MVP resolves the spec's §10 open items.

**Intentional deviation from spec §5 tool list (YAGNI):** the MVP builds only the two data tools its two analysts actually use — `get_valuation` (Fundamental) and `get_technical_indicators` (Technical) — plus the pure `compute_indicators` helper. `get_institutional_flows` and a raw `get_price_history` tool are deferred to Phase 2, where their consumers (Institutional analyst, Risk Manager) live. `EvidenceLedger` is still built now (cheap, used in Phase 2). Building a tool with no consumer would violate YAGNI.

**Compatibility:** All code targets Python 3.9 — use `typing.List/Dict/Optional/Union`, never `X | Y` unions or `match` statements.

---

## File structure created by this plan

```
llm-test/
  agentcore/
    __init__.py
    events.py          # Event + EventBus
    evidence.py        # EvidenceLedger
    tools.py           # Tool + ToolRegistry
    llm.py             # LLMClient (NVIDIA, streaming + tool-call assembly)
    agent.py           # Agent (tool-calling loop, emits events)
    orchestrator.py    # Orchestrator (research -> verdict)
  committee/
    __init__.py
    config.py          # model mapping + settings
    data/
      __init__.py
      twse.py          # TwseClient: price_history(), valuation() + disk cache
      indicators.py    # compute_indicators() (pure pandas)
    domain_tools.py    # build_registry() -> ToolRegistry with the MVP tools
    agents.py          # build_committee() -> (analysts, chair)
  main.py              # terminal runner + TerminalRenderer
  scripts/
    twse_spike.py      # one-off: capture real TWSE responses to inspect shape
  tests/
    __init__.py
    conftest.py
    test_events.py
    test_evidence.py
    test_tools.py
    test_llm.py
    test_agent.py
    test_twse.py
    test_indicators.py
    test_domain_tools.py
    test_agents_def.py
    test_orchestrator.py
    test_live_smoke.py
  requirements.txt
  .env.example
  .gitignore
  pytest.ini
```

---

### Task 0: Project scaffold & tooling

**Files:**
- Create: `requirements.txt`, `.gitignore`, `.env.example`, `pytest.ini`
- Create: `agentcore/__init__.py`, `committee/__init__.py`, `committee/data/__init__.py`, `tests/__init__.py`, `tests/conftest.py`

- [ ] **Step 1: Initialize git (project is not yet a repo)**

Run:
```bash
git init
```
Expected: `Initialized empty Git repository ...`

- [ ] **Step 2: Create `requirements.txt`**

```
openai>=2.0
requests>=2.31
pandas>=2.0
python-dotenv>=1.0
pytest>=8.0
```

- [ ] **Step 3: Create `.gitignore`**

```
__pycache__/
*.pyc
.env
cache/
reports/
.superpowers/
.ruff_cache/
.pytest_cache/
```

- [ ] **Step 4: Create `.env.example`**

```
# Copy to .env and fill in. Never commit .env.
NVIDIA_API_KEY=nvapi-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
# Optional model overrides:
# MODEL_REASONER=moonshotai/kimi-k2.6
# MODEL_TOOL_CALLER=meta/llama-3.3-70b-instruct
```

- [ ] **Step 5: Create `pytest.ini`**

```ini
[pytest]
testpaths = tests
python_files = test_*.py
markers =
    live: hits real NVIDIA/TWSE network (deselect with -m "not live")
addopts = -m "not live"
```

- [ ] **Step 6: Create empty package files**

Create these as empty files: `agentcore/__init__.py`, `committee/__init__.py`, `committee/data/__init__.py`, `tests/__init__.py`.

- [ ] **Step 7: Create `tests/conftest.py`**

```python
import sys
from pathlib import Path

# Make project root importable so `import agentcore` works from tests.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
```

- [ ] **Step 8: Install deps and verify pytest runs**

Run:
```bash
pip install -r requirements.txt
pytest -q
```
Expected: pytest collects 0 tests and exits 0 (`no tests ran`).

- [ ] **Step 9: Commit**

```bash
git add requirements.txt .gitignore .env.example pytest.ini agentcore committee tests
git commit -m "chore: project scaffold for agentic investment committee MVP"
```

---

### Task 1: Spike — capture real TWSE response shapes

This is a **reality check** for spec §10, not TDD. It records what TWSE actually returns so the parsers (Task 7) match reality. Parser unit tests use hand-written fixtures matching the *documented* shape; this spike confirms that shape is real and prints any mismatch to fix.

**Files:**
- Create: `scripts/twse_spike.py`

- [ ] **Step 1: Write the spike script**

```python
"""One-off: fetch real TWSE endpoints and print their JSON shape.
Run manually: python scripts/twse_spike.py
TWSE endpoints (documented shapes the parsers assume):
  STOCK_DAY : data rows = [ROC date, volume, turnover, open, high, low, close, change, txns]
  BWIBBU_ALL: data rows = [code, name, dividend_yield, dividend_year, pe, pb, fin_period]
"""
import requests

HEADERS = {"User-Agent": "Mozilla/5.0 (committee-mvp spike)"}


def show(name, url, params):
    r = requests.get(url, params=params, headers=HEADERS, timeout=20)
    print("=" * 60)
    print(name, "->", r.status_code, r.url)
    body = r.json()
    if isinstance(body, dict):
        print("keys:", list(body.keys()))
        print("fields:", body.get("fields"))
        rows = body.get("data") or []
        print("first row:", rows[0] if rows else "(none)")
    else:
        print("first item:", body[0] if body else "(none)")


def main():
    show(
        "STOCK_DAY 2330",
        "https://www.twse.com.tw/exchangeReport/STOCK_DAY",
        {"response": "json", "date": "20260501", "stockNo": "2330"},
    )
    show(
        "BWIBBU_ALL",
        "https://www.twse.com.tw/exchangeReport/BWIBBU_ALL",
        {"response": "json"},
    )


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run it and read the output**

Run:
```bash
python scripts/twse_spike.py
```
Expected: prints status 200 and the `fields` + first row for each endpoint. **Confirm the column order matches the docstring.** If TWSE changed shapes, note the real order — Task 7's parser and its test fixtures must use the real order. (TWSE sometimes returns `stat: "很抱歉..."` and empty `data` for non-trading dates; if so, change the `date` param to a recent weekday and re-run.)

- [ ] **Step 3: Commit**

```bash
git add scripts/twse_spike.py
git commit -m "chore: add TWSE shape spike script"
```

---

### Task 2: EventBus

**Files:**
- Create: `agentcore/events.py`
- Test: `tests/test_events.py`

- [ ] **Step 1: Write the failing test**

```python
from agentcore.events import Event, EventBus


def test_emit_delivers_event_to_all_subscribers():
    bus = EventBus()
    seen_a, seen_b = [], []
    bus.subscribe(seen_a.append)
    bus.subscribe(seen_b.append)

    bus.emit(Event(type="message", agent="chair", data={"text": "hi"}))

    assert len(seen_a) == 1 and len(seen_b) == 1
    assert seen_a[0].type == "message"
    assert seen_a[0].agent == "chair"
    assert seen_a[0].data == {"text": "hi"}


def test_event_has_timestamp():
    e = Event(type="token", agent="x")
    assert isinstance(e.ts, float) and e.ts > 0
    assert e.data == {}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_events.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'agentcore.events'`

- [ ] **Step 3: Write minimal implementation**

```python
import time
from dataclasses import dataclass, field
from typing import Callable, Dict, List


@dataclass
class Event:
    type: str            # phase|message|token|tool_call|tool_result|verdict|verification|error
    agent: str           # agent name, or "system"
    data: Dict = field(default_factory=dict)
    ts: float = field(default_factory=time.time)


class EventBus:
    def __init__(self) -> None:
        self._subscribers: List[Callable[[Event], None]] = []

    def subscribe(self, fn: Callable[[Event], None]) -> None:
        self._subscribers.append(fn)

    def emit(self, event: Event) -> None:
        for fn in self._subscribers:
            fn(event)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_events.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add agentcore/events.py tests/test_events.py
git commit -m "feat: add Event and EventBus to agent core"
```

---

### Task 3: EvidenceLedger

**Files:**
- Create: `agentcore/evidence.py`
- Test: `tests/test_evidence.py`

- [ ] **Step 1: Write the failing test**

```python
from agentcore.evidence import EvidenceLedger


def test_record_and_read_entries():
    ledger = EvidenceLedger()
    ledger.record("get_valuation", {"stock_no": "2330"}, {"pe": 22.5})

    entries = ledger.entries()
    assert len(entries) == 1
    assert entries[0].tool == "get_valuation"
    assert entries[0].args == {"stock_no": "2330"}
    assert entries[0].result == {"pe": 22.5}


def test_args_are_copied_not_referenced():
    ledger = EvidenceLedger()
    args = {"stock_no": "2330"}
    ledger.record("get_valuation", args, {"pe": 1})
    args["stock_no"] = "MUTATED"
    assert ledger.entries()[0].args == {"stock_no": "2330"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_evidence.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'agentcore.evidence'`

- [ ] **Step 3: Write minimal implementation**

```python
from dataclasses import dataclass
from typing import Any, Dict, List


@dataclass
class EvidenceEntry:
    tool: str
    args: Dict[str, Any]
    result: Any


class EvidenceLedger:
    def __init__(self) -> None:
        self._entries: List[EvidenceEntry] = []

    def record(self, tool: str, args: Dict[str, Any], result: Any) -> None:
        self._entries.append(EvidenceEntry(tool=tool, args=dict(args), result=result))

    def entries(self) -> List[EvidenceEntry]:
        return list(self._entries)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_evidence.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add agentcore/evidence.py tests/test_evidence.py
git commit -m "feat: add EvidenceLedger to agent core"
```

---

### Task 4: Tool & ToolRegistry

**Files:**
- Create: `agentcore/tools.py`
- Test: `tests/test_tools.py`

- [ ] **Step 1: Write the failing test**

```python
import pytest
from agentcore.tools import Tool, ToolRegistry


def _sample_tool():
    return Tool(
        name="get_valuation",
        description="Get P/E etc.",
        parameters={
            "type": "object",
            "properties": {"stock_no": {"type": "string"}},
            "required": ["stock_no"],
        },
        fn=lambda stock_no: {"pe": 22.5},
    )


def test_to_openai_schema_shape():
    schema = _sample_tool().to_openai_schema()
    assert schema["type"] == "function"
    assert schema["function"]["name"] == "get_valuation"
    assert schema["function"]["parameters"]["required"] == ["stock_no"]


def test_registry_register_get_and_schemas():
    reg = ToolRegistry()
    reg.register(_sample_tool())
    assert reg.get("get_valuation").fn(stock_no="2330") == {"pe": 22.5}
    schemas = reg.schemas(["get_valuation"])
    assert len(schemas) == 1 and schemas[0]["function"]["name"] == "get_valuation"


def test_get_unknown_tool_raises():
    with pytest.raises(KeyError):
        ToolRegistry().get("nope")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_tools.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'agentcore.tools'`

- [ ] **Step 3: Write minimal implementation**

```python
from dataclasses import dataclass
from typing import Any, Callable, Dict, List


@dataclass
class Tool:
    name: str
    description: str
    parameters: Dict[str, Any]   # JSON Schema for the function arguments
    fn: Callable[..., Any]

    def to_openai_schema(self) -> Dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: Dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool:
        if name not in self._tools:
            raise KeyError("Tool not registered: " + name)
        return self._tools[name]

    def schemas(self, names: List[str]) -> List[Dict[str, Any]]:
        return [self._tools[n].to_openai_schema() for n in names]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_tools.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add agentcore/tools.py tests/test_tools.py
git commit -m "feat: add Tool and ToolRegistry to agent core"
```

---

### Task 5: LLMClient (streaming + tool-call assembly)

The hard part of agentic code: assembling streamed `tool_calls` deltas and streaming content tokens. We test against a **fake OpenAI client** (no network) that yields chunk objects shaped like the real SDK.

**Files:**
- Create: `agentcore/llm.py`
- Test: `tests/test_llm.py`

- [ ] **Step 1: Write the failing test**

```python
from types import SimpleNamespace
from agentcore.llm import LLMClient


def _delta_chunk(content=None, tool_calls=None):
    delta = SimpleNamespace(content=content, tool_calls=tool_calls)
    return SimpleNamespace(choices=[SimpleNamespace(delta=delta, finish_reason=None)])


def _tc(index, id=None, name=None, arguments=None):
    fn = SimpleNamespace(name=name, arguments=arguments)
    return SimpleNamespace(index=index, id=id, function=fn)


class _FakeCompletions:
    def __init__(self, chunks):
        self._chunks = chunks
        self.last_kwargs = None

    def create(self, **kwargs):
        self.last_kwargs = kwargs
        return iter(self._chunks)


class _FakeClient:
    def __init__(self, chunks):
        self.chat = SimpleNamespace(completions=_FakeCompletions(chunks))


def test_streams_content_tokens_and_returns_text():
    chunks = [_delta_chunk(content="Hel"), _delta_chunk(content="lo")]
    client = LLMClient(client=_FakeClient(chunks))
    tokens = []
    msg = client.chat(model="m", messages=[{"role": "user", "content": "hi"}],
                      on_token=tokens.append)
    assert tokens == ["Hel", "lo"]
    assert msg["content"] == "Hello"
    assert msg["tool_calls"] == []


def test_assembles_streamed_tool_call_fragments():
    chunks = [
        _delta_chunk(tool_calls=[_tc(0, id="call_1", name="get_valuation", arguments='{"sto')]),
        _delta_chunk(tool_calls=[_tc(0, arguments='ck_no": "2330"}')]),
    ]
    client = LLMClient(client=_FakeClient(chunks))
    msg = client.chat(model="m", messages=[{"role": "user", "content": "hi"}])
    assert msg["content"] is None
    assert msg["tool_calls"] == [
        {"id": "call_1", "name": "get_valuation", "arguments": '{"stock_no": "2330"}'}
    ]


def test_passes_tools_and_tool_choice_when_tools_given():
    client = LLMClient(client=_FakeClient([_delta_chunk(content="x")]))
    client.chat(model="m", messages=[], tools=[{"type": "function"}])
    kwargs = client._client.chat.completions.last_kwargs
    assert kwargs["stream"] is True
    assert kwargs["tool_choice"] == "auto"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_llm.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'agentcore.llm'`

- [ ] **Step 3: Write minimal implementation**

```python
import os
from typing import Any, Callable, Dict, List, Optional


class LLMClient:
    """Model-agnostic wrapper over the NVIDIA OpenAI-compatible endpoint.

    Streams content tokens (via on_token) and assembles tool-call fragments
    into a normalized assistant message:
        {"role": "assistant", "content": Optional[str], "tool_calls": [
            {"id": str, "name": str, "arguments": str(json)} ]}
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: str = "https://integrate.api.nvidia.com/v1",
        client: Any = None,
    ) -> None:
        if client is not None:
            self._client = client
            return
        key = api_key or os.environ.get("NVIDIA_API_KEY")
        if not key:
            raise RuntimeError("NVIDIA_API_KEY is not set")
        from openai import OpenAI

        self._client = OpenAI(base_url=base_url, api_key=key)

    def chat(
        self,
        model: str,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        on_token: Optional[Callable[[str], None]] = None,
        temperature: float = 0.6,
        max_tokens: int = 1024,
    ) -> Dict[str, Any]:
        kwargs: Dict[str, Any] = dict(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
        )
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        stream = self._client.chat.completions.create(**kwargs)
        content_parts: List[str] = []
        acc: Dict[int, Dict[str, str]] = {}

        for chunk in stream:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta
            text = getattr(delta, "content", None)
            if text:
                content_parts.append(text)
                if on_token:
                    on_token(text)
            for tc in (getattr(delta, "tool_calls", None) or []):
                slot = acc.setdefault(tc.index, {"id": "", "name": "", "arguments": ""})
                if getattr(tc, "id", None):
                    slot["id"] = tc.id
                fn = getattr(tc, "function", None)
                if fn is not None:
                    if getattr(fn, "name", None):
                        slot["name"] = fn.name
                    if getattr(fn, "arguments", None):
                        slot["arguments"] += fn.arguments

        tool_calls = [acc[i] for i in sorted(acc)]
        content = "".join(content_parts) if content_parts else None
        return {"role": "assistant", "content": content, "tool_calls": tool_calls}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_llm.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add agentcore/llm.py tests/test_llm.py
git commit -m "feat: add LLMClient with streaming + tool-call assembly"
```

---

### Task 6: Agent (tool-calling loop)

**Files:**
- Create: `agentcore/agent.py`
- Test: `tests/test_agent.py`

- [ ] **Step 1: Write the failing test**

```python
from agentcore.agent import Agent
from agentcore.events import EventBus
from agentcore.evidence import EvidenceLedger
from agentcore.tools import Tool, ToolRegistry


class _ScriptedLLM:
    """Returns queued assistant messages in order, ignoring inputs."""

    def __init__(self, scripted):
        self._scripted = list(scripted)
        self.calls = []

    def chat(self, model, messages, tools=None, on_token=None, **kw):
        self.calls.append({"messages": list(messages), "tools": tools})
        return self._scripted.pop(0)


def _registry():
    reg = ToolRegistry()
    reg.register(Tool(
        name="get_valuation",
        description="x",
        parameters={"type": "object", "properties": {"stock_no": {"type": "string"}}},
        fn=lambda stock_no: {"pe": 22.5, "stock_no": stock_no},
    ))
    return reg


def test_agent_calls_tool_then_returns_final_text():
    llm = _ScriptedLLM([
        {"role": "assistant", "content": None,
         "tool_calls": [{"id": "c1", "name": "get_valuation",
                         "arguments": '{"stock_no": "2330"}'}]},
        {"role": "assistant", "content": "PE is 22.5, looks fair. BULLISH.",
         "tool_calls": []},
    ])
    bus, ledger = EventBus(), EvidenceLedger()
    events = []
    bus.subscribe(events.append)
    agent = Agent(name="fundamental", role="Fundamental", system_prompt="sys",
                  model="m", tool_names=["get_valuation"])

    out = agent.run(task="analyze 2330", llm=llm, registry=_registry(),
                    bus=bus, ledger=ledger)

    assert out == "PE is 22.5, looks fair. BULLISH."
    # Tool result was recorded as evidence
    assert ledger.entries()[0].tool == "get_valuation"
    assert ledger.entries()[0].result == {"pe": 22.5, "stock_no": "2330"}
    # Emitted a tool_call, a tool_result, and a final message
    types = [e.type for e in events]
    assert "tool_call" in types and "tool_result" in types and "message" in types


def test_tool_exception_is_fed_back_not_raised():
    reg = ToolRegistry()
    reg.register(Tool(name="boom", description="x",
                      parameters={"type": "object", "properties": {}},
                      fn=lambda: (_ for _ in ()).throw(ValueError("nope"))))
    llm = _ScriptedLLM([
        {"role": "assistant", "content": None,
         "tool_calls": [{"id": "c1", "name": "boom", "arguments": "{}"}]},
        {"role": "assistant", "content": "handled gracefully", "tool_calls": []},
    ])
    bus, ledger = EventBus(), EvidenceLedger()
    events = []
    bus.subscribe(events.append)
    agent = Agent(name="x", role="x", system_prompt="s", model="m", tool_names=["boom"])

    out = agent.run(task="t", llm=llm, registry=reg, bus=bus, ledger=ledger)

    assert out == "handled gracefully"
    assert any(e.type == "error" for e in events)
    # error tool turn must not be recorded as valid evidence
    assert ledger.entries() == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_agent.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'agentcore.agent'`

- [ ] **Step 3: Write minimal implementation**

```python
import json
from dataclasses import dataclass, field
from typing import Any, Dict, List

from agentcore.events import Event


def _to_openai_tool_calls(calls: List[Dict[str, str]]) -> List[Dict[str, Any]]:
    return [
        {"id": c["id"], "type": "function",
         "function": {"name": c["name"], "arguments": c["arguments"]}}
        for c in calls
    ]


@dataclass
class Agent:
    name: str
    role: str
    system_prompt: str
    model: str
    tool_names: List[str] = field(default_factory=list)
    max_tool_rounds: int = 4

    def run(self, task, llm, registry, bus, ledger, context: str = "") -> str:
        messages: List[Dict[str, Any]] = [{"role": "system", "content": self.system_prompt}]
        if context:
            messages.append({"role": "user", "content": context})
        messages.append({"role": "user", "content": task})

        bus.emit(Event(type="phase", agent=self.name, data={"status": "start"}))
        tools_schema = registry.schemas(self.tool_names) if self.tool_names else None

        def on_token(t: str) -> None:
            bus.emit(Event(type="token", agent=self.name, data={"text": t}))

        for _ in range(self.max_tool_rounds):
            assistant = llm.chat(model=self.model, messages=messages,
                                 tools=tools_schema, on_token=on_token)
            calls = assistant.get("tool_calls") or []

            if calls:
                messages.append({"role": "assistant",
                                 "content": assistant.get("content") or "",
                                 "tool_calls": _to_openai_tool_calls(calls)})
            else:
                messages.append({"role": "assistant",
                                 "content": assistant.get("content") or ""})
                text = assistant.get("content") or ""
                bus.emit(Event(type="message", agent=self.name, data={"text": text}))
                return text

            for call in calls:
                try:
                    args = json.loads(call["arguments"] or "{}")
                except json.JSONDecodeError:
                    args = {}
                bus.emit(Event(type="tool_call", agent=self.name,
                               data={"tool": call["name"], "args": args}))
                try:
                    result = registry.get(call["name"]).fn(**args)
                    ledger.record(call["name"], args, result)
                    bus.emit(Event(type="tool_result", agent=self.name,
                                   data={"tool": call["name"], "result": result}))
                    content = json.dumps(result, ensure_ascii=False, default=str)
                except Exception as exc:  # tool failure must not crash the debate
                    content = json.dumps({"error": str(exc)})
                    bus.emit(Event(type="error", agent=self.name,
                                   data={"tool": call["name"], "error": str(exc)}))
                messages.append({"role": "tool", "tool_call_id": call["id"],
                                 "content": content})

        bus.emit(Event(type="message", agent=self.name,
                       data={"text": "(stopped: max tool rounds reached)"}))
        return ""
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_agent.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add agentcore/agent.py tests/test_agent.py
git commit -m "feat: add Agent tool-calling loop with evidence + events"
```

---

### Task 7: TwseClient (price_history, valuation, disk cache)

Parsers use the **real** column order confirmed by the Task 1 spike:
- `STOCK_DAY` data row: `[0]=ROC date, [1]=volume, [2]=turnover, [3]=open, [4]=high, [5]=low, [6]=close, [7]=change, [8]=txns, [9]=註記 (extra, unused)`.
- `BWIBBU_ALL` data row (5 cols): `[0]=code, [1]=name, [2]=PE, [3]=dividend_yield(%), [4]=PB`. (No dividend_year / fin_period — the documented 7-col shape was wrong.)

Tests use hand-written fixtures matching these real shapes; a `requests`-like session is injected (no network).

**Files:**
- Create: `committee/data/twse.py`
- Test: `tests/test_twse.py`

- [ ] **Step 1: Write the failing test**

```python
from committee.data.twse import TwseClient, roc_to_iso, to_float


class _FakeResp:
    def __init__(self, payload):
        self._payload = payload
        self.status_code = 200

    def json(self):
        return self._payload

    def raise_for_status(self):
        pass


class _FakeSession:
    def __init__(self, by_url):
        self._by_url = by_url
        self.requested = []

    def get(self, url, params=None, headers=None, timeout=None):
        self.requested.append((url, params))
        for key, payload in self._by_url.items():
            if key in url:
                return _FakeResp(payload)
        raise AssertionError("unexpected url: " + url)


def test_roc_to_iso_and_to_float_helpers():
    assert roc_to_iso("115/05/02") == "2026-05-02"
    assert to_float("1,234.50") == 1234.5
    assert to_float("--") is None


def test_valuation_parses_bwibbu_all_row(tmp_path):
    payload = {"fields": ["股票代號", "股票名稱", "本益比", "殖利率(%)", "股價淨值比"],
               "data": [["2330", "台積電", "22.50", "1.85", "6.30"],
                        ["2317", "鴻海", "10.10", "4.10", "1.20"]]}
    session = _FakeSession({"BWIBBU_ALL": payload})
    client = TwseClient(cache_dir=str(tmp_path), session=session)

    val = client.valuation("2330")
    assert val == {"stock_no": "2330", "name": "台積電",
                   "pe": 22.5, "pb": 6.3, "dividend_yield": 1.85}


def test_price_history_parses_and_orders_rows(tmp_path):
    payload = {"stat": "OK",
               "fields": ["日期", "成交股數", "成交金額", "開盤價", "最高價",
                          "最低價", "收盤價", "漲跌價差", "成交筆數"],
               "data": [["115/05/02", "20,000,000", "1", "900.00", "910.00",
                         "895.00", "905.00", "+5.00", "30000", ""],
                        ["115/05/03", "21,000,000", "1", "906.00", "915.00",
                         "900.00", "912.00", "+7.00", "31000", ""]]}
    session = _FakeSession({"STOCK_DAY": payload})
    client = TwseClient(cache_dir=str(tmp_path), session=session)

    rows = client.price_history("2330", months=1)
    assert rows[0] == {"date": "2026-05-02", "open": 900.0, "high": 910.0,
                       "low": 895.0, "close": 905.0, "volume": 20000000}
    assert rows[-1]["date"] == "2026-05-03"


def test_disk_cache_avoids_second_network_call(tmp_path):
    payload = {"fields": ["股票代號", "股票名稱", "本益比", "殖利率(%)", "股價淨值比"],
               "data": [["2330", "台積電", "22.50", "1.85", "6.30"]]}
    session = _FakeSession({"BWIBBU_ALL": payload})
    client = TwseClient(cache_dir=str(tmp_path), session=session)
    client.valuation("2330")
    client.valuation("2330")
    # BWIBBU_ALL is one snapshot for the day -> only one network call.
    assert len(session.requested) == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_twse.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'committee.data.twse'`

- [ ] **Step 3: Write minimal implementation**

```python
import json
import os
from datetime import date
from typing import Any, Dict, List, Optional

_BASE = "https://www.twse.com.tw"
_HEADERS = {"User-Agent": "Mozilla/5.0 (committee-mvp)"}


def roc_to_iso(roc: str) -> str:
    """'115/05/02' (ROC year) -> '2026-05-02'."""
    y, m, d = roc.split("/")
    return "{:04d}-{}-{}".format(int(y) + 1911, m, d)


def to_float(raw: str) -> Optional[float]:
    raw = (raw or "").replace(",", "").replace("+", "").strip()
    if raw in ("", "--", "X0.00", "null", "None"):
        return None
    try:
        return float(raw)
    except ValueError:
        return None


class TwseClient:
    def __init__(self, cache_dir: str = "cache", session: Any = None,
                 today: Optional[date] = None) -> None:
        self._cache_dir = cache_dir
        self._today = today or date.today()
        if session is not None:
            self._session = session
        else:
            import requests
            self._session = requests.Session()
        os.makedirs(self._cache_dir, exist_ok=True)

    def _get_json(self, endpoint: str, params: Dict[str, str], cache_key: str) -> Dict[str, Any]:
        path = os.path.join(self._cache_dir, cache_key + ".json")
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as fh:
                return json.load(fh)
        url = _BASE + "/exchangeReport/" + endpoint
        resp = self._session.get(url, params=params, headers=_HEADERS, timeout=20)
        resp.raise_for_status()
        body = resp.json()
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(body, fh, ensure_ascii=False)
        return body

    def valuation(self, stock_no: str) -> Dict[str, Any]:
        key = "bwibbu_all_" + self._today.strftime("%Y%m%d")
        body = self._get_json("BWIBBU_ALL", {"response": "json"}, key)
        for row in body.get("data") or []:
            if row and row[0] == stock_no:
                return {"stock_no": stock_no, "name": row[1],
                        "pe": to_float(row[2]), "dividend_yield": to_float(row[3]),
                        "pb": to_float(row[4])}
        raise ValueError("No valuation row for stock " + stock_no)

    def price_history(self, stock_no: str, months: int = 3) -> List[Dict[str, Any]]:
        rows: List[Dict[str, Any]] = []
        for yyyymm in self._recent_months(months):
            key = "stock_day_{}_{}".format(stock_no, yyyymm)
            body = self._get_json(
                "STOCK_DAY",
                {"response": "json", "date": yyyymm + "01", "stockNo": stock_no},
                key,
            )
            for row in body.get("data") or []:
                rows.append({
                    "date": roc_to_iso(row[0]),
                    "open": to_float(row[3]), "high": to_float(row[4]),
                    "low": to_float(row[5]), "close": to_float(row[6]),
                    "volume": int(float((row[1] or "0").replace(",", ""))),
                })
        rows.sort(key=lambda r: r["date"])
        return rows

    def _recent_months(self, months: int) -> List[str]:
        out: List[str] = []
        y, m = self._today.year, self._today.month
        for _ in range(months):
            out.append("{:04d}{:02d}".format(y, m))
            m -= 1
            if m == 0:
                m = 12
                y -= 1
        return list(reversed(out))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_twse.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add committee/data/twse.py tests/test_twse.py
git commit -m "feat: add TwseClient with valuation + price history and disk cache"
```

---

### Task 8: compute_indicators (pure pandas)

**Files:**
- Create: `committee/data/indicators.py`
- Test: `tests/test_indicators.py`

- [ ] **Step 1: Write the failing test**

```python
from committee.data.indicators import compute_indicators


def _series(closes):
    return [{"date": "2026-05-{:02d}".format(i + 1),
             "open": c, "high": c, "low": c, "close": c, "volume": 1000 + i}
            for i, c in enumerate(closes)]


def test_moving_averages_and_trend_up():
    closes = list(range(1, 26))  # 1..25, strictly rising
    out = compute_indicators(_series(closes))
    assert out["last_close"] == 25.0
    assert round(out["ma5"], 2) == 23.0       # mean(21..25)
    assert round(out["ma20"], 2) == 15.5      # mean(6..25)
    assert out["ma60"] is None                # not enough data
    assert out["trend"] == "up"               # last_close > ma20


def test_trend_down_when_below_ma20():
    closes = list(range(25, 0, -1))  # 25..1, falling
    out = compute_indicators(_series(closes))
    assert out["trend"] == "down"


def test_empty_series_returns_nulls():
    out = compute_indicators([])
    assert out["last_close"] is None and out["ma5"] is None and out["trend"] == "flat"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_indicators.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'committee.data.indicators'`

- [ ] **Step 3: Write minimal implementation**

```python
from typing import Any, Dict, List, Optional

import pandas as pd


def _ma(closes: "pd.Series", window: int) -> Optional[float]:
    if len(closes) < window:
        return None
    return float(closes.tail(window).mean())


def compute_indicators(ohlcv: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not ohlcv:
        return {"last_close": None, "ma5": None, "ma20": None, "ma60": None,
                "pct_change_period": None, "avg_volume": None, "trend": "flat"}

    df = pd.DataFrame(ohlcv).sort_values("date")
    closes = df["close"].astype(float).reset_index(drop=True)
    last_close = float(closes.iloc[-1])
    ma20 = _ma(closes, 20)

    if ma20 is None:
        trend = "flat"
    elif last_close > ma20:
        trend = "up"
    elif last_close < ma20:
        trend = "down"
    else:
        trend = "flat"

    first_close = float(closes.iloc[0])
    pct = None if first_close == 0 else round((last_close - first_close) / first_close * 100, 2)

    return {
        "last_close": last_close,
        "ma5": _ma(closes, 5),
        "ma20": ma20,
        "ma60": _ma(closes, 60),
        "pct_change_period": pct,
        "avg_volume": float(df["volume"].astype(float).mean()),
        "trend": trend,
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_indicators.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add committee/data/indicators.py tests/test_indicators.py
git commit -m "feat: add compute_indicators (MA, trend, pct change)"
```

---

### Task 9: Domain tools registry

Wires the TWSE client + indicators into `Tool`s the agents can call. `get_technical_indicators` fetches price history then computes indicators in one call (simpler for the LLM than passing arrays around).

**Files:**
- Create: `committee/domain_tools.py`
- Test: `tests/test_domain_tools.py`

- [ ] **Step 1: Write the failing test**

```python
from committee.domain_tools import build_registry


class _FakeTwse:
    def valuation(self, stock_no):
        return {"stock_no": stock_no, "name": "台積電", "pe": 22.5,
                "pb": 6.3, "dividend_yield": 1.85}

    def price_history(self, stock_no, months=3):
        return [{"date": "2026-05-0{}".format(i + 1), "open": 10 + i, "high": 10 + i,
                 "low": 10 + i, "close": 10 + i, "volume": 1000} for i in range(5)]


def test_registry_exposes_mvp_tools():
    reg = build_registry(_FakeTwse())
    schemas = {s["function"]["name"] for s in
               reg.schemas(["get_valuation", "get_technical_indicators"])}
    assert schemas == {"get_valuation", "get_technical_indicators"}


def test_get_valuation_tool_runs():
    reg = build_registry(_FakeTwse())
    out = reg.get("get_valuation").fn(stock_no="2330")
    assert out["pe"] == 22.5


def test_get_technical_indicators_tool_runs():
    reg = build_registry(_FakeTwse())
    out = reg.get("get_technical_indicators").fn(stock_no="2330", months=1)
    assert out["last_close"] == 14.0  # close of last (10+4) row
    assert "trend" in out
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_domain_tools.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'committee.domain_tools'`

- [ ] **Step 3: Write minimal implementation**

```python
from typing import Any

from agentcore.tools import Tool, ToolRegistry
from committee.data.indicators import compute_indicators

_STOCK_NO = {"type": "string", "description": "Taiwan stock code, e.g. 2330"}


def build_registry(twse: Any) -> ToolRegistry:
    reg = ToolRegistry()

    reg.register(Tool(
        name="get_valuation",
        description="Get P/E, P/B and dividend yield for a Taiwan stock from TWSE.",
        parameters={"type": "object",
                    "properties": {"stock_no": _STOCK_NO},
                    "required": ["stock_no"]},
        fn=lambda stock_no: twse.valuation(stock_no),
    ))

    def _indicators(stock_no: str, months: int = 3):
        return compute_indicators(twse.price_history(stock_no, months=months))

    reg.register(Tool(
        name="get_technical_indicators",
        description=("Get moving averages (MA5/20/60), trend, period % change and "
                     "average volume for a Taiwan stock, computed from TWSE daily prices."),
        parameters={"type": "object",
                    "properties": {"stock_no": _STOCK_NO,
                                   "months": {"type": "integer",
                                              "description": "recent months of data",
                                              "default": 3}},
                    "required": ["stock_no"]},
        fn=_indicators,
    ))

    return reg
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_domain_tools.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add committee/domain_tools.py tests/test_domain_tools.py
git commit -m "feat: wire TWSE + indicators into the MVP tool registry"
```

---

### Task 10: Config (model mapping)

**Files:**
- Create: `committee/config.py`

- [ ] **Step 1: Write `committee/config.py`** (no test — pure constants read from env)

```python
import os

NVIDIA_BASE_URL = "https://integrate.api.nvidia.com/v1"

# Two-tier mapping (spec decision #6). Override via env if a model tool-calls poorly.
# These defaults are CANDIDATES to validate in the live smoke test (Task 13 / spec §10).
MODEL_REASONER = os.environ.get("MODEL_REASONER", "moonshotai/kimi-k2.6")
MODEL_TOOL_CALLER = os.environ.get("MODEL_TOOL_CALLER", "meta/llama-3.3-70b-instruct")

CACHE_DIR = os.environ.get("CACHE_DIR", "cache")
```

- [ ] **Step 2: Commit**

```bash
git add committee/config.py
git commit -m "feat: add committee config with two-tier model mapping"
```

---

### Task 11: Committee agent definitions

**Files:**
- Create: `committee/agents.py`
- Test: `tests/test_agents_def.py`

- [ ] **Step 1: Write the failing test**

```python
from committee.agents import build_committee
from committee.config import MODEL_REASONER, MODEL_TOOL_CALLER


def test_build_committee_roles_and_models():
    analysts, chair = build_committee()
    names = {a.name for a in analysts}
    assert names == {"fundamental", "technical"}
    for a in analysts:
        assert a.model == MODEL_TOOL_CALLER
        assert a.tool_names  # each analyst has at least one tool
    assert chair.name == "chair"
    assert chair.model == MODEL_REASONER
    assert chair.tool_names == []


def test_analyst_tool_names_match_mvp_tools():
    analysts, _ = build_committee()
    by_name = {a.name: a for a in analysts}
    assert by_name["fundamental"].tool_names == ["get_valuation"]
    assert by_name["technical"].tool_names == ["get_technical_indicators"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_agents_def.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'committee.agents'`

- [ ] **Step 3: Write minimal implementation**

```python
from typing import List, Tuple

from agentcore.agent import Agent
from committee.config import MODEL_REASONER, MODEL_TOOL_CALLER

_FUNDAMENTAL_PROMPT = (
    "You are a buy-side Fundamental Analyst covering Taiwan equities. "
    "Use get_valuation to fetch real P/E, P/B and dividend yield. "
    "Judge whether the valuation is attractive. Be concise (<=120 words). "
    "End with a clear lean: BULLISH, BEARISH, or NEUTRAL. "
    "Never invent numbers; if a tool fails, say the data is unavailable."
)

_TECHNICAL_PROMPT = (
    "You are a Technical Analyst covering Taiwan equities. "
    "Use get_technical_indicators to fetch moving averages, trend and momentum. "
    "Assess the trend and timing. Be concise (<=120 words). "
    "End with a clear lean: BULLISH, BEARISH, or NEUTRAL. "
    "Never invent numbers; if a tool fails, say the data is unavailable."
)

_CHAIR_PROMPT = (
    "You are the Chair of an investment committee. You receive the analysts' "
    "statements and must issue ONE final call. Output exactly: a first line "
    "'RECOMMENDATION: BUY|HOLD|SELL', then a 'CONFIDENCE: NN%' line, then a "
    "one-paragraph rationale that references the analysts' points. Do not invent "
    "figures beyond what the analysts reported."
)


def build_committee() -> Tuple[List[Agent], Agent]:
    fundamental = Agent(name="fundamental", role="Fundamental Analyst",
                        system_prompt=_FUNDAMENTAL_PROMPT, model=MODEL_TOOL_CALLER,
                        tool_names=["get_valuation"])
    technical = Agent(name="technical", role="Technical Analyst",
                      system_prompt=_TECHNICAL_PROMPT, model=MODEL_TOOL_CALLER,
                      tool_names=["get_technical_indicators"])
    chair = Agent(name="chair", role="Chair", system_prompt=_CHAIR_PROMPT,
                  model=MODEL_REASONER, tool_names=[])
    return [fundamental, technical], chair
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_agents_def.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add committee/agents.py tests/test_agents_def.py
git commit -m "feat: add MVP committee agent definitions"
```

---

### Task 12: Orchestrator (research → verdict)

**Files:**
- Create: `agentcore/orchestrator.py`
- Test: `tests/test_orchestrator.py`

- [ ] **Step 1: Write the failing test**

```python
from agentcore.orchestrator import Orchestrator
from agentcore.events import EventBus
from agentcore.evidence import EvidenceLedger


class _StubAgent:
    def __init__(self, name, reply):
        self.name = name
        self._reply = reply
        self.tasks = []

    def run(self, task, llm, registry, bus, ledger, context=""):
        self.tasks.append({"task": task, "context": context})
        return self._reply


def test_orchestrator_runs_analysts_then_chair_with_their_statements():
    a1 = _StubAgent("fundamental", "PE fair. BULLISH.")
    a2 = _StubAgent("technical", "Above MA20. BULLISH.")
    chair = _StubAgent("chair", "RECOMMENDATION: BUY\nCONFIDENCE: 70%\nLooks good.")
    orch = Orchestrator(analysts=[a1, a2], chair=chair)
    bus, ledger = EventBus(), EvidenceLedger()
    events = []
    bus.subscribe(events.append)

    verdict = orch.run(stock_no="2330", llm=None, registry=None, bus=bus, ledger=ledger)

    assert verdict.startswith("RECOMMENDATION: BUY")
    chair_task = chair.tasks[0]["task"]
    assert "PE fair. BULLISH." in chair_task
    assert "Above MA20. BULLISH." in chair_task
    phases = [e.data.get("phase") for e in events if e.type == "phase" and "phase" in e.data]
    assert phases == ["RESEARCH", "VERDICT"]
    assert any(e.type == "verdict" for e in events)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_orchestrator.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'agentcore.orchestrator'`

- [ ] **Step 3: Write minimal implementation**

```python
from dataclasses import dataclass
from typing import Any, List

from agentcore.events import Event

_ANALYST_TASK = (
    "Analyze Taiwan stock {stock} from your perspective. Use your tools to get real "
    "data first, then give your concise opinion and a BULLISH/BEARISH/NEUTRAL lean."
)


@dataclass
class Orchestrator:
    analysts: List[Any]
    chair: Any

    def run(self, stock_no, llm, registry, bus, ledger) -> str:
        bus.emit(Event(type="phase", agent="system", data={"phase": "RESEARCH", "stock": stock_no}))
        statements = []
        for analyst in self.analysts:
            text = analyst.run(task=_ANALYST_TASK.format(stock=stock_no), llm=llm,
                               registry=registry, bus=bus, ledger=ledger)
            statements.append((analyst.name, text))

        bus.emit(Event(type="phase", agent="system", data={"phase": "VERDICT", "stock": stock_no}))
        summary = "\n\n".join("[{}]\n{}".format(name, text) for name, text in statements)
        chair_task = (
            "Stock under review: {}. The committee analysts said:\n\n{}\n\n"
            "Now issue the committee's final recommendation."
        ).format(stock_no, summary)
        verdict = self.chair.run(task=chair_task, llm=llm, registry=registry,
                                 bus=bus, ledger=ledger)
        bus.emit(Event(type="verdict", agent=self.chair.name, data={"text": verdict}))
        return verdict
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_orchestrator.py -v`
Expected: PASS (1 passed)

- [ ] **Step 5: Run the FULL suite to confirm nothing regressed**

Run: `pytest -q`
Expected: PASS (all tests from Tasks 2–12 green)

- [ ] **Step 6: Commit**

```bash
git add agentcore/orchestrator.py tests/test_orchestrator.py
git commit -m "feat: add Orchestrator (research then chair verdict)"
```

---

### Task 13: Terminal runner + live smoke test

Wires everything together and renders the live run in the terminal. Includes a `live`-marked test that hits real NVIDIA + TWSE (deselected by default).

**Files:**
- Create: `main.py`
- Test: `tests/test_live_smoke.py`

- [ ] **Step 1: Write `main.py`**

```python
import sys

from dotenv import load_dotenv

from agentcore.events import Event, EventBus
from agentcore.evidence import EvidenceLedger
from agentcore.llm import LLMClient
from agentcore.orchestrator import Orchestrator
from committee.agents import build_committee
from committee.config import CACHE_DIR, NVIDIA_BASE_URL
from committee.data.twse import TwseClient
from committee.domain_tools import build_registry


class TerminalRenderer:
    """Subscribes to the EventBus and prints the live debate."""

    def __init__(self) -> None:
        self._streaming_agent = None

    def __call__(self, e: Event) -> None:
        if e.type == "phase" and e.data.get("phase"):
            print("\n\n=== {} ({}) ===".format(e.data["phase"], e.data.get("stock", "")))
        elif e.type == "token":
            if self._streaming_agent != e.agent:
                print("\n[{}] ".format(e.agent), end="")
                self._streaming_agent = e.agent
            print(e.data["text"], end="", flush=True)
        elif e.type == "tool_call":
            self._streaming_agent = None
            print("\n  📡 {}({})".format(e.data["tool"], e.data.get("args", {})))
        elif e.type == "tool_result":
            print("  ✓ {} returned".format(e.data["tool"]))
        elif e.type == "error":
            print("\n  ⚠️  {} error: {}".format(e.data.get("tool"), e.data.get("error")))
        elif e.type == "verdict":
            print("\n\n========== VERDICT ==========\n{}".format(e.data["text"]))


def run(stock_no: str) -> str:
    bus = EventBus()
    bus.subscribe(TerminalRenderer())
    ledger = EvidenceLedger()
    llm = LLMClient(base_url=NVIDIA_BASE_URL)
    registry = build_registry(TwseClient(cache_dir=CACHE_DIR))
    analysts, chair = build_committee()
    orch = Orchestrator(analysts=analysts, chair=chair)
    return orch.run(stock_no=stock_no, llm=llm, registry=registry, bus=bus, ledger=ledger)


if __name__ == "__main__":
    load_dotenv()
    stock = sys.argv[1] if len(sys.argv) > 1 else "2330"
    run(stock)
    print()
```

- [ ] **Step 2: Write the live smoke test**

```python
import os
import pytest

pytestmark = pytest.mark.live


@pytest.mark.skipif(not os.environ.get("NVIDIA_API_KEY"),
                    reason="NVIDIA_API_KEY not set")
def test_live_run_produces_recommendation():
    from main import run
    verdict = run("2330")
    assert "RECOMMENDATION:" in verdict.upper()
```

- [ ] **Step 3: Run the unit suite (live deselected) to confirm import health**

Run: `pytest -q`
Expected: PASS — all non-live tests green; the live test is deselected by the `-m "not live"` default in `pytest.ini`.

- [ ] **Step 4: Manual live run (requires `.env` with `NVIDIA_API_KEY`)**

Run:
```bash
python main.py 2330
```
Expected: you SEE the live debate — Fundamental and Technical agents fire `📡 get_valuation` / `📡 get_technical_indicators`, stream their opinions, then the Chair prints a `RECOMMENDATION: BUY|HOLD|SELL` block. **This is the MVP "it works" moment.**

If a model tool-calls poorly (no `📡` lines, or invented numbers), switch `MODEL_TOOL_CALLER` in `.env` to another NVIDIA free model and re-run — this resolves the spec §10 model question. Record the working model.

- [ ] **Step 5: Optional — run the live test explicitly**

Run:
```bash
pytest -m live -v
```
Expected: PASS (one live test) when `NVIDIA_API_KEY` is set and the endpoints are reachable.

- [ ] **Step 6: Commit**

```bash
git add main.py tests/test_live_smoke.py
git commit -m "feat: add terminal runner and live smoke test (MVP end-to-end)"
```

---

## Self-Review (completed during planning)

**1. Spec coverage (Phase 1 scope):**
- Reusable core (LLMClient, Tool/Registry, Agent, EventBus, Orchestrator) → Tasks 2,4,5,6,12. ✅
- EvidenceLedger in MVP → Task 3. ✅
- TWSE tools + indicators → Tasks 7,8,9. ✅
- 3 agents (Fundamental, Technical, Chair) → Task 11. ✅
- Terminal event output → Task 13 (`TerminalRenderer`). ✅
- Model-agnostic two-tier config → Task 10. ✅
- TDD with mock LLMClient / mock agents / fixture-based TWSE → Tasks 5,6,7,12. ✅
- Error handling: tool failure fed back not raised → Task 6 test. ✅; missing TWSE data raises and surfaces as a tool error.
- §10 open items: TWSE shape (Task 1 spike + Task 7 fixtures), model tool-calling (Task 13 step 4). ✅
- **Documented deviation:** `get_institutional_flows` + raw `get_price_history` tool deferred to Phase 2 (YAGNI) — stated in Scope.

**2. Placeholder scan:** No TBD/TODO; every code step shows complete code; every run step shows the command + expected result. ✅

**3. Type consistency:** `Event(type, agent, data, ts)`, `EventBus.subscribe/emit`, `EvidenceLedger.record/entries`, `Tool(name, description, parameters, fn)`/`to_openai_schema`, `ToolRegistry.register/get/schemas`, `LLMClient.chat(...) -> {role, content, tool_calls:[{id,name,arguments}]}`, `Agent.run(task, llm, registry, bus, ledger, context="")`, `Orchestrator(analysts, chair).run(stock_no, llm, registry, bus, ledger)`, `TwseClient(cache_dir, session, today).valuation/price_history`, `build_registry(twse)`, `build_committee() -> (analysts, chair)` — all consistent across tasks. ✅

---

## Definition of Done (MVP)

- `pytest -q` passes (all unit tests, live deselected).
- `python main.py 2330` shows a live 2-analyst + chair debate driven by real TWSE data and prints a `RECOMMENDATION` block.
- The working `MODEL_TOOL_CALLER` model is recorded (resolves §10 model question).
- All work committed in small, green increments.
