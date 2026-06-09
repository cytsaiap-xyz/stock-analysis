"""Self-contained, analyst-grade HTML equity-research report for a committee run.

Consumes a ReportCollector (event buffer) + the EvidenceLedger and produces a
single HTML file that opens/shares with no extra assets. The structure mirrors a
sell-side research note: rating banner, thesis, a data dashboard built from the
recorded tool results, an inline-SVG price chart, per-aspect sections, a risk
box, a data-integrity note, a disclaimer, and a collapsible debate appendix.

All figures come from the EvidenceLedger / committee transcript — the report adds
no new LLM calls and invents no numbers.
"""
import html
import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from agentcore.report import ReportCollector

_AGENT_ZH = {
    "fundamental": "基本面分析師", "technical": "技術面分析師",
    "institutional": "籌碼面分析師", "news": "新聞輿情分析師",
    "risk": "風險經理", "skeptic": "唱反調者",
    "chair": "主席", "verifier": "查核員", "system": "系統",
}
_PHASE_ZH = {"RESEARCH": "研究分析", "CHALLENGE": "質詢", "REBUTTAL": "答辯",
             "VERDICT": "最終結論", "REFLECT": "自我反省", "VERIFY": "自我查核"}

# Which ledger tool feeds which dashboard bucket.
_TOOL_BUCKET = {
    "get_valuation": "valuation", "get_financials": "financials",
    "get_technical_indicators": "technical", "get_institutional_flows": "institutional",
    "get_relative_strength": "relative", "get_risk_metrics": "risk",
    "get_monthly_revenue": "revenue",
}
_RATING_CLASS = {"買進": "buy", "持有": "hold", "賣出": "sell",
                 "BUY": "buy", "HOLD": "hold", "SELL": "sell"}
_DISCLAIMER = (
    "免責聲明:本報告由 AI 投資委員會自動產生,所有數據取自公開資料來源(TWSE 等),"
    "僅供研究與技術展示參考,不構成任何投資建議或要約。投資人應自行判斷並承擔風險。"
)


def _esc(s: Any) -> str:
    return html.escape(str(s if s is not None else ""))


def _num(v: Any, nd: int = 2, suffix: str = "") -> str:
    if v is None or v == "":
        return "—"
    try:
        return ("{:,.%df}" % nd).format(float(v)) + suffix
    except (TypeError, ValueError):
        return _esc(v)


def _lots(shares: Any) -> str:
    """Net shares -> 張 (1 lot = 1000 shares), thousands-grouped, signed."""
    if shares in (None, ""):
        return "—"
    try:
        return "{:+,}".format(round(float(shares) / 1000))
    except (TypeError, ValueError):
        return _esc(shares)


def _metrics(ledger: Any) -> Dict[str, Dict[str, Any]]:
    out: Dict[str, Dict[str, Any]] = {}
    if ledger is None:
        return out
    for entry in ledger.entries():
        bucket = _TOOL_BUCKET.get(entry.tool)
        if bucket and isinstance(entry.result, dict):
            out[bucket] = entry.result   # last call per tool wins
    return out


def _rating(verdict_text: str) -> Dict[str, str]:
    text = verdict_text or ""
    rating = {"label": "—", "cls": "na", "confidence": ""}
    m = re.search(r"(?:建議|Recommendation)\s*[:：]\s*([買進持有賣出]+|BUY|HOLD|SELL)",
                  text, re.IGNORECASE)
    if m:
        label = m.group(1).upper() if m.group(1).isascii() else m.group(1)
        rating["label"] = label
        rating["cls"] = _RATING_CLASS.get(label, "na")
    c = re.search(r"(?:信心|Confidence)\s*[:：]\s*([0-9]{1,3})\s*%", text, re.IGNORECASE)
    if c:
        rating["confidence"] = c.group(1) + "%"
    return rating


def _last_messages(collector: ReportCollector) -> Dict[str, str]:
    """Each agent's final statement (rebuttal overrides research — last wins)."""
    msgs: Dict[str, str] = {}
    for e in collector.events:
        if e.type == "message":
            t = (e.data.get("text") or "").strip()
            if t:
                msgs[e.agent] = t
    return msgs


