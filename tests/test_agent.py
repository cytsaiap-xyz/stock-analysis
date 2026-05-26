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
