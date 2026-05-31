// Build "自主投資委員會" intro deck (system + flow) as a .pptx via pptxgenjs.
// Run: node docs/slides/build.js   ->   docs/slides/自主投資委員會-系統介紹.pptx
const pptxgen = require("pptxgenjs");

const P = {
  ink: "0B0E13", ink2: "10141C", panel: "151B27", panel2: "1C2230",
  paper: "ECE6D8", muted: "8B909C", faint: "5B6270",
  gold: "E8B24A", gold2: "F4CF7A", bull: "63B98E", bear: "D97070",
  line: "2A3242", lineSoft: "1E2532",
};
const F = { cjk: "Microsoft JhengHei", mono: "Consolas", serif: "Georgia" };

const pres = new pptxgen();
pres.defineLayout({ name: "W", width: 13.333, height: 7.5 });
pres.layout = "W";
pres.author = "Agentic Investment Committee";
pres.title = "自主投資委員會 — 系統介紹";
const W = 13.333, H = 7.5, M = 0.75;

const shadow = () => ({ type: "outer", color: "000000", blur: 9, offset: 3, angle: 90, opacity: 0.35 });

let pageNo = 0;
function base(slide) {
  slide.background = { color: P.ink };
  for (let gx = 1; gx < 8; gx++) slide.addShape(pres.shapes.LINE, { x: gx * (W / 8), y: 0, w: 0, h: H, line: { color: P.lineSoft, width: 0.5 } });
  slide.addShape(pres.shapes.RECTANGLE, { x: M, y: 0.42, w: 0.12, h: 0.12, fill: { color: P.gold }, line: { type: "none" } });
  slide.addText("自主投資委員會 · AGENTIC INVESTMENT COMMITTEE", { x: M + 0.22, y: 0.3, w: 8, h: 0.36, fontFace: F.mono, fontSize: 9, color: P.muted, charSpacing: 2, align: "left", valign: "middle" });
}
function counter(slide) {
  pageNo += 1;
  slide.addText([
    { text: String(pageNo).padStart(2, "0"), options: { color: P.gold } },
    { text: " / 11", options: { color: P.muted } },
  ], { x: W - 2.2, y: 0.3, w: 1.45, h: 0.36, fontFace: F.mono, fontSize: 10, align: "right", valign: "middle" });
  slide.addShape(pres.shapes.LINE, { x: 0, y: H - 0.04, w: (pageNo / 11) * W, h: 0, line: { color: P.gold, width: 2.5 } });
}
function card(slide, x, y, w, h, rule) {
  slide.addShape(pres.shapes.RECTANGLE, { x, y, w, h, fill: { color: P.panel }, line: { color: P.line, width: 1 }, shadow: shadow() });
  if (rule !== false) slide.addShape(pres.shapes.RECTANGLE, { x, y, w: 0.05, h, fill: { color: P.gold }, line: { type: "none" } });
}
function newSlide() { const s = pres.addSlide(); base(s); return s; }

/* ---------- 1 · COVER ---------- */
{
  const s = pres.addSlide(); s.background = { color: P.ink };
  for (let gx = 1; gx < 8; gx++) s.addShape(pres.shapes.LINE, { x: gx * (W / 8), y: 0, w: 0, h: H, line: { color: P.lineSoft, width: 0.5 } });
  s.addShape(pres.shapes.OVAL, { x: 9.4, y: 1.1, w: 5.2, h: 5.2, fill: { type: "none" }, line: { color: P.gold, width: 1, transparency: 55 } });
  s.addShape(pres.shapes.OVAL, { x: 10.5, y: 2.2, w: 3.0, h: 3.0, fill: { type: "none" }, line: { color: P.gold, width: 1, transparency: 30 } });
  s.addText("2330", { x: 9.4, y: 3.05, w: 5.2, h: 1.3, fontFace: F.mono, fontSize: 40, color: P.gold, align: "center", charSpacing: 6, transparency: 25 });

  s.addShape(pres.shapes.RECTANGLE, { x: M, y: 1.55, w: 0.34, h: 0.07, fill: { color: P.gold }, line: { type: "none" } });
  s.addText("系統介紹 · 流程說明", { x: M + 0.5, y: 1.34, w: 8, h: 0.4, fontFace: F.mono, fontSize: 13, color: P.gold, charSpacing: 3 });
  s.addText("自主投資委員會", { x: M, y: 2.0, w: 9.2, h: 2.2, fontFace: F.cjk, fontSize: 72, bold: true, color: P.paper, charSpacing: 1 });
  s.addText([
    { text: "七位 AI 委員,針對 ", options: {} },
    { text: "一檔台股", options: { color: P.gold } },
    { text: " 展開一場結構化辯論,", options: { breakLine: true } },
    { text: "產出 analyst-grade 的繁體中文判讀。", options: {} },
  ], { x: M + 0.02, y: 4.35, w: 8.4, h: 1.0, fontFace: F.cjk, fontSize: 19, color: P.muted, lineSpacingMultiple: 1.3 });
  const meta = ["7-Agent LLM Committee", "研究 → 辯論 → 反省 → 查核", "CLI · GUI · Web"];
  meta.forEach((t, i) => {
    s.addShape(pres.shapes.OVAL, { x: M + i * 3.55, y: 6.05, w: 0.1, h: 0.1, fill: { color: P.gold }, line: { type: "none" } });
    s.addText(t, { x: M + 0.22 + i * 3.55, y: 5.86, w: 3.4, h: 0.4, fontFace: F.mono, fontSize: 11, color: P.muted, charSpacing: 1 });
  });
  counter(s);
}

