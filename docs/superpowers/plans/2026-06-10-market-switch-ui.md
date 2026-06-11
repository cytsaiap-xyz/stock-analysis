# TW/US Market Switch (Web + GUI) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a TW/US toggle to the web app and desktop GUI that sets both the UI language and the analyzed market (the toggle is the source of truth; ticker format is ignored).

**Architecture:** Every market-specific UI string lives in the market profile. `ReportLabels.agent_names`/`phase_names` already localize the roster/phase labels; a new `MarketProfile.ui` dict (built by `tw_ui()`/`us_ui()`) adds the remaining live-view chrome (title, status verbs, buttons). Front-ends call `get_profile(<chosen market>)` directly. `agentcore/` and the report builder are untouched.

**Tech Stack:** Python 3.9 (run via `.venv/bin/python`), FastAPI + vanilla JS + Tkinter, pytest with hand-rolled fakes.

**Spec:** `docs/superpowers/specs/2026-06-10-market-switch-ui-design.md`

**Conventions (follow exactly):**
- Test with `.venv/bin/python -m pytest` (the default `python` is a broken anaconda 3.7).
- Web routes are tested as plain functions (the repo avoids `starlette.TestClient`).
- `app.js` / `index.html` have NO automated test harness — verify by importing the server, a structural grep that hardcoded Chinese status strings are gone, and a manual note.
- Reproduce existing Chinese strings VERBATIM for the TW set (they are the source of truth).
- Commit after every green/verified step.

---

## File Structure

**Modify:**
- `committee/markets/base.py` — add `ui: Dict[str, str]` to `MarketProfile`
- `committee/markets/tw.py` — add `tw_ui()`
- `committee/markets/us.py` — add `us_ui()`
- `committee/markets/__init__.py` — `build_tw_profile`/`build_us_profile` set `ui=`
- `web/server.py` — `committee_info(market)`, `/ws/run/{market}/{stock_no}`, drop `_AGENT_ZH`/`_PHASE_ZH`
- `web/static/index.html` — toggle + element ids (full rewrite, 35 lines)
- `web/static/app.js` — market-aware (full rewrite)
- `gui.py` — TW/US control, market-aware `format_event`/labels/status
- `tests/test_web.py` — market-aware committee_info + run wiring
- `tests/test_gui_format.py` — `format_event` with market labels

---

## Phase A — Backend: profile `ui` + market-aware routes

### Task 1: Add `MarketProfile.ui` + `tw_ui()`/`us_ui()`

**Files:**
- Modify: `committee/markets/base.py`, `committee/markets/tw.py`, `committee/markets/us.py`, `committee/markets/__init__.py`
- Test: `tests/test_markets.py`

- [ ] **Step 1: Write failing tests** — append to `tests/test_markets.py`:

```python
def test_profiles_carry_localized_ui_text():
    from committee.markets import get_profile
    tw = get_profile("tw").ui
    us = get_profile("us").ui
    # same key set in both markets
    assert set(tw) == set(us)
    # a few representative values
    assert tw["title"] == "台股投資委員會"
    assert us["title"] == "US Equity Investment Committee"
    assert tw["example_ticker"] == "2330" and us["example_ticker"] == "AAPL"
    assert tw["run_button"] == "開始分析" and us["run_button"] == "Analyze"
    assert tw["thinking"] == "思考中" and us["thinking"] == "thinking"
    assert tw["lean_words"] == ["看多", "看空", "中性"]
    assert us["lean_words"] == ["Bullish", "Bearish", "Neutral"]
```

- [ ] **Step 2: Run, verify fail** — `.venv/bin/python -m pytest tests/test_markets.py -k ui -v` → FAIL (`MarketProfile` has no `ui`).

- [ ] **Step 3: Add the `ui` field** in `committee/markets/base.py` — add as the LAST field of `MarketProfile`:

```python
@dataclass
class MarketProfile:
    market: str
    lang: str
    client: Any
    committee: Any
    templates: Templates
    labels: ReportLabels
    descriptions: ToolDescriptions
    ui: Dict[str, str]
```

- [ ] **Step 4: Add `tw_ui()`** to `committee/markets/tw.py` (append). Values reproduce the current web/GUI Chinese strings verbatim:

