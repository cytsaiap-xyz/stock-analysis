export const meta = {
  name: 'tw_stock_analyzed_workflow',
  description: '台股個股多面向分析:抓真實 TWSE 資料 → 7 面向並行分析 → 主席合成分析師報告 → 數字接地驗證 → 定稿。回傳含 report(繁中 Markdown)的物件。',
  whenToUse: '需要對單一台股做各面向(估值/技術/籌碼/基本面/風險/相對強弱/輿情)分析並產生分析師等級研究報告時。args 傳股票代號字串(例 "2330")、或 {stock_no, months},或直接傳 collect_stock_data.py 產出的已蒐集 JSON 物件(含 valuation 欄位則略過蒐集)。',
  phases: [
    { title: '蒐集', detail: '執行 scripts/collect_stock_data.py 抓真實 TWSE 資料(若 args 已含資料則略過)' },
    { title: '分析', detail: '7 個面向分析師並行,各依真實資料分析一個面向' },
    { title: '合成', detail: '主席整合各面向,撰寫分析師等級研究報告(繁中 Markdown)' },
    { title: '驗證', detail: '逐一核對報告數字是否接地於原始資料(容差 ±2%)' },
    { title: '定稿', detail: '若有未接地/矛盾數字則修正並加接地註記,否則沿用' },
  ],
}

// ---- 解析 args:股票代號字串 / {stock_no, months} / 已蒐集的資料物件 ----
const A = args == null ? {} : args
const isData = A && typeof A === 'object' && A.valuation !== undefined
const stock = isData
  ? (A.stock_no || '2330')
  : (typeof A === 'string' ? A.trim() : (A.stock_no || A.stock || '2330'))
const months = isData
  ? (A.months || 6)
  : (typeof A === 'object' && A.months ? A.months : 6)

const COLLECT_SCHEMA = {
  type: 'object', additionalProperties: false,
  properties: {
    data_json: {
      type: 'string',
      description: 'collect_stock_data.py 的完整 JSON stdout(從第一個 { 到最後一個 }),原樣貼入,不可改動數字',
    },
  },
  required: ['data_json'],
}

const ASPECT_SCHEMA = {
  type: 'object', additionalProperties: false,
  properties: {
    aspect: { type: 'string' },
    stance: { type: 'string', enum: ['偏多', '中性', '偏空'] },
    summary: { type: 'string', description: '2-4 句繁體中文分析,務必引用資料中的真實數字' },
    key_points: { type: 'array', items: { type: 'string' } },
    risks: { type: 'array', items: { type: 'string' } },
  },
  required: ['aspect', 'stance', 'summary', 'key_points', 'risks'],
}

const VERIFY_SCHEMA = {
  type: 'object', additionalProperties: false,
  properties: {
    grounded: { type: 'boolean' },
    flags: {
      type: 'array',
      items: {
        type: 'object', additionalProperties: false,
        properties: { figure: { type: 'string' }, issue: { type: 'string' } },
        required: ['figure', 'issue'],
      },
    },
    consistency_notes: { type: 'string' },
  },
  required: ['grounded', 'flags', 'consistency_notes'],
}

const ASPECTS = [
  { key: '估值面', focus: 'P/E、P/B、現金殖利率;判斷相對偏貴或合理,與成長性是否匹配' },
  { key: '技術面', focus: 'MA5/20/60 排列與趨勢、期間漲幅、量能、RSI14、KD、MACD;多空方向與是否超買' },
  { key: '籌碼面', focus: '三大法人(外資/投信/自營商)最新買賣超股數與合計;主力買賣方向與訊號強度' },
  { key: '基本面', focus: '最新季財報:營收、毛利率、營益率、稅後淨利、ROE、EPS、每股淨值;若月營收 available=false 須誠實說明資料暫無' },
  { key: '風險面', focus: '年化波動率、最大回撤;下檔風險與波動水準' },
  { key: '相對強弱', focus: '個股 vs 加權指數的期間報酬、超額報酬(excess_return_pct)、beta;是否強於大盤' },
  { key: '輿情面', focus: '近期新聞標題與摘要呈現的市場焦點與情緒(偏多/中性/偏空)' },
]

// ---- 階段一:蒐集真實 TWSE 資料(args 已含資料則略過)----
let D = isData ? A : null
if (!D) {
  phase('蒐集')
  log(`蒐集 ${stock} 的真實 TWSE 資料(近 ${months} 個月)`)
  const collected = await agent(
    `你的任務是蒐集台股資料。請執行以下指令(Windows/PowerShell 與 bash 皆可):\n` +
    `    python scripts/collect_stock_data.py ${stock} ${months}\n` +
    `它會對臺灣證交所做唯讀查詢並印出單一 JSON。\n` +
    `把該指令完整 stdout(從第一個 { 到最後一個 })原樣放入 data_json 欄位,不要改動任何數字、不要加說明文字。\n` +
    `注意:若第一次執行被「Fact-Forcing Gate」攔下,請先用純文字陳述:(1) 使用者請求一句話、(2) 此指令產生什麼,然後重試同一指令。`,
    { label: `蒐集:${stock}`, phase: '蒐集', schema: COLLECT_SCHEMA },
  )
  try {
    const raw = collected.data_json
    D = JSON.parse(raw.slice(raw.indexOf('{'), raw.lastIndexOf('}') + 1))
  } catch (e) {
    return { error: `資料蒐集或 JSON 解析失敗:${e.message}`, stock_no: stock }
  }
}

