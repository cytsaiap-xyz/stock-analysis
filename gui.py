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
from committee.agents import build_committee
from committee.config import API_KEY_ENV, BASE_URL, REFLECTION_PASSES
from committee.domain_tools import build_registry
from committee.markets import detect_market, get_profile
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
AGENT_ZH = {
    "fundamental": "基本面分析師",
    "technical": "技術面分析師",
    "institutional": "籌碼面分析師",
    "news": "新聞輿情分析師",
    "risk": "風險經理",
    "skeptic": "唱反調者",
    "chair": "主席",
    "verifier": "查核員",
    "system": "系統",
}
PHASE_ZH = {"RESEARCH": "研究分析", "CHALLENGE": "質詢",
            "REBUTTAL": "答辯", "VERDICT": "最終結論",
            "REFLECT": "自我反省", "VERIFY": "自我查核"}

_PENDING = ("⏳ 等待", "#6e7681")
_RUNNING = ("▶ 進行中", "#1f6feb")
_DLDONE = ("✓ 完成", "#2ea043")

_DONE = "_run_done"  # internal sentinel: a run finished


def _zh(agent: str) -> str:
    return AGENT_ZH.get(agent, agent)


def _default_labels():
    from committee.markets import get_profile
    return get_profile("tw").labels


def detect_lean(text: str) -> str:
    """從分析師文字中找出傾向關鍵字(看多/看空/中性),找不到回傳「完成」。"""
    for kw in ("看多", "看空", "中性"):
        if kw in (text or ""):
            return kw
    return "完成"


def verdict_headline(text: str) -> str:
    """取出主席結論中含「建議」的那一行,否則取第一行。"""
    for line in (text or "").splitlines():
        if "建議" in line:
            return line.strip()
    lines = (text or "").strip().splitlines()
    return lines[0] if lines else "完成"