/* ---------- 2 · WHAT ---------- */
{
  const s = newSlide();
  s.addText("WHAT IS THIS", { x: M, y: 1.15, w: 9, h: 0.35, fontFace: F.mono, fontSize: 12, color: P.muted, charSpacing: 3 });
  s.addText("把「投資委員會開會」變成可執行的多智能體系統", { x: M, y: 1.55, w: 11.8, h: 1.0, fontFace: F.cjk, fontSize: 33, bold: true, color: P.paper });
  s.addText([
    { text: "不是單一模型給答案,而是 ", options: {} },
    { text: "七位各有專業與立場的 AI 委員", options: { color: P.gold } },
    { text: ",針對同一檔台股,跑完整一輪", options: { breakLine: true } },
    { text: "研究 → 質詢 → 答辯 → 裁決 → 自我反省 → 查核 的辯論。", options: { color: P.gold2 } },
  ], { x: M, y: 2.95, w: 11.6, h: 1.1, fontFace: F.cjk, fontSize: 20, color: P.paper, lineSpacingMultiple: 1.35 });
  card(s, M, 4.3, 11.83, 1.2);
  s.addText([
    { text: "最終輸出  ", options: { color: P.muted, fontFace: F.mono } },
    { text: "買進 / 持有 / 賣出", options: { color: P.gold, bold: true } },
    { text: "  + 信心度 + 一份專業研究報告(評等橫幅 + 數據儀表板 + 走勢圖)。全程繁體中文,所有數字都來自真實工具呼叫。", options: { color: P.paper } },
  ], { x: M + 0.35, y: 4.3, w: 11.2, h: 1.2, fontFace: F.cjk, fontSize: 16, valign: "middle", lineSpacingMultiple: 1.25 });
  const pills = ["單一檔股 · 2330", "真實資料 · TWSE / openapi / 新聞", "三前端共用同一引擎"];
  pills.forEach((t, i) => {
    const pw = 3.85, px = M + i * (pw + 0.13);
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: px, y: 5.85, w: pw, h: 0.6, rectRadius: 0.3, fill: { color: P.ink2 }, line: { color: P.line, width: 1 } });
    s.addText(t, { x: px, y: 5.85, w: pw, h: 0.6, fontFace: F.mono, fontSize: 11.5, color: P.paper, align: "center", valign: "middle", charSpacing: 1 });
  });
  counter(s);
}

