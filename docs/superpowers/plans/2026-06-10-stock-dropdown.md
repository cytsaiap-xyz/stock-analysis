# Categorized Stock Dropdown Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the free-text ticker input with a per-market categorized dropdown (TW sectors / US tech categories) plus an "Others" option that reveals a text box — in the web app and the desktop GUI.

**Architecture:** A curated `stocklist` (list of `{label, items:[{code,name}]}`) lives on each `MarketProfile`, built in `committee/markets/tw.py`/`us.py`. `committee_info` returns it; `app.js` builds a grouped `<select>`; the Tkinter GUI builds a `ttk.Combobox`. Both follow the existing TW/US market toggle and add an "Others" escape hatch.

**Tech Stack:** Python 3.12 (`.venv/bin/python`), Django/Channels, vanilla JS, Tkinter, pytest.

**Spec:** `docs/superpowers/specs/2026-06-10-stock-dropdown-design.md`

**Conventions:** Test with `.venv/bin/python -m pytest`. Branch `feat/stock-dropdown`. The web/GUI dropdown building has no unit harness — verified by a browser smoke + structural checks; the data + `committee_info` are unit-tested.

---

## File Structure

**Modify:**
- `committee/markets/base.py` — add `stocklist` field to `MarketProfile`
- `committee/markets/tw.py` — `tw_stocklist()` + `others_label` in `tw_ui()`
- `committee/markets/us.py` — `us_stocklist()` + `others_label` in `us_ui()`
- `committee/markets/__init__.py` — builders pass `stocklist=`
- `committee_web/views.py` — `committee_info` returns `stocklist`
- `web/static/index.html`, `web/static/app.js`, `web/static/style.css` — grouped select + Others
- `gui.py` — `ttk.Combobox` + Others entry
- `tests/test_markets.py`, `tests/test_django_web.py`

---

## Task 1: `MarketProfile.stocklist` + curated lists

**Files:** Modify `committee/markets/base.py`, `tw.py`, `us.py`, `__init__.py`; Test `tests/test_markets.py`

- [ ] **Step 1: Write failing tests** — append to `tests/test_markets.py`:

```python
def test_profiles_carry_stocklist():
    from committee.markets import get_profile
    for m in ("tw", "us"):
        sl = get_profile(m).stocklist
        assert isinstance(sl, list) and sl
        for cat in sl:
            assert cat["label"] and isinstance(cat["items"], list) and cat["items"]
            for it in cat["items"]:
                assert it["code"] and it["name"]


def test_tw_stocklist_has_semiconductors_with_tsmc():
    from committee.markets import get_profile
    sl = get_profile("tw").stocklist
    semi = next(c for c in sl if c["label"] == "半導體")
    assert {"code": "2330", "name": "台積電"} in semi["items"]
    # TW codes are 4-6 digits
    for c in sl:
        for it in c["items"]:
            assert it["code"].isdigit() and 4 <= len(it["code"]) <= 6


def test_us_stocklist_categories_and_placements():
    from committee.markets import get_profile
    sl = get_profile("us").stocklist
    labels = [c["label"] for c in sl]
    assert "CPU" in labels and "EDA" in labels and "EV & Autonomous" in labels
    codes = {c["label"]: [it["code"] for it in c["items"]] for c in sl}
    assert "SNPS" in codes["EDA"] and "CDNS" in codes["EDA"]
    assert "SNDK" in codes["Memory & Storage"]
    assert "SMCI" in codes["AI Infrastructure / Servers"]
    assert "PLTR" in codes["AI & Data Software"]
    assert "TSLA" in codes["EV & Autonomous"]
    # US codes are alphabetic tickers
    for c in sl:
        for it in c["items"]:
            assert it["code"].isalpha()


def test_ui_has_others_label_both_markets():
    from committee.markets import get_profile
    assert get_profile("tw").ui["others_label"]
    assert get_profile("us").ui["others_label"]
```

- [ ] **Step 2: Run, verify fail** — `.venv/bin/python -m pytest tests/test_markets.py -k "stocklist or others_label" -v` → FAIL.

- [ ] **Step 3: Add the `stocklist` field** to `committee/markets/base.py` — append it as the LAST field of `MarketProfile`:

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
    stocklist: list
