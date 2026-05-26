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