/* ---------- 3 · ARCHITECTURE ---------- */
{
  const s = newSlide();
  s.addText("ARCHITECTURE", { x: M, y: 1.15, w: 9, h: 0.35, fontFace: F.mono, fontSize: 12, color: P.muted, charSpacing: 3 });
  s.addText("兩層架構,事件驅動", { x: M, y: 1.55, w: 11.8, h: 0.9, fontFace: F.cjk, fontSize: 33, bold: true, color: P.paper });
  const cw = 5.83, cy = 2.85, ch = 2.0;
  card(s, M, cy, cw, ch);
  s.addText("agentcore — 通用核心", { x: M + 0.35, y: cy + 0.25, w: cw - 0.6, h: 0.4, fontFace: F.mono, fontSize: 13, bold: true, color: P.gold, charSpacing: 1 });
  s.addText([
    { text: "完全不含股市知識的可重用多智能體引擎:", options: { breakLine: true, color: P.paper } },
    { text: "EventBus · Agent · Orchestrator · LLMClient · EvidenceLedger · verify · ReportCollector", options: { color: P.muted, fontFace: F.mono, fontSize: 12 } },
  ], { x: M + 0.35, y: cy + 0.7, w: cw - 0.7, h: 1.1, fontFace: F.cjk, fontSize: 15, lineSpacingMultiple: 1.3 });
  const x2 = M + cw + 0.17;
  card(s, x2, cy, cw, ch);
  s.addText("committee — 台股領域層", { x: x2 + 0.35, y: cy + 0.25, w: cw - 0.6, h: 0.4, fontFace: F.mono, fontSize: 13, bold: true, color: P.gold, charSpacing: 1 });
  s.addText([
    { text: "所有「台股」知識都在這:", options: { breakLine: true, color: P.paper } },
    { text: "委員 prompts & 名冊 · 8 個資料工具 · TWSE／新聞 clients · HTML 報告產生器", options: { color: P.muted, fontFace: F.cjk, fontSize: 13 } },
  ], { x: x2 + 0.35, y: cy + 0.7, w: cw - 0.7, h: 1.1, fontFace: F.cjk, fontSize: 15, lineSpacingMultiple: 1.3 });
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: M, y: 5.25, w: cw * 2 + 0.17, h: 0.62, rectRadius: 0.1, fill: { color: P.gold }, line: { type: "none" } });
  s.addText("EventBus  —  引擎只廣播事件,前端全是 subscriber", { x: M, y: 5.25, w: cw * 2 + 0.17, h: 0.62, fontFace: F.cjk, fontSize: 14, bold: true, color: "1A1206", align: "center", valign: "middle" });
  s.addText("要加新前端 = 寫一個事件處理函式,引擎完全不動。", { x: M, y: 6.1, w: 11.8, h: 0.5, fontFace: F.cjk, fontSize: 15, color: P.muted });
  counter(s);
}

/* ---------- 4 · ROSTER ---------- */
{
  const s = newSlide();
  s.addText("THE COMMITTEE", { x: M, y: 1.15, w: 9, h: 0.35, fontFace: F.mono, fontSize: 12, color: P.muted, charSpacing: 3 });
  s.addText("八位委員,兩種模型層級", { x: M, y: 1.55, w: 11.8, h: 0.9, fontFace: F.cjk, fontSize: 33, bold: true, color: P.paper });
  const agents = [
    ["研究組", "基本面", "估值 · 月營收 · 財報", "tool-caller", P.bull],
    ["研究組", "技術面", "均線 · RSI/KD/MACD · 相對強弱", "tool-caller", P.bull],
    ["研究組", "籌碼面", "三大法人買賣超", "tool-caller", P.bull],
    ["研究組", "新聞輿情", "近期新聞利多利空", "tool-caller", P.bull],
    ["挑戰組", "風險經理", "波動 · 回撤 · 下檔風險", "reasoner", P.gold],
    ["挑戰組", "魔鬼代言人", "無工具,專破共識盲點", "reasoner", P.gold],
    ["決策", "主席", "彙整辯論,下最終裁決", "reasoner", P.gold],
    ["把關", "查核員", "檢查結論與數據一致性", "reasoner", P.gold],
  ];
  const gw = 2.86, gh = 1.78, gx0 = M, gy0 = 2.75, gapx = 0.13, gapy = 0.16;
  agents.forEach((a, i) => {
    const c = i % 4, r = Math.floor(i / 4);
    const x = gx0 + c * (gw + gapx), y = gy0 + r * (gh + gapy);
    s.addShape(pres.shapes.RECTANGLE, { x, y, w: gw, h: gh, fill: { color: P.ink2 }, line: { color: a[4] === P.gold ? P.gold : P.line, width: 1, transparency: a[4] === P.gold ? 40 : 0 }, shadow: shadow() });
    s.addText(a[0], { x: x + 0.2, y: y + 0.16, w: gw - 0.4, h: 0.3, fontFace: F.mono, fontSize: 9.5, color: P.muted, charSpacing: 2 });
    s.addText(a[1], { x: x + 0.2, y: y + 0.46, w: gw - 0.4, h: 0.5, fontFace: F.cjk, fontSize: 21, bold: true, color: P.paper });
    s.addText(a[2], { x: x + 0.2, y: y + 1.0, w: gw - 0.4, h: 0.45, fontFace: F.cjk, fontSize: 11.5, color: P.muted, lineSpacingMultiple: 1.1 });
    s.addText(a[3], { x: x + 0.2, y: y + 1.45, w: gw - 0.4, h: 0.28, fontFace: F.mono, fontSize: 9, color: a[4], charSpacing: 1 });
  });
  counter(s);
}