```

- [ ] **Step 4: Add `tw_stocklist()` + `others_label`** to `committee/markets/tw.py`:

In `tw_ui()`'s dict add: `"others_label": "其他(自行輸入)",`. Then append:

```python
def tw_stocklist() -> list:
    def cat(label, *pairs):
        return {"label": label, "items": [{"code": c, "name": n} for c, n in pairs]}
    return [
        cat("半導體", ("2330", "台積電"), ("2454", "聯發科"), ("2303", "聯電"),
            ("3711", "日月光投控"), ("2379", "瑞昱"), ("3034", "聯詠"),
            ("2327", "國巨"), ("3037", "欣興")),
        cat("電子/科技硬體", ("2317", "鴻海"), ("2382", "廣達"), ("2357", "華碩"),
            ("2308", "台達電"), ("3231", "緯創"), ("4938", "和碩"), ("2356", "英業達"),
            ("2376", "技嘉"), ("3008", "大立光"), ("2345", "智邦"), ("2395", "研華"),
            ("2301", "光寶科")),
        cat("金融", ("2891", "中信金"), ("2882", "國泰金"), ("2881", "富邦金"),
            ("2886", "兆豐金"), ("2884", "玉山金"), ("2885", "元大金"), ("2892", "第一金"),
            ("2880", "華南金"), ("2887", "台新金"), ("2883", "開發金"), ("5880", "合庫金")),
        cat("電信", ("2412", "中華電"), ("3045", "台灣大"), ("4904", "遠傳")),
        cat("傳產/塑化/鋼鐵", ("1301", "台塑"), ("1303", "南亞"), ("1326", "台化"),
            ("6505", "台塑化"), ("2002", "中鋼"), ("1101", "台泥")),
        cat("航運", ("2603", "長榮"), ("2615", "萬海"), ("2609", "陽明"), ("2618", "長榮航")),
        cat("汽車/消費", ("2207", "和泰車"), ("1216", "統一"), ("2912", "統一超"),
            ("9910", "豐泰"), ("2105", "正新")),
    ]
```

- [ ] **Step 5: Add `us_stocklist()` + `others_label`** to `committee/markets/us.py`:

In `us_ui()`'s dict add: `"others_label": "Others (enter code)",`. Then append:

```python
def us_stocklist() -> list:
    def cat(label, *pairs):
        return {"label": label, "items": [{"code": c, "name": n} for c, n in pairs]}
    return [
        cat("CPU", ("INTC", "Intel"), ("AMD", "AMD"), ("ARM", "Arm Holdings"),
            ("QCOM", "Qualcomm")),
        cat("GPU / AI Accelerators", ("NVDA", "NVIDIA"), ("AMD", "AMD"),
            ("AVGO", "Broadcom"), ("MRVL", "Marvell")),
        cat("Memory & Storage", ("MU", "Micron"), ("WDC", "Western Digital"),
            ("STX", "Seagate"), ("SNDK", "SanDisk"), ("SIMO", "Silicon Motion")),
        cat("Semiconductor Equipment", ("ASML", "ASML"), ("AMAT", "Applied Materials"),
            ("LRCX", "Lam Research"), ("KLAC", "KLA"), ("TER", "Teradyne")),
        cat("EDA", ("SNPS", "Synopsys"), ("CDNS", "Cadence")),
        cat("Software (Enterprise & Security)", ("MSFT", "Microsoft"), ("ORCL", "Oracle"),
            ("ADBE", "Adobe"), ("CRM", "Salesforce"), ("NOW", "ServiceNow"),
            ("INTU", "Intuit"), ("PANW", "Palo Alto Networks"), ("CRWD", "CrowdStrike")),
        cat("AI & Data Software", ("PLTR", "Palantir"), ("SNOW", "Snowflake"),
            ("DDOG", "Datadog"), ("NET", "Cloudflare"), ("MDB", "MongoDB")),
        cat("AI Infrastructure / Servers", ("SMCI", "Super Micro"), ("DELL", "Dell"),
            ("HPE", "HPE"), ("ANET", "Arista"), ("VRT", "Vertiv")),
        cat("Internet & Cloud", ("GOOGL", "Alphabet"), ("AMZN", "Amazon"),
            ("META", "Meta"), ("NFLX", "Netflix"), ("UBER", "Uber")),
        cat("Devices & Networking", ("AAPL", "Apple"), ("CSCO", "Cisco"),
            ("MSI", "Motorola Solutions"), ("JNPR", "Juniper")),
        cat("EV & Autonomous", ("TSLA", "Tesla"), ("RIVN", "Rivian"),
            ("LCID", "Lucid"), ("MBLY", "Mobileye")),
    ]
