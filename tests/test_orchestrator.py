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
                                         _DEFAULT_REBUTTAL_TASK, _DEFAULT_REFLECT_TASK)
    for tmpl in (_DEFAULT_ANALYST_TASK, _DEFAULT_CHALLENGE_TASK,
                 _DEFAULT_REBUTTAL_TASK, _DEFAULT_REFLECT_TASK):
        assert "Taiwan" not in tmpl and "{stock}" in tmpl


def test_reflection_off_by_default_keeps_phases_and_chair_calls_unchanged():
    fund = _StubAgent("fundamental", "看多")
    chair = _StubAgent("chair", "建議: 持有")
    orch = _orch([fund], [], chair)            # reflection_passes defaults to 0
    bus, ledger = EventBus(), EvidenceLedger()
    events = []
    bus.subscribe(events.append)

    orch.run(stock_no="2330", llm=None, registry=None, bus=bus, ledger=ledger)

    phases = [e.data.get("phase") for e in events if e.type == "phase" and "phase" in e.data]
    assert "REFLECT" not in phases
    assert len(chair.tasks) == 1


def test_reflection_adds_phase_and_one_extra_chair_call_when_enabled():
    fund = _StubAgent("fundamental", "看多")
    chair = _StubAgent("chair", "建議: 持有\n信心: 60%\n理由。")
    orch = _orch([fund], [], chair,
                 reflect_task_template="Reflect on your verdict for {stock}.",
                 reflection_passes=1)
    bus, ledger = EventBus(), EvidenceLedger()
    events = []
    bus.subscribe(events.append)

    verdict = orch.run(stock_no="2330", llm=None, registry=None, bus=bus, ledger=ledger)

    phases = [e.data.get("phase") for e in events if e.type == "phase" and "phase" in e.data]
    assert phases == ["RESEARCH", "CHALLENGE", "REBUTTAL", "VERDICT", "REFLECT"]
    assert len(chair.tasks) == 2                        # draft + one reflection
    assert chair.tasks[1]["context"] == "建議: 持有\n信心: 60%\n理由。"  # reflects on its draft
    assert verdict.startswith("建議: 持有")
    verdicts = [e for e in events if e.type == "verdict"]
    assert verdicts[-1].data.get("reflected") is True


def test_reflection_runs_before_verify():
    fund = _StubAgent("fundamental", "看多")
    chair = _StubAgent("chair", "建議: 持有\n本益比 30.52 偏高")  # 30.52 is supported
    verifier = _StubAgent("verifier", "查核通過")
    orch = _orch([fund], [], chair, verifier=verifier,
                 reflect_task_template="Reflect {stock}.", reflection_passes=1)
    bus, ledger = EventBus(), EvidenceLedger()
    ledger.record("get_valuation", {}, {"pe": 30.52})
    events = []
    bus.subscribe(events.append)

    orch.run(stock_no="2330", llm=None, registry=None, bus=bus, ledger=ledger)

    phases = [e.data.get("phase") for e in events if e.type == "phase" and "phase" in e.data]
    assert phases == ["RESEARCH", "CHALLENGE", "REBUTTAL", "VERDICT", "REFLECT", "VERIFY"]
    assert len(chair.tasks) == 2                        # draft + reflection; verdict grounded


def test_custom_analyst_task_template_is_used():
    analyst = _StubAgent("a", "看多")
    chair = _StubAgent("chair", "建議: 持有")
    orch = _orch([analyst], [], chair, analyst_task_template="Custom review of {stock} please.")
    bus, ledger = EventBus(), EvidenceLedger()

    orch.run(stock_no="2330", llm=None, registry=None, bus=bus, ledger=ledger)

    assert analyst.tasks[0]["task"] == "Custom review of 2330 please."