```python
def tw_ui() -> dict:
    return {
        "title": "台股投資委員會",
        "subtitle": "Agentic AI (7 位委員 + 自我查核)",
        "ticker_label": "股票代號:",
        "example_ticker": "2330",
        "run_button": "開始分析",
        "running_button": "分析中...",
        "idle": "● 閒置",
        "done_idle": "● 閒置 — 已完成",
        "pipeline_heading": "執行流程 Pipeline",
        "debate_heading": "即時討論 Live debate",
        "verdict_placeholder": "結論:(請先執行分析)",
        "verdict_prefix": "結論:",
        "verdict_running": "結論:分析 {stock} 中...",
        "verdict_done": "結論完成 ✓",
        "start_status": "開始分析 {stock} ...",
        "pending_badge": "⏳ 等待",
        "running_badge": "▶ 進行中",
        "done_badge": "✓ 完成",
        "thinking": "思考中",
        "writing": "撰寫中",
        "calling": "呼叫",
        "received": "已取得",
        "model_label": "模型: ",
        "tools_label": "工具: ",
        "tool_word": "工具",
        "done_word": "完成",
        "warn_word": "警告",
        "verify_prefix": "自我查核:數據支持",
        "unsupported_word": "未支持",
        "report_saved": "📄 報告已存",
        "open_report": "→ 開啟報告",
        "ws_error": "⚠ WebSocket 錯誤",
        "load_failed": "載入失敗: ",
        "recommend_word": "建議",
        "lean_words": ["看多", "看空", "中性"],
    }
```

- [ ] **Step 5: Add `us_ui()`** to `committee/markets/us.py` (append) — English equivalents, same keys:

```python
def us_ui() -> dict:
    return {
        "title": "US Equity Investment Committee",
        "subtitle": "Agentic AI (7 members + self-check)",
        "ticker_label": "Ticker:",
        "example_ticker": "AAPL",
        "run_button": "Analyze",
        "running_button": "Analyzing...",
        "idle": "● Idle",
        "done_idle": "● Idle — finished",
        "pipeline_heading": "Pipeline",
        "debate_heading": "Live Debate",
        "verdict_placeholder": "Verdict: (run an analysis first)",
        "verdict_prefix": "Verdict: ",
        "verdict_running": "Verdict: analyzing {stock} ...",
        "verdict_done": "Verdict ready ✓",
        "start_status": "Analyzing {stock} ...",
        "pending_badge": "⏳ waiting",
        "running_badge": "▶ running",
        "done_badge": "✓ done",
        "thinking": "thinking",
        "writing": "writing",
        "calling": "calling",
        "received": "received",
        "model_label": "Model: ",
        "tools_label": "Tools: ",
        "tool_word": "tool",
        "done_word": "done",
        "warn_word": "warning",
        "verify_prefix": "Self-check: figures supported",
        "unsupported_word": "unsupported",
        "report_saved": "📄 Report saved",
        "open_report": "→ Open report",
        "ws_error": "⚠ WebSocket error",
        "load_failed": "Load failed: ",
        "recommend_word": "Recommendation",
        "lean_words": ["Bullish", "Bearish", "Neutral"],
    }
```

- [ ] **Step 6: Wire `ui` into the builders** in `committee/markets/__init__.py` — add the `ui=` argument to both `MarketProfile(...)` calls, importing the builder:

```python
# in build_tw_profile, extend the tw.py import and the return:
    from committee.markets.tw import tw_prompts, tw_templates, tw_labels, tw_tool_descriptions, tw_ui
    return MarketProfile(market="tw", lang="zh-TW", client=TwseClient(cache_dir=CACHE_DIR),
                         committee=build_committee(tw_prompts()), templates=tw_templates(),
                         labels=tw_labels(), descriptions=tw_tool_descriptions(), ui=tw_ui())

# in build_us_profile:
    from committee.markets.us import us_prompts, us_templates, us_labels, us_tool_descriptions, us_ui
    return MarketProfile(market="us", lang="en", client=UsClient(cache_dir=CACHE_DIR),
                         committee=build_committee(us_prompts()), templates=us_templates(),
                         labels=us_labels(), descriptions=us_tool_descriptions(), ui=us_ui())
```

- [ ] **Step 7: Run, verify pass** — `.venv/bin/python -m pytest tests/test_markets.py -v` → PASS. Then `.venv/bin/python -m pytest -q` → full suite PASS (existing `MarketProfile(...)` constructions: none in tests construct it positionally — confirm by running).

- [ ] **Step 8: Commit**

```bash
git add committee/markets/base.py committee/markets/tw.py committee/markets/us.py committee/markets/__init__.py tests/test_markets.py
git commit -m "feat: per-market UI text on MarketProfile.ui"
```

---

### Task 2: `committee_info(market)` returns market-localized roster + ui

**Files:**
- Modify: `web/server.py`
- Test: `tests/test_web.py`

- [ ] **Step 1: Write failing tests** — append to `tests/test_web.py` (it imports `committee_info` already; mirror its style):

```python
def test_committee_info_tw_is_chinese():
    from web.server import committee_info
    info = committee_info("tw")
    assert info["ui"]["title"] == "台股投資委員會"
    assert info["phase_names"]["RESEARCH"] == "研究分析"
    fundamental = next(a for a in info["research"] if a["name"] == "fundamental")
    assert fundamental["label"] == "基本面分析師"


def test_committee_info_us_is_english():
    from web.server import committee_info
    info = committee_info("us")
    assert info["ui"]["title"] == "US Equity Investment Committee"
    assert info["phase_names"]["RESEARCH"] == "Research"
    fundamental = next(a for a in info["research"] if a["name"] == "fundamental")
    assert fundamental["label"] == "Fundamentals Analyst"


def test_committee_info_unknown_market_falls_back_to_tw():
    from web.server import committee_info
    assert committee_info("jp")["ui"]["title"] == "台股投資委員會"
```

