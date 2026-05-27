"""Tkinter desktop front-end for the Agentic Investment Committee.

The committee engine is unchanged: this GUI is just another EventBus subscriber.
Because a run does ~30-90s of network/LLM work and Tkinter is single-threaded,
the committee runs on a background thread that pushes Events onto a thread-safe
queue; the Tk main loop drains that queue via root.after() and updates widgets
(widgets are only ever touched from the main thread).

Run:  python gui.py
"""
import queue
import threading
import tkinter as tk
from tkinter import scrolledtext
from typing import Optional, Tuple

from dotenv import load_dotenv

from agentcore.events import Event, EventBus
from agentcore.evidence import EvidenceLedger
from agentcore.llm import LLMClient
from agentcore.orchestrator import Orchestrator
from committee.agents import ANALYST_TASK_TEMPLATE, build_committee
from committee.config import CACHE_DIR, NVIDIA_BASE_URL
from committee.data.twse import TwseClient
from committee.domain_tools import build_registry

AGENT_COLORS = {
    "fundamental": "#1f6feb",
    "technical": "#2ea043",
    "chair": "#8957e5",
    "system": "#6e7681",
}

# Internal sentinel event signalling a run finished (re-enables the button).
_DONE = "_run_done"


def format_event(e: Event) -> Optional[Tuple[str, str]]:
    """Map an Event to (display_text, tag) for the feed, or None to ignore.

    Tokens are ignored (the GUI shows completed `message` events, not token-by-token)
    and `verdict` is handled separately (it updates the banner, not the feed).
    """
    if e.type == "phase" and e.data.get("phase"):
        return ("\n=== {} ({}) ===\n".format(e.data["phase"], e.data.get("stock", "")), "system")
    if e.type == "tool_call":
        return ("  [tool] {}({})\n".format(e.data.get("tool"), e.data.get("args", {})), e.agent)
    if e.type == "tool_result":
        return ("  [ok] {} returned\n".format(e.data.get("tool")), e.agent)
    if e.type == "error":
        return ("  [warn] {} error: {}\n".format(e.data.get("tool"), e.data.get("error")), "system")
    if e.type == "message" and e.data.get("text"):
        return ("[{}] {}\n".format(e.agent, e.data["text"]), e.agent)
    return None


class CommitteeGUI:
    def __init__(self, root: "tk.Tk") -> None:
        self.root = root
        self.queue: "queue.Queue" = queue.Queue()
        self._busy = False
        self._build_widgets()
        self.root.after(50, self._drain)

    def _build_widgets(self) -> None:
        self.root.title("Agentic Investment Committee")
        top = tk.Frame(self.root)
        top.pack(fill="x", padx=8, pady=6)
        tk.Label(top, text="Ticker:").pack(side="left")
        self.ticker = tk.Entry(top, width=10)
        self.ticker.insert(0, "2330")
        self.ticker.pack(side="left", padx=4)
        self.ticker.bind("<Return>", lambda _e: self._on_analyze())
        self.btn = tk.Button(top, text="Analyze", command=self._on_analyze)
        self.btn.pack(side="left")

        self.verdict = tk.Label(self.root, text="Verdict: (run an analysis)",
                                font=("Segoe UI", 12, "bold"), anchor="w",
                                justify="left", wraplength=660)
        self.verdict.pack(fill="x", padx=8, pady=4)

        self.feed = scrolledtext.ScrolledText(self.root, width=92, height=30,
                                              wrap="word", state="disabled",
                                              font=("Consolas", 9))
        self.feed.pack(fill="both", expand=True, padx=8, pady=6)
        for name, color in AGENT_COLORS.items():
            self.feed.tag_config(name, foreground=color)

    # ---- user action ----
    def _on_analyze(self) -> None:
        if self._busy:
            return
        stock = self.ticker.get().strip() or "2330"
        self._busy = True
        self.btn.config(state="disabled", text="Analyzing...")
        self.verdict.config(text="Verdict: analyzing {} ...".format(stock))
        self._clear_feed()
        threading.Thread(target=self._run_worker, args=(stock,), daemon=True).start()

    # ---- background worker (NOT the GUI thread) ----
    def _run_worker(self, stock: str) -> None:
        try:
            bus = EventBus()
            bus.subscribe(self.queue.put)   # Queue is thread-safe; widgets are not touched here
            llm = LLMClient(base_url=NVIDIA_BASE_URL)
            registry = build_registry(TwseClient(cache_dir=CACHE_DIR))
            analysts, chair = build_committee()
            orch = Orchestrator(analysts=analysts, chair=chair,
                                analyst_task_template=ANALYST_TASK_TEMPLATE)
            orch.run(stock_no=stock, llm=llm, registry=registry,
                     bus=bus, ledger=EvidenceLedger())
        except Exception as exc:  # surface any failure in the feed instead of dying silently
            self.queue.put(Event(type="error", agent="system",
                                 data={"tool": "run", "error": str(exc)}))
        finally:
            self.queue.put(Event(type=_DONE, agent="system"))

    # ---- GUI-thread queue drain ----
    def _drain(self) -> None:
        try:
            while True:
                self._handle(self.queue.get_nowait())
        except queue.Empty:
            pass
        self.root.after(50, self._drain)

    def _handle(self, e: Event) -> None:
        if e.type == _DONE:
            self._busy = False
            self.btn.config(state="normal", text="Analyze")
            return
        if e.type == "verdict":
            headline = (e.data.get("text") or "").strip().splitlines()
            self.verdict.config(text="Verdict: " + (" | ".join(headline[:2]) if headline else "(none)"))
            return
        formatted = format_event(e)
        if formatted:
            text, tag = formatted
            self._append(text, tag)

    def _append(self, text: str, tag: str) -> None:
        self.feed.config(state="normal")
        self.feed.insert("end", text, tag)
        self.feed.see("end")
        self.feed.config(state="disabled")

    def _clear_feed(self) -> None:
        self.feed.config(state="normal")
        self.feed.delete("1.0", "end")
        self.feed.config(state="disabled")


def main() -> None:
    load_dotenv()
    root = tk.Tk()
    root.geometry("760x680")
    CommitteeGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
