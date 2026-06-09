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
