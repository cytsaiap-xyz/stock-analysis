"""台股投資委員會 — Tkinter 桌面介面(7 位委員 + 辯論回合 步驟方塊版)。

委員會引擎完全不變:此 GUI 只是另一個 EventBus 訂閱者。委員會在背景執行緒執行,
透過執行緒安全的 queue 推送 Event;Tk 主迴圈以 root.after() 取出並更新畫面。

左側為「執行流程」步驟方塊(可捲動):每個方塊顯示委員、使用的 LLM 模型、工具與
即時狀態。右側為逐字串流的對話 feed。

執行:  python gui.py
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
from agentcore.report import ReportCollector
from committee.config import API_KEY_ENV, BASE_URL, REFLECTION_PASSES
from committee.domain_tools import build_registry
from committee.markets import get_profile
from committee.report import save_report

AGENT_COLORS = {
    "fundamental": "#1f6feb",
    "technical": "#2ea043",
    "institutional": "#d29922",
    "news": "#db61a2",
    "risk": "#cf222e",
    "skeptic": "#bf3989",
    "chair": "#8957e5",
    "verifier": "#0a7ea4",
    "system": "#6e7681",
}
_PENDING = ("⏳ 等待", "#6e7681")
_RUNNING = ("▶ 進行中", "#1f6feb")
_DLDONE = ("✓ 完成", "#2ea043")

_DONE = "_run_done"  # internal sentinel: a run finished


def _default_labels():
    from committee.markets import get_profile
    return get_profile("tw").labels


def _default_ui():
    from committee.markets import get_profile
    return get_profile("tw").ui


def detect_lean(text, lean_words=None, done_word=None):
    """Find a stance keyword in the analyst text; fall back to done_word."""
    words = lean_words or ("看多", "看空", "中性")
    for kw in words:
        if kw in (text or ""):
            return kw
    return done_word or "完成"


def verdict_headline(text, recommend_word=None, done_word=None):
    """Pick the chair's recommendation line; else the first line."""
    rw = recommend_word or "建議"
    for line in (text or "").splitlines():
        if rw in line:
            return line.strip()
    lines = (text or "").strip().splitlines()
    return lines[0] if lines else (done_word or "完成")


def format_event(e: "Event", labels=None, ui=None) -> "Optional[Tuple[str, str]]":
    """將非串流事件轉成 (顯示文字, 顏色標籤),或回傳 None 表示忽略。"""
    if labels is None:
        labels = _default_labels()
    if ui is None:
        ui = _default_ui()
    if e.type == "phase" and e.data.get("phase"):
        phase = labels.phase_names.get(e.data["phase"], e.data["phase"])
        return ("\n=== {} ({}) ===\n".format(phase, e.data.get("stock", "")), "system")
    if e.type == "tool_call":
        return ("  [{}] {}({})\n".format(ui["tool_word"], e.data.get("tool"), e.data.get("args", {})), e.agent)
    if e.type == "tool_result":
        return ("  [{}] {}\n".format(ui["done_word"], e.data.get("tool")), e.agent)
    if e.type == "error":
        return ("  [{}] {}: {}\n".format(ui["warn_word"], e.data.get("tool"), e.data.get("error")), "system")
    if e.type == "message" and e.data.get("text"):
        return ("[{}] {}\n".format(labels.agent_names.get(e.agent, e.agent), e.data["text"]), e.agent)
    return None