def format_event(e: Event, labels=None) -> Optional[Tuple[str, str]]:
    """將非串流事件轉成 (顯示文字, 顏色標籤),或回傳 None 表示忽略。"""
    if labels is None:
        labels = _default_labels()
    if e.type == "phase" and e.data.get("phase"):
        phase = labels.phase_names.get(e.data["phase"], e.data["phase"])
        return ("\n=== {} ({}) ===\n".format(phase, e.data.get("stock", "")), "system")
    if e.type == "tool_call":
        return ("  [工具] {}({})\n".format(e.data.get("tool"), e.data.get("args", {})), e.agent)
    if e.type == "tool_result":
        return ("  [完成] {} 已回傳\n".format(e.data.get("tool")), e.agent)
    if e.type == "error":
        return ("  [警告] {} 錯誤:{}\n".format(e.data.get("tool"), e.data.get("error")), "system")
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
        self._build_widgets()
        self.root.after(50, self._drain)

    # ---- 版面 ----
    def _build_widgets(self) -> None:
        self.root.title("台股投資委員會 — Agentic AI (7 位委員)")
        top = tk.Frame(self.root)
        top.pack(fill="x", padx=8, pady=6)
        tk.Label(top, text="股票代號:").pack(side="left")
        self.ticker = tk.Entry(top, width=10)
        self.ticker.insert(0, "2330")
        self.ticker.pack(side="left", padx=4)
        self.ticker.bind("<Return>", lambda _e: self._on_analyze())
        self.btn = tk.Button(top, text="開始分析", command=self._on_analyze)
        self.btn.pack(side="left")

        self.verdict = tk.Label(self.root, text="結論:(請先執行分析)",
                                font=("Microsoft JhengHei", 12, "bold"), anchor="w",
                                justify="left", wraplength=820)
        self.verdict.pack(fill="x", padx=8, pady=(4, 0))
        self.status = tk.Label(self.root, text="● 閒置", anchor="w",
                               fg="#6e7681", font=("Microsoft JhengHei", 9))
        self.status.pack(fill="x", padx=8, pady=(0, 4))

        body = tk.Frame(self.root)
        body.pack(fill="both", expand=True, padx=8, pady=6)

        # 左側:可捲動的執行流程步驟方塊
        left = tk.Frame(body, width=300)
        left.pack(side="left", fill="y", padx=(0, 8))
        left.pack_propagate(False)
        tk.Label(left, text="執行流程 Pipeline", anchor="w",
                 font=("Microsoft JhengHei", 10, "bold")).pack(fill="x")
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
        tk.Label(right, text="即時討論 Live debate", anchor="w",
                 font=("Microsoft JhengHei", 10, "bold")).pack(fill="x")
        self.feed = scrolledtext.ScrolledText(right, wrap="word", state="disabled",
                                              font=("Microsoft JhengHei", 10))
        self.feed.pack(fill="both", expand=True)
        for name, color in AGENT_COLORS.items():
            self.feed.tag_config(name, foreground=color)

    def _build_pipeline(self) -> None:
        c = build_committee()
        steps = [("phase:RESEARCH", "研究分析", "system", None, None)]
        for a in c.research:
            steps.append(("agent:" + a.name, _zh(a.name), a.name, a.model, a.tool_names))
        steps.append(("phase:CHALLENGE", "質詢", "system", None, None))
        for a in c.challengers:
            steps.append(("agent:" + a.name, _zh(a.name), a.name, a.model, a.tool_names))
        steps.append(("phase:REBUTTAL", "答辯(分析師回應)", "system", None, None))
        steps.append(("phase:VERDICT", "最終結論", "system", None, None))
        steps.append(("agent:chair", _zh("chair"), "chair", c.chair.model, []))
        if REFLECTION_PASSES > 0:
            steps.append(("phase:REFLECT", "自我反省", "system", None, None))
        steps.append(("phase:VERIFY", "自我查核", "system", None, None))
        steps.append(("agent:verifier", _zh("verifier"), "verifier", c.verifier.model, []))

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
        status = tk.Label(hdr, text=_PENDING[0], fg=_PENDING[1],
                          font=("Microsoft JhengHei", 8))
        status.pack(side="right")
        if model:
            tk.Label(card, text="模型: " + model, fg="#444444", anchor="w",
                     font=("Consolas", 7), wraplength=260, justify="left").pack(fill="x")
        if tools:
            tk.Label(card, text="工具: " + ", ".join(tools), fg="#777777", anchor="w",
                     font=("Microsoft JhengHei", 7), wraplength=260, justify="left").pack(fill="x")
        result = tk.Label(card, text="—", fg="#333333", anchor="w",
                          font=("Microsoft JhengHei", 8), wraplength=260, justify="left")
        result.pack(fill="x")
        self.cards[key] = {"status": status, "result": result}

    # ---- 步驟方塊更新 ----
    def _card_running(self, key) -> None:
        c = self.cards.get(key)
        if c:
            c["status"].config(text=_RUNNING[0], fg=_RUNNING[1])

    def _card_done(self, key, result: str = "") -> None:
        c = self.cards.get(key)
        if c:
            c["status"].config(text=_DLDONE[0], fg=_DLDONE[1])
            if result:
                c["result"].config(text=result)

    def _card_result(self, key, text: str) -> None:
        c = self.cards.get(key)
        if c and text:
            c["result"].config(text=text)

    def _reset_cards(self) -> None:
        for c in self.cards.values():
            c["status"].config(text=_PENDING[0], fg=_PENDING[1])
            c["result"].config(text="—")

    # ---- 使用者操作 ----
    def _on_analyze(self) -> None:
        if self._busy:
            return
        stock = self.ticker.get().strip() or "2330"
        self._busy = True
        self._cur_agent = None
        self._cur_has_tokens = False
        self._cur_phase = None
        self.btn.config(state="disabled", text="分析中...")
        self.verdict.config(text="結論:分析 {} 中...".format(stock))
        self._set_status("開始分析 {} ...".format(stock))
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
            profile = get_profile(detect_market(stock))
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
        if et == _DONE:
            self._end_stream()
            if self._cur_phase:
                self._card_done("phase:" + self._cur_phase)
            self._busy = False
            self.btn.config(state="normal", text="開始分析")
            self._set_status("● 閒置 — 已完成")
            return
        if et == "report":
            self._set_status("📄 報告已存: " + e.data.get("path", ""))
            return
        if et == "verdict":
            head = verdict_headline(e.data.get("text", ""))
            self.verdict.config(text="結論:" + head)
            self._card_done("agent:chair", head)
            self._set_status("結論完成 ✓")
            return
        if et == "verification":
            g = e.data.get("grounding", {})
            txt = "數據支持 {}/{}".format(g.get("supported", 0), g.get("checked", 0))
            if not g.get("grounded", True):
                txt += " ⚠ 未支持: " + ", ".join(str(x) for x in g.get("unsupported", []))
            self._card_done("phase:VERIFY", txt)
            self._set_status("查核:" + txt)
            return
        if et == "phase":
            ph = e.data.get("phase")
            if ph:
                self._end_stream()
                self._append(*format_event(e))
                self._set_status("● {} — {}".format(PHASE_ZH.get(ph, ph), e.data.get("stock", "")))
                if self._cur_phase and self._cur_phase != ph:
                    self._card_done("phase:" + self._cur_phase)
                self._card_running("phase:" + ph)
                self._cur_phase = ph
            elif e.data.get("status") == "start":
                self._set_status("{}:思考中 ...".format(_zh(e.agent)))
                self._card_running("agent:" + e.agent)
            return
        if et == "token":
            self._stream_token(e.agent, e.data.get("text", ""))
            self._set_status("{}:撰寫中 ...".format(_zh(e.agent)))
            return
        if et == "message":
            self._finish_message(e)
            self._set_status("{}:完成".format(_zh(e.agent)))
            txt = e.data.get("text", "")
            if e.agent == "chair":
                result = verdict_headline(txt)
            elif e.agent == "verifier":
                lines = txt.strip().splitlines()
                result = (lines[0][:24] if lines else "完成")
            else:
                result = detect_lean(txt)
            self._card_done("agent:" + e.agent, result)
            return
        if et in ("tool_call", "tool_result", "error"):
            self._end_stream()
            formatted = format_event(e)
            if formatted:
                self._append(*formatted)
            if et == "tool_call":
                self._set_status("{}:呼叫 {} ...".format(_zh(e.agent), e.data.get("tool")))
                self._card_result("agent:" + e.agent, "呼叫 {} ...".format(e.data.get("tool")))
            elif et == "tool_result":
                self._set_status("{}:已取得 {}".format(_zh(e.agent), e.data.get("tool")))
            else:
                self._set_status("⚠ {}:{}".format(e.data.get("tool"), e.data.get("error")))

    # ---- 逐字串流輔助 ----
    def _stream_token(self, agent: str, text: str) -> None:
        if self._cur_agent != agent:
            self._end_stream()
            self._append("[{}] ".format(_zh(agent)), agent)
            self._cur_agent = agent
            self._cur_has_tokens = False
        if text:
            self._append(text, agent)
            self._cur_has_tokens = True

    def _finish_message(self, e: Event) -> None:
        if self._cur_agent == e.agent and self._cur_has_tokens:
            self._append("\n", e.agent)
        else:
            formatted = format_event(e)
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