- [ ] **Step 2: Run, verify fail** — `.venv/bin/python -m pytest tests/test_web.py -k committee_info -v` → FAIL (`committee_info` takes no arg / no `ui`).

- [ ] **Step 3: Rewrite `committee_info`** in `web/server.py`. Delete the module-level `_AGENT_ZH` and `_PHASE_ZH` dicts (lines with those maps) and replace the route:

```python
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
```

Add `from committee.markets import get_profile` if not already imported (it is — line 31). Remove the now-unused `from committee.agents import build_committee` import IF nothing else in the file uses it (check: after this change `build_committee` is unused in web/server.py — remove it). Also change the FastAPI app title to a neutral value: `app = FastAPI(title="Agentic Investment Committee")`.

- [ ] **Step 4: Run, verify pass** — `.venv/bin/python -m pytest tests/test_web.py -v` → PASS.

- [ ] **Step 5: Commit**

```bash
git add web/server.py tests/test_web.py
git commit -m "feat: committee_info localizes roster + ui by market"
```

---

### Task 3: WebSocket route forces the market

**Files:**
- Modify: `web/server.py`
- Test: `tests/test_web.py`

- [ ] **Step 1: Write a failing test** — `_run_committee` should build the client for the forced market. Append to `tests/test_web.py`:

```python
def test_run_committee_uses_forced_market(monkeypatch, tmp_path):
    """_run_committee must route by the explicit market arg, not the ticker."""
    import web.server as ws
    captured = {}

    class _StubOrch:
        def __init__(self, **kw):
            pass

        def run(self, **kw):
            captured["ran"] = True

    # Force US market with a TW-looking ticker; the US client must be chosen.
    monkeypatch.setattr(ws, "Orchestrator", _StubOrch)
    monkeypatch.setattr(ws, "LLMClient", lambda **kw: object())
    monkeypatch.setattr(ws, "save_report", lambda *a, **k: type("P", (), {"name": "x.html"})())
    import queue
    from agentcore.report import ReportCollector
    from agentcore.evidence import EvidenceLedger
    q = queue.Queue()
    ws._run_committee("2330", "us", q, ReportCollector(), EvidenceLedger())
    # the client built for the run is a UsClient because market was forced to "us"
    assert captured.get("ran") is True
    assert captured.get("client_type") == "UsClient"
```

To make the test observe the client type, the implementation (Step 3) records it. Adjust: instead of `_StubOrch` ignoring kwargs, capture via a registry hook. Simpler — assert on the registry's tool by stubbing `build_registry`:

```python
    monkeypatch.setattr(ws, "build_registry",
                        lambda client, desc: captured.update(client_type=type(client).__name__) or "REG")
```

Place that `monkeypatch.setattr` line with the others (before calling `_run_committee`).

- [ ] **Step 2: Run, verify fail** — `.venv/bin/python -m pytest tests/test_web.py -k forced_market -v` → FAIL (`_run_committee` takes no `market` arg).

- [ ] **Step 3: Add `market` to `_run_committee` and the WS route** in `web/server.py`:

```python
def _run_committee(stock_no: str, market: str, q: "queue.Queue",
                   collector: ReportCollector, ledger: EvidenceLedger) -> None:
    try:
        bus = EventBus()
        bus.subscribe(q.put)
        bus.subscribe(collector)
        llm = LLMClient(base_url=BASE_URL, api_key_env=API_KEY_ENV)
        profile = get_profile(_safe_market(market))
        registry = build_registry(profile.client, profile.descriptions)
        ...  # rest unchanged
```

Remove the now-unused `detect_market` import if nothing else uses it (the WS route below passes `market` explicitly, so `detect_market` becomes unused in web/server.py — remove it from the import). Update the route:

```python
@app.websocket("/ws/run/{market}/{stock_no}")
async def ws_run(ws: WebSocket, market: str, stock_no: str) -> None:
    await ws.accept()
    q: "queue.Queue" = queue.Queue()
    collector = ReportCollector()
    ledger = EvidenceLedger()
    threading.Thread(target=_run_committee,
                     args=(stock_no, market, q, collector, ledger),
                     daemon=True).start()
    ...  # rest of the existing drain loop unchanged
```

(Keep the existing drain/await loop body exactly; only the decorator signature and the thread `args` change.)

- [ ] **Step 4: Run, verify pass** — `.venv/bin/python -m pytest tests/test_web.py -v` → PASS. Full suite: `.venv/bin/python -m pytest -q` → PASS.

- [ ] **Step 5: Commit**

```bash
git add web/server.py tests/test_web.py
git commit -m "feat: web run route forces the selected market"
```

---

## Phase B — Web frontend (no JS unit tests; verify by server import + grep + manual)