const ctx = JSON.stringify(D)
const name = (D && D.company_name) || ''
const collectedDate = (D && D.collected_date) || '最新交易日'

// ---- 階段二:7 面向並行分析 ----
phase('分析')
log(`開始分析 ${name}(${stock})— 7 個面向並行`)
const analyses = (await parallel(ASPECTS.map((a) => () =>
  agent(
    `你是台股賣方(sell-side)研究分析師。只能根據以下「真實 TWSE 資料」(JSON)分析【${a.key}】這一個面向,不可杜撰任何數字。\n` +
    `分析聚焦:${a.focus}\n` +
    `規則:(1)所有數字必須來自資料 JSON 的真實值;(2)若某欄位為 null 或 available=false,就誠實說「資料暫無」;` +
    `(3)用繁體中文;(4)stance 三選一:偏多/中性/偏空。\n\n` +
    `真實資料 JSON:\n${ctx}`,
    { label: `分析:${a.key}`, phase: '分析', schema: ASPECT_SCHEMA },
  ),
))).filter(Boolean)

const analysisDigest = analyses.map((r) =>
  `### ${r.aspect}(立場:${r.stance})\n${r.summary}\n重點:${(r.key_points || []).join(';')}\n風險:${(r.risks || []).join(';')}`
).join('\n\n')

// ---- 階段三:主席合成分析師報告 ----
phase('合成')
const report = await agent(
  `你是台股投資委員會主席,要把以下 7 個面向分析整合成一份「分析師等級(analyst-grade)研究報告」。\n` +
  `輸出格式:繁體中文 Markdown,只輸出報告本身(不要任何前言或結語客套)。\n\n` +
  `報告結構必須包含:\n` +
  `1. 標題(含 ${name} ${stock}、日期 ${collectedDate})\n` +
  `2. **評級**(買進 / 中立 / 賣出)+ 一句話投資論點\n` +
  `3. **關鍵數據表**(Markdown 表格:收盤價、P/E、P/B、殖利率、ROE、EPS、毛利率、年化波動率、三大法人合計買賣超、相對大盤超額報酬)— 數字一律取自真實資料\n` +
  `4. **各面向解析**:估值 / 技術 / 籌碼 / 基本面 / 風險 / 相對強弱 / 輿情(每段 2-4 句)\n` +
  `5. **主要風險**(條列)\n` +
  `6. **結論與目標價區間**:可基於 P/E 或技術區間給推估區間,但必須明確標註「(推估)」\n\n` +
  `鐵則:除了明確標註「(推估)」的目標價外,所有數字都必須能在下方真實資料中找到;資料暫無者誠實寫「資料暫無」,絕不杜撰。\n\n` +
  `=== 各面向分析摘要 ===\n${analysisDigest}\n\n` +
  `=== 真實資料 JSON(數字唯一來源)===\n${ctx}`,
  { label: '合成報告', phase: '合成' },
)

// ---- 階段四:數字接地驗證 ----
phase('驗證')
const verdict = await agent(
  `你是嚴格的查核員。下面有一份研究報告草稿與其唯一的真實資料來源 JSON。\n` +
  `任務:抽取報告中出現的每一個數據型數字(股價、百分比、比率、買賣超股數、EPS 等),逐一核對是否能在 JSON 中找到對應值(數值容差 ±2%)。\n` +
  `規則:(1)明確標註「(推估)」的目標價/情境數字不需接地,略過;(2)找不到對應、或與 JSON 矛盾的,放進 flags(figure=該數字、issue=問題);` +
  `(3)全部接地則 grounded=true 且 flags 為空。consistency_notes 寫整體一致性評語(繁中)。\n\n` +
  `=== 報告草稿 ===\n${report}\n\n=== 真實資料 JSON ===\n${ctx}`,
  { label: '接地驗證', phase: '驗證', schema: VERIFY_SCHEMA },
)

// ---- 階段五:定稿(僅在有未接地/矛盾數字時修正)----
phase('定稿')
let final = report
const flags = (verdict && verdict.flags) || []
if (!verdict.grounded || flags.length > 0) {
  log(`驗證發現 ${flags.length} 個待處理數字,進行一輪定稿修正`)
  final = await agent(
    `你是報告主席。查核員標記了以下數字有「未接地/矛盾」問題,請修正報告:\n` +
    `${JSON.stringify(flags, null, 2)}\n\n` +
    `修正規則:(1)把被標記的數字改為真實資料 JSON 中的正確值;若資料中確實沒有,改寫為「資料暫無」或標為「(推估)」;` +
    `(2)在報告最末新增「## 接地註記」,逐項說明每個被標記數字的處理方式;(3)其餘內容保持不變。\n` +
    `只輸出完整修正後的報告 Markdown(繁體中文)。\n\n` +
    `=== 原報告 ===\n${report}\n\n=== 真實資料 JSON ===\n${ctx}`,
    { label: '定稿修正', phase: '定稿' },
  )
} else {
  log('驗證通過:報告所有數字均接地於真實資料')
}

return {
  stock_no: stock,
  company_name: name,
  collected_date: collectedDate,
  report: final,
  grounded: !!verdict.grounded,
  flags_count: flags.length,
  consistency_notes: (verdict && verdict.consistency_notes) || '',
  aspects: analyses.map((a) => ({ aspect: a.aspect, stance: a.stance })),
}
