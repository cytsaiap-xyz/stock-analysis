from datetime import datetime

from agentcore.events import Event
from agentcore.evidence import EvidenceLedger
from agentcore.report import ReportCollector
from committee.report import build_html, save_report


def test_collector_captures_verdict_and_grounding():
    c = ReportCollector()
    c(Event(type="phase", agent="system", data={"phase": "RESEARCH", "stock": "2330"}))
    c(Event(type="message", agent="fundamental", data={"text": "看多"}))
    c(Event(type="phase", agent="system", data={"phase": "VERDICT", "stock": "2330"}))
    c(Event(type="verdict", agent="chair", data={"text": "建議: 持有\n信心: 60%"}))
    c(Event(type="verification", agent="verifier",
            data={"grounding": {"supported": 3, "checked": 3, "grounded": True,
                                "unsupported": []}}))
    assert c.verdict_text.startswith("建議: 持有")
    assert c.grounding["grounded"] is True


def test_final_grounding_replaces_initial():
    c = ReportCollector()
    c(Event(type="verification", agent="v",
            data={"grounding": {"grounded": False, "supported": 0, "checked": 1,
                                "unsupported": [1180.0]}}))
    c(Event(type="verification", agent="v",
            data={"grounding": {"grounded": True, "supported": 1, "checked": 1,
                                "unsupported": []}, "final": True}))
    assert c.grounding["grounded"] is True


def test_build_html_contains_verdict_phases_and_evidence():
    c = ReportCollector()
    c(Event(type="phase", agent="system", data={"phase": "RESEARCH", "stock": "2330"}))
    c(Event(type="tool_call", agent="fundamental",
            data={"tool": "get_valuation", "args": {"stock_no": "2330"}}))
    c(Event(type="tool_result", agent="fundamental", data={"tool": "get_valuation"}))
    c(Event(type="message", agent="fundamental",
            data={"text": "本益比偏高,看多"}))
    c(Event(type="phase", agent="system", data={"phase": "CHALLENGE", "stock": "2330"}))
    c(Event(type="message", agent="skeptic", data={"text": "估值已高,別追"}))
    c(Event(type="phase", agent="system", data={"phase": "VERDICT", "stock": "2330"}))
    c(Event(type="verdict", agent="chair", data={"text": "建議: 持有\n信心: 60%"}))
    led = EvidenceLedger()
    led.record("get_valuation", {"stock_no": "2330"}, {"pe": 30.52})

    html = build_html("2330", c, ledger=led,
                     generated_at="2026-05-28 10:00:00")

    assert "2026-05-28 10:00:00" in html
    assert "建議: 持有" in html
    assert "基本面分析師" in html and "唱反調者" in html
    assert "研究分析" in html and "質詢" in html and "最終結論" in html
    assert "get_valuation" in html and "30.52" in html       # evidence table
    assert html.lstrip().startswith("<!DOCTYPE")


def _rich_collector():
    c = ReportCollector()
    c(Event(type="phase", agent="system", data={"phase": "RESEARCH", "stock": "2330"}))
    c(Event(type="message", agent="fundamental", data={"text": "本益比偏高但ROE穩健,看多"}))
    c(Event(type="message", agent="technical", data={"text": "均線多頭排列,RSI中性,看多"}))
    c(Event(type="message", agent="institutional", data={"text": "外資連續買超,看多"}))
    c(Event(type="message", agent="news", data={"text": "AI需求強勁,看多"}))
    c(Event(type="phase", agent="system", data={"phase": "CHALLENGE", "stock": "2330"}))
    c(Event(type="message", agent="risk", data={"text": "年化波動偏高,留意回撤"}))
    c(Event(type="message", agent="skeptic", data={"text": "估值已高,別追高"}))
    c(Event(type="phase", agent="system", data={"phase": "VERDICT", "stock": "2330"}))
    c(Event(type="verdict", agent="chair",
            data={"text": "建議: 買進\n信心: 72%\n綜合各面看好。"}))
    c(Event(type="verification", agent="verifier",
            data={"grounding": {"supported": 5, "checked": 5, "grounded": True,
                                "unsupported": []}}))
    return c