### Task 4: Rewrite `index.html` with the toggle + element ids

**Files:**
- Modify: `web/static/index.html`

- [ ] **Step 1: Replace the file** with this (adds the TW/US toggle and ids; strings will be set by JS, so the static HTML uses neutral/placeholder text):

```html
<!DOCTYPE html>
<html lang="zh-TW" id="html-root">
<head>
<meta charset="utf-8">
<title id="page-title">Agentic Investment Committee</title>
<link rel="stylesheet" href="/static/style.css">
</head>
<body>
<header>
  <h1 id="title">Agentic Investment Committee <span class="sub" id="subtitle"></span></h1>
  <div class="controls">
    <div class="market-switch">
      <label><input type="radio" name="market" value="tw" checked> TW</label>
      <label><input type="radio" name="market" value="us"> US</label>
    </div>
    <label id="ticker-label">股票代號:</label>
    <input id="ticker" type="text" value="2330" maxlength="6">
    <button id="run">開始分析</button>
  </div>
</header>

<section id="verdict"></section>
<section id="verify" class="hidden"></section>
<section id="status"></section>

<main>
  <aside id="pipeline">
    <h2 id="pipeline-heading">Pipeline</h2>
    <div id="cards">…</div>
  </aside>
  <article id="feed">
    <h2 id="debate-heading">Live debate</h2>
    <div id="messages"></div>
  </article>
</main>
<script src="/static/app.js"></script>
</body>
</html>
```

- [ ] **Step 2: Add minimal styling** for the switch — append to `web/static/style.css`:

```css
.market-switch { display: inline-flex; gap: 8px; margin-right: 12px; }
.market-switch label { cursor: pointer; font-weight: 600; }
```

- [ ] **Step 3: Verify it serves** — `.venv/bin/python -c "from pathlib import Path; h=Path('web/static/index.html').read_text(encoding='utf-8'); assert 'name=\"market\"' in h and 'id=\"title\"' in h and 'id=\"subtitle\"' in h; print('html ok')"` → `html ok`.

- [ ] **Step 4: Commit**

```bash
git add web/static/index.html web/static/style.css
git commit -m "feat: web index adds TW/US switch + element ids"
```

---

### Task 5: Rewrite `app.js` to be market-aware

**Files:**
- Modify: `web/static/app.js`

- [ ] **Step 1: Replace `web/static/app.js`** with the version below. It reads the selected market from the radio buttons, fetches `/api/committee?market=…`, applies `ui`/`phase_names`/`agent_names`, and opens `/ws/run/{market}/{ticker}`.

