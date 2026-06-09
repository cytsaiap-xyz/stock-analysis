"""FastAPI + WebSocket front-end for the committee.

The committee engine is unchanged — this server is just another EventBus subscriber.
A run is launched on a worker thread that pushes Events onto a thread-safe queue;
the WebSocket handler drains the queue and forwards each event as JSON to the
browser. A static directory serves the HTML/JS UI, and a /reports route serves
saved HTML reports.

Launch:  uvicorn web.server:app --reload
Open:    http://localhost:8000
"""
import asyncio
import queue
import threading
from pathlib import Path
from typing import Any, Dict

from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from agentcore.events import Event, EventBus
from agentcore.evidence import EvidenceLedger
from agentcore.llm import LLMClient
from agentcore.orchestrator import Orchestrator
from agentcore.report import ReportCollector
from committee.config import API_KEY_ENV, BASE_URL, REFLECTION_PASSES
from committee.domain_tools import build_registry
from committee.markets import get_profile
from committee.report import save_report

_STATIC = Path(__file__).parent / "static"
_REPORTS = Path("reports")
_REPORTS.mkdir(exist_ok=True)

load_dotenv()

app = FastAPI(title="Agentic Investment Committee")
app.mount("/static", StaticFiles(directory=str(_STATIC)), name="static")
app.mount("/reports", StaticFiles(directory=str(_REPORTS)), name="reports")


def serialize_event(e: Event) -> Dict[str, Any]:
    """Convert an Event dataclass to a JSON-safe dict for WebSocket transport."""
    return {"type": e.type, "agent": e.agent, "data": e.data, "ts": e.ts}


@app.get("/")
def index() -> FileResponse:
    return FileResponse(_STATIC / "index.html")


def _safe_market(market: str) -> str:
    return market if market in ("tw", "us") else "tw"


@app.get("/api/committee")
def committee_info(market: str = "tw") -> Dict[str, Any]:
    """Roster + localized UI text for a market's pipeline view."""
    profile = get_profile(_safe_market(market))
    c = profile.committee
    labels = profile.labels
    names = labels.agent_names

    def info(a, group):
        return {"name": a.name, "label": names.get(a.name, a.name),
                "model": a.model, "tools": list(a.tool_names), "group": group}

    return {
        "market": profile.market,
        "research": [info(a, "research") for a in c.research],
        "challengers": [info(a, "challengers") for a in c.challengers],
        "chair": info(c.chair, "chair"),
        "verifier": info(c.verifier, "verifier"),
        "phase_names": labels.phase_names,
        "agent_names": names,
        "reflection_passes": REFLECTION_PASSES,
        "ui": profile.ui,
    }


_DONE_SENTINEL = object()


def _run_committee(stock_no: str, market: str, q: "queue.Queue",
                   collector: ReportCollector, ledger: EvidenceLedger) -> None:
    """Background worker: runs the committee, pushes events into the queue.
    Saves the HTML report on completion and pushes a final 'report' event."""
    try:
        bus = EventBus()
        bus.subscribe(q.put)
        bus.subscribe(collector)
        llm = LLMClient(base_url=BASE_URL, api_key_env=API_KEY_ENV)
        profile = get_profile(_safe_market(market))
        registry = build_registry(profile.client, profile.descriptions)
        t = profile.templates
        committee = profile.committee
        orch = Orchestrator(research=committee.research,
                            challengers=committee.challengers, chair=committee.chair,
                            verifier=committee.verifier,
                            analyst_task_template=t.analyst,
                            challenge_task_template=t.challenge,
                            rebuttal_task_template=t.rebuttal,
                            reflect_task_template=t.reflect,
                            reflection_passes=REFLECTION_PASSES,
                            verify_task_template=t.verify,
                            correction_task_template=t.correction)
        orch.run(stock_no=stock_no, llm=llm, registry=registry,
                 bus=bus, ledger=ledger)
        path = save_report(stock_no, collector, ledger=ledger,
                           reports_dir=str(_REPORTS), twse=profile.client,
                           labels=profile.labels)
        q.put(Event(type="report", agent="system",
                    data={"path": path.name, "url": "/reports/" + path.name}))
    except Exception as exc:  # surface failures to the browser instead of dying silently
        q.put(Event(type="error", agent="system",
                    data={"tool": "run", "error": str(exc)}))
    finally:
        q.put(_DONE_SENTINEL)


@app.websocket("/ws/run/{market}/{stock_no}")
async def ws_run(ws: WebSocket, market: str, stock_no: str) -> None:
    await ws.accept()
    q: "queue.Queue" = queue.Queue()
    collector = ReportCollector()
    ledger = EvidenceLedger()
    threading.Thread(target=_run_committee, args=(stock_no, market, q, collector, ledger),
                     daemon=True).start()

    try:
        while True:
            try:
                item = q.get_nowait()
            except queue.Empty:
                await asyncio.sleep(0.05)
                continue
            if item is _DONE_SENTINEL:
                break
            await ws.send_json(serialize_event(item))
    except WebSocketDisconnect:
        pass
    finally:
        try:
            await ws.close()
        except Exception:
            pass