def _svg_price_chart(series: List[Dict[str, Any]]) -> str:
    closes = [r.get("close") for r in series if r.get("close") is not None]
    if len(closes) < 2:
        return ""
    width, height, pad = 900, 260, 34
    lo, hi = min(closes), max(closes)
    rng = (hi - lo) or 1.0
    n = len(closes)

    def px(i: int) -> float:
        return pad + i * (width - 2 * pad) / (n - 1)

    def py(v: float) -> float:
        return height - pad - (v - lo) / rng * (height - 2 * pad)

    close_pts = " ".join("{:.1f},{:.1f}".format(px(i), py(v)) for i, v in enumerate(closes))
    ma_pts = " ".join(
        "{:.1f},{:.1f}".format(px(i), py(sum(closes[i - 19:i + 1]) / 20))
        for i in range(19, n)
    )
    first_d = _esc(series[0].get("date", ""))
    last_d = _esc(series[-1].get("date", ""))
    p = ['<svg viewBox="0 0 {} {}" class="chart" preserveAspectRatio="xMidYMid meet">'.format(width, height)]
    p.append('<line x1="{}" y1="{}" x2="{}" y2="{}" class="axis"/>'.format(pad, height - pad, width - pad, height - pad))
    if ma_pts:
        p.append('<polyline class="ma" points="{}"/>'.format(ma_pts))
    p.append('<polyline class="price" points="{}"/>'.format(close_pts))
    p.append('<text x="{}" y="{}" class="lbl">{}</text>'.format(pad, pad - 4, _num(hi)))
    p.append('<text x="{}" y="{}" class="lbl">{}</text>'.format(pad, height - pad + 18, _num(lo)))
    p.append('<text x="{}" y="{}" class="lbl end">收盤 {}</text>'.format(width - pad, py(closes[-1]) - 8, _num(closes[-1])))
    p.append('<text x="{}" y="{}" class="dt">{}</text>'.format(pad, height - 8, first_d))
    p.append('<text x="{}" y="{}" class="dt end">{}</text>'.format(width - pad, height - 8, last_d))
    p.append('<text x="{}" y="{}" class="dt">收盤價 · MA20(虛線)</text>'.format(pad + 90, pad - 4))
    p.append("</svg>")
    return "".join(p)


def _card(title: str, rows: List) -> str:
    body = "".join(
        '<div class="row"><span class="k">{}</span><span class="v">{}</span></div>'.format(
            _esc(k), v) for k, v in rows)
    return '<div class="card"><h3>{}</h3>{}</div>'.format(_esc(title), body)


def _dashboard(m: Dict[str, Dict[str, Any]]) -> str:
    cards: List[str] = []
    if "valuation" in m:
        v = m["valuation"]
        cards.append(_card("估值", [
            ("本益比 (PE)", _num(v.get("pe"))),
            ("股價淨值比 (PB)", _num(v.get("pb"))),
            ("殖利率", _num(v.get("dividend_yield"), 2, "%")),
        ]))
    if "financials" in m and m["financials"].get("available", True):
        f = m["financials"]
        cards.append(_card("獲利能力 · " + _esc(f.get("period", "")), [
            ("毛利率", _num(f.get("gross_margin_pct"), 2, "%")),
            ("營業利益率", _num(f.get("operating_margin_pct"), 2, "%")),
            ("ROE", _num(f.get("roe_pct"), 2, "%")),
            ("EPS", _num(f.get("eps"))),
        ]))
    if "technical" in m:
        t = m["technical"]
        cards.append(_card("技術指標", [
            ("收盤", _num(t.get("last_close"))),
            ("MA20", _num(t.get("ma20"))),
            ("RSI14", _num(t.get("rsi14"))),
            ("KD", "{} / {}".format(_num(t.get("kd_k")), _num(t.get("kd_d")))),
            ("MACD", _num(t.get("macd"))),
            ("期間漲跌", _num(t.get("pct_change_period"), 2, "%")),
        ]))
    if "relative" in m:
        r = m["relative"]
        cards.append(_card("相對大盤", [
            ("個股報酬", _num(r.get("stock_return_pct"), 2, "%")),
            ("大盤報酬", _num(r.get("index_return_pct"), 2, "%")),
            ("超額報酬", _num(r.get("excess_return_pct"), 2, "%")),
            ("Beta", _num(r.get("beta"))),
        ]))
    if "institutional" in m:
        i = m["institutional"]
        cards.append(_card("三大法人(張)", [
            ("外資", _lots(i.get("foreign_net"))),
            ("投信", _lots(i.get("trust_net"))),
            ("自營商", _lots(i.get("dealer_net"))),
            ("合計", _lots(i.get("total_net"))),
        ]))
    if "risk" in m:
        rk = m["risk"]
        cards.append(_card("風險", [
            ("年化波動率", _num(rk.get("volatility_annual_pct"), 2, "%")),
            ("最大回撤", _num(rk.get("max_drawdown_pct"), 2, "%")),
        ]))
    if "revenue" in m and m["revenue"].get("available", True):
        rv = m["revenue"]
        cards.append(_card("月營收 · " + _esc(rv.get("period", "")), [
            ("當月營收", _num(rv.get("revenue"), 0)),
            ("年增率 (YoY)", _num(rv.get("yoy_pct"), 2, "%")),
            ("月增率 (MoM)", _num(rv.get("mom_pct"), 2, "%")),
        ]))
    if not cards:
        return ""
    return '<section><h2>關鍵數據儀表板</h2><div class="grid">' + "".join(cards) + "</div></section>"