```javascript
"use strict";
// Committee front-end: fetch roster for the selected market, build pipeline,
// connect to /ws/run/{market}/{ticker}, render EventBus events. All UI strings
// come from the market's `ui` map so the view is TW (zh) or US (en).

const $ = (id) => document.getElementById(id);
const tickerEl = $("ticker");
const runBtn = $("run");
const verdictEl = $("verdict");
const verifyEl = $("verify");
const statusEl = $("status");
const cardsEl = $("cards");
const messagesEl = $("messages");

let roster = null;     // /api/committee response (includes ui, phase_names, agent_names)
let ui = {};           // roster.ui shortcut
let cards = {};
let curStreamingAgent = null;
let curStreamingHasTokens = false;
let curStreamingMsgEl = null;
let curPhase = null;
let ws = null;

function market() {
  const el = document.querySelector('input[name="market"]:checked');
  return el ? el.value : "tw";
}
function agentLabel(a) { return (roster && roster.agent_names[a]) || a; }
function phaseLabel(p) { return (roster && roster.phase_names[p]) || p; }
function setStatus(t) { statusEl.textContent = t; }
function escapeHtml(s) { const d = document.createElement("div"); d.textContent = s == null ? "" : String(s); return d.innerHTML; }

function makeCard(parent, num, key, title, model, tools) {
  const el = document.createElement("div");
  el.className = "card";
  el.innerHTML = `
    <div class="hdr"><span><span class="num">${num}.</span>${escapeHtml(title)}</span>
      <span class="status pending">${escapeHtml(ui.pending_badge)}</span></div>
    ${model ? `<div class="model">${escapeHtml(ui.model_label)}${escapeHtml(model)}</div>` : ""}
    ${tools && tools.length ? `<div class="tools">${escapeHtml(ui.tools_label)}${escapeHtml(tools.join(", "))}</div>` : ""}
    <div class="result">—</div>`;
  parent.appendChild(el);
  cards[key] = { statusEl: el.querySelector(".status"), resultEl: el.querySelector(".result") };
}

function buildPipeline() {
  cardsEl.innerHTML = "";
  cards = {};
  let i = 0;
  const push = (key, title, model, tools) => {
    i += 1;
    makeCard(cardsEl, i, key, title, model || "", tools || []);
    const arrow = document.createElement("div"); arrow.className = "arrow"; arrow.textContent = "↓";
    cardsEl.appendChild(arrow);
  };
  push("phase:RESEARCH", phaseLabel("RESEARCH"));
  for (const a of roster.research) push("agent:" + a.name, a.label, a.model, a.tools);
  push("phase:CHALLENGE", phaseLabel("CHALLENGE"));
  for (const a of roster.challengers) push("agent:" + a.name, a.label, a.model, a.tools);
  push("phase:REBUTTAL", phaseLabel("REBUTTAL"));
  push("phase:VERDICT", phaseLabel("VERDICT"));
  push("agent:chair", roster.chair.label, roster.chair.model, []);
  if (roster.reflection_passes > 0) push("phase:REFLECT", phaseLabel("REFLECT"));
  push("phase:VERIFY", phaseLabel("VERIFY"));
  push("agent:verifier", roster.verifier.label, roster.verifier.model, []);
  if (cardsEl.lastChild && cardsEl.lastChild.className === "arrow") cardsEl.removeChild(cardsEl.lastChild);
}

function setCardStatus(key, label, cls) {
  const c = cards[key]; if (!c) return;
  c.statusEl.textContent = label; c.statusEl.className = "status " + cls;
}
function setCardResult(key, text) { const c = cards[key]; if (c && text) c.resultEl.textContent = text; }
function resetCards() {
  for (const k of Object.keys(cards)) {
    cards[k].statusEl.textContent = ui.pending_badge;
    cards[k].statusEl.className = "status pending";
    cards[k].resultEl.textContent = "—";
  }
}

function endStream() {
  if (curStreamingAgent !== null) { curStreamingAgent = null; curStreamingHasTokens = false; curStreamingMsgEl = null; }
}
function streamToken(agent, text) {
  if (curStreamingAgent !== agent) {
    endStream();
    const el = document.createElement("div");
    el.className = "msg agent-" + agent;
    el.innerHTML = `<span class="who">[${escapeHtml(agentLabel(agent))}]</span><span class="body"></span>`;
    messagesEl.appendChild(el);
    curStreamingAgent = agent;
    curStreamingMsgEl = el.querySelector(".body");
    curStreamingHasTokens = false;
  }
  if (text) { curStreamingMsgEl.textContent += text; curStreamingHasTokens = true; }
  messagesEl.scrollTop = messagesEl.scrollHeight;
}
function appendMessage(agent, text) {
  const el = document.createElement("div");
  el.className = "msg agent-" + agent;
  el.innerHTML = `<span class="who">[${escapeHtml(agentLabel(agent))}]</span>${escapeHtml(text)}`;
  messagesEl.appendChild(el);
  messagesEl.scrollTop = messagesEl.scrollHeight;
}
function appendTool(klass, text) {
  const el = document.createElement("div"); el.className = klass; el.textContent = text;
  messagesEl.appendChild(el); messagesEl.scrollTop = messagesEl.scrollHeight;
}
function appendPhaseHeader(phase, stock) {
  const el = document.createElement("div");
  el.className = "phase-hdr"; el.textContent = `=== ${phaseLabel(phase)} (${stock || ""}) ===`;
  messagesEl.appendChild(el);
}
function detectLean(text) {
  for (const kw of ui.lean_words) if ((text || "").includes(kw)) return kw;
  return ui.done_word;
}
function verdictHeadline(text) {
  for (const line of (text || "").split("\n")) if (line.includes(ui.recommend_word)) return line.trim();
  return ((text || "").split("\n")[0] || ui.done_word).trim();
}

function handleEvent(e) {
  const t = e.type;
  if (t === "phase" && e.data.phase) {
    endStream();
    appendPhaseHeader(e.data.phase, e.data.stock);
    setStatus("● " + phaseLabel(e.data.phase) + " — " + (e.data.stock || ""));
    if (curPhase && curPhase !== e.data.phase) setCardStatus("phase:" + curPhase, ui.done_badge, "done");
    setCardStatus("phase:" + e.data.phase, ui.running_badge, "running");
    curPhase = e.data.phase;
    return;
  }
  if (t === "phase" && e.data.status === "start") {
    setStatus(agentLabel(e.agent) + ":" + ui.thinking + " ...");
    setCardStatus("agent:" + e.agent, ui.running_badge, "running");
    return;
  }
  if (t === "token") { streamToken(e.agent, e.data.text || ""); setStatus(agentLabel(e.agent) + ":" + ui.writing + " ..."); return; }
  if (t === "message") {
    if (curStreamingAgent === e.agent && curStreamingHasTokens) { endStream(); }
    else if (e.data.text) { endStream(); appendMessage(e.agent, e.data.text); }
    setStatus(agentLabel(e.agent) + ":" + ui.done_word);
    let result;
    if (e.agent === "chair") result = verdictHeadline(e.data.text || "");
    else if (e.agent === "verifier") result = ((e.data.text || "").split("\n")[0] || ui.done_word).slice(0, 24);
    else result = detectLean(e.data.text || "");
    setCardResult("agent:" + e.agent, result);
    setCardStatus("agent:" + e.agent, ui.done_badge, "done");
    return;
  }
  if (t === "tool_call") {
    endStream();
    appendTool("tool", `  [${ui.tool_word}] ${e.data.tool}(${JSON.stringify(e.data.args || {})})`);
    setStatus(`${agentLabel(e.agent)}:${ui.calling} ${e.data.tool} ...`);
    setCardResult("agent:" + e.agent, `${ui.calling} ${e.data.tool} ...`);
    return;
  }
  if (t === "tool_result") {
    endStream();
    appendTool("tool", `  [${ui.done_word}] ${e.data.tool}`);
    setStatus(`${agentLabel(e.agent)}:${ui.received} ${e.data.tool}`);
    return;
  }
  if (t === "error") {
    endStream();
    appendTool("err", `  [${ui.warn_word}] ${e.data.tool || ""}: ${e.data.error || ""}`);
    setStatus(`⚠ ${e.data.tool || ""}: ${e.data.error || ""}`);
    return;
  }
  if (t === "verdict") {
    const head = verdictHeadline(e.data.text || "");
    verdictEl.textContent = ui.verdict_prefix + head;
    setCardResult("agent:chair", head);
    setStatus(ui.verdict_done);
    return;
  }
  if (t === "verification") {
    const g = e.data.grounding || {};
    let txt = `${ui.verify_prefix} ${g.supported || 0}/${g.checked || 0}`;
    let cls = "ok";
    if (!g.grounded) { txt += " ⚠ " + ui.unsupported_word + ": " + JSON.stringify(g.unsupported || []); cls = "warn"; }
    verifyEl.textContent = txt; verifyEl.className = cls;
    setCardResult("phase:VERIFY", txt);
    setCardStatus("phase:VERIFY", ui.done_badge, "done");
    setStatus(txt);
    return;
  }
  if (t === "report") {
    setStatus(ui.report_saved);
    const link = document.createElement("a");
    link.id = "report-link"; link.href = e.data.url; link.target = "_blank";
    link.textContent = ui.open_report + " (" + e.data.path + ")";
    verdictEl.appendChild(link);
    runBtn.disabled = false; runBtn.textContent = ui.run_button;
    return;
  }
}

function applyUi() {
  document.documentElement.lang = roster.market === "us" ? "en" : "zh-TW";
  $("page-title").textContent = ui.title;
  $("title").firstChild.textContent = ui.title + " ";
  $("subtitle").textContent = ui.subtitle;
  $("ticker-label").textContent = ui.ticker_label;
  $("pipeline-heading").textContent = ui.pipeline_heading;
  $("debate-heading").textContent = ui.debate_heading;
  runBtn.textContent = ui.run_button;
  verdictEl.textContent = ui.verdict_placeholder;
  setStatus(ui.idle);
}

async function loadRoster() {
  const r = await fetch("/api/committee?market=" + market());
  roster = await r.json();
  ui = roster.ui;
  applyUi();
  // Swap example ticker if the field is empty or holds the other market's example.
  const others = ["2330", "AAPL"];
  if (!tickerEl.value.trim() || others.includes(tickerEl.value.trim())) {
    tickerEl.value = ui.example_ticker;
  }
  buildPipeline();
}

function start() {
  const stock = (tickerEl.value || ui.example_ticker).trim();
  const m = market();
  if (ws && ws.readyState <= 1) { ws.close(); }
  resetCards();
  messagesEl.innerHTML = "";
  verifyEl.textContent = ""; verifyEl.className = "hidden";
  verdictEl.textContent = ui.verdict_running.replace("{stock}", stock);
  setStatus(ui.start_status.replace("{stock}", stock));
  runBtn.disabled = true; runBtn.textContent = ui.running_button;
  curStreamingAgent = null; curStreamingHasTokens = false; curPhase = null;

  const proto = window.location.protocol === "https:" ? "wss" : "ws";
  ws = new WebSocket(`${proto}://${window.location.host}/ws/run/${m}/${encodeURIComponent(stock)}`);
  ws.onmessage = (msg) => { try { handleEvent(JSON.parse(msg.data)); } catch (err) { console.error(err); } };
  ws.onclose = () => { runBtn.disabled = false; runBtn.textContent = ui.run_button; };
  ws.onerror = (err) => { setStatus(ui.ws_error); console.error(err); };
}

