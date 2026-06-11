import sys

from dotenv import load_dotenv

from agentcore.events import Event, EventBus
from agentcore.evidence import EvidenceLedger
from agentcore.llm import LLMClient
from agentcore.orchestrator import Orchestrator
from agentcore.report import ReportCollector
from committee.config import API_KEY_ENV, BASE_URL, DISCUSSION_ROUNDS, REFLECTION_PASSES
from committee.domain_tools import build_registry
from committee.markets import detect_market, get_profile
from committee.report import save_report


class TerminalRenderer:
    """Subscribes to the EventBus and prints the live debate."""

    def __init__(self) -> None:
        self._streaming_agent = None

    def __call__(self, e: Event) -> None:
        if e.type == "phase" and e.data.get("phase"):
            print("\n\n=== {} ({}) ===".format(e.data["phase"], e.data.get("stock", "")))
        elif e.type == "token":
            if self._streaming_agent != e.agent:
                print("\n[{}] ".format(e.agent), end="")
                self._streaming_agent = e.agent
            print(e.data["text"], end="", flush=True)
        elif e.type == "tool_call":
            self._streaming_agent = None
            print("\n  [tool] {}({})".format(e.data["tool"], e.data.get("args", {})))
        elif e.type == "tool_result":
            print("  [ok] {} returned".format(e.data["tool"]))
        elif e.type == "error":
            print("\n  [warn] {} error: {}".format(e.data.get("tool"), e.data.get("error")))
        elif e.type == "verification":
            g = e.data.get("grounding", {})
            tail = "" if g.get("grounded", True) else " [warn] 未支持: {}".format(g.get("unsupported", []))
            print("\n  [查核] 數據支持 {}/{}{}".format(
                g.get("supported", 0), g.get("checked", 0), tail))
        elif e.type == "verdict":
            print("\n\n========== VERDICT ==========\n{}".format(e.data["text"]))


def run(stock_no: str) -> str:
    bus = EventBus()
    bus.subscribe(TerminalRenderer())
    collector = ReportCollector()
    bus.subscribe(collector)
    ledger = EvidenceLedger()
    llm = LLMClient(base_url=BASE_URL, api_key_env=API_KEY_ENV)

    profile = get_profile(detect_market(stock_no))
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
                        discussion_rounds=DISCUSSION_ROUNDS,
                        discussion_task_template=t.discussion,
                        agent_labels=profile.labels.agent_names,
                        verify_task_template=t.verify,
                        correction_task_template=t.correction)
    verdict = orch.run(stock_no=stock_no, llm=llm, registry=registry,
                       bus=bus, ledger=ledger)
    path = save_report(stock_no, collector, ledger=ledger, twse=profile.client,
                       labels=profile.labels)
    print("\n[report] saved to: {}".format(path))
    return verdict


if __name__ == "__main__":
    # Windows consoles default to cp950; force UTF-8 so Chinese output isn't mangled.
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    load_dotenv()
    stock = sys.argv[1] if len(sys.argv) > 1 else "2330"
    run(stock)
    print()