/* ---------- 5 · TOOLS ---------- */
{
  const s = newSlide();
  s.addText("THE TOOLBOX", { x: M, y: 1.15, w: 9, h: 0.35, fontFace: F.mono, fontSize: 12, color: P.muted, charSpacing: 3 });
  s.addText("八個資料工具,全部抓真實資料", { x: M, y: 1.55, w: 11.8, h: 0.9, fontFace: F.cjk, fontSize: 33, bold: true, color: P.paper });
  const tools = [
    ["get_valuation", "本益比 · 淨值比 · 殖利率", "TWSE"],
    ["get_technical_indicators", "均線 · RSI · KD · MACD", "TWSE"],
    ["get_institutional_flows", "三大法人買賣超", "TWSE T86"],
    ["get_monthly_revenue", "月營收年增 / 月增", "openapi"],
    ["get_risk_metrics", "年化波動 · 最大回撤", "TWSE"],
    ["search_news", "近期新聞標題摘要", "DuckDuckGo"],
    ["get_relative_strength", "相對大盤超額報酬 · Beta", "TWSE 指數"],
    ["get_financials", "毛利率 · 營益率 · ROE · EPS", "財報 openapi"],
  ];
  const gw = 2.86, gh = 1.5, gx0 = M, gy0 = 2.75, gapx = 0.13, gapy = 0.18;
  tools.forEach((t, i) => {
    const c = i % 4, r = Math.floor(i / 4);
    const x = gx0 + c * (gw + gapx), y = gy0 + r * (gh + gapy);
    s.addShape(pres.shapes.RECTANGLE, { x, y, w: gw, h: gh, fill: { color: P.ink2 }, line: { color: P.line, width: 1 }, shadow: shadow() });
    s.addShape(pres.shapes.RECTANGLE, { x, y, w: 0.05, h: gh, fill: { color: P.gold }, line: { type: "none" } });
    s.addText(t[0], { x: x + 0.22, y: y + 0.18, w: gw - 0.4, h: 0.4, fontFace: F.mono, fontSize: 12, color: P.gold, bold: true });
    s.addText(t[1], { x: x + 0.22, y: y + 0.62, w: gw - 0.4, h: 0.45, fontFace: F.cjk, fontSize: 12.5, color: P.paper, lineSpacingMultiple: 1.1 });
    s.addText(t[2], { x: x + 0.22, y: y + 1.12, w: gw - 0.4, h: 0.28, fontFace: F.mono, fontSize: 9, color: P.muted, charSpacing: 1 });
  });
  s.addText("欄位順序皆由 spike 腳本實測確認,不信官方文件;LLM 傳來的字串參數一律防禦性轉型。", { x: M, y: 6.35, w: 11.8, h: 0.4, fontFace: F.cjk, fontSize: 13, color: P.muted });
  counter(s);
}