def _full_ledger():
    led = EvidenceLedger()
    led.record("get_valuation", {"stock_no": "2330"},
               {"name": "台積電", "pe": 30.52, "pb": 6.3, "dividend_yield": 1.85})
    led.record("get_financials", {"stock_no": "2330"},
               {"available": True, "period": "115Q1", "gross_margin_pct": 60.0,
                "operating_margin_pct": 50.0, "roe_pct": 9.66, "eps": 13.94})
    led.record("get_technical_indicators", {"stock_no": "2330"},
               {"last_close": 1085.0, "ma5": 1070.0, "ma20": 1050.0, "ma60": 1000.0,
                "rsi14": 57.0, "kd_k": 54.0, "kd_d": 44.0, "macd": -8.0,
                "trend": "up", "pct_change_period": 12.5})
    led.record("get_institutional_flows", {"stock_no": "2330"},
               {"foreign_net": 13284272, "trust_net": 654192, "dealer_net": 125200,
                "total_net": 14063664})
    led.record("get_relative_strength", {"stock_no": "2330"},
               {"stock_return_pct": 14.9, "index_return_pct": 27.5,
                "excess_return_pct": -12.5, "beta": 1.08})
    led.record("get_risk_metrics", {"stock_no": "2330"},
               {"volatility_annual_pct": 38.28, "max_drawdown_pct": -10.89})
    return led


class _FakeTwse:
    def price_history(self, stock_no, months=3):
        return [{"date": "2026-05-{:02d}".format(i + 1), "open": 1000 + i,
                 "high": 1010 + i, "low": 995 + i, "close": 1000 + i * 5, "volume": 1000}
                for i in range(20)]


def test_report_shows_rating_banner_with_confidence():
    html = build_html("2330", _rich_collector(), ledger=_full_ledger())
    assert "買進" in html and "72%" in html
    assert "rating-buy" in html        # rating class drives the banner colour


def test_report_dashboard_shows_key_metrics_from_ledger():
    html = build_html("2330", _rich_collector(), ledger=_full_ledger())
    for label in ("本益比", "ROE", "RSI", "Beta", "年化波動"):
        assert label in html
    assert "30.52" in html and "9.66" in html and "1.08" in html


def test_report_embeds_svg_chart_when_twse_available():
    html = build_html("2330", _rich_collector(), ledger=_full_ledger(), twse=_FakeTwse())
    assert "<svg" in html and "polyline" in html


def test_report_skips_chart_gracefully_without_twse():
    html = build_html("2330", _rich_collector(), ledger=_full_ledger())  # no twse
    assert "<svg" not in html          # chart omitted, but no crash
    assert html.lstrip().startswith("<!DOCTYPE")


def test_report_has_sections_riskbox_disclaimer_and_appendix():
    html = build_html("2330", _rich_collector(), ledger=_full_ledger())
    assert "基本面" in html and "技術面" in html       # per-aspect sections
    assert "風險" in html                              # risk / bear box
    assert "免責" in html                              # disclaimer footer
    assert "<details" in html                          # collapsible transcript appendix


def test_save_report_passes_twse_through_for_chart(tmp_path):
    path = save_report("2330", _rich_collector(), ledger=_full_ledger(),
                       twse=_FakeTwse(), reports_dir=str(tmp_path),
                       now=datetime(2026, 5, 28, 9, 30, 0))
    body = path.read_text(encoding="utf-8")
    assert "<svg" in body


def test_save_report_writes_file_with_timestamped_name(tmp_path):
    c = ReportCollector()
    c(Event(type="verdict", agent="chair", data={"text": "建議: 賣出"}))
    now = datetime(2026, 5, 28, 9, 30, 0)

    path = save_report("2454", c, reports_dir=str(tmp_path), now=now)

    assert path.exists() and path.name == "2454_20260528-093000.html"
    body = path.read_text(encoding="utf-8")
    assert "建議: 賣出" in body and "2454" in body


def test_rating_parses_english_verdict():
    from committee.report import _rating
    r = _rating("Recommendation: BUY\nConfidence: 60%\nStrong fundamentals.")
    assert r["label"] == "BUY"
    assert r["cls"] == "buy"
    assert r["confidence"] == "60%"


def test_aspect_message_renders_markdown_and_collapsible_thinking():
    from committee.report import build_html
    c = ReportCollector()
    c(Event(type="message", agent="fundamental",
            data={"text": "<thought>my reasoning</thought>Verdict: **Bullish**\n- strong margins"}))
    html = build_html("AAPL", c, generated_at="2026-06-10 10:00:00")
    assert "<strong>Bullish</strong>" in html
    assert "<li>strong margins</li>" in html
    assert '<details class="thinking">' in html
    assert "my reasoning" in html
    assert "<thought>" not in html


def test_plain_message_without_thinking_has_no_details():
    from committee.report import build_html
    c = ReportCollector()
    c(Event(type="message", agent="technical", data={"text": "Neutral stance"}))
    html = build_html("AAPL", c, generated_at="2026-06-10 10:00:00")
    assert "Neutral stance" in html
    assert html.count('<details class="thinking">') == 0