```

- [ ] **Step 6: Wire `stocklist` into the builders** in `committee/markets/__init__.py`. In `build_tw_profile`, extend the tw import to include `tw_stocklist` and add `stocklist=tw_stocklist()` as the final `MarketProfile(...)` argument; same for `build_us_profile` with `us_stocklist`. Example (TW; mirror for US):
```python
    from committee.markets.tw import (tw_prompts, tw_templates, tw_labels,
                                      tw_tool_descriptions, tw_ui, tw_stocklist)
    return MarketProfile(market="tw", lang="zh-TW", client=TwseClient(cache_dir=CACHE_DIR),
                         committee=build_committee(tw_prompts()), templates=tw_templates(),
                         labels=tw_labels(), descriptions=tw_tool_descriptions(),
                         ui=tw_ui(), stocklist=tw_stocklist())
```

- [ ] **Step 7: Run, verify pass** — `.venv/bin/python -m pytest tests/test_markets.py -v` → all PASS (incl. the existing `test_profiles_carry_localized_ui_text`, since `others_label` is in BOTH ui dicts). Full suite `.venv/bin/python -m pytest -q` → PASS.

- [ ] **Step 8: Commit**
```bash
git add committee/markets/base.py committee/markets/tw.py committee/markets/us.py committee/markets/__init__.py tests/test_markets.py
git commit -m "feat: per-market curated stocklist on MarketProfile"
```

---

## Task 2: `committee_info` returns `stocklist`

**Files:** Modify `committee_web/views.py`; Test `tests/test_django_web.py`

- [ ] **Step 1: Write failing tests** — append to `tests/test_django_web.py`:

```python
def test_committee_info_returns_us_stocklist():
    d = _client().get("/api/committee?market=us").json()
    labels = [c["label"] for c in d["stocklist"]]
    assert "CPU" in labels and "EDA" in labels
    eda = next(c for c in d["stocklist"] if c["label"] == "EDA")
    assert any(it["code"] == "SNPS" for it in eda["items"])


def test_committee_info_returns_tw_stocklist_chinese():
    d = _client().get("/api/committee?market=tw").json()
    labels = [c["label"] for c in d["stocklist"]]
    assert "半導體" in labels
```

- [ ] **Step 2: Run, verify fail** — `.venv/bin/python -m pytest tests/test_django_web.py -k stocklist -v` → FAIL (no `stocklist` key).

- [ ] **Step 3: Add `stocklist` to the response** in `committee_web/views.py` `committee_info` — add one key to the returned `JsonResponse` dict:
```python
        "ui": profile.ui,
        "stocklist": profile.stocklist,
    })
```
(Insert `"stocklist": profile.stocklist,` right after the existing `"ui": profile.ui,` line.)

- [ ] **Step 4: Run, verify pass** — `.venv/bin/python -m pytest tests/test_django_web.py -v` → PASS. Full suite → PASS.

- [ ] **Step 5: Commit**
```bash
git add committee_web/views.py tests/test_django_web.py
git commit -m "feat: committee_info returns the market stocklist"
```

---

## Task 3: Web grouped dropdown (`index.html` + `app.js` + `style.css`)

**Files:** Modify `web/static/index.html`, `web/static/app.js`, `web/static/style.css`

- [ ] **Step 1: Replace the ticker input with a select + hidden text box** in `web/static/index.html`. The current controls block is:
```html
    <label id="ticker-label">股票代號:</label>
    <input id="ticker" type="text" value="2330" maxlength="6">
    <button id="run">開始分析</button>
```
Replace with:
```html
    <label id="ticker-label">股票代號:</label>
    <select id="stock-select"></select>
    <input id="ticker" type="text" maxlength="6" class="hidden" placeholder="代號 / code">
    <button id="run">開始分析</button>
```

- [ ] **Step 2: Add the stock-select element + build/select logic** in `web/static/app.js`.

(a) Add the element handle near the other `$()` handles at the top (after `const tickerEl = $("ticker");`):
```javascript
const stockSelect = $("stock-select");
```

(b) Add these two functions (place them near `buildPipeline`):
```javascript
function buildStockList() {
  stockSelect.innerHTML = "";
  for (const catg of (roster.stocklist || [])) {
    const og = document.createElement("optgroup");
    og.label = catg.label;
    for (const it of catg.items) {
      const o = document.createElement("option");
      o.value = it.code;
      o.textContent = it.code + " " + it.name;
      og.appendChild(o);
    }
    stockSelect.appendChild(og);
  }
  const other = document.createElement("option");
  other.value = "__other__";
  other.textContent = ui.others_label;
  stockSelect.appendChild(other);
  stockSelect.selectedIndex = 0;       // first stock of the first category
  tickerEl.classList.add("hidden");
}