/* ---------- 6 · FLOW (centerpiece) ---------- */
{
  const s = newSlide();
  s.addText("THE FLOW · 辯論流程", { x: M, y: 1.15, w: 9, h: 0.35, fontFace: F.mono, fontSize: 12, color: P.gold, charSpacing: 3 });
  s.addText("六階段,主席主導的有界辯論", { x: M, y: 1.55, w: 11.8, h: 0.9, fontFace: F.cjk, fontSize: 32, bold: true, color: P.paper });
  const phases = [
    ["01", "RESEARCH", "研究分析", "4 分析師\n用工具取數據", false],
    ["02", "CHALLENGE", "質詢", "風險 + 魔鬼\n代言人挑弱點", false],
    ["03", "REBUTTAL", "答辯", "分析師回應\n修正立場", false],
    ["04", "VERDICT", "裁決", "主席彙整出\n建議草稿", false],
    ["05", "REFLECT", "自我反省", "主席自批\n重寫結論", true],
    ["06", "VERIFY", "查核", "數據比對\n必要時修正", true],
  ];
  const bw = 1.79, bh = 2.85, gap = 0.21, y = 3.05;
  let x = M;
  phases.forEach((p, i) => {
    const gate = p[4];
    s.addShape(pres.shapes.RECTANGLE, { x, y, w: bw, h: bh, fill: { color: gate ? P.panel2 : P.ink2 }, line: { color: gate ? P.gold : P.line, width: gate ? 1.5 : 1 }, shadow: shadow() });
    if (gate) s.addText("品質把關", { x: x + 0.1, y: y - 0.16, w: bw - 0.2, h: 0.3, fontFace: F.cjk, fontSize: 9, bold: true, color: "1A1206", fill: { color: P.gold }, align: "center", valign: "middle", charSpacing: 1 });
    s.addText(p[0], { x: x + 0.18, y: y + 0.18, w: bw - 0.36, h: 0.3, fontFace: F.mono, fontSize: 12, color: P.muted });
    s.addText(p[1], { x: x + 0.18, y: y + 0.62, w: bw - 0.36, h: 0.3, fontFace: F.mono, fontSize: 11.5, color: P.gold, charSpacing: 1, bold: true });
    s.addText(p[2], { x: x + 0.18, y: y + 0.95, w: bw - 0.36, h: 0.55, fontFace: F.cjk, fontSize: 19, bold: true, color: P.paper });
    s.addText(p[3], { x: x + 0.18, y: y + 1.62, w: bw - 0.36, h: 0.9, fontFace: F.cjk, fontSize: 11.5, color: P.muted, lineSpacingMultiple: 1.15 });
    if (i < phases.length - 1) s.addText("→", { x: x + bw, y: y, w: gap, h: bh, fontFace: F.mono, fontSize: 16, color: P.gold, align: "center", valign: "middle" });
    x += bw + gap;
  });
  s.addText("REFLECT 與 VERIFY 是裁決後的兩道品質把關 — 自我反省 + 數據查核。", { x: M, y: 6.35, w: 11.8, h: 0.4, fontFace: F.cjk, fontSize: 13, color: P.muted });
  counter(s);
}

/* ---------- 7 · PHASE DETAIL ---------- */
{
  const s = newSlide();
  s.addText("PHASE BY PHASE", { x: M, y: 1.15, w: 9, h: 0.35, fontFace: F.mono, fontSize: 12, color: P.muted, charSpacing: 3 });
  s.addText("每個階段在做什麼", { x: M, y: 1.55, w: 11.8, h: 0.9, fontFace: F.cjk, fontSize: 33, bold: true, color: P.paper });
  const steps = [
    ["1", "RESEARCH · 研究分析", "四位分析師各自呼叫工具抓真實數據,給出看多／看空／中性傾向。"],
    ["2", "CHALLENGE · 質詢", "風險經理與魔鬼代言人專挑最弱、最樂觀、最缺證據的論點開火。"],
    ["3", "REBUTTAL · 答辯", "分析師針對與自己專業相關的質疑回應,或修正先前看法。"],
    ["4", "VERDICT · 裁決", "主席彙整整場辯論,輸出「建議 / 信心 / 理由」格式的結論草稿。"],
    ["5", "REFLECT · 自我反省（新）", "主席回頭檢視推理是否紮實、一致、有據,重寫一版改良結論。"],
    ["6", "VERIFY · 查核", "確定性數據比對 + LLM 一致性檢查;未支持數字標記、必要時修正。"],
  ];
  const cw = 5.83, rh = 1.18, x0 = M, y0 = 2.7, gx = 0.17, gy = 0.16;
  steps.forEach((st, i) => {
    const c = i % 2, r = Math.floor(i / 2);
    const x = x0 + c * (cw + gx), y = y0 + r * (rh + gy);
    s.addShape(pres.shapes.OVAL, { x, y: y + 0.1, w: 0.66, h: 0.66, fill: { color: P.gold }, line: { type: "none" } });
    s.addText(st[0], { x, y: y + 0.1, w: 0.66, h: 0.66, fontFace: F.serif, fontSize: 26, bold: true, color: "1A1206", align: "center", valign: "middle" });
    s.addText(st[1], { x: x + 0.85, y: y, w: cw - 0.9, h: 0.4, fontFace: F.cjk, fontSize: 14, bold: true, color: P.gold2 });
    s.addText(st[2], { x: x + 0.85, y: y + 0.4, w: cw - 0.9, h: 0.7, fontFace: F.cjk, fontSize: 13, color: P.muted, lineSpacingMultiple: 1.2 });
  });
  counter(s);
}

