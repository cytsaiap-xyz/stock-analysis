# Categorized Stock Dropdown — Design Spec

**Date:** 2026-06-10
**Status:** Approved (pending spec review)
**Topic:** Replace the free-text ticker input with a categorized dropdown (per market), with an "Others" escape hatch for arbitrary codes. Web app + desktop GUI.

## Goal

Instead of typing a stock code, the user picks from a **categorized dropdown**:
- **TW:** the Taiwan-50 (top 50), grouped by sector (e.g. 2330 台積電 under 半導體).
- **US:** technology stocks grouped by field (CPU, GPU, Memory, EDA, Software, …).
- A trailing **"Others"** option reveals a text box for any code (today's behavior).

The list shown follows the existing TW/US market toggle. Applies to the **web app**
and the **Tkinter desktop GUI**. The CLI keeps its argument.

## Decisions (locked)

1. **UI:** one grouped `<select>` (an `<optgroup>` per category) + an "Others"
   option; selecting Others reveals the text input. (GUI: a read-only
   `ttk.Combobox` of grouped rows + an "Others" row that enables a text Entry.)
2. **Scope:** web app **and** desktop GUI.
3. **Data:** a curated static `stocklist` lives on the market profile (per market),
   returned by `committee_info` for the web and read directly by the GUI.
4. **Lists:** curated snapshots (below); updating them is a data edit, not dynamic.

## Data structure: `MarketProfile.stocklist`

A new field on `MarketProfile`, built by `tw_stocklist()` / `us_stocklist()` in
`committee/markets/tw.py` / `us.py` (same pattern as `ui`):

```python
stocklist = [
    {"label": "<category>", "items": [{"code": "<code>", "name": "<name>"}, ...]},
    ...
]
```

- TW codes are 4-digit TWSE codes; `name` is the Chinese company name. Category
  labels are Chinese.
- US `code` is the ticker; `name` is the company name. Category labels are English.
- `committee_info` returns `stocklist` in its JSON (alongside `ui`, roster). The
  GUI reads `profile.stocklist`.

### TW list (Taiwan-50, by sector)

- **半導體**: 2330 台積電, 2454 聯發科, 2303 聯電, 3711 日月光投控, 2379 瑞昱,
  3034 聯詠, 2327 國巨, 3037 欣興
- **電子/科技硬體**: 2317 鴻海, 2382 廣達, 2357 華碩, 2308 台達電, 3231 緯創,
  4938 和碩, 2356 英業達, 2376 技嘉, 3008 大立光, 2345 智邦, 2395 研華, 2301 光寶科
- **金融**: 2891 中信金, 2882 國泰金, 2881 富邦金, 2886 兆豐金, 2884 玉山金,
  2885 元大金, 2892 第一金, 2880 華南金, 2887 台新金, 2883 開發金, 5880 合庫金
- **電信**: 2412 中華電, 3045 台灣大, 4904 遠傳
- **傳產/塑化/鋼鐵**: 1301 台塑, 1303 南亞, 1326 台化, 6505 台塑化, 2002 中鋼,
  1101 台泥
- **航運**: 2603 長榮, 2615 萬海, 2609 陽明, 2618 長榮航
- **汽車/消費**: 2207 和泰車, 1216 統一, 2912 統一超, 9910 豐泰, 2105 正新

### US list (technology, 11 categories)

- **CPU**: INTC Intel, AMD AMD, ARM Arm Holdings, QCOM Qualcomm
- **GPU / AI Accelerators**: NVDA NVIDIA, AMD AMD, AVGO Broadcom, MRVL Marvell
- **Memory & Storage**: MU Micron, WDC Western Digital, STX Seagate,
  SNDK SanDisk, SIMO Silicon Motion
- **Semiconductor Equipment**: ASML ASML, AMAT Applied Materials, LRCX Lam Research,
  KLAC KLA, TER Teradyne
- **EDA**: SNPS Synopsys, CDNS Cadence
- **Software (Enterprise & Security)**: MSFT Microsoft, ORCL Oracle, ADBE Adobe,
  CRM Salesforce, NOW ServiceNow, INTU Intuit, PANW Palo Alto Networks,
  CRWD CrowdStrike
- **AI & Data Software**: PLTR Palantir, SNOW Snowflake, DDOG Datadog,
  NET Cloudflare, MDB MongoDB
- **AI Infrastructure / Servers**: SMCI Super Micro, DELL Dell, HPE HPE,
  ANET Arista, VRT Vertiv
- **Internet & Cloud**: GOOGL Alphabet, AMZN Amazon, META Meta, NFLX Netflix,
  UBER Uber
- **Devices & Networking**: AAPL Apple, CSCO Cisco, MSI Motorola Solutions,
  JNPR Juniper
- **EV & Autonomous**: TSLA Tesla, RIVN Rivian, LCID Lucid, MBLY Mobileye

(AMD/INTC appear under both CPU and GPU — they make both; that's intentional.)

## Web UI

**Files:** `web/static/index.html`, `web/static/app.js`, `web/static/style.css`,
`committee/markets/tw.py`/`us.py` (stocklist + an `ui.others_label`).

- Replace `<input id="ticker">` with `<select id="stock-select">` and keep a hidden
  `<input id="ticker">` shown only when "Others" is chosen.
- `buildStockList(stocklist, othersLabel)`: clears the `<select>`, appends one
  `<optgroup label="<category>">` per category with `<option value="<code>">code name</option>`,
  then a final `<option value="__other__">{othersLabel}</option>`.
- Change listener on `#stock-select`: when value is `__other__`, unhide `#ticker`
  and focus it; otherwise hide it.
- `start()` resolves the stock: if `#stock-select` is `__other__`, use
  `#ticker.value.trim()`; else use the selected option's value (the code).
- On **market toggle** (`loadRoster`), rebuild the dropdown from the new market's
  `stocklist` and select the first stock; the "Others" label comes from
  `ui.others_label` (localized). This replaces today's example-ticker swap.
- `style.css`: minor rule so the `<select>` matches the control row.

## Desktop GUI

**Files:** `gui.py`.

- Replace the ticker `Entry` with a read-only `ttk.Combobox` whose values are
  `"— <category> —"` separators interleaved with `"<code> <name>"` rows, plus a
  final `"Others / 其他"` row, built from `self.profile.stocklist`. Keep a (hidden
  until needed) `Entry` for the Others case.
- On selection: if "Others", show/enable the Entry; if a `"— <category> —"`
  separator row is picked (these have no leading code), it is **non-actionable** —
  revert the combobox to the previously selected stock; otherwise parse the leading
  code from the combobox value.
- On **market change** (`_on_market_change`), repopulate the combobox from the new
  `self.profile.stocklist` and select its first stock.
- The run uses the resolved code (or the typed Entry value for Others). Threading
  model unchanged.

## Testing

- `tests/test_markets.py` (extend): `get_profile("tw").stocklist` and `us` are
  non-empty lists of `{label, items}`; every item has non-empty `code` and `name`;
  TW codes are 4–6 digits; US codes are alphabetic tickers; a couple of spot checks
  (TW 半導體 contains 2330 台積電; US EDA contains SNPS; US Memory contains SNDK;
  US "AI Infrastructure / Servers" contains SMCI; US EV contains TSLA).
- `tests/test_markets.py`: both `ui` dicts gain `others_label` and the
  `set(tw)==set(us)` key-set test stays green.
- `tests/test_django_web.py` (extend): `committee_info("us")` returns a `stocklist`
  with the expected category labels; `committee_info("tw")` returns Chinese labels.
- Web/GUI dropdown DOM building has no unit harness → a **browser smoke** (select a
  category stock, run; pick "Others", type a code, run) and a GUI import/structural
  check.

## Out of scope

- Live/dynamic constituent fetching (lists are a curated static snapshot).
- CLI (keeps its positional argument).
- Validating that a typed "Others" code exists (the data layer already degrades
  gracefully on a bad code).

## Risks / notes

- The lists are a **point-in-time snapshot** (index membership changes); refreshing
  them is a one-file data edit in `tw.py`/`us.py`.
- `stocklist` is added to `MarketProfile` after `ui` (last field), consistent with
  how `descriptions`/`ui` were added; both builders set it.