def _aspect_sections(msgs: Dict[str, str]) -> str:
    order = [("fundamental", "基本面分析"), ("technical", "技術面分析"),
             ("institutional", "籌碼面分析"), ("news", "新聞輿情分析")]
    blocks = []
    for agent, title in order:
        txt = msgs.get(agent)
        if txt:
            blocks.append('<div class="aspect"><h3>{}</h3><p>{}</p></div>'.format(
                _esc(title), _esc(txt)))
    if not blocks:
        return ""
    return '<section><h2>分面分析</h2>' + "".join(blocks) + "</section>"


def _risk_box(msgs: Dict[str, str]) -> str:
    items = []
    for agent in ("risk", "skeptic"):
        txt = msgs.get(agent)
        if txt:
            items.append('<li><b>{}:</b> {}</li>'.format(
                _esc(_AGENT_ZH.get(agent, agent)), _esc(txt)))
    if not items:
        return ""
    return ('<section><h2>風險與空方觀點</h2><ul class="risk-list">'
            + "".join(items) + "</ul></section>")


def _transcript(collector: ReportCollector, ledger: Any) -> str:
    by_phase: Dict[str, List] = {}
    cur = "RESEARCH"
    by_phase[cur] = []
    for e in collector.events:
        if e.type == "phase" and e.data.get("phase"):
            cur = e.data["phase"]
            by_phase.setdefault(cur, [])
        elif e.type in ("message", "tool_call", "tool_result", "error", "verdict"):
            by_phase.setdefault(cur, []).append((e.agent, e.type, e.data))

    p = ['<details class="appendix"><summary>附錄:完整辯論逐字稿與工具資料</summary>']
    for ph in ("RESEARCH", "CHALLENGE", "REBUTTAL", "VERDICT", "REFLECT", "VERIFY"):
        items = by_phase.get(ph) or []
        if not items:
            continue
        p.append('<h3>' + _esc(_PHASE_ZH.get(ph, ph)) + '</h3>')
        for agent, etype, data in items:
            zh = _AGENT_ZH.get(agent, agent)
            if etype in ("message", "verdict"):
                txt = (data.get("text") or "").strip()
                if txt:
                    p.append('<div class="msg"><span class="who">[{}]</span> {}</div>'.format(
                        _esc(zh), _esc(txt)))
            elif etype == "tool_call":
                p.append('<div class="tool">[工具] {}({})</div>'.format(
                    _esc(data.get("tool")), _esc(data.get("args", {}))))
            elif etype == "tool_result":
                p.append('<div class="tool">[完成] {} 已回傳</div>'.format(_esc(data.get("tool"))))
            elif etype == "error":
                p.append('<div class="err">[警告] {} 錯誤: {}</div>'.format(
                    _esc(data.get("tool")), _esc(data.get("error"))))

    if ledger is not None and ledger.entries():
        p.append('<h3>工具呼叫資料(證據)</h3>')
        p.append('<table><tr><th>工具</th><th>參數</th><th>回傳</th></tr>')
        for entry in ledger.entries():
            p.append('<tr><td>{}</td><td><pre>{}</pre></td><td><pre>{}</pre></td></tr>'.format(
                _esc(entry.tool),
                _esc(json.dumps(entry.args, ensure_ascii=False)),
                _esc(json.dumps(entry.result, ensure_ascii=False, default=str))))
        p.append('</table>')
    p.append('</details>')
    return "".join(p)