runBtn.addEventListener("click", start);
tickerEl.addEventListener("keydown", (e) => { if (e.key === "Enter") start(); });
for (const r of document.querySelectorAll('input[name="market"]')) {
  r.addEventListener("change", () => { loadRoster().catch((e) => { cardsEl.textContent = ui.load_failed + e; }); });
}
loadRoster().catch((e) => { cardsEl.textContent = "Load failed: " + e; });
```

- [ ] **Step 2: Structural verification** — confirm the hardcoded Chinese status literals are gone and the new wiring exists:

```bash
cd /Users/steventsai/Documents/Claude_Project/stock-ana/stock-analysis
.venv/bin/python - <<'PY'
src = open("web/static/app.js", encoding="utf-8").read()
banned = ["思考中", "撰寫中", "已取得", "開始分析", "研究分析", "結論:", "等待"]
present = [w for w in banned if w in src]
assert not present, "hardcoded Chinese still in app.js: %s" % present
assert "/ws/run/${m}/" in src and "market=" in src and "ui.thinking" in src
print("app.js market-aware ok")
PY
```

- [ ] **Step 3: Server import smoke** — `.venv/bin/python -c "import web.server; print('server ok')"` → `server ok`.

- [ ] **Step 4: Manual check (note in commit, not automated)** — start the server (`.venv/bin/python -m uvicorn web.server:app`), open http://localhost:8000, confirm: default TW shows Chinese title/labels; flipping to US switches title to "US Equity Investment Committee", labels to English, ticker to `AAPL`; running `AAPL` streams with English status. (Reviewer/operator performs this; it is not a unit test.)

- [ ] **Step 5: Commit**

```bash
git add web/static/app.js
git commit -m "feat: web app.js localizes live view + routes by selected market"
```

---

## Phase C — Desktop GUI

### Task 6: Make `gui.py` `format_event` market-aware

**Files:**
- Modify: `gui.py`
- Test: `tests/test_gui_format.py`

- [ ] **Step 1: Write failing tests** — append to `tests/test_gui_format.py`:

```python
from committee.markets import get_profile


