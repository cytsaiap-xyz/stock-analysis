"""Phase 3 web server tests.

We test the server's pure helpers (serialize_event) and route handlers directly
rather than via starlette's TestClient, which is sensitive to the installed
httpx version. The route handlers are plain functions — calling them as Python
is the simplest, version-proof way to verify them.
"""
from pathlib import Path

from agentcore.events import Event
from web.server import _STATIC, committee_info, serialize_event


def test_serialize_event_is_json_safe_dict():
    e = Event(type="message", agent="chair", data={"text": "hi"})
    out = serialize_event(e)
    assert out["type"] == "message"
    assert out["agent"] == "chair"
    assert out["data"] == {"text": "hi"}
    assert isinstance(out["ts"], float)


def test_committee_info_returns_full_roster():
    body = committee_info()
    assert [a["name"] for a in body["research"]] == [
        "fundamental", "technical", "institutional", "news"]
    assert [a["name"] for a in body["challengers"]] == ["risk", "skeptic"]
    assert body["chair"]["name"] == "chair"
    assert body["verifier"]["name"] == "verifier"
    assert "RESEARCH" in body["phase_names"] and "VERIFY" in body["phase_names"]
    # Each entry carries the metadata the front-end pipeline needs.
    fund = next(a for a in body["research"] if a["name"] == "fundamental")
    assert "model" in fund and isinstance(fund["tools"], list)


def test_committee_info_exposes_reflection_settings():
    body = committee_info()
    # Front-end needs the ZH label for the new REFLECT phase and whether it's on.
    assert "REFLECT" in body["phase_names"]
    assert isinstance(body["reflection_passes"], int)


def test_static_index_is_present_on_disk():
    # The GET / FileResponse just serves this file; if it's missing, the route 404s.
    assert (_STATIC / "index.html").is_file()
    assert (_STATIC / "app.js").is_file()
    assert (_STATIC / "style.css").is_file()


def test_committee_info_tw_is_chinese():
    from web.server import committee_info
    info = committee_info("tw")
    assert info["ui"]["title"] == "台股投資委員會"
    assert info["phase_names"]["RESEARCH"] == "研究分析"
    fundamental = next(a for a in info["research"] if a["name"] == "fundamental")
    assert fundamental["label"] == "基本面分析師"


def test_committee_info_us_is_english():
    from web.server import committee_info
    info = committee_info("us")
    assert info["ui"]["title"] == "US Equity Investment Committee"
    assert info["phase_names"]["RESEARCH"] == "Research"
    fundamental = next(a for a in info["research"] if a["name"] == "fundamental")
    assert fundamental["label"] == "Fundamentals Analyst"


def test_committee_info_unknown_market_falls_back_to_tw():
    from web.server import committee_info
    assert committee_info("jp")["ui"]["title"] == "台股投資委員會"
