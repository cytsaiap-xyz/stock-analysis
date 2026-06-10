# tests/test_markets.py
from committee.markets.base import (Templates, Prompts, ToolDescriptions,
                                    ReportLabels, MarketProfile)


def test_dataclasses_construct_with_expected_fields():
    t = Templates(analyst="a", challenge="c", rebuttal="r", reflect="rf",
                  verify="v", correction="co", discussion="d")
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


from committee.markets import get_profile


def test_get_profile_tw_is_chinese_with_twse_client():
    p = get_profile("tw")
    assert p.market == "tw" and p.lang == "zh-TW"
    assert p.labels.institutional_kind == "lots"
    assert type(p.client).__name__ == "TwseClient"
    assert [a.name for a in p.committee.research] == ["fundamental", "technical",
                                                      "institutional", "news"]


def test_get_profile_us_is_english_with_us_client():
    p = get_profile("us")
    assert p.market == "us" and p.lang == "en"
    assert p.labels.institutional_kind == "ownership"
    assert p.labels.revenue_kind == "quarterly"
    assert type(p.client).__name__ == "UsClient"
    assert "Recommendation" in p.committee.chair.system_prompt
    assert p.templates.analyst.find("{stock}") >= 0


def test_get_profile_unknown_market_raises():
    import pytest
    with pytest.raises(ValueError):
        get_profile("jp")


def test_profiles_carry_localized_ui_text():
    from committee.markets import get_profile
    tw = get_profile("tw").ui
    us = get_profile("us").ui
    assert set(tw) == set(us)
    assert tw["title"] == "台股投資委員會"
    assert us["title"] == "US Equity Investment Committee"
    assert tw["example_ticker"] == "2330" and us["example_ticker"] == "AAPL"
    assert tw["run_button"] == "開始分析" and us["run_button"] == "Analyze"
    assert tw["thinking"] == "思考中" and us["thinking"] == "thinking"
    assert tw["lean_words"] == ["看多", "看空", "中性"]
    assert us["lean_words"] == ["Bullish", "Bearish", "Neutral"]


def test_profiles_carry_stocklist():
    from committee.markets import get_profile
    for m in ("tw", "us"):
        sl = get_profile(m).stocklist
        assert isinstance(sl, list) and sl
        for cat in sl:
            assert cat["label"] and isinstance(cat["items"], list) and cat["items"]
            for it in cat["items"]:
                assert it["code"] and it["name"]


def test_tw_stocklist_has_semiconductors_with_tsmc():
    from committee.markets import get_profile
    sl = get_profile("tw").stocklist
    semi = next(c for c in sl if c["label"] == "半導體")
    assert {"code": "2330", "name": "台積電"} in semi["items"]
    for c in sl:
        for it in c["items"]:
            assert it["code"].isdigit() and 4 <= len(it["code"]) <= 6


def test_us_stocklist_categories_and_placements():
    from committee.markets import get_profile
    sl = get_profile("us").stocklist
    labels = [c["label"] for c in sl]
    assert "CPU" in labels and "EDA" in labels and "EV & Autonomous" in labels
    codes = {c["label"]: [it["code"] for it in c["items"]] for c in sl}
    assert "SNPS" in codes["EDA"] and "CDNS" in codes["EDA"]
    assert "SNDK" in codes["Memory & Storage"]
    assert "SMCI" in codes["AI Infrastructure / Servers"]
    assert "PLTR" in codes["AI & Data Software"]
    assert "TSLA" in codes["EV & Autonomous"]
    for c in sl:
        for it in c["items"]:
            assert it["code"].isalpha()


def test_ui_has_others_label_both_markets():
    from committee.markets import get_profile
    assert get_profile("tw").ui["others_label"]
    assert get_profile("us").ui["others_label"]


def test_templates_have_discussion_and_phase_label():
    from committee.markets import get_profile
    for m, label in (("tw", "討論交鋒"), ("us", "Discussion")):
        p = get_profile(m)
        assert p.templates.discussion and "{stock}" in p.templates.discussion
        assert p.labels.phase_names["DISCUSSION"] == label


def test_unverified_label_present_in_ui_and_report_labels():
    from committee.markets import get_profile
    for m in ("tw", "us"):
        p = get_profile(m)
        assert p.ui["unverified_label"]
        assert p.labels.text["unverified_label"]
