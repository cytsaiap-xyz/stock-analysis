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
    assert ledger.entries()[0].tool == "get_valuation"
    assert ledger.entries()[0].result == {"pe": 22.5, "stock_no": "2330"}
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
    assert ledger.entries() == []


def test_returns_empty_when_max_tool_rounds_exhausted():
    # LLM always asks for a tool, never gives a final answer -> loop must bail out.
    always_tool = {"role": "assistant", "content": None,
                   "tool_calls": [{"id": "c", "name": "get_valuation",
                                   "arguments": '{"stock_no": "2330"}'}]}
    llm = _ScriptedLLM([always_tool] * 10)
    bus, ledger = EventBus(), EvidenceLedger()
    events = []
    bus.subscribe(events.append)
    agent = Agent(name="x", role="x", system_prompt="s", model="m",
                  tool_names=["get_valuation"], max_tool_rounds=3)

    out = agent.run(task="t", llm=llm, registry=_registry(), bus=bus, ledger=ledger)

    assert out == ""
    assert len(llm.calls) == 3  # stopped at max_tool_rounds, did not loop forever


def test_malformed_tool_arguments_emit_error_and_use_empty_args():
    reg = ToolRegistry()
    seen_args = {}
    reg.register(Tool(name="noargs", description="x",
                      parameters={"type": "object", "properties": {}},
                      fn=lambda **kw: seen_args.update(kw) or {"ok": True}))
    llm = _ScriptedLLM([
        {"role": "assistant", "content": None,
         "tool_calls": [{"id": "c1", "name": "noargs", "arguments": "{not json"}]},
        {"role": "assistant", "content": "done", "tool_calls": []},
    ])
    bus, ledger = EventBus(), EvidenceLedger()
    events = []
    bus.subscribe(events.append)
    agent = Agent(name="x", role="x", system_prompt="s", model="m", tool_names=["noargs"])

    out = agent.run(task="t", llm=llm, registry=reg, bus=bus, ledger=ledger)

    assert out == "done"
    assert seen_args == {}  # malformed JSON -> called with no args
    assert any(e.type == "error" and "malformed" in e.data.get("error", "") for e in events)