class CommitteeGUI:
    def __init__(self, root: "tk.Tk") -> None:
        self.root = root
        self.queue: "queue.Queue" = queue.Queue()
        self._busy = False
        self._cur_agent = None
        self._cur_has_tokens = False
        self._cur_phase = None
        self.cards = {}
        self.market_var = tk.StringVar(value="tw")
        self.profile = get_profile("tw")
        self._build_widgets()
        self.root.after(50, self._drain)

    # ---- 版面 ----
    def _build_widgets(self) -> None:
        ui = self.profile.ui
        self.root.title(ui["title"])
        top = tk.Frame(self.root)
        top.pack(fill="x", padx=8, pady=6)
        self.ticker_label = tk.Label(top, text=ui["ticker_label"])
        self.ticker_label.pack(side="left")
        self.ticker = tk.Entry(top, width=10)
        self.ticker.insert(0, ui["example_ticker"])
        self.ticker.pack(side="left", padx=4)
        self.ticker.bind("<Return>", lambda _e: self._on_analyze())
        self.btn = tk.Button(top, text=ui["run_button"], command=self._on_analyze)
        self.btn.pack(side="left")
        tk.Radiobutton(top, text="TW", variable=self.market_var, value="tw",
                       command=self._on_market_change).pack(side="left")
        tk.Radiobutton(top, text="US", variable=self.market_var, value="us",
                       command=self._on_market_change).pack(side="left")

        self.verdict = tk.Label(self.root, text=ui["verdict_placeholder"],
                                font=("Microsoft JhengHei", 12, "bold"), anchor="w",
                                justify="left", wraplength=820)
        self.verdict.pack(fill="x", padx=8, pady=(4, 0))
        self.status = tk.Label(self.root, text=ui["idle"], anchor="w",
                               fg="#6e7681", font=("Microsoft JhengHei", 9))
        self.status.pack(fill="x", padx=8, pady=(0, 4))

        body = tk.Frame(self.root)
        body.pack(fill="both", expand=True, padx=8, pady=6)

        # 左側:可捲動的執行流程步驟方塊
        left = tk.Frame(body, width=300)
        left.pack(side="left", fill="y", padx=(0, 8))
        left.pack_propagate(False)
        self.pipeline_heading = tk.Label(left, text=ui["pipeline_heading"], anchor="w",
                                         font=("Microsoft JhengHei", 10, "bold"))
        self.pipeline_heading.pack(fill="x")
        canvas = tk.Canvas(left, width=290, highlightthickness=0)
        sb = tk.Scrollbar(left, orient="vertical", command=canvas.yview)
        self._pipeline = tk.Frame(canvas)
        self._pipeline.bind(
            "<Configure>", lambda _e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=self._pipeline, anchor="nw")
        canvas.configure(yscrollcommand=sb.set)
        canvas.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        self._build_pipeline()

        # 右側:逐字串流對話
        right = tk.Frame(body)
        right.pack(side="left", fill="both", expand=True)
        self.debate_heading = tk.Label(right, text=ui["debate_heading"], anchor="w",
                                       font=("Microsoft JhengHei", 10, "bold"))
        self.debate_heading.pack(fill="x")
        self.feed = scrolledtext.ScrolledText(right, wrap="word", state="disabled",
                                              font=("Microsoft JhengHei", 10))
        self.feed.pack(fill="both", expand=True)
        for name, color in AGENT_COLORS.items():
            self.feed.tag_config(name, foreground=color)

    def _build_pipeline(self) -> None:
        c = self.profile.committee
        lbl = self.profile.labels
        pn = lbl.phase_names
        an = lbl.agent_names
        steps = [("phase:RESEARCH", pn.get("RESEARCH", "RESEARCH"), "system", None, None)]
        for a in c.research:
            steps.append(("agent:" + a.name, an.get(a.name, a.name), a.name, a.model, a.tool_names))
        steps.append(("phase:CHALLENGE", pn.get("CHALLENGE", "CHALLENGE"), "system", None, None))
        for a in c.challengers:
            steps.append(("agent:" + a.name, an.get(a.name, a.name), a.name, a.model, a.tool_names))
        steps.append(("phase:REBUTTAL", pn.get("REBUTTAL", "REBUTTAL"), "system", None, None))
        steps.append(("phase:VERDICT", pn.get("VERDICT", "VERDICT"), "system", None, None))
        steps.append(("agent:chair", an.get("chair", "chair"), "chair", c.chair.model, []))
        if REFLECTION_PASSES > 0:
            steps.append(("phase:REFLECT", pn.get("REFLECT", "REFLECT"), "system", None, None))
        steps.append(("phase:VERIFY", pn.get("VERIFY", "VERIFY"), "system", None, None))
        steps.append(("agent:verifier", an.get("verifier", "verifier"), "verifier", c.verifier.model, []))

        for i, (key, title, ck, model, tools) in enumerate(steps, start=1):
            self._make_card(i, key, title, ck, model, tools)
            if i < len(steps):
                tk.Label(self._pipeline, text="↓", fg="#b0b0b0").pack()

    def _make_card(self, num, key, title, color_key, model, tools) -> None:
        color = AGENT_COLORS.get(color_key, "#333333")
        card = tk.Frame(self._pipeline, bd=1, relief="solid", padx=6, pady=3)
        card.pack(fill="x")
        hdr = tk.Frame(card)
        hdr.pack(fill="x")
        tk.Label(hdr, text="{}. {}".format(num, title), fg=color,
                 font=("Microsoft JhengHei", 9, "bold")).pack(side="left")
        status = tk.Label(hdr, text=self.profile.ui["pending_badge"], fg=_PENDING[1],
                          font=("Microsoft JhengHei", 8))
        status.pack(side="right")
        if model:
            tk.Label(card, text=self.profile.ui["model_label"] + model, fg="#444444", anchor="w",
                     font=("Consolas", 7), wraplength=260, justify="left").pack(fill="x")
        if tools:
            tk.Label(card, text=self.profile.ui["tools_label"] + ", ".join(tools), fg="#777777",
                     anchor="w", font=("Microsoft JhengHei", 7), wraplength=260,
                     justify="left").pack(fill="x")
        result = tk.Label(card, text="—", fg="#333333", anchor="w",
                          font=("Microsoft JhengHei", 8), wraplength=260, justify="left")
        result.pack(fill="x")
        self.cards[key] = {"status": status, "result": result}

    # ---- 市場切換 ----
    def _on_market_change(self) -> None:
        self.profile = get_profile(self.market_var.get())
        ui = self.profile.ui
        self.root.title(self.profile.ui["title"])
        self.btn.config(text=ui["run_button"])
        self.ticker_label.config(text=ui["ticker_label"])
        self.verdict.config(text=ui["verdict_placeholder"])
        self.status.config(text=ui["idle"])
        self.pipeline_heading.config(text=ui["pipeline_heading"])
        self.debate_heading.config(text=ui["debate_heading"])
        cur = self.ticker.get().strip()
        if not cur or cur in ("2330", "AAPL"):
            self.ticker.delete(0, "end")
            self.ticker.insert(0, ui["example_ticker"])
        for w in self._pipeline.winfo_children():
            w.destroy()
        self.cards = {}
        self._build_pipeline()

    # ---- 步驟方塊更新 ----
    def _card_running(self, key) -> None:
        c = self.cards.get(key)
        if c:
            c["status"].config(text=self.profile.ui["running_badge"], fg=_RUNNING[1])

    def _card_done(self, key, result: str = "") -> None:
        c = self.cards.get(key)
        if c:
            c["status"].config(text=self.profile.ui["done_badge"], fg=_DLDONE[1])
            if result:
                c["result"].config(text=result)

    def _card_result(self, key, text: str) -> None:
        c = self.cards.get(key)
        if c and text:
            c["result"].config(text=text)

    def _reset_cards(self) -> None:
        for c in self.cards.values():
            c["status"].config(text=self.profile.ui["pending_badge"], fg=_PENDING[1])
            c["result"].config(text="—")

    # ---- 使用者操作 ----
    def _on_analyze(self) -> None:
        if self._busy:
            return
        ui = self.profile.ui
        stock = self.ticker.get().strip() or ui["example_ticker"]
        self._busy = True
        self._cur_agent = None
        self._cur_has_tokens = False
        self._cur_phase = None
        self.btn.config(state="disabled", text=ui["running_button"])
        self.verdict.config(text=ui["verdict_running"].format(stock=stock))
        self._set_status(ui["start_status"].format(stock=stock))
        self._reset_cards()
        self._clear_feed()
        threading.Thread(target=self._run_worker, args=(stock,), daemon=True).start()

    # ---- 背景執行緒(非 GUI 執行緒) ----
    def _run_worker(self, stock: str) -> None:
        try:
            bus = EventBus()
            bus.subscribe(self.queue.put)
            collector = ReportCollector()
            bus.subscribe(collector)
            ledger = EvidenceLedger()
            llm = LLMClient(base_url=BASE_URL, api_key_env=API_KEY_ENV)
            profile = self.profile
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
            orch.run(stock_no=stock, llm=llm, registry=registry,
                     bus=bus, ledger=ledger)
            path = save_report(stock, collector, ledger=ledger, twse=profile.client,
                               labels=profile.labels)
            self.queue.put(Event(type="report", agent="system",
                                 data={"path": str(path)}))
        except Exception as exc:
            self.queue.put(Event(type="error", agent="system",
                                 data={"tool": "run", "error": str(exc)}))
        finally:
            self.queue.put(Event(type=_DONE, agent="system"))

    # ---- GUI 執行緒:取出事件 ----
    def _drain(self) -> None:
        try:
            while True:
                self._handle(self.queue.get_nowait())
        except queue.Empty:
            pass
        self.root.after(50, self._drain)

    def _handle(self, e: Event) -> None:
        et = e.type
        ui = self.profile.ui
        labels = self.profile.labels
        an = labels.agent_names
        if et == _DONE:
            self._end_stream()
            if self._cur_phase:
                self._card_done("phase:" + self._cur_phase)
            self._busy = False
            self.btn.config(state="normal", text=ui["run_button"])
            self._set_status(ui["done_idle"])
            return
        if et == "report":
            self._set_status(ui["report_saved"] + ": " + e.data.get("path", ""))
            return
        if et == "verdict":
            head = verdict_headline(e.data.get("text", ""), ui["recommend_word"], ui["done_word"])
            self.verdict.config(text=ui["verdict_prefix"] + head)
            self._card_done("agent:chair", head)
            self._set_status(ui["verdict_done"])
            return
        if et == "verification":
            g = e.data.get("grounding", {})
            txt = "{} {}/{}".format(self.profile.ui["verify_prefix"], g.get("supported", 0), g.get("checked", 0))
            if not g.get("grounded", True):
                txt += " ⚠ " + self.profile.ui["unsupported_word"] + ": " + ", ".join(str(x) for x in g.get("unsupported", []))
            self._card_done("phase:VERIFY", txt)
            self._set_status(txt)
            return
        if et == "phase":
            ph = e.data.get("phase")
            if ph:
                self._end_stream()
                self._append(*format_event(e, self.profile.labels, self.profile.ui))
                self._set_status("● {} — {}".format(labels.phase_names.get(ph, ph), e.data.get("stock", "")))
                if self._cur_phase and self._cur_phase != ph:
                    self._card_done("phase:" + self._cur_phase)
                self._card_running("phase:" + ph)
                self._cur_phase = ph
            elif e.data.get("status") == "start":
                self._set_status("{}:{} ...".format(an.get(e.agent, e.agent), ui["thinking"]))
                self._card_running("agent:" + e.agent)
            return
        if et == "token":
            self._stream_token(e.agent, e.data.get("text", ""))
            self._set_status("{}:{} ...".format(an.get(e.agent, e.agent), ui["writing"]))
            return
        if et == "message":
            self._finish_message(e)
            self._set_status("{}:{}".format(an.get(e.agent, e.agent), ui["done_word"]))
            txt = e.data.get("text", "")
            if e.agent == "chair":
                result = verdict_headline(txt, ui["recommend_word"], ui["done_word"])
            elif e.agent == "verifier":
                lines = txt.strip().splitlines()
                result = (lines[0][:24] if lines else ui["done_word"])
            else:
                result = detect_lean(txt, self.profile.ui["lean_words"], ui["done_word"])
            self._card_done("agent:" + e.agent, result)
            return
        if et in ("tool_call", "tool_result", "error"):
            self._end_stream()
            formatted = format_event(e, self.profile.labels, self.profile.ui)
            if formatted:
                self._append(*formatted)
            if et == "tool_call":
                self._set_status("{}:{} {} ...".format(an.get(e.agent, e.agent), ui["calling"], e.data.get("tool")))
                self._card_result("agent:" + e.agent, "{} {} ...".format(ui["calling"], e.data.get("tool")))
            elif et == "tool_result":
                self._set_status("{}:{} {}".format(an.get(e.agent, e.agent), ui["received"], e.data.get("tool")))
            else:
                self._set_status("⚠ {}:{}".format(e.data.get("tool"), e.data.get("error")))

    # ---- 逐字串流輔助 ----
    def _stream_token(self, agent: str, text: str) -> None:
        if self._cur_agent != agent:
            self._end_stream()
            self._append("[{}] ".format(self.profile.labels.agent_names.get(agent, agent)), agent)
            self._cur_agent = agent
            self._cur_has_tokens = False
        if text:
            self._append(text, agent)
            self._cur_has_tokens = True

    def _finish_message(self, e: Event) -> None:
        if self._cur_agent == e.agent and self._cur_has_tokens:
            self._append("\n", e.agent)
        else:
            formatted = format_event(e, self.profile.labels, self.profile.ui)
            if formatted:
                self._append(*formatted)
        self._cur_agent = None
        self._cur_has_tokens = False

    def _end_stream(self) -> None:
        if self._cur_agent is not None:
            self._append("\n", self._cur_agent)
            self._cur_agent = None
            self._cur_has_tokens = False

    # ---- 畫面元件輔助(僅 GUI 執行緒) ----
    def _set_status(self, text: str) -> None:
        self.status.config(text=text)

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
    root.geometry("1040x760")
    CommitteeGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