def build_html(stock_no: str, collector: ReportCollector, ledger: Any = None,
               generated_at: Optional[str] = None, twse: Any = None,
               months: int = 3) -> str:
    generated_at = generated_at or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    m = _metrics(ledger)
    rating = _rating(collector.verdict_text or "")
    msgs = _last_messages(collector)
    name = (m.get("valuation") or {}).get("name") or ""
    last_close = (m.get("technical") or {}).get("last_close")

    p = ['<!DOCTYPE html>', '<html lang="zh-TW"><head><meta charset="utf-8">',
         '<meta name="viewport" content="width=device-width, initial-scale=1">']
    p.append('<title>個股研究報告 — ' + _esc(stock_no) + ' ' + _esc(name) + '</title>')
    p.append('<style>' + _css() + '</style></head><body><main>')

    p.append('<header><div class="eyebrow">AI 投資委員會 · 個股研究報告</div>'
             '<h1>{}<span class="code"> {}</span></h1>'
             '<div class="meta">產出時間 {}</div></header>'.format(
                 _esc(name or "台股個股分析"), _esc(stock_no), _esc(generated_at)))
    p.append('<div class="rating rating-{}">'.format(_esc(rating["cls"]))
             + '<div class="rcol"><span class="rlabel">投資評等</span>'
               '<span class="rval">{}</span></div>'.format(_esc(rating["label"]))
             + '<div class="rcol"><span class="rlabel">信心度</span>'
               '<span class="rnum">{}</span></div>'.format(_esc(rating["confidence"] or "—"))
             + '<div class="rcol"><span class="rlabel">參考收盤</span>'
               '<span class="rnum">{}</span></div>'.format(_num(last_close))
             + '</div>')

    if collector.verdict_text:
        p.append('<section class="thesis"><h2>投資論點摘要</h2><pre>'
                 + _esc(collector.verdict_text) + '</pre></section>')

    p.append(_dashboard(m))

    chart = _svg_price_chart(twse.price_history(stock_no, months=months)) if twse is not None else ""
    if chart:
        p.append('<section><h2>近期股價走勢</h2>' + chart + '</section>')

    p.append(_aspect_sections(msgs))
    p.append(_risk_box(msgs))

    if collector.grounding:
        g = collector.grounding
        ok = g.get("grounded", True)
        line = '<section class="integrity {}"><h2>資料完整性查核</h2><p>數據支持 {}/{}'.format(
            "ok" if ok else "warn", _esc(g.get("supported", 0)), _esc(g.get("checked", 0)))
        if not ok:
            line += ' · 未獲數據支持(已標記): ' + _esc(g.get("unsupported"))
        p.append(line + '</p></section>')

    p.append('<footer class="disclaimer">' + _esc(_DISCLAIMER) + '</footer>')
    p.append(_transcript(collector, ledger))
    p.append('</main></body></html>')
    return "\n".join(part for part in p if part)


def save_report(stock_no: str, collector: ReportCollector, ledger: Any = None,
                reports_dir: str = "reports", now: Optional[datetime] = None,
                twse: Any = None) -> Path:
    os.makedirs(reports_dir, exist_ok=True)
    stamp = (now or datetime.now())
    ts = stamp.strftime("%Y%m%d-%H%M%S")
    path = Path(reports_dir) / "{}_{}.html".format(stock_no, ts)
    path.write_text(build_html(stock_no, collector, ledger=ledger, twse=twse,
                               generated_at=stamp.strftime("%Y-%m-%d %H:%M:%S")),
                    encoding="utf-8")
    return path


