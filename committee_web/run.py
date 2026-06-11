from typing import Any, Dict

from django.conf import settings

from agentcore.events import Event, EventBus
from agentcore.llm import LLMClient
from agentcore.orchestrator import Orchestrator
from committee.config import API_KEY_ENV, BASE_URL, REFLECTION_PASSES
from committee.domain_tools import build_registry
from committee.markets import get_profile
from committee.report import save_report

DONE_SENTINEL = object()


def safe_market(market: str) -> str:
    return market if market in ("tw", "us") else "tw"


def serialize_event(e: Event) -> Dict[str, Any]:
    """Convert an Event dataclass to a JSON-safe dict for WebSocket transport."""
    return {"type": e.type, "agent": e.agent, "data": e.data, "ts": e.ts}


def run_committee(stock_no, market, q, collector, ledger) -> None:
    """Background worker: run the committee, push Events onto q, save the report,
    then push DONE_SENTINEL. Never raises — failures become an 'error' event."""
    try:
        bus = EventBus()
        bus.subscribe(q.put)
        bus.subscribe(collector)
        llm = LLMClient(base_url=BASE_URL, api_key_env=API_KEY_ENV)
        profile = get_profile(safe_market(market))
        registry = build_registry(profile.client, profile.descriptions)
        t = profile.templates
        committee = profile.committee
        orch = Orchestrator(research=committee.research, challengers=committee.challengers,
                            chair=committee.chair, verifier=committee.verifier,
                            analyst_task_template=t.analyst,
                            challenge_task_template=t.challenge,
                            rebuttal_task_template=t.rebuttal,
                            reflect_task_template=t.reflect,
                            reflection_passes=REFLECTION_PASSES,
                            verify_task_template=t.verify,
                            correction_task_template=t.correction)
        orch.run(stock_no=stock_no, llm=llm, registry=registry, bus=bus, ledger=ledger)
        path = save_report(stock_no, collector, ledger=ledger,
                           reports_dir=str(settings.REPORTS_DIR), twse=profile.client,
                           labels=profile.labels)
        q.put(Event(type="report", agent="system",
                    data={"path": path.name, "url": "/reports/" + path.name}))
    except Exception as exc:  # surface failures to the browser instead of dying silently
        q.put(Event(type="error", agent="system",
                    data={"tool": "run", "error": str(exc)}))
    finally:
        q.put(DONE_SENTINEL)
