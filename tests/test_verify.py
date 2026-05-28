from agentcore.evidence import EvidenceLedger
from agentcore.verify import check_grounding


def _ledger(**results):
    led = EvidenceLedger()
    for tool, res in results.items():
        led.record(tool, {}, res)
    return led


def test_grounded_when_cited_figures_match_evidence():
    led = _ledger(get_valuation={"pe": 30.52, "pb": 6.30, "dividend_yield": 0.97})
    verdict = "本益比 30.52、股價淨值比 6.3、殖利率 0.97%,估值偏高。建議: 持有 信心: 55%"
    out = check_grounding(verdict, led)
    assert out["grounded"] is True
    assert out["unsupported"] == []


def test_flags_hallucinated_figure():
    led = _ledger(get_valuation={"pe": 30.52})
    verdict = "目標價 1180.00 元,建議買進。"  # 1180.00 is not in the evidence
    out = check_grounding(verdict, led)
    assert out["grounded"] is False
    assert 1180.0 in out["unsupported"]


def test_plain_integers_like_confidence_are_not_checked():
    led = _ledger(get_valuation={"pe": 30.52})
    verdict = "建議: 持有\n信心: 55%\n本益比 30.52 偏高。"  # 55 is a plain int, ignored
    out = check_grounding(verdict, led)
    assert out["grounded"] is True


def test_thousands_grouped_shares_match_integer_evidence():
    led = _ledger(get_institutional_flows={"foreign_net": 12000})
    verdict = "外資買超 12,000 張,偏多。"
    out = check_grounding(verdict, led)
    assert out["grounded"] is True
