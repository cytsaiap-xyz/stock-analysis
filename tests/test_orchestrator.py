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


def _orch(research, challengers, chair, **kw):
    return Orchestrator(research=research, challengers=challengers, chair=chair, **kw)


def test_debate_runs_phases_in_order_and_chair_sees_everything():
    fund = _StubAgent("fundamental", "PE fair. 看多")
    tech = _StubAgent("technical", "站上季線. 看多")
    risk = _StubAgent("risk", "波動偏高,留意回撤。")
    skeptic = _StubAgent("skeptic", "外資隔日沖,別追高。")
    chair = _StubAgent("chair", "建議: 持有\n信心: 60%\n綜合以上。")
    orch = _orch([fund, tech], [risk, skeptic], chair)
    bus, ledger = EventBus(), EvidenceLedger()
    events = []
    bus.subscribe(events.append)

    verdict = orch.run(stock_no="2330", llm=None, registry=None, bus=bus, ledger=ledger)

    assert verdict.startswith("建議: 持有")
    phases = [e.data.get("phase") for e in events if e.type == "phase" and "phase" in e.data]
    assert phases == ["RESEARCH", "CHALLENGE", "REBUTTAL", "VERDICT"]
    assert any(e.type == "verdict" for e in events)
    # Chair's prompt contains every participant's statement.
    chair_task = chair.tasks[0]["task"]
    for snippet in ("PE fair. 看多", "站上季線. 看多", "波動偏高", "外資隔日沖"):
        assert snippet in chair_task


def test_challengers_receive_research_as_context():
    fund = _StubAgent("fundamental", "PE fair. 看多")
    risk = _StubAgent("risk", "風險偏高。")
    chair = _StubAgent("chair", "建議: 持有")
    orch = _orch([fund], [risk], chair)
    bus, ledger = EventBus(), EvidenceLedger()

    orch.run(stock_no="2330", llm=None, registry=None, bus=bus, ledger=ledger)

    assert "PE fair. 看多" in risk.tasks[0]["context"]


def test_research_analyst_gets_a_rebuttal_round():
    fund = _StubAgent("fundamental", "PE fair. 看多")
    skeptic = _StubAgent("skeptic", "估值已高。")
    chair = _StubAgent("chair", "建議: 賣出")
    orch = _orch([fund], [skeptic], chair)
    bus, ledger = EventBus(), EvidenceLedger()

    orch.run(stock_no="2330", llm=None, registry=None, bus=bus, ledger=ledger)

    # analyst runs twice: once in RESEARCH, once in REBUTTAL (with challenge context)
    assert len(fund.tasks) == 2
    assert "估值已高" in fund.tasks[1]["context"]


def test_default_templates_are_domain_neutral():
    from agentcore.orchestrator import (_DEFAULT_ANALYST_TASK, _DEFAULT_CHALLENGE_TASK,
                                         _DEFAULT_REBUTTAL_TASK)
    for tmpl in (_DEFAULT_ANALYST_TASK, _DEFAULT_CHALLENGE_TASK, _DEFAULT_REBUTTAL_TASK):
        assert "Taiwan" not in tmpl and "{stock}" in tmpl


def test_custom_analyst_task_template_is_used():
    analyst = _StubAgent("a", "看多")
    chair = _StubAgent("chair", "建議: 持有")
    orch = _orch([analyst], [], chair, analyst_task_template="Custom review of {stock} please.")
    bus, ledger = EventBus(), EvidenceLedger()

    orch.run(stock_no="2330", llm=None, registry=None, bus=bus, ledger=ledger)

    assert analyst.tasks[0]["task"] == "Custom review of 2330 please."