def test_verify_phase_runs_when_verifier_present_and_verdict_grounded():
    fund = _StubAgent("fundamental", "看多")
    chair = _StubAgent("chair", "建議: 持有\n本益比 30.52 偏高")
    verifier = _StubAgent("verifier", "查核通過")
    orch = _orch([fund], [], chair, verifier=verifier)
    bus, ledger = EventBus(), EvidenceLedger()
    ledger.record("get_valuation", {}, {"pe": 30.52})  # evidence supports 30.52
    events = []
    bus.subscribe(events.append)

    orch.run(stock_no="2330", llm=None, registry=None, bus=bus, ledger=ledger)

    phases = [e.data.get("phase") for e in events if e.type == "phase" and "phase" in e.data]
    assert phases[-1] == "VERIFY"
    verifs = [e for e in events if e.type == "verification"]
    assert len(verifs) == 1 and verifs[0].data["grounding"]["grounded"] is True
    assert len(verifier.tasks) == 1            # ran once; no correction needed
    assert len(chair.tasks) == 1


def test_verify_triggers_one_correction_when_ungrounded():
    fund = _StubAgent("fundamental", "看多")
    chair = _StubAgent("chair", "建議: 買進\n目標價 1180.00")  # 1180.00 unsupported
    verifier = _StubAgent("verifier", "發現未獲支持的數字")
    orch = _orch([fund], [], chair, verifier=verifier)
    bus, ledger = EventBus(), EvidenceLedger()
    ledger.record("get_valuation", {}, {"pe": 30.52})
    events = []
    bus.subscribe(events.append)

    orch.run(stock_no="2330", llm=None, registry=None, bus=bus, ledger=ledger)

    assert len(chair.tasks) == 2               # verdict + one correction round
    verifs = [e for e in events if e.type == "verification"]
    assert len(verifs) == 2 and verifs[-1].data.get("final") is True


def test_discussion_phase_replaces_challenge_rebuttal_when_enabled():
    fund = _StubAgent("fundamental", "PE 合理。看多")
    tech = _StubAgent("technical", "站上季線。看多")
    risk = _StubAgent("risk", "波動偏高。")
    skeptic = _StubAgent("skeptic", "別追高。")
    chair = _StubAgent("chair", "建議: 持有\n信心: 60%")
    orch = _orch([fund, tech], [risk, skeptic], chair, discussion_rounds=2)
    bus, ledger = EventBus(), EvidenceLedger()
    events = []
    bus.subscribe(events.append)

    orch.run(stock_no="2330", llm=None, registry=None, bus=bus, ledger=ledger)

    phases = [e.data.get("phase") for e in events if e.type == "phase" and "phase" in e.data]
    assert phases == ["RESEARCH", "DISCUSSION", "VERDICT"]
    # research analysts: 1 RESEARCH turn + 2 discussion turns; challengers: 2 discussion turns
    assert len(fund.tasks) == 3 and len(risk.tasks) == 2
    # the Chair sees the discussion turns
    assert "別追高" in chair.tasks[0]["task"]


def test_discussion_turn_with_unsourced_figure_is_flagged():
    fund = _StubAgent("fundamental", "PE 約 30.52,偏高")   # 30.52 not in the (empty) ledger
    skeptic = _StubAgent("skeptic", "看空")                 # no figure -> no flag
    chair = _StubAgent("chair", "建議: 賣出")
    orch = _orch([fund], [skeptic], chair, discussion_rounds=1)
    bus, ledger = EventBus(), EvidenceLedger()
    events = []
    bus.subscribe(events.append)

    orch.run(stock_no="2330", llm=None, registry=None, bus=bus, ledger=ledger)

    flags = [e for e in events if e.type == "grounding_flag"]
    assert any(e.agent == "fundamental" and 30.52 in e.data["unsupported"] for e in flags)
    assert not any(e.agent == "skeptic" for e in flags)


def test_discussion_disabled_by_default_keeps_challenge_rebuttal():
    fund = _StubAgent("fundamental", "看多")
    risk = _StubAgent("risk", "風險偏高。")
    chair = _StubAgent("chair", "建議: 持有")
    orch = _orch([fund], [risk], chair)   # discussion_rounds defaults to 0
    bus, ledger = EventBus(), EvidenceLedger()
    events = []
    bus.subscribe(events.append)

    orch.run(stock_no="2330", llm=None, registry=None, bus=bus, ledger=ledger)

    phases = [e.data.get("phase") for e in events if e.type == "phase" and "phase" in e.data]
    assert phases == ["RESEARCH", "CHALLENGE", "REBUTTAL", "VERDICT"]