def test_format_event_message_uses_market_labels():
    from gui import format_event
    us = get_profile("us").labels
    out = format_event(Event(type="message", agent="fundamental", data={"text": "hi"}), us)
    assert out == ("[Fundamentals Analyst] hi\n", "fundamental")


def test_format_event_phase_uses_market_labels():
    from gui import format_event
    us = get_profile("us").labels
    out = format_event(Event(type="phase", agent="system",
                             data={"phase": "RESEARCH", "stock": "AAPL"}), us)
    text, tag = out
    assert "Research" in text and tag == "system"


def test_format_event_defaults_to_tw_when_no_labels():
    from gui import format_event
    out = format_event(Event(type="message", agent="fundamental", data={"text": "hi"}))
    assert out == ("[基本面分析師] hi\n", "fundamental")
```

- [ ] **Step 2: Run, verify fail** — `.venv/bin/python -m pytest tests/test_gui_format.py -k market -v` → FAIL (`format_event` takes one arg).

- [ ] **Step 3: Refactor the GUI format helpers** in `gui.py`. Replace the module-level `_zh`, the phase-label map, and `format_event` so they accept a `labels` object (default TW). Read the current `format_event` and the phase map it uses, then:

```python
def _default_labels():
    from committee.markets import get_profile
    return get_profile("tw").labels


def _agent_label(agent, labels):
    return labels.agent_names.get(agent, agent)


def format_event(e: "Event", labels=None) -> "Optional[Tuple[str, str]]":
    if labels is None:
        labels = _default_labels()
    # ... keep the existing branch logic, but replace every _zh(e.agent) with
    # _agent_label(e.agent, labels) and every phase-label lookup with
    # labels.phase_names.get(phase, phase). Keep the "  [完成] {} 已回傳" style
    # tool line but source "完成"/"已回傳" wording — for the feed formatter keep
    # it simple: use labels.phase_names / agent_names for names; tool lines may
    # stay as-is since they are not part of these tests. Preserve return shapes
    # (text, tag) exactly.
