"""Self-contained HTML analyst report for a committee run.

Consumes a ReportCollector (event buffer) + the EvidenceLedger and produces a
single HTML file that can be opened/shared without any extra assets.
"""
import html
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from agentcore.report import ReportCollector

_AGENT_ZH = {
    "fundamental": "基本面分析師", "technical": "技術面分析師",
    "institutional": "籌碼面分析師", "news": "新聞輿情分析師",
    "risk": "風險經理", "skeptic": "唱反調者",
    "chair": "主席", "verifier": "查核員", "system": "系統",
}
_PHASE_ZH = {"RESEARCH": "研究分析", "CHALLENGE": "質詢",
             "REBUTTAL": "答辯", "VERDICT": "最終結論", "VERIFY": "自我查核"}


def _esc(s: Any) -> str:
    return html.escape(str(s if s is not None else ""))


def build_html(stock_no: str, collector: ReportCollector, ledger: Any = None,
               generated_at: Optional[str] = None) -> str:
    generated_at = generated_at or datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Bucket non-meta events by the phase they occurred in.
    by_phase = {}
    cur_phase = "RESEARCH"
    by_phase[cur_phase] = []
    for e in collector.events:
        if e.type == "phase" and e.data.get("phase"):
            cur_phase = e.data["phase"]
            by_phase.setdefault(cur_phase, [])
        elif e.type in ("message", "tool_call", "tool_result", "error"):
            by_phase.setdefault(cur_phase, []).append((e.agent, e.type, e.data))

    parts = ['<!DOCTYPE html>', '<html lang="zh-TW"><head><meta charset="utf-8">']
    parts.append('<title>台股投資委員會分析報告 — ' + _esc(stock_no) + '</title>')
    parts.append('<style>' + _css() + '</style></head><body>')
    parts.append('<h1>台股投資委員會分析報告</h1>')
    parts.append('<div class="meta">股票代號: <b>' + _esc(stock_no)
                 + '</b> · 產出時間: ' + _esc(generated_at) + '</div>')

    if collector.verdict_text:
        parts.append('<div class="verdict-card"><h2>最終結論</h2><pre>'
                     + _esc(collector.verdict_text) + '</pre></div>')

    if collector.grounding:
        g = collector.grounding
        ok = g.get("grounded", True)
        parts.append('<div class="verify ' + ('ok' if ok else 'warn') + '">'
                     '<b>自我查核:</b> 數據支持 '
                     + _esc(g.get("supported", 0)) + '/' + _esc(g.get("checked", 0)))
        if not ok:
            parts.append(' · 未支持: ' + _esc(g.get("unsupported")))
        parts.append('</div>')

    for ph in ("RESEARCH", "CHALLENGE", "REBUTTAL", "VERDICT", "VERIFY"):
        items = by_phase.get(ph) or []
        if not items:
            continue
        parts.append('<h2>' + _esc(_PHASE_ZH.get(ph, ph)) + '</h2>')
        for agent, etype, data in items:
            zh = _AGENT_ZH.get(agent, agent)
            if etype == "message":
                txt = (data.get("text") or "").strip()
                if not txt:
                    continue
                parts.append('<div class="msg agent-' + _esc(agent) + '">'
                             '<span class="who">[' + _esc(zh) + ']</span> '
                             + _esc(txt) + '</div>')
            elif etype == "tool_call":
                parts.append('<div class="tool">[工具] '
                             + _esc(data.get("tool")) + '('
                             + _esc(data.get("args", {})) + ')</div>')
            elif etype == "tool_result":
                parts.append('<div class="tool">[完成] '
                             + _esc(data.get("tool")) + ' 已回傳</div>')
            elif etype == "error":
                parts.append('<div class="err">[警告] '
                             + _esc(data.get("tool")) + ' 錯誤: '
                             + _esc(data.get("error")) + '</div>')

    if ledger is not None and ledger.entries():
        parts.append('<h2>工具呼叫資料(證據)</h2>')
        parts.append('<table><tr><th>工具</th><th>參數</th><th>回傳</th></tr>')
        for entry in ledger.entries():
            parts.append('<tr><td>' + _esc(entry.tool) + '</td>'
                         '<td><pre>'
                         + _esc(json.dumps(entry.args, ensure_ascii=False))
                         + '</pre></td><td><pre>'
                         + _esc(json.dumps(entry.result, ensure_ascii=False, default=str))
                         + '</pre></td></tr>')
        parts.append('</table>')

    parts.append('</body></html>')
    return "\n".join(parts)


def save_report(stock_no: str, collector: ReportCollector, ledger: Any = None,
                reports_dir: str = "reports",
                now: Optional[datetime] = None) -> Path:
    os.makedirs(reports_dir, exist_ok=True)
    stamp = (now or datetime.now())
    ts = stamp.strftime("%Y%m%d-%H%M%S")
    path = Path(reports_dir) / "{}_{}.html".format(stock_no, ts)
    path.write_text(build_html(stock_no, collector, ledger=ledger,
                               generated_at=stamp.strftime("%Y-%m-%d %H:%M:%S")),
                    encoding="utf-8")
    return path


def _css() -> str:
    return (
        'body{font-family:"Microsoft JhengHei","Segoe UI",sans-serif;'
        'max-width:980px;margin:24px auto;padding:0 16px;color:#222;}'
        'h1{font-size:1.6em;margin-bottom:4px;}'
        'h2{margin-top:28px;border-bottom:1px solid #e4e4e4;padding-bottom:4px;color:#444;}'
        '.meta{color:#666;font-size:0.9em;margin-bottom:20px;}'
        '.verdict-card{background:#f3eefb;border-left:4px solid #8957e5;'
        'padding:14px 16px;border-radius:6px;}'
        '.verdict-card h2{margin:0 0 8px;border:none;font-size:1.1em;color:#8957e5;}'
        '.verdict-card pre{white-space:pre-wrap;margin:0;font-family:inherit;}'
        '.verify{margin:14px 0;padding:8px 12px;border-radius:6px;}'
        '.verify.ok{background:#e6f7ec;color:#1a7f37;}'
        '.verify.warn{background:#fff8c5;color:#7d4e00;}'
        '.msg{margin:8px 0;line-height:1.6;}'
        '.msg .who{font-weight:bold;margin-right:6px;}'
        '.agent-fundamental .who{color:#1f6feb;}'
        '.agent-technical .who{color:#2ea043;}'
        '.agent-institutional .who{color:#d29922;}'
        '.agent-news .who{color:#db61a2;}'
        '.agent-risk .who{color:#cf222e;}'
        '.agent-skeptic .who{color:#bf3989;}'
        '.agent-chair .who{color:#8957e5;}'
        '.agent-verifier .who{color:#0a7ea4;}'
        '.tool{color:#6e7681;font-family:Consolas,monospace;font-size:0.9em;margin-left:14px;}'
        '.err{color:#cf222e;font-family:Consolas,monospace;font-size:0.9em;margin-left:14px;}'
        'table{border-collapse:collapse;width:100%;margin-top:10px;font-size:0.9em;}'
        'th,td{border:1px solid #e4e4e4;padding:6px 8px;vertical-align:top;}'
        'th{background:#f6f8fa;text-align:left;}'
        'pre{margin:0;white-space:pre-wrap;word-break:break-word;}'
    )
