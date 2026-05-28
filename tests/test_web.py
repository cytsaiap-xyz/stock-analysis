from fastapi.testclient import TestClient

from agentcore.events import Event
from web.server import app, serialize_event

client = TestClient(app)


def test_serialize_event_is_json_safe_dict():
    e = Event(type="message", agent="chair", data={"text": "hi"})
    out = serialize_event(e)
    assert out["type"] == "message"
    assert out["agent"] == "chair"
    assert out["data"] == {"text": "hi"}
    assert isinstance(out["ts"], float)


def test_index_serves_html():
    r = client.get("/")
    assert r.status_code == 200
    assert "<title>" in r.text and "投資委員會" in r.text


def test_committee_info_returns_full_roster():
    r = client.get("/api/committee")
    assert r.status_code == 200
    body = r.json()
    assert [a["name"] for a in body["research"]] == [
        "fundamental", "technical", "institutional", "news"]
    assert [a["name"] for a in body["challengers"]] == ["risk", "skeptic"]
    assert body["chair"]["name"] == "chair"
    assert body["verifier"]["name"] == "verifier"
    assert "RESEARCH" in body["phase_zh"] and "VERIFY" in body["phase_zh"]
