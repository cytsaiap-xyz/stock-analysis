"use strict";
// 委員會前端:取得 roster 建立 pipeline 步驟方塊,連到 /ws/run/{ticker}
// 接收 EventBus 事件並更新畫面。逐字串流 token,phase/agent 卡片狀態即時變化。

const $ = (id) => document.getElementById(id);
const tickerEl = $("ticker");
const runBtn = $("run");
const verdictEl = $("verdict");
const verifyEl = $("verify");
const statusEl = $("status");
const cardsEl = $("cards");
const messagesEl = $("messages");

let roster = null;            // /api/committee 回傳
let cards = {};               // key -> {statusEl, resultEl}
let curStreamingAgent = null; // 目前正在 stream tokens 的委員 name
let curStreamingHasTokens = false;
let curStreamingMsgEl = null;
let curPhase = null;
let ws = null;

function setStatus(t) { statusEl.textContent = t; }
function escapeHtml(s) { const d = document.createElement("div"); d.textContent = s == null ? "" : String(s); return d.innerHTML; }

function makeCard(parent, num, key, title, model, tools) {
  const el = document.createElement("div");
  el.className = "card";
  el.innerHTML = `
    <div class="hdr"><span><span class="num">${num}.</span>${escapeHtml(title)}</span>
      <span class="status pending">⏳ 等待</span></div>
    ${model ? `<div class="model">模型: ${escapeHtml(model)}</div>` : ""}
    ${tools && tools.length ? `<div class="tools">工具: ${escapeHtml(tools.join(", "))}</div>` : ""}
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
  push("phase:RESEARCH", "研究分析");
  for (const a of roster.research) push("agent:" + a.name, a.zh, a.model, a.tools);
  push("phase:CHALLENGE", "質詢");
  for (const a of roster.challengers) push("agent:" + a.name, a.zh, a.model, a.tools);
  push("phase:REBUTTAL", "答辯(分析師回應)");
  push("phase:VERDICT", "最終結論");
  push("agent:chair", roster.chair.zh, roster.chair.model, []);
  push("phase:VERIFY", "自我查核");
  push("agent:verifier", roster.verifier.zh, roster.verifier.model, []);
  if (cardsEl.lastChild && cardsEl.lastChild.className === "arrow") cardsEl.removeChild(cardsEl.lastChild);
}

function setCardStatus(key, label, cls) {
  const c = cards[key]; if (!c) return;
  c.statusEl.textContent = label; c.statusEl.className = "status " + cls;
}
function setCardResult(key, text) {
  const c = cards[key]; if (c && text) c.resultEl.textContent = text;
}
function resetCards() {
  for (const k of Object.keys(cards)) {
    cards[k].statusEl.textContent = "⏳ 等待";
    cards[k].statusEl.className = "status pending";
    cards[k].resultEl.textContent = "—";
  }
}

function endStream() {
  if (curStreamingAgent !== null) {
    curStreamingAgent = null;
    curStreamingHasTokens = false;
    curStreamingMsgEl = null;
  }
}

function streamToken(agent, text) {
  const zh = roster.agent_zh[agent] || agent;
  if (curStreamingAgent !== agent) {
    endStream();
    const el = document.createElement("div");
    el.className = "msg agent-" + agent;
    el.innerHTML = `<span class="who">[${escapeHtml(zh)}]</span><span class="body"></span>`;
    messagesEl.appendChild(el);
    curStreamingAgent = agent;
    curStreamingMsgEl = el.querySelector(".body");
    curStreamingHasTokens = false;
  }
  if (text) { curStreamingMsgEl.textContent += text; curStreamingHasTokens = true; }
  messagesEl.scrollTop = messagesEl.scrollHeight;
}

function appendMessage(agent, text) {
  const zh = roster.agent_zh[agent] || agent;
  const el = document.createElement("div");
  el.className = "msg agent-" + agent;
  el.innerHTML = `<span class="who">[${escapeHtml(zh)}]</span>${escapeHtml(text)}`;
  messagesEl.appendChild(el);
  messagesEl.scrollTop = messagesEl.scrollHeight;
}

function appendTool(klass, text) {
  const el = document.createElement("div");
  el.className = klass; el.textContent = text;
  messagesEl.appendChild(el);
  messagesEl.scrollTop = messagesEl.scrollHeight;
}

function appendPhaseHeader(phase, stock) {
  const ph = roster.phase_zh[phase] || phase;
  const el = document.createElement("div");
  el.className = "phase-hdr"; el.textContent = `=== ${ph} (${stock || ""}) ===`;
  messagesEl.appendChild(el);
}

function detectLean(text) {
  for (const kw of ["看多", "看空", "中性"]) if ((text || "").includes(kw)) return kw;
  return "完成";
}
function verdictHeadline(text) {
  for (const line of (text || "").split("\n")) if (line.includes("建議")) return line.trim();
  return ((text || "").split("\n")[0] || "完成").trim();
}

function handleEvent(e) {
  const t = e.type;
  if (t === "phase" && e.data.phase) {
    endStream();
    appendPhaseHeader(e.data.phase, e.data.stock);
    setStatus("● " + (roster.phase_zh[e.data.phase] || e.data.phase) + " — " + (e.data.stock || ""));
    if (curPhase && curPhase !== e.data.phase) setCardStatus("phase:" + curPhase, "✓ 完成", "done");
    setCardStatus("phase:" + e.data.phase, "▶ 進行中", "running");
    curPhase = e.data.phase;
    return;
  }
  if (t === "phase" && e.data.status === "start") {
    setStatus((roster.agent_zh[e.agent] || e.agent) + ":思考中 ...");
    setCardStatus("agent:" + e.agent, "▶ 進行中", "running");
    return;
  }
  if (t === "token") { streamToken(e.agent, e.data.text || ""); setStatus((roster.agent_zh[e.agent] || e.agent) + ":撰寫中 ..."); return; }
  if (t === "message") {
    if (curStreamingAgent === e.agent && curStreamingHasTokens) {
      endStream();
    } else if (e.data.text) {
      endStream(); appendMessage(e.agent, e.data.text);
    }
    setStatus((roster.agent_zh[e.agent] || e.agent) + ":完成");
    let result;
    if (e.agent === "chair") result = verdictHeadline(e.data.text || "");
    else if (e.agent === "verifier") result = ((e.data.text || "").split("\n")[0] || "完成").slice(0, 24);
    else result = detectLean(e.data.text || "");
    setCardResult("agent:" + e.agent, result);
    setCardStatus("agent:" + e.agent, "✓ 完成", "done");
    return;
  }
  if (t === "tool_call") {
    endStream();
    appendTool("tool", `  [工具] ${e.data.tool}(${JSON.stringify(e.data.args || {})})`);
    setStatus(`${roster.agent_zh[e.agent] || e.agent}:呼叫 ${e.data.tool} ...`);
    setCardResult("agent:" + e.agent, `呼叫 ${e.data.tool} ...`);
    return;
  }
  if (t === "tool_result") {
    endStream();
    appendTool("tool", `  [完成] ${e.data.tool} 已回傳`);
    setStatus(`${roster.agent_zh[e.agent] || e.agent}:已取得 ${e.data.tool}`);
    return;
  }
  if (t === "error") {
    endStream();
    appendTool("err", `  [警告] ${e.data.tool || ""} 錯誤:${e.data.error || ""}`);
    setStatus(`⚠ ${e.data.tool || ""}:${e.data.error || ""}`);
    return;
  }
  if (t === "verdict") {
    const head = verdictHeadline(e.data.text || "");
    verdictEl.textContent = "結論:" + head;
    setCardResult("agent:chair", head);
    setStatus("結論完成 ✓");
    return;
  }
  if (t === "verification") {
    const g = e.data.grounding || {};
    let txt = `自我查核:數據支持 ${g.supported || 0}/${g.checked || 0}`;
    let cls = "ok";
    if (!g.grounded) { txt += " ⚠ 未支持: " + JSON.stringify(g.unsupported || []); cls = "warn"; }
    verifyEl.textContent = txt;
    verifyEl.className = cls;
    setCardResult("phase:VERIFY", txt);
    setCardStatus("phase:VERIFY", "✓ 完成", "done");
    setStatus(txt);
    return;
  }
  if (t === "report") {
    setStatus("📄 報告已存");
    const link = document.createElement("a");
    link.id = "report-link";
    link.href = e.data.url; link.target = "_blank";
    link.textContent = "→ 開啟報告 (" + e.data.path + ")";
    verdictEl.appendChild(link);
    runBtn.disabled = false; runBtn.textContent = "開始分析";
    return;
  }
}

async function loadRoster() {
  const r = await fetch("/api/committee"); roster = await r.json();
  buildPipeline();
}

function start() {
  const stock = (tickerEl.value || "2330").trim();
  if (ws && ws.readyState <= 1) { ws.close(); }
  resetCards();
  messagesEl.innerHTML = "";
  verifyEl.textContent = ""; verifyEl.className = "hidden";
  verdictEl.textContent = "結論:分析 " + stock + " 中...";
  setStatus("開始分析 " + stock + " ...");
  runBtn.disabled = true; runBtn.textContent = "分析中...";
  curStreamingAgent = null; curStreamingHasTokens = false; curPhase = null;

  const proto = window.location.protocol === "https:" ? "wss" : "ws";
  ws = new WebSocket(`${proto}://${window.location.host}/ws/run/${encodeURIComponent(stock)}`);
  ws.onmessage = (m) => { try { handleEvent(JSON.parse(m.data)); } catch (e) { console.error(e); } };
  ws.onclose = () => { runBtn.disabled = false; runBtn.textContent = "開始分析"; };
  ws.onerror = (e) => { setStatus("⚠ WebSocket 錯誤"); console.error(e); };
}

runBtn.addEventListener("click", start);
tickerEl.addEventListener("keydown", (e) => { if (e.key === "Enter") start(); });
loadRoster().catch((e) => { cardsEl.textContent = "載入失敗: " + e; });