```

Concretely: keep `detect_lean`/`verdict_headline` as-is (they are tested for TW and used only for TW-style content in the existing tests; the GUI `_handle` will pass market lean words separately in Task 7). The ONLY required change in this task is that `format_event(e, labels=None)` uses `labels.agent_names` and `labels.phase_names`, defaulting to TW. Do not change the tool/error line wording in `format_event` (the existing TW tests for those still pass because default labels are TW).

- [ ] **Step 4: Run, verify pass** — `.venv/bin/python -m pytest tests/test_gui_format.py -v` → PASS (existing TW tests + new market tests).

- [ ] **Step 5: Commit**

```bash
git add gui.py tests/test_gui_format.py
git commit -m "feat: gui format_event takes market labels (TW default)"
```

---

### Task 7: GUI toggle + market-aware pipeline/status

**Files:**
- Modify: `gui.py`

- [ ] **Step 1: Add a TW/US control and market state.** Read the GUI `__init__`/top-controls section. Add, next to the ticker input, a `tk.StringVar(value="tw")` named `self.market_var` and two radio buttons (`TW`/`US`) bound to it with a `command=self._on_market_change`. Store the current profile: `self.profile = get_profile("tw")` in `__init__` (import `from committee.markets import get_profile, detect_market` — but use the toggle, not detect).

- [ ] **Step 2: Make `_build_pipeline` and chrome use the selected profile.** Change `_build_pipeline` to use `self.profile.committee` (not `build_committee()`) and the profile's `labels.agent_names`/`phase_names` for the step titles (replace `_zh(...)` and the hardcoded phase strings `"研究分析"`, `"質詢"`, `"答辯(分析師回應)"`, `"最終結論"`, `"自我反省"`, `"自我查核"` with `self.profile.labels.phase_names[...]`). Set the window title and the `股票代號`/`開始分析`/`執行流程 Pipeline`/`即時討論 Live debate`/`結論:(請先執行分析)`/`● 閒置` widgets from `self.profile.ui` (store references to those widgets in `__init__` so `_on_market_change` can update them).

- [ ] **Step 3: Implement `_on_market_change`:**

```python
def _on_market_change(self) -> None:
    self.profile = get_profile(self.market_var.get())
    ui = self.profile.ui
    self.root.title(ui["title"])
    self.btn.config(text=ui["run_button"])
    self.ticker_label.config(text=ui["ticker_label"])
    self.verdict.config(text=ui["verdict_placeholder"])
    self.status.config(text=ui["idle"])
    self.pipeline_heading.config(text=ui["pipeline_heading"])
    self.debate_heading.config(text=ui["debate_heading"])
    # swap example ticker if empty or the other market's example
    cur = self.ticker.get().strip()
    if not cur or cur in ("2330", "AAPL"):
        self.ticker.delete(0, "end")
        self.ticker.insert(0, ui["example_ticker"])
    # rebuild the pipeline cards for the new roster/labels
    for w in self._pipeline.winfo_children():
        w.destroy()
    self.cards = {}
    self._build_pipeline()
```

(Adjust attribute names to the actual widgets; store `self.ticker_label`, `self.pipeline_heading`, `self.debate_heading` when creating those `tk.Label`s.)

- [ ] **Step 4: Force market on run + localize streaming status.** In `_on_analyze`/the run worker, build the run with `self.profile` (forced market) instead of `get_profile(detect_market(stock))`. In `_handle`, replace the hardcoded `_zh(e.agent)` with `self.profile.labels.agent_names.get(e.agent, e.agent)` and the status verbs (`思考中`/`撰寫中`/`完成`/`呼叫`/`已取得`) with `self.profile.ui[...]`, and pass `self.profile.labels` to `format_event(e, self.profile.labels)` where the feed formatter is called.

- [ ] **Step 5: Verify** — `.venv/bin/python -c "import gui; print('gui import ok')"` → ok. `.venv/bin/python -m pytest tests/test_gui_format.py -q` → PASS. Structural grep:

```bash
.venv/bin/python - <<'PY'
src = open("gui.py", encoding="utf-8").read()
assert "self.market_var" in src and "_on_market_change" in src
assert "get_profile(self.market_var.get())" in src
print("gui toggle ok")
PY
```

- [ ] **Step 6: Manual check (operator, not a unit test)** — run `.venv/bin/python gui.py`, flip TW↔US, confirm the window title, labels, and example ticker switch, and a US run streams English status.

- [ ] **Step 7: Commit**

```bash
git add gui.py
git commit -m "feat: desktop GUI TW/US toggle + localized live view"
```

---

### Task 8: Full suite + smoke

**Files:** none (verification + optional README touch)

- [ ] **Step 1: Full suite** — `.venv/bin/python -m pytest -q` → PASS (expect 156+ passed, 1 deselected).

- [ ] **Step 2: Server + GUI import smoke** — `.venv/bin/python -c "import web.server, gui; print('imports ok')"`.

- [ ] **Step 3: (optional) README** — add one line under the "Markets" section that the web app and desktop GUI have a TW/US switch that sets the UI language and market.

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "docs: note TW/US UI switch"
```

---

## Self-Review Notes

- **Spec coverage:** `MarketProfile.ui` + `tw_ui`/`us_ui` (T1); `committee_info(market)` localized roster + ui (T2); WS route forces market (T3); index.html toggle + ids (T4); app.js market-aware live view + routing + example-ticker swap (T5); GUI `format_event` labels (T6) and toggle + localized pipeline/status + forced market (T7); suite/smoke (T8). Default TW honored (radio `checked` on tw; `_safe_market` default "tw"). All spec sections map to a task.
- **No automated JS tests** is called out explicitly; T5 uses a structural grep + server import + a manual operator check instead.
- **Backward-compat:** `committee_info` default arg `market="tw"`, `format_event(e, labels=None)` default TW, `_safe_market` fallback — existing TW behavior and the unchanged tests stay green.
- **Type consistency:** the JSON field for an agent's display name is renamed `zh` → `label` in both `committee_info` (T2) and `app.js` (T5: `a.label`); roster maps renamed `phase_zh`/`agent_zh` → `phase_names`/`agent_names` in both. The `ui` dict keys are defined once in T1 and referenced identically in T5/T7.
- **Out of scope (per spec):** CLI localization; persisting last-used market.
