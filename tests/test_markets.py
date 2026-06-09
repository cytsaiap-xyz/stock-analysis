# tests/test_markets.py
from committee.markets.base import (Templates, Prompts, ToolDescriptions,
                                    ReportLabels, MarketProfile)


def test_dataclasses_construct_with_expected_fields():
    t = Templates(analyst="a", challenge="c", rebuttal="r", reflect="rf",
                  verify="v", correction="co")
    assert t.analyst == "a" and t.correction == "co"

    p = Prompts(fundamental="f", technical="t", institutional="i", news="n",
                risk="rk", skeptic="sk", chair="ch", verifier="vf")
    assert p.chair == "ch"

    td = ToolDescriptions(stock_param="sp", get_valuation="gv",
                          get_technical_indicators="gti",
                          get_institutional_flows="gif",
                          get_monthly_revenue="gmr", get_risk_metrics="grm",
                          get_relative_strength="grs", get_financials="gf",
                          search_news="sn")
    assert td.get_valuation == "gv"

    labels = ReportLabels(lang="en", text={"k": "v"}, rating_class={"BUY": "buy"},
                          recommend_label="Recommendation", confidence_label="Confidence",
                          agent_names={"chair": "Chair"}, phase_names={"RESEARCH": "Research"},
                          aspect_order=[("fundamental", "Fundamentals")],
                          institutional_kind="ownership", revenue_kind="quarterly",
                          disclaimer="d")
    assert labels.institutional_kind == "ownership"