/* ---------- 8 · QUALITY GATES ---------- */
{
  const s = newSlide();
  s.addText("QUALITY GATES", { x: M, y: 1.15, w: 9, h: 0.35, fontFace: F.mono, fontSize: 12, color: P.muted, charSpacing: 3 });
  s.addText("兩道品質把關", { x: M, y: 1.55, w: 11.8, h: 0.9, fontFace: F.cjk, fontSize: 33, bold: true, color: P.paper });
  const cw = 5.83, cy = 2.85, ch = 2.55;
  card(s, M, cy, cw, ch);
  s.addText("REFLECT · 自我反省", { x: M + 0.35, y: cy + 0.28, w: cw - 0.7, h: 0.4, fontFace: F.cjk, fontSize: 17, bold: true, color: P.gold });
  s.addText([
    { text: "裁決後、查核前,主席先自我批判並重寫(Self-Refine)。只輸出同格式的改良結論,避免把思考草稿當答案。", options: { breakLine: true } },
    { text: "核心預設關閉,由領域層 env 開啟(預設 1 輪、可調)。", options: { color: P.muted, fontFace: F.mono, fontSize: 12 } },
  ], { x: M + 0.35, y: cy + 0.85, w: cw - 0.7, h: 1.5, fontFace: F.cjk, fontSize: 14.5, color: P.paper, lineSpacingMultiple: 1.3 });
  const x2 = M + cw + 0.17;
  card(s, x2, cy, cw, ch);
  s.addText("VERIFY · 確定性查核", { x: x2 + 0.35, y: cy + 0.28, w: cw - 0.7, h: 0.4, fontFace: F.cjk, fontSize: 17, bold: true, color: P.gold });
  s.addText([
    { text: "從結論抽出數字,逐一比對證據帳本(EvidenceLedger)裡的工具結果。", options: { breakLine: true } },
    { text: "未支持的數字永遠標記、絕不偷偷刪除;grounding 失敗則對主席做一次修正回合。", options: {} },
  ], { x: x2 + 0.35, y: cy + 0.85, w: cw - 0.7, h: 1.5, fontFace: F.cjk, fontSize: 14.5, color: P.paper, lineSpacingMultiple: 1.3 });
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: M, y: 5.7, w: cw * 2 + 0.17, h: 0.78, rectRadius: 0.12, fill: { color: P.ink2 }, line: { color: P.gold, width: 1, transparency: 50 } });
  s.addText("設計原則:寧可誠實標記不確定,也不產生看似精確、實則無據的數字。", { x: M, y: 5.7, w: cw * 2 + 0.17, h: 0.78, fontFace: F.cjk, fontSize: 15, color: P.gold2, align: "center", valign: "middle" });
  counter(s);
}

/* ---------- 9 · MODELS / PROVIDER ---------- */
{
  const s = newSlide();
  s.addText("MODEL STRATEGY", { x: M, y: 1.15, w: 9, h: 0.35, fontFace: F.mono, fontSize: 12, color: P.muted, charSpacing: 3 });
  s.addText("兩層模型 · 可切換供應商", { x: M, y: 1.55, w: 11.8, h: 0.9, fontFace: F.cjk, fontSize: 33, bold: true, color: P.paper });
  const rows = [
    ["TOOL-CALLER", "4 位研究分析師 — 需要可靠的 function calling 去抓資料。"],
    ["REASONER", "主席 / 風險 / 魔鬼代言人 / 查核員 — 需要深度推理與格式遵循。"],
    ["PROVIDER", "一個 env 切換 NVIDIA ↔ OpenRouter;皆為 OpenAI 相容,只差 base_url + key + model id。"],
  ];
  let y = 2.85;
  rows.forEach((r) => {
    card(s, M, y, 11.83, 1.0);
    s.addText(r[0], { x: M + 0.35, y: y, w: 2.7, h: 1.0, fontFace: F.mono, fontSize: 14, bold: true, color: P.gold, valign: "middle", charSpacing: 1 });
    s.addText(r[1], { x: M + 3.1, y: y, w: 8.4, h: 1.0, fontFace: F.cjk, fontSize: 15, color: P.paper, valign: "middle", lineSpacingMultiple: 1.2 });
    y += 1.16;
  });
  s.addText("⚠  免費模型有每日配額與限流 → model 可填逗號清單,主模型 429 時自動切換備援。", { x: M, y: 6.45, w: 11.8, h: 0.4, fontFace: F.cjk, fontSize: 13, color: P.muted });
  counter(s);
}