function selectedStock() {
  if (stockSelect.value === "__other__") return tickerEl.value.trim();
  return stockSelect.value;
}
```

(c) Reveal the text box when "Others" is chosen — add this listener near the bottom (with the other `addEventListener` calls):
```javascript
stockSelect.addEventListener("change", () => {
  if (stockSelect.value === "__other__") { tickerEl.classList.remove("hidden"); tickerEl.focus(); }
  else { tickerEl.classList.add("hidden"); }
});
```

(d) In `loadRoster`, replace the example-ticker swap block with a `buildStockList()` call. The current tail of `loadRoster` is:
```javascript
  applyUi();
  const others = ["2330", "AAPL"];
  if (!tickerEl.value.trim() || others.includes(tickerEl.value.trim())) {
    tickerEl.value = ui.example_ticker;
  }
  buildPipeline();
}
```
Replace with:
```javascript
  applyUi();
  buildStockList();
  buildPipeline();
}
```

(e) In `start`, resolve the stock from the dropdown. The current first line is
`const stock = (tickerEl.value || ui.example_ticker).trim();`. Replace with:
```javascript
  const stock = selectedStock();
  if (!stock) return;                  // Others selected but no code typed
```

(f) `applyUi` currently sets `verdictEl.textContent = ui.verdict_placeholder;` — leave it. It no longer sets the ticker value (handled by buildStockList).

- [ ] **Step 3: CSS** — append to `web/static/style.css`:
```css
#stock-select { padding: 3px 6px; max-width: 320px; }
.hidden { display: none; }
```
(The `.hidden` rule may already exist — if `grep -n "\.hidden" web/static/style.css` finds it, do NOT add a duplicate; keep just the `#stock-select` rule.)

- [ ] **Step 4: Structural verification**
```bash
cd /Users/steventsai/Documents/Claude_Project/stock-ana/stock-analysis
.venv/bin/python -c "s=open('web/static/index.html').read(); assert 'id=\"stock-select\"' in s and 'id=\"ticker\"' in s and 'class=\"hidden\"' in s; print('index ok')"
.venv/bin/python -c "s=open('web/static/app.js').read(); assert 'buildStockList' in s and 'selectedStock' in s and 'stockSelect' in s and '__other__' in s; print('app.js ok')"
command -v node >/dev/null 2>&1 && node --check web/static/app.js && echo "app.js syntax ok" || echo "(node not available)"
.venv/bin/python -m pytest -q 2>&1 | tail -1
```
Expected: `index ok`, `app.js ok`, `app.js syntax ok` (if node), full suite PASS.

- [ ] **Step 5: Manual browser smoke (operator/controller — not a unit test).** Start `manage.py runserver`; confirm: the dropdown shows category groups with `code name` options; picking a TW stock then running works; toggling US rebuilds the list (CPU/GPU/…); picking "Others" reveals the text box and a typed code runs.

- [ ] **Step 6: Commit**
```bash
git add web/static/index.html web/static/app.js web/static/style.css
git commit -m "feat: web grouped stock dropdown + Others text box"
```

---

## Task 4: Desktop GUI dropdown (`gui.py`)

**Files:** Modify `gui.py`

- [ ] **Step 1: Read `gui.py`** — the controls are built in `_build_widgets` (the `top` frame holds `self.ticker_label`, `self.ticker` Entry, `self.btn`, the TW/US radios). `_on_analyze` reads `self.ticker.get()`. `_on_market_change` re-localizes widgets. You will replace the `self.ticker` Entry with a `ttk.Combobox` + a hidden Entry for Others.

- [ ] **Step 2: Import ttk** — add to the imports at the top of `gui.py`:
```python
from tkinter import ttk
```

- [ ] **Step 3: Replace the ticker Entry with a combobox in `_build_widgets`.** The current lines are:
```python
        self.ticker = tk.Entry(top, width=10)
        self.ticker.insert(0, ui["example_ticker"])
        self.ticker.pack(side="left", padx=4)
        self.ticker.bind("<Return>", lambda _e: self._on_analyze())
```
Replace with:
```python
        self.stock_combo = ttk.Combobox(top, state="readonly", width=26)
        self.stock_combo.pack(side="left", padx=4)
        self.stock_combo.bind("<<ComboboxSelected>>", self._on_stock_select)
        self.ticker = tk.Entry(top, width=10)   # shown only when "Others" is picked
        self.ticker.bind("<Return>", lambda _e: self._on_analyze())
        self._last_stock = None
        self._populate_stocks()
```

