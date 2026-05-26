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