def _css() -> str:
    return (
        ':root{--ink:#1a1f29;--muted:#6b7280;--line:#e6e8eb;--bg:#fbfbfa;'
        '--accent:#1f6feb;--buy:#1a7f37;--sell:#cf222e;--hold:#9a6700;}'
        '*{box-sizing:border-box}'
        'body{font-family:"Microsoft JhengHei","Segoe UI",sans-serif;color:var(--ink);'
        'background:var(--bg);margin:0;line-height:1.65;}'
        'main{max-width:1000px;margin:0 auto;padding:32px 22px 56px;}'
        'header .eyebrow{font-size:.8em;letter-spacing:.18em;color:var(--accent);'
        'text-transform:uppercase;font-weight:600;}'
        'h1{font-size:2em;margin:.18em 0 .1em;font-weight:800;}'
        'h1 .code{color:var(--muted);font-weight:500;font-size:.6em;}'
        '.meta{color:var(--muted);font-size:.86em;}'
        'h2{font-size:1.18em;margin:30px 0 12px;padding-bottom:6px;'
        'border-bottom:2px solid var(--ink);display:inline-block;}'
        'section{margin-top:6px;}'
        '.rating{display:flex;gap:30px;align-items:stretch;margin:20px 0 6px;padding:16px 22px;'
        'border-radius:12px;border:1px solid var(--line);background:#fff;border-left:8px solid var(--muted);}'
        '.rating .rcol{display:flex;flex-direction:column;gap:4px;}'
        '.rating .rlabel{font-size:.74em;color:var(--muted);letter-spacing:.08em;}'
        '.rating .rval{font-size:1.9em;font-weight:800;line-height:1;}'
        '.rating .rnum{font-size:1.5em;font-weight:700;font-family:Consolas,monospace;}'
        '.rating-buy{border-left-color:var(--buy);} .rating-buy .rval{color:var(--buy);}'
        '.rating-sell{border-left-color:var(--sell);} .rating-sell .rval{color:var(--sell);}'
        '.rating-hold{border-left-color:var(--hold);} .rating-hold .rval{color:var(--hold);}'
        '.thesis pre{white-space:pre-wrap;font-family:inherit;background:#fff;border:1px solid var(--line);'
        'border-radius:10px;padding:16px 18px;margin:0;font-size:1.02em;}'
        '.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(228px,1fr));gap:14px;}'
        '.card{background:#fff;border:1px solid var(--line);border-radius:10px;padding:14px 16px;}'
        '.card h3{margin:0 0 10px;font-size:.92em;color:var(--accent);border-bottom:1px solid var(--line);'
        'padding-bottom:7px;}'
        '.card .row{display:flex;justify-content:space-between;padding:3px 0;font-size:.95em;}'
        '.card .k{color:var(--muted);} .card .v{font-weight:600;font-family:Consolas,monospace;}'
        '.chart{width:100%;height:auto;background:#fff;border:1px solid var(--line);border-radius:10px;}'
        '.chart .axis{stroke:var(--line);stroke-width:1;}'
        '.chart .price{fill:none;stroke:var(--accent);stroke-width:2;}'
        '.chart .ma{fill:none;stroke:var(--hold);stroke-width:1.4;stroke-dasharray:5 4;opacity:.8;}'
        '.chart .lbl{fill:var(--ink);font:600 12px Consolas,monospace;}'
        '.chart .dt{fill:var(--muted);font:11px Consolas,monospace;}'
        '.chart .end{text-anchor:end;}'
        '.aspect{margin:12px 0;} .aspect h3{margin:0 0 4px;font-size:1em;}'
        '.aspect p{margin:0;color:#33373f;}'
        '.risk-list{margin:6px 0;padding-left:20px;} .risk-list li{margin:6px 0;}'
        '.integrity p{display:inline-block;padding:8px 14px;border-radius:8px;font-size:.92em;}'
        '.integrity.ok p{background:#e6f7ec;color:var(--buy);} '
        '.integrity.warn p{background:#fff8c5;color:var(--hold);}'
        '.disclaimer{margin-top:34px;padding-top:14px;border-top:1px solid var(--line);'
        'color:var(--muted);font-size:.82em;}'
        '.appendix{margin-top:22px;border:1px solid var(--line);border-radius:10px;'
        'background:#fff;padding:6px 16px;}'
        '.appendix summary{cursor:pointer;font-weight:600;padding:8px 0;color:var(--accent);}'
        '.appendix h3{font-size:.98em;margin:16px 0 6px;color:#444;}'
        '.appendix .msg{margin:6px 0;} .appendix .who{font-weight:bold;margin-right:6px;}'
        '.appendix .tool{color:#6e7681;font-family:Consolas,monospace;font-size:.86em;margin-left:12px;}'
        '.appendix .err{color:var(--sell);font-family:Consolas,monospace;font-size:.86em;margin-left:12px;}'
        '.appendix table{border-collapse:collapse;width:100%;margin-top:8px;font-size:.84em;}'
        '.appendix th,.appendix td{border:1px solid var(--line);padding:6px 8px;vertical-align:top;text-align:left;}'
        '.appendix th{background:#f6f8fa;} .appendix pre{margin:0;white-space:pre-wrap;word-break:break-word;}'
        '@media print{body{background:#fff;} .appendix{display:none;}}'
    )
