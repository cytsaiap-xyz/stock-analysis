import queue

from django.test import Client

from agentcore.evidence import EvidenceLedger
from agentcore.report import ReportCollector


def _client():
    return Client()


def test_committee_info_tw_is_chinese():
    d = _client().get("/api/committee?market=tw").json()
    assert d["ui"]["title"] == "台股投資委員會"
    assert d["phase_names"]["RESEARCH"] == "研究分析"
    assert next(a for a in d["research"] if a["name"] == "fundamental")["label"] == "基本面分析師"


def test_committee_info_us_is_english():
    d = _client().get("/api/committee?market=us").json()
    assert d["ui"]["title"] == "US Equity Investment Committee"
    assert d["phase_names"]["RESEARCH"] == "Research"
    assert next(a for a in d["research"] if a["name"] == "fundamental")["label"] == "Fundamentals Analyst"


def test_committee_info_unknown_market_falls_back_to_tw():
    d = _client().get("/api/committee?market=jp").json()
    assert d["ui"]["title"] == "台股投資委員會"


def test_index_serves_the_spa_html():
    resp = _client().get("/")
    body = b"".join(resp.streaming_content)
    assert b'name="market"' in body and b"app.js" in body


def test_run_committee_uses_forced_market(monkeypatch):
    """run_committee routes by the explicit market arg, not the ticker format."""
    import committee_web.run as run

    captured = {}

    class _StubOrch:
        def __init__(self, **kw):
            pass

        def run(self, **kw):
            captured["ran"] = True

    monkeypatch.setattr(run, "Orchestrator", _StubOrch)
    monkeypatch.setattr(run, "LLMClient", lambda **kw: object())
    monkeypatch.setattr(run, "save_report", lambda *a, **k: type("P", (), {"name": "x.html"})())
    monkeypatch.setattr(run, "build_registry",
                        lambda client, desc: captured.update(client_type=type(client).__name__) or "REG")

    q = queue.Queue()
    run.run_committee("2330", "us", q, ReportCollector(), EvidenceLedger())
    assert captured.get("ran") is True
    assert captured.get("client_type") == "UsClient"  # forced US despite TW ticker


def test_consumer_drain_sends_events_then_closes():
    import asyncio
    import json as _json
    import queue

    from committee_web.consumers import RunConsumer
    from committee_web.run import DONE_SENTINEL
    from agentcore.events import Event

    sent = []
    closed = []
    consumer = RunConsumer()

    async def _send(text_data=None):
        sent.append(text_data)

    async def _close():
        closed.append(True)

    consumer.send = _send
    consumer.close = _close

    q = queue.Queue()
    q.put(Event(type="phase", agent="system", data={"phase": "RESEARCH", "stock": "AAPL"}))
    q.put(DONE_SENTINEL)
    asyncio.run(consumer._drain(q))

    assert _json.loads(sent[0])["type"] == "phase"
    assert closed == [True]


def test_asgi_application_routes_http_and_websocket():
    # Importing the ASGI app must succeed (runserver loads it) and expose both
    # protocols — guards against a bad handler/import that unit tests using the
    # Django test Client would not exercise.
    from config.asgi import application
    assert set(application.application_mapping) == {"http", "websocket"}


def test_committee_info_returns_us_stocklist():
    d = _client().get("/api/committee?market=us").json()
    labels = [c["label"] for c in d["stocklist"]]
    assert "CPU" in labels and "EDA" in labels
    eda = next(c for c in d["stocklist"] if c["label"] == "EDA")
    assert any(it["code"] == "SNPS" for it in eda["items"])


def test_committee_info_returns_tw_stocklist_chinese():
    d = _client().get("/api/committee?market=tw").json()
    labels = [c["label"] for c in d["stocklist"]]
    assert "半導體" in labels
