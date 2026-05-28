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


def test_save_report_writes_file_with_timestamped_name(tmp_path):
    c = ReportCollector()
    c(Event(type="verdict", agent="chair", data={"text": "建議: 賣出"}))
    now = datetime(2026, 5, 28, 9, 30, 0)

    path = save_report("2454", c, reports_dir=str(tmp_path), now=now)

    assert path.exists() and path.name == "2454_20260528-093000.html"
    body = path.read_text(encoding="utf-8")
    assert "建議: 賣出" in body and "2454" in body