- [ ] **Step 4: Add the combobox helpers** (place these methods on the `CommitteeGUI` class, e.g. after `_on_market_change`):
```python
    def _build_stock_values(self):
        """Return (values, first_stock_string) for the combobox from the profile's
        stocklist: '— <category> —' separators + '<code> <name>' rows + Others."""
        values, first = [], None
        for catg in self.profile.stocklist:
            values.append("— {} —".format(catg["label"]))
            for it in catg["items"]:
                v = "{} {}".format(it["code"], it["name"])
                values.append(v)
                if first is None:
                    first = v
        values.append(self.profile.ui["others_label"])
        return values, first

    def _populate_stocks(self):
        values, first = self._build_stock_values()
        self.stock_combo.config(values=values)
        if first:
            self.stock_combo.set(first)
            self._last_stock = first
        self.ticker.pack_forget()

    def _on_stock_select(self, _e=None):
        v = self.stock_combo.get()
        if v == self.profile.ui["others_label"]:
            self.ticker.pack(side="left", padx=4)
            self.ticker.focus_set()
        elif v.startswith("— "):                # separator rows are non-actionable
            if self._last_stock:
                self.stock_combo.set(self._last_stock)
        else:
            self._last_stock = v
            self.ticker.pack_forget()

    def _selected_stock(self):
        v = self.stock_combo.get()
        if v == self.profile.ui["others_label"]:
            return self.ticker.get().strip()
        if v.startswith("— "):
            return ""
        return v.split(" ", 1)[0]               # the leading code
```

- [ ] **Step 5: Repopulate on market change.** In `_on_market_change`, after the label updates and BEFORE the pipeline rebuild, replace the existing example-ticker block:
```python
        cur = self.ticker.get().strip()
        if not cur or cur in ("2330", "AAPL"):
            self.ticker.delete(0, "end")
            self.ticker.insert(0, ui["example_ticker"])
```
with:
```python
        self.ticker.delete(0, "end")
        self._populate_stocks()
```

- [ ] **Step 6: Use the selected stock in `_on_analyze`.** The current line is
`stock = self.ticker.get().strip() or ui["example_ticker"]`. Replace with:
```python
        stock = self._selected_stock()
        if not stock:
            return
```
(Place it where `stock` is first computed; keep the rest of `_on_analyze` unchanged.)

- [ ] **Step 7: Verify**
```bash
cd /Users/steventsai/Documents/Claude_Project/stock-ana/stock-analysis
.venv/bin/python -c "import gui; print('gui import ok')"
.venv/bin/python -m pytest tests/test_gui_format.py -q 2>&1 | tail -1
.venv/bin/python -m pytest -q 2>&1 | tail -1
.venv/bin/python - <<'PY'
src = open("gui.py", encoding="utf-8").read()
for needed in ["ttk.Combobox", "_build_stock_values", "_populate_stocks",
               "_selected_stock", "self.profile.stocklist", "_on_stock_select"]:
    assert needed in src, "missing: " + needed
print("gui dropdown ok")
PY
```
Expected: `gui import ok`, gui-format tests PASS, full suite PASS, `gui dropdown ok`.

- [ ] **Step 8: Manual GUI smoke (operator — not a unit test).** `.venv/bin/python gui.py`: the combobox lists categories + stocks; selecting a stock then Run works; toggling US repopulates; selecting "Others" shows the entry and a typed code runs.

- [ ] **Step 9: Commit**
```bash
git add gui.py
git commit -m "feat: desktop GUI categorized stock combobox + Others entry"
```

---

## Self-Review Notes

- **Spec coverage:** `stocklist` data + `others_label` (T1), `committee_info` returns it (T2), web grouped `<select>` + Others reveal + market rebuild (T3), GUI `ttk.Combobox` + separators non-actionable + Others entry + market repopulate (T4). The exact TW (7 sectors) and US (11 categories, with SNDK→Memory, SMCI→AI Infra, PLTR→AI Software, TSLA→EV) lists are in T1. All spec sections map to a task.
- **Type/name consistency:** `stocklist` is a `list` of `{"label", "items":[{"code","name"}]}` defined in T1 and consumed identically in T2/T3/T4. `ui["others_label"]` added to both markets (T1); the web option value sentinel is `"__other__"` (T3) and the GUI uses the `others_label` string + `"— "` separator prefix (T4). `MarketProfile.stocklist` is the last dataclass field (T1).
- **Backward-compat / existing tests:** `others_label` is added to BOTH `ui` dicts so `test_profiles_carry_localized_ui_text` (`set(tw)==set(us)`) stays green; no test constructs `MarketProfile(...)` positionally (the new field is appended).
- **Placeholder scan:** none — full data and code in every step.
- **Out of scope (per spec):** dynamic constituent fetching, CLI, validating typed Others codes.