/* ---------- 10 · FRONT-ENDS ---------- */
{
  const s = newSlide();
  s.addText("THREE FRONT-ENDS", { x: M, y: 1.15, w: 9, h: 0.35, fontFace: F.mono, fontSize: 12, color: P.muted, charSpacing: 3 });
  s.addText("同一引擎,三種介面", { x: M, y: 1.55, w: 11.8, h: 0.9, fontFace: F.cjk, fontSize: 33, bold: true, color: P.paper });
  const fe = [
    ["CLI", "main.py", "終端機渲染器,逐字串流辯論過程。"],
    ["Desktop GUI", "gui.py", "Tkinter 視窗,pipeline 卡片 + 即時串流。"],
    ["Web", "web/server.py", "FastAPI + WebSocket,瀏覽器即時儀表板。"],
  ];
  const cw = 3.83, cy = 2.9, ch = 2.4;
  fe.forEach((f, i) => {
    const x = M + i * (cw + 0.17);
    card(s, x, cy, cw, ch);
    s.addText(f[0], { x: x + 0.35, y: cy + 0.3, w: cw - 0.7, h: 0.5, fontFace: F.cjk, fontSize: 22, bold: true, color: P.paper });
    s.addText(f[1], { x: x + 0.35, y: cy + 0.95, w: cw - 0.7, h: 0.35, fontFace: F.mono, fontSize: 13, color: P.gold });
    s.addText(f[2], { x: x + 0.35, y: cy + 1.4, w: cw - 0.7, h: 0.9, fontFace: F.cjk, fontSize: 13.5, color: P.muted, lineSpacingMultiple: 1.25 });
  });
  s.addText([
    { text: "三者跑同一份引擎、產出同一份 ", options: { color: P.paper } },
    { text: "reports/<股號>_<時間>.html", options: { color: P.gold, fontFace: F.mono } },
    { text: "。差別只在「如何把事件畫到畫面上」。", options: { color: P.paper } },
  ], { x: M, y: 5.6, w: 11.8, h: 0.6, fontFace: F.cjk, fontSize: 15, valign: "middle" });
  counter(s);
}

/* ---------- 11 · FINALE ---------- */
{
  const s = pres.addSlide(); s.background = { color: P.ink };
  for (let gx = 1; gx < 8; gx++) s.addShape(pres.shapes.LINE, { x: gx * (W / 8), y: 0, w: 0, h: H, line: { color: P.lineSoft, width: 0.5 } });
  s.addShape(pres.shapes.OVAL, { x: -1.5, y: 4.5, w: 5, h: 5, fill: { type: "none" }, line: { color: P.gold, width: 1, transparency: 60 } });
  s.addText("總結", { x: M, y: 1.5, w: 6, h: 0.4, fontFace: F.mono, fontSize: 13, color: P.gold, charSpacing: 4 });
  s.addText([
    { text: "可重用核心", options: { breakLine: true } },
    { text: "+ 台股領域層", options: { breakLine: true } },
    { text: "+ 事件驅動", options: {} },
  ], { x: M, y: 2.0, w: 11.8, h: 2.8, fontFace: F.cjk, fontSize: 52, bold: true, color: P.paper, lineSpacingMultiple: 1.05 });
  s.addText("研究分析 → 質詢 → 答辯 → 裁決 → 自我反省 → 查核", { x: M, y: 5.2, w: 11.8, h: 0.5, fontFace: F.mono, fontSize: 16, color: P.gold, charSpacing: 1 });
  s.addText("= 一個可擴充、可審計、誠實面對不確定性的 AI 投資委員會。", { x: M, y: 5.85, w: 11.8, h: 0.5, fontFace: F.cjk, fontSize: 18, color: P.muted });
  s.addShape(pres.shapes.LINE, { x: 0, y: H - 0.04, w: W, h: 0, line: { color: P.gold, width: 2.5 } });
  s.addText("11 / 11", { x: W - 2.2, y: 0.3, w: 1.45, h: 0.36, fontFace: F.mono, fontSize: 10, color: P.muted, align: "right" });
}

pres.writeFile({ fileName: "docs/slides/自主投資委員會-系統介紹.pptx" }).then((f) => {
  console.log("WROTE", f);
}).catch((e) => { console.error("ERR", e); process.exit(1); });
