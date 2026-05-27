"""台股投資委員會 — Tkinter 桌面介面。

委員會引擎完全不變:此 GUI 只是另一個 EventBus 訂閱者。由於一次分析需要約
30-90 秒的網路/LLM 運算,而 Tkinter 為單執行緒,委員會在背景執行緒執行,
透過執行緒安全的 queue 推送 Event;Tk 主迴圈以 root.after() 取出事件並更新
畫面(畫面元件只在主執行緒操作)。

各分析師的文字逐字串流顯示;狀態列即時顯示目前步驟(思考 / 呼叫工具 / 撰寫 / 完成)。

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

# 顯示用的中文名稱(事件內部仍用英文 key 當作顏色標籤)。
AGENT_ZH = {
    "fundamental": "基本面分析師",
    "technical": "技術面分析師",
    "chair": "主席",
    "system": "系統",
}
PHASE_ZH = {"RESEARCH": "研究分析", "VERDICT": "最終結論"}

# Internal sentinel event signalling a run finished (re-enables the button).
_DONE = "_run_done"


def _zh(agent: str) -> str:
    return AGENT_ZH.get(agent, agent)


def format_event(e: Event) -> Optional[Tuple[str, str]]:
    """將非串流事件轉成 (顯示文字, 顏色標籤),或回傳 None 表示忽略。

    token 由 GUI 逐字串流處理(有狀態,不在此處);verdict 更新結論橫幅而非
    feed,故此處回傳 None;message 僅在某分析師完全沒有串流 token 時作為後備。
    """
    if e.type == "phase" and e.data.get("phase"):
        phase = PHASE_ZH.get(e.data["phase"], e.data["phase"])
        return ("\n=== {} ({}) ===\n".format(phase, e.data.get("stock", "")), "system")
    if e.type == "tool_call":
        return ("  [工具] {}({})\n".format(e.data.get("tool"), e.data.get("args", {})), e.agent)
    if e.type == "tool_result":
        return ("  [完成] {} 已回傳\n".format(e.data.get("tool")), e.agent)
    if e.type == "error":
        return ("  [警告] {} 錯誤:{}\n".format(e.data.get("tool"), e.data.get("error")), "system")
    if e.type == "message" and e.data.get("text"):
        return ("[{}] {}\n".format(_zh(e.agent), e.data["text"]), e.agent)
    return None


class CommitteeGUI:
    def __init__(self, root: "tk.Tk") -> None:
        self.root = root
        self.queue: "queue.Queue" = queue.Queue()
        self._busy = False
        self._cur_agent = None          # agent whose tokens are currently streaming
        self._cur_has_tokens = False    # did this agent stream any token text?
        self._build_widgets()
        self.root.after(50, self._drain)

    def _build_widgets(self) -> None:
        self.root.title("台股投資委員會 — Agentic AI")
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
                                justify="left", wraplength=720)
        self.verdict.pack(fill="x", padx=8, pady=(4, 0))

        # 即時狀態列:顯示目前步驟。
        self.status = tk.Label(self.root, text="● 閒置", anchor="w",
                               fg="#6e7681", font=("Microsoft JhengHei", 9))
        self.status.pack(fill="x", padx=8, pady=(0, 4))

        self.feed = scrolledtext.ScrolledText(self.root, width=92, height=30,
                                              wrap="word", state="disabled",
                                              font=("Microsoft JhengHei", 10))
        self.feed.pack(fill="both", expand=True, padx=8, pady=6)
        for name, color in AGENT_COLORS.items():
            self.feed.tag_config(name, foreground=color)

    # ---- 使用者操作 ----
    def _on_analyze(self) -> None:
        if self._busy:
            return
        stock = self.ticker.get().strip() or "2330"
        self._busy = True
        self._cur_agent = None
        self._cur_has_tokens = False
        self.btn.config(state="disabled", text="分析中...")
        self.verdict.config(text="結論:分析 {} 中...".format(stock))
        self._set_status("開始分析 {} ...".format(stock))
        self._clear_feed()
        threading.Thread(target=self._run_worker, args=(stock,), daemon=True).start()

    # ---- 背景執行緒(非 GUI 執行緒) ----
    def _run_worker(self, stock: str) -> None:
        try:
            bus = EventBus()
            bus.subscribe(self.queue.put)   # Queue 為執行緒安全;此處不操作畫面元件
            llm = LLMClient(base_url=NVIDIA_BASE_URL)
            registry = build_registry(TwseClient(cache_dir=CACHE_DIR))
            analysts, chair = build_committee()
            orch = Orchestrator(analysts=analysts, chair=chair,
                                analyst_task_template=ANALYST_TASK_TEMPLATE)
            orch.run(stock_no=stock, llm=llm, registry=registry,
                     bus=bus, ledger=EvidenceLedger())
        except Exception as exc:  # 任何失敗都顯示在 feed,不靜默崩潰
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
            self._busy = False
            self.btn.config(state="normal", text="開始分析")
            self._set_status("● 閒置 — 已完成")
            return
        if et == "verdict":
            headline = (e.data.get("text") or "").strip().splitlines()
            self.verdict.config(text="結論:"
                                + (" ｜ ".join(headline[:2]) if headline else "(無)"))
            self._set_status("結論完成 ✓")
            return
        if et == "phase":
            if e.data.get("phase"):                     # 委員會階段標題
                self._end_stream()
                self._append(*format_event(e))
                self._set_status("● {} — {}".format(
                    PHASE_ZH.get(e.data["phase"], e.data["phase"]), e.data.get("stock", "")))
            elif e.data.get("status") == "start":       # 某分析師開始發言
                self._set_status("{}:思考中 ...".format(_zh(e.agent)))
            return
        if et == "token":
            self._stream_token(e.agent, e.data.get("text", ""))
            self._set_status("{}:撰寫中 ...".format(_zh(e.agent)))
            return
        if et == "message":
            self._finish_message(e)
            self._set_status("{}:完成".format(_zh(e.agent)))
            return
        if et in ("tool_call", "tool_result", "error"):
            self._end_stream()
            formatted = format_event(e)
            if formatted:
                self._append(*formatted)
            if et == "tool_call":
                self._set_status("{}:呼叫 {} ...".format(_zh(e.agent), e.data.get("tool")))
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
            self._append("\n", e.agent)          # token 已顯示;補上換行收尾
        else:
            formatted = format_event(e)          # 完全沒串流 token;顯示完整文字
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
    root.geometry("780x700")
    CommitteeGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
