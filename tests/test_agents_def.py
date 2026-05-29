from committee.agents import build_committee
from committee.config import MODEL_REASONER, MODEL_TOOL_CALLER


def test_committee_roster():
    c = build_committee()
    assert [a.name for a in c.research] == ["fundamental", "technical",
                                            "institutional", "news"]
    assert [a.name for a in c.challengers] == ["risk", "skeptic"]
    assert c.chair.name == "chair"
    assert c.verifier.name == "verifier"


def test_research_analysts_use_tool_caller_tier_and_have_tools():
    c = build_committee()
    for a in c.research:
        assert a.model == MODEL_TOOL_CALLER
        assert a.tool_names  # every research analyst has at least one tool


def test_chair_and_verifier_are_reasoners_without_tools():
    c = build_committee()
    assert c.chair.model == MODEL_REASONER and c.chair.tool_names == []
    assert c.verifier.model == MODEL_REASONER and c.verifier.tool_names == []


def test_fundamental_uses_valuation_revenue_and_financials():
    c = build_committee()
    fundamental = next(a for a in c.research if a.name == "fundamental")
    assert fundamental.tool_names == ["get_valuation", "get_monthly_revenue",
                                      "get_financials"]


def test_technical_uses_indicators_and_relative_strength():
    c = build_committee()
    technical = next(a for a in c.research if a.name == "technical")
    assert technical.tool_names == ["get_technical_indicators", "get_relative_strength"]


def test_skeptic_has_no_tools_risk_has_one():
    c = build_committee()
    by_name = {a.name: a for a in c.challengers}
    assert by_name["skeptic"].tool_names == []
    assert by_name["risk"].tool_names == ["get_risk_metrics"]
    assert by_name["risk"].model == MODEL_REASONER
