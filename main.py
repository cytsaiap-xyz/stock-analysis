import sys

from dotenv import load_dotenv

from agentcore.events import Event, EventBus
from agentcore.evidence import EvidenceLedger
from agentcore.llm import LLMClient
from agentcore.orchestrator import Orchestrator
from committee.agents import ANALYST_TASK_TEMPLATE, build_committee
from committee.config import CACHE_DIR, NVIDIA_BASE_URL
from committee.data.twse import TwseClient
from committee.domain_tools import build_registry


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
        elif e.type == "verdict":
            print("\n\n========== VERDICT ==========\n{}".format(e.data["text"]))


def run(stock_no: str) -> str:
    bus = EventBus()
    bus.subscribe(TerminalRenderer())
    ledger = EvidenceLedger()
    llm = LLMClient(base_url=NVIDIA_BASE_URL)
    registry = build_registry(TwseClient(cache_dir=CACHE_DIR))
    analysts, chair = build_committee()
    orch = Orchestrator(analysts=analysts, chair=chair,
                        analyst_task_template=ANALYST_TASK_TEMPLATE)
    return orch.run(stock_no=stock_no, llm=llm, registry=registry, bus=bus, ledger=ledger)


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
