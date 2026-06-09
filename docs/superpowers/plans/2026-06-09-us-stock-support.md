# US Stock Support Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Analyze both Taiwan- and US-listed stocks in the same committee engine, auto-detecting the market from the ticker — TW reports in Traditional Chinese, US reports in English.

**Architecture:** A `MarketProfile` per market bundles the data client, agent prompts, task templates, tool descriptions, and report labels. Front-ends call `get_profile(detect_market(symbol))` and stay market-agnostic. `agentcore/` is untouched; the TW data clients (`twse.py`, `indicators.py`, `news.py`) are reused unchanged. US data comes from `yfinance` (market data) + SEC EDGAR (financial statements).

**Tech Stack:** Python 3.9, `requests`, `yfinance` (new), SEC EDGAR REST, pytest with hand-rolled fakes (no `unittest.mock`).

**Spec:** `docs/superpowers/specs/2026-06-09-us-stock-support-design.md`

**Conventions from this codebase (follow exactly):**
- Tests use tiny hand-rolled fake classes near the top of the file (`_FakeTwse`, `_FakeDDGS`), never `unittest.mock`.
- Data-client methods never raise on missing data — they return `{"available": False, "note": "..."}`.
- LLMs pass numeric args as strings; coerce with `int(...)` defensively.
- Run the suite with `pytest -q` (pytest.ini sets `-m "not live" -p no:dash`).
- Commit after every green step.

---

## File Structure

**Create:**
- `committee/markets/__init__.py` — `detect_market(symbol)`, `get_profile(market)`
- `committee/markets/base.py` — `Templates`, `Prompts`, `ToolDescriptions`, `ReportLabels`, `MarketProfile` dataclasses
- `committee/markets/tw.py` — `build_tw_profile()` (Chinese)
- `committee/markets/us.py` — `build_us_profile()` (English)
- `committee/data/us_market.py` — `UsClient`
- `tests/test_detect_market.py`
- `tests/test_us_market.py`
- `tests/test_markets.py`

**Modify:**
- `committee/agents.py` — accept a `Prompts` + `Templates` set; keep TW default
- `committee/domain_tools.py` — accept per-market `ToolDescriptions`; keep TW default
- `committee/report.py` — `build_html(..., labels=...)`; bilingual rating parse + labels
- `main.py`, `gui.py`, `web/server.py` — wire `MarketProfile`
- `scripts/collect_stock_data.py` — route by market
- `requirements.txt` — add `yfinance`
- `tests/test_report.py` — add English rating-parse test

---

## Phase 1 — Market detection

### Task 1: `detect_market`

**Files:**
- Create: `committee/markets/__init__.py`
- Test: `tests/test_detect_market.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_detect_market.py
import pytest

from committee.markets import detect_market


@pytest.mark.parametrize("symbol", ["2330", "0050", "00878", "6488", " 2330 ", "2330.TW", "2454.TWO"])
def test_taiwan_codes_detected_as_tw(symbol):
    assert detect_market(symbol) == "tw"


@pytest.mark.parametrize("symbol", ["AAPL", "aapl", "TSLA", "NVDA", "BRK.B", "BRK-B", "F", "GOOGL"])
def test_us_tickers_detected_as_us(symbol):
    assert detect_market(symbol) == "us"


def test_empty_symbol_raises():
    with pytest.raises(ValueError):
        detect_market("")
```

- [ ] **Step 2: Run it, verify it fails**

Run: `pytest tests/test_detect_market.py -v`
Expected: FAIL — `ImportError: cannot import name 'detect_market'`.

- [ ] **Step 3: Implement `detect_market`**

```python
# committee/markets/__init__.py
"""Market routing: detect a symbol's market and build its MarketProfile."""
import re

_TW_RE = re.compile(r"^\d{4,6}(\.TWO?|\.TW)?$")


def detect_market(symbol: str) -> str:
    """Return "tw" or "us" for a stock symbol, inferred from its format.

    Taiwan codes are 4-6 digits (optionally suffixed .TW/.TWO); anything
    containing letters is treated as a US ticker.
    """
    s = (symbol or "").strip().upper()
    if not s:
        raise ValueError("empty symbol")
    if _TW_RE.match(s):
        return "tw"
    return "us"
```

- [ ] **Step 4: Run it, verify it passes**

Run: `pytest tests/test_detect_market.py -v`
Expected: PASS (all parametrized cases).

- [ ] **Step 5: Commit**

```bash
git add committee/markets/__init__.py tests/test_detect_market.py
git commit -m "feat: detect_market routes ticker to tw/us"
```

---

## Phase 2 — Profile dataclasses

### Task 2: Profile interface dataclasses

**Files:**
- Create: `committee/markets/base.py`
- Test: `tests/test_markets.py` (started here, extended later)

- [ ] **Step 1: Write the failing test**

```python
# tests/test_markets.py
from committee.markets.base import (Templates, Prompts, ToolDescriptions,
                                    ReportLabels, MarketProfile)


def test_dataclasses_construct_with_expected_fields():
    t = Templates(analyst="a", challenge="c", rebuttal="r", reflect="rf",
                  verify="v", correction="co")
    assert t.analyst == "a" and t.correction == "co"

    p = Prompts(fundamental="f", technical="t", institutional="i", news="n",
                risk="rk", skeptic="sk", chair="ch", verifier="vf")
    assert p.chair == "ch"

    td = ToolDescriptions(stock_param="sp", get_valuation="gv",
                          get_technical_indicators="gti",
                          get_institutional_flows="gif",
                          get_monthly_revenue="gmr", get_risk_metrics="grm",
                          get_relative_strength="grs", get_financials="gf",
                          search_news="sn")
    assert td.get_valuation == "gv"

    labels = ReportLabels(lang="en", text={"k": "v"}, rating_class={"BUY": "buy"},
                          recommend_label="Recommendation", confidence_label="Confidence",
                          agent_names={"chair": "Chair"}, phase_names={"RESEARCH": "Research"},
                          aspect_order=[("fundamental", "Fundamentals")],
                          institutional_kind="ownership", revenue_kind="quarterly",
                          disclaimer="d")
    assert labels.institutional_kind == "ownership"
```

- [ ] **Step 2: Run it, verify it fails**

Run: `pytest tests/test_markets.py -v`
Expected: FAIL — `ModuleNotFoundError: committee.markets.base`.

- [ ] **Step 3: Implement the dataclasses**

```python
# committee/markets/base.py
"""Market-profile interface: the bundle of market-specific config every market
fills in. agentcore/ stays domain-neutral; all market text lives behind these."""
from dataclasses import dataclass
from typing import Any, Dict, List, Tuple


@dataclass
class Templates:
    """The six domain task templates injected into the (neutral) Orchestrator."""
    analyst: str
    challenge: str
    rebuttal: str
    reflect: str
    verify: str
    correction: str


@dataclass
class Prompts:
    """System prompts for the 8 committee roles."""
    fundamental: str
    technical: str
    institutional: str
    news: str
    risk: str
    skeptic: str
    chair: str
    verifier: str


@dataclass
class ToolDescriptions:
    """LLM-facing descriptions for each registered tool + the stock_no param.

    Tool *names* are identical across markets so report buckets and the roster
    stay shared; only the descriptions localize.
    """
    stock_param: str
    get_valuation: str
    get_technical_indicators: str
    get_institutional_flows: str
    get_monthly_revenue: str
    get_risk_metrics: str
    get_relative_strength: str
    get_financials: str
    search_news: str


@dataclass
class ReportLabels:
    """Everything the HTML report needs to render in one language."""
    lang: str                          # "zh-TW" | "en"
    text: Dict[str, str]               # UI label strings, keyed (see tw.py/us.py)
    rating_class: Dict[str, str]       # verdict word -> css class (buy/hold/sell)
    recommend_label: str               # "建議" | "Recommendation"
    confidence_label: str              # "信心" | "Confidence"
    agent_names: Dict[str, str]        # agent id -> display name
    phase_names: Dict[str, str]        # phase id -> display name
    aspect_order: List[Tuple[str, str]]  # (agent id, section title)
    institutional_kind: str            # "lots" | "ownership"
    revenue_kind: str                  # "monthly" | "quarterly"
    disclaimer: str


@dataclass
class MarketProfile:
    """Self-contained config for analyzing one market. Front-ends consume this."""
    market: str                        # "tw" | "us"
    lang: str                          # "zh-TW" | "en"
    client: Any                        # MarketDataClient (duck-typed)
    committee: Any                     # committee.agents.Committee
    templates: Templates
    labels: ReportLabels
```

- [ ] **Step 4: Run it, verify it passes**

Run: `pytest tests/test_markets.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add committee/markets/base.py tests/test_markets.py
git commit -m "feat: MarketProfile interface dataclasses"
```

---

## Phase 3 — US data client (`UsClient`)

Each task adds one method with its fake-backed test. The constructor and cache
mirror `TwseClient`. `yfinance` and the EDGAR session are injectable for testing.

### Task 3: `UsClient` skeleton + `valuation`

**Files:**
- Create: `committee/data/us_market.py`
- Test: `tests/test_us_market.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_us_market.py
import tempfile

from committee.data.us_market import UsClient


class _FakeTicker:
    def __init__(self, symbol):
        self.symbol = symbol
        self.info = {"longName": "Apple Inc.", "trailingPE": 30.5,
                     "priceToBook": 45.2, "dividendYield": 0.0045}


class _FakeYf:
    """Stand-in for the yfinance module."""
    def Ticker(self, symbol):
        return _FakeTicker(symbol)


def _client(**kw):
    return UsClient(cache_dir=tempfile.mkdtemp(), yf=_FakeYf(), **kw)


def test_valuation_maps_info_fields_and_normalizes_yield_to_percent():
    out = _client().valuation("AAPL")
    assert out["stock_no"] == "AAPL"
    assert out["name"] == "Apple Inc."
    assert out["pe"] == 30.5
    assert out["pb"] == 45.2
    # 0.0045 fraction -> 0.45 percent (TW field semantics are a percent)
    assert abs(out["dividend_yield"] - 0.45) < 1e-9
```

- [ ] **Step 2: Run it, verify it fails**

Run: `pytest tests/test_us_market.py -v`
Expected: FAIL — `ModuleNotFoundError: committee.data.us_market`.

- [ ] **Step 3: Implement skeleton + `valuation`**

```python
# committee/data/us_market.py
"""US market data client: yfinance for market data, SEC EDGAR for financial
statements. Mirrors TwseClient's method shape and disk-cache pattern so the
committee tools and report work for either market. Never raises on missing
data — returns {"available": False, "note": ...}."""
import json
import os
from datetime import date
from typing import Any, Dict, List, Optional

_EDGAR = "https://data.sec.gov"
_EDGAR_TICKERS = "https://www.sec.gov/files/company_tickers.json"
# SEC requires a descriptive UA with contact info; requests without it are blocked.
_HEADERS = {"User-Agent": "tw-stock-analysis committee (contact: research@example.com)"}


def _norm_yield(raw: Any) -> Optional[float]:
    """yfinance returns dividendYield as a fraction (0.0045) or percent (0.45)
    depending on version. Normalize to a percent to match TW's field meaning."""
    if raw is None:
        return None
    try:
        v = float(raw)
    except (TypeError, ValueError):
        return None
    return round(v * 100, 4) if v < 1 else round(v, 4)


class UsClient:
    def __init__(self, cache_dir: str = "cache", yf: Any = None,
                 session: Any = None, today: Optional[date] = None) -> None:
        self._cache_dir = cache_dir
        self._today = today or date.today()
        self._yf = yf  # injected in tests; lazily imported in production
        if session is not None:
            self._session = session
        else:
            import requests
            self._session = requests.Session()
        os.makedirs(self._cache_dir, exist_ok=True)

    def _yfinance(self) -> Any:
        if self._yf is None:
            import yfinance
            self._yf = yfinance
        return self._yf

    def _cache(self, key: str, build) -> Any:
        """Return cached JSON for key, else call build(), cache, and return it."""
        path = os.path.join(self._cache_dir, key + ".json")
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as fh:
                return json.load(fh)
        value = build()
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(value, fh, ensure_ascii=False, default=str)
        return value

    def valuation(self, stock_no: str) -> Dict[str, Any]:
        def build():
            info = self._yfinance().Ticker(stock_no).info or {}
            return {"stock_no": stock_no, "name": info.get("longName") or stock_no,
                    "pe": info.get("trailingPE"), "pb": info.get("priceToBook"),
                    "dividend_yield": _norm_yield(info.get("dividendYield"))}
        return self._cache("us_valuation_{}_{}".format(stock_no, self._today.strftime("%Y%m%d")), build)
```

- [ ] **Step 4: Run it, verify it passes**

Run: `pytest tests/test_us_market.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add committee/data/us_market.py tests/test_us_market.py
git commit -m "feat: UsClient.valuation via yfinance"
```

---

### Task 4: `UsClient.price_history` + `index_history`

**Files:**
- Modify: `committee/data/us_market.py`
- Test: `tests/test_us_market.py`

- [ ] **Step 1: Add to the fake + write the failing tests**

Add a history-capable fake at the top of `tests/test_us_market.py`:

```python
class _FakeHistory:
    """Mimics the DataFrame returned by yfinance Ticker.history(): iterable rows
    via .itertuples() with Index (Timestamp-like) + OHLCV attributes."""
    def __init__(self, rows):
        self._rows = rows  # list of dicts with date/open/high/low/close/volume

    def itertuples(self):
        class _Row:
            pass
        for r in self._rows:
            row = _Row()
            row.Index = _FakeTs(r["date"])
            row.Open, row.High, row.Low = r["open"], r["high"], r["low"]
            row.Close, row.Volume = r["close"], r["volume"]
            yield row


class _FakeTs:
    def __init__(self, iso):
        self._iso = iso

    def strftime(self, fmt):  # only "%Y-%m-%d" is used
        return self._iso


class _FakeTickerWithHistory(_FakeTicker):
    def history(self, period=None, interval=None):
        return _FakeHistory([
            {"date": "2026-05-0{}".format(i + 1), "open": 10 + i, "high": 11 + i,
             "low": 9 + i, "close": 10 + i, "volume": 1000 + i} for i in range(5)])


class _FakeYfHistory(_FakeYf):
    def Ticker(self, symbol):
        return _FakeTickerWithHistory(symbol)
```

```python
def test_price_history_returns_ohlcv_rows_sorted_by_date():
    c = UsClient(cache_dir=tempfile.mkdtemp(), yf=_FakeYfHistory())
    rows = c.price_history("AAPL", months=1)
    assert rows[0]["date"] == "2026-05-01"
    assert rows[-1]["close"] == 14.0
    assert set(rows[0]) == {"date", "open", "high", "low", "close", "volume"}


def test_index_history_uses_sp500_close_series():
    c = UsClient(cache_dir=tempfile.mkdtemp(), yf=_FakeYfHistory())
    idx = c.index_history(months=1)
    assert idx[0]["date"] == "2026-05-01"
    assert "close" in idx[0] and len(idx[0]) == 2
```

- [ ] **Step 2: Run, verify failure**

Run: `pytest tests/test_us_market.py -k "history" -v`
Expected: FAIL — `AttributeError: 'UsClient' object has no attribute 'price_history'`.

- [ ] **Step 3: Implement both methods**

Add to `UsClient` (`_PERIOD` helper maps months → a yfinance period string):

```python
    _PERIOD = {1: "1mo", 2: "3mo", 3: "3mo", 6: "6mo", 12: "1y"}

    def _history(self, symbol: str, months: int) -> List[Dict[str, Any]]:
        period = self._PERIOD.get(int(months), "6mo")
        df = self._yfinance().Ticker(symbol).history(period=period, interval="1d")
        rows: List[Dict[str, Any]] = []
        for r in df.itertuples():
            rows.append({"date": r.Index.strftime("%Y-%m-%d"),
                         "open": _f(r.Open), "high": _f(r.High), "low": _f(r.Low),
                         "close": _f(r.Close), "volume": int(r.Volume or 0)})
        rows.sort(key=lambda x: x["date"])
        return rows

    def price_history(self, stock_no: str, months: int = 3) -> List[Dict[str, Any]]:
        key = "us_stock_day_{}_{}_{}".format(stock_no, int(months), self._today.strftime("%Y%m%d"))
        return self._cache(key, lambda: self._history(stock_no, months))

    def index_history(self, months: int = 3) -> List[Dict[str, Any]]:
        key = "us_index_{}_{}".format(int(months), self._today.strftime("%Y%m%d"))
        rows = self._cache(key, lambda: self._history("^GSPC", months))
        return [{"date": r["date"], "close": r["close"]} for r in rows]
```

Add this module-level helper near `_norm_yield`:

```python
def _f(v: Any) -> Optional[float]:
    try:
        return float(v)
    except (TypeError, ValueError):
        return None
```

- [ ] **Step 4: Run, verify pass**

Run: `pytest tests/test_us_market.py -k "history" -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add committee/data/us_market.py tests/test_us_market.py
git commit -m "feat: UsClient price_history + S&P500 index_history"
```

---

### Task 5: `UsClient.institutional_flows` (ownership substitute)

**Files:**
- Modify: `committee/data/us_market.py`
- Test: `tests/test_us_market.py`

- [ ] **Step 1: Write the failing test**

```python
class _FakeTickerHolders(_FakeTicker):
    def __init__(self, symbol):
        super().__init__(symbol)
        self.info = {"longName": "Apple Inc.", "heldPercentInstitutions": 0.612}

    def get_institutional_holders(self):
        return [{"Holder": "Vanguard", "pctHeld": 0.084},
                {"Holder": "BlackRock", "pctHeld": 0.066}]


class _FakeYfHolders(_FakeYf):
    def Ticker(self, symbol):
        return _FakeTickerHolders(symbol)


def test_institutional_flows_returns_ownership_and_top_holders():
    c = UsClient(cache_dir=tempfile.mkdtemp(), yf=_FakeYfHolders())
    out = c.institutional_flows("AAPL")
    assert out["available"] is True
    assert abs(out["inst_ownership_pct"] - 61.2) < 1e-9
    assert out["top_holders"][0] == {"holder": "Vanguard", "pct": 8.4}


def test_institutional_flows_missing_data_is_graceful():
    class _Empty(_FakeYf):
        def Ticker(self, symbol):
            t = _FakeTicker(symbol)
            t.info = {}
            t.get_institutional_holders = lambda: None
            return t
    c = UsClient(cache_dir=tempfile.mkdtemp(), yf=_Empty())
    out = c.institutional_flows("AAPL")
    assert out["available"] is False
```

- [ ] **Step 2: Run, verify failure**

Run: `pytest tests/test_us_market.py -k institutional -v`
Expected: FAIL — no `institutional_flows`.

- [ ] **Step 3: Implement**

```python
    def institutional_flows(self, stock_no: str) -> Dict[str, Any]:
        def build():
            t = self._yfinance().Ticker(stock_no)
            info = t.info or {}
            pct = info.get("heldPercentInstitutions")
            holders = t.get_institutional_holders() or []
            top = [{"holder": h.get("Holder"), "pct": round(float(h.get("pctHeld")) * 100, 4)}
                   for h in holders if h.get("pctHeld") is not None][:5]
            if pct is None and not top:
                return {"stock_no": stock_no, "available": False,
                        "note": "Institutional ownership data unavailable"}
            return {"stock_no": stock_no, "available": True,
                    "name": info.get("longName") or stock_no,
                    "inst_ownership_pct": round(float(pct) * 100, 4) if pct is not None else None,
                    "top_holders": top}
        return self._cache("us_inst_{}_{}".format(stock_no, self._today.strftime("%Y%m%d")), build)
```

- [ ] **Step 4: Run, verify pass**

Run: `pytest tests/test_us_market.py -k institutional -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add committee/data/us_market.py tests/test_us_market.py
git commit -m "feat: UsClient institutional ownership substitute"
```

---

### Task 6: `UsClient.monthly_revenue` (quarterly substitute)

**Files:**
- Modify: `committee/data/us_market.py`
- Test: `tests/test_us_market.py`

- [ ] **Step 1: Write the failing test**

```python
class _FakeTickerRevenue(_FakeTicker):
    def get_quarterly_revenue(self):
        # most-recent first: [(period, revenue, year-ago revenue)]
        return [("2026Q1", 95_000_000_000.0, 81_000_000_000.0)]


class _FakeYfRevenue(_FakeYf):
    def Ticker(self, symbol):
        return _FakeTickerRevenue(symbol)


def test_monthly_revenue_returns_latest_quarter_and_yoy():
    c = UsClient(cache_dir=tempfile.mkdtemp(), yf=_FakeYfRevenue())
    out = c.monthly_revenue("AAPL")
    assert out["available"] is True
    assert out["period"] == "2026Q1"
    assert out["revenue"] == 95_000_000_000.0
    # (95 - 81) / 81 * 100 = 17.28%
    assert abs(out["yoy_pct"] - 17.2840) < 1e-3


def test_monthly_revenue_missing_is_graceful():
    class _Empty(_FakeYf):
        def Ticker(self, symbol):
            t = _FakeTicker(symbol)
            t.get_quarterly_revenue = lambda: []
            return t
    out = UsClient(cache_dir=tempfile.mkdtemp(), yf=_Empty()).monthly_revenue("AAPL")
    assert out["available"] is False
```

> NOTE: `get_quarterly_revenue` is a small adapter the production client computes
> from `yfinance` `Ticker.quarterly_income_stmt`. To keep the unit under test
> deterministic and version-independent, `UsClient` calls a private
> `_quarterly_revenue(ticker)` that the test overrides via the fake's
> `get_quarterly_revenue`. Implement the adapter in Step 3.

- [ ] **Step 2: Run, verify failure**

Run: `pytest tests/test_us_market.py -k revenue -v`
Expected: FAIL — no `monthly_revenue`.

- [ ] **Step 3: Implement**

```python
    def _quarterly_revenue(self, ticker: Any):
        """Return [(period_str, revenue, year_ago_revenue)], most-recent first.

        Tests inject `ticker.get_quarterly_revenue`; production reads
        yfinance's quarterly_income_stmt (Total Revenue row, newest column
        first) and pairs each quarter with the one 4 quarters earlier."""
        if hasattr(ticker, "get_quarterly_revenue"):
            return ticker.get_quarterly_revenue()
        stmt = getattr(ticker, "quarterly_income_stmt", None)
        if stmt is None or getattr(stmt, "empty", True):
            return []
        try:
            row = stmt.loc["Total Revenue"]
        except Exception:
            return []
        cols = list(row.index)  # newest first
        out = []
        for i, col in enumerate(cols):
            rev = _f(row[col])
            prior = _f(row[cols[i + 4]]) if i + 4 < len(cols) else None
            period = col.strftime("%YQ%q") if hasattr(col, "strftime") else str(col)
            out.append((period, rev, prior))
        return out

    def monthly_revenue(self, stock_no: str) -> Dict[str, Any]:
        def build():
            rows = self._quarterly_revenue(self._yfinance().Ticker(stock_no))
            if not rows:
                return {"stock_no": stock_no, "available": False,
                        "note": "Quarterly revenue data unavailable"}
            period, rev, prior = rows[0]
            yoy = round((rev - prior) / prior * 100, 4) if (rev is not None and prior) else None
            return {"stock_no": stock_no, "available": True, "period": period,
                    "revenue": rev, "yoy_pct": yoy}
        return self._cache("us_qrev_{}_{}".format(stock_no, self._today.strftime("%Y%m")), build)
```

- [ ] **Step 4: Run, verify pass**

Run: `pytest tests/test_us_market.py -k revenue -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add committee/data/us_market.py tests/test_us_market.py
git commit -m "feat: UsClient quarterly-revenue substitute"
```

---

### Task 7: `UsClient.financials` via SEC EDGAR

**Files:**
- Modify: `committee/data/us_market.py`
- Test: `tests/test_us_market.py`

- [ ] **Step 1: Write the failing test**

```python
class _FakeEdgarSession:
    """Returns canned JSON for the two EDGAR URLs UsClient calls."""
    def __init__(self):
        self.tickers = {"0": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."}}
        self.facts = {
            "entityName": "Apple Inc.",
            "facts": {"us-gaap": {
                "Revenues": {"units": {"USD": [
                    {"end": "2026-03-31", "val": 95000000000, "form": "10-Q", "fp": "Q1", "fy": 2026}]}},
                "GrossProfit": {"units": {"USD": [
                    {"end": "2026-03-31", "val": 42000000000, "form": "10-Q", "fp": "Q1", "fy": 2026}]}},
                "OperatingIncomeLoss": {"units": {"USD": [
                    {"end": "2026-03-31", "val": 30000000000, "form": "10-Q", "fp": "Q1", "fy": 2026}]}},
                "NetIncomeLoss": {"units": {"USD": [
                    {"end": "2026-03-31", "val": 24000000000, "form": "10-Q", "fp": "Q1", "fy": 2026}]}},
                "StockholdersEquity": {"units": {"USD": [
                    {"end": "2026-03-31", "val": 80000000000, "form": "10-Q", "fp": "Q1", "fy": 2026}]}},
                "EarningsPerShareBasic": {"units": {"USD/shares": [
                    {"end": "2026-03-31", "val": 1.5, "form": "10-Q", "fp": "Q1", "fy": 2026}]}},
            }},
        }

    def get(self, url, headers=None, timeout=None):
        body = self.tickers if "company_tickers" in url else self.facts
        return _FakeResp(body)


class _FakeResp:
    def __init__(self, body):
        self._body = body

    def raise_for_status(self):
        pass

    def json(self):
        return self._body


def test_financials_from_edgar_computes_margins_and_roe():
    c = UsClient(cache_dir=tempfile.mkdtemp(), yf=_FakeYf(), session=_FakeEdgarSession())
    out = c.financials("AAPL")
    assert out["available"] is True
    assert out["revenue"] == 95000000000
    assert abs(out["gross_margin_pct"] - 44.21) < 0.1     # 42/95
    assert abs(out["operating_margin_pct"] - 31.58) < 0.1  # 30/95
    assert abs(out["roe_pct"] - 30.0) < 0.1                # 24/80
    assert out["eps"] == 1.5


def test_financials_unknown_ticker_is_graceful():
    c = UsClient(cache_dir=tempfile.mkdtemp(), yf=_FakeYf(), session=_FakeEdgarSession())
    out = c.financials("ZZZZ")
    assert out["available"] is False
```

- [ ] **Step 2: Run, verify failure**

Run: `pytest tests/test_us_market.py -k financials -v`
Expected: FAIL — no `financials`.

- [ ] **Step 3: Implement**

```python
    def _cik(self, stock_no: str) -> Optional[str]:
        body = self._cache("us_cik_map", lambda: self._session.get(
            _EDGAR_TICKERS, headers=_HEADERS, timeout=20).json())
        for row in (body or {}).values():
            if str(row.get("ticker", "")).upper() == stock_no.upper():
                return "{:010d}".format(int(row["cik_str"]))
        return None

    def financials(self, stock_no: str) -> Dict[str, Any]:
        def build():
            cik = self._cik(stock_no)
            if cik is None:
                return {"stock_no": stock_no, "available": False,
                        "note": "Ticker not found in SEC EDGAR"}
            resp = self._session.get(
                _EDGAR + "/api/xbrl/companyfacts/CIK{}.json".format(cik),
                headers=_HEADERS, timeout=20)
            resp.raise_for_status()
            facts = (resp.json() or {}).get("facts", {}).get("us-gaap", {})

            def latest(tag, unit="USD"):
                series = facts.get(tag, {}).get("units", {}).get(unit, [])
                if not series:
                    return None, None
                row = sorted(series, key=lambda r: r.get("end", ""))[-1]
                return _f(row.get("val")), row

            revenue, rev_row = latest("Revenues")
            if revenue is None:
                revenue, rev_row = latest("RevenueFromContractWithCustomerExcludingAssessedTax")
            gross, _ = latest("GrossProfit")
            operating, _ = latest("OperatingIncomeLoss")
            net, _ = latest("NetIncomeLoss")
            equity, _ = latest("StockholdersEquity")
            eps, _ = latest("EarningsPerShareBasic", "USD/shares")
            if revenue is None and net is None:
                return {"stock_no": stock_no, "available": False,
                        "note": "No us-gaap financial facts available"}
            period = ""
            if rev_row:
                period = "{}{}".format(rev_row.get("fy", ""), rev_row.get("fp", ""))

            def pct(num, den):
                return round(num / den * 100, 2) if (num is not None and den) else None

            return {"stock_no": stock_no, "available": True,
                    "name": stock_no, "period": period, "revenue": revenue,
                    "gross_margin_pct": pct(gross, revenue),
                    "operating_margin_pct": pct(operating, revenue),
                    "net_income": net, "roe_pct": pct(net, equity), "eps": eps,
                    "book_value_per_share": None}
        return self._cache("us_fin_{}_{}".format(stock_no, self._today.strftime("%Y%m")), build)
```

- [ ] **Step 4: Run, verify pass**

Run: `pytest tests/test_us_market.py -v`
Expected: PASS (whole file).

- [ ] **Step 5: Commit**

```bash
git add committee/data/us_market.py tests/test_us_market.py
git commit -m "feat: UsClient.financials via SEC EDGAR companyfacts"
```

---

## Phase 4 — Refactor domain layer to consume profiles (TW behavior unchanged)

### Task 8: Make `build_committee` accept prompts + move TW prompts to `markets/tw.py`

**Files:**
- Modify: `committee/agents.py`
- Create: `committee/markets/tw.py`
- Test: `tests/test_agents_def.py` (existing — must stay green)

- [ ] **Step 1: Create `markets/tw.py` with the TW prompt/template/toolset**

Move the prompt and template strings **verbatim** from `committee/agents.py:8-87`
into `committee/markets/tw.py`, wrapped in builder functions. Reproduce the exact
Chinese strings; do not paraphrase.

```python
# committee/markets/tw.py
"""Taiwan market profile: Chinese prompts, templates, tool descriptions, labels."""
from committee.markets.base import Prompts, Templates, ToolDescriptions


def tw_prompts() -> Prompts:
    return Prompts(
        fundamental=(
            "你是一位專注台股的基本面分析師。請使用 get_valuation 取得本益比、股價淨值比與"
            "殖利率,get_monthly_revenue 取得最新月營收年增率,並用 get_financials 取得最新一季"
            "毛利率、營業利益率、ROE 與 EPS,綜合判斷估值、獲利能力與成長性。"
            "請以繁體中文、精簡作答(120字以內),最後以明確傾向作結:看多、看空 或 中性。"
            "切勿捏造數字;若工具失敗或資料暫無,請直接說明。"),
        technical=(
            "你是一位專注台股的技術面分析師。請使用 get_technical_indicators 取得均線、趨勢、"
            "動能與震盪指標(RSI14、KD、MACD),並用 get_relative_strength 取得相對大盤的超額"
            "報酬與 beta,綜合判斷趨勢、超買超賣、相對強弱與進場時機。"
            "請以繁體中文、精簡作答(120字以內),最後以明確傾向作結:看多、看空 或 中性。"
            "切勿捏造數字;若工具失敗或某指標為 null(資料不足),請直接說明,不要臆測。"),
        institutional=(
            "你是一位專注台股的籌碼面分析師。請使用 get_institutional_flows 取得三大法人"
            "(外資/投信/自營商)買賣超,判斷主力資金是進場或出場。請以繁體中文、精簡作答"
            "(120字以內),最後以明確傾向作結:看多、看空 或 中性。切勿捏造數字。"),
        news=(
            "你是一位專注台股的新聞輿情分析師。請使用 search_news 搜尋該公司的近期新聞,"
            "歸納利多/利空與市場情緒。請以繁體中文、精簡作答(120字以內),最後以明確傾向"
            "作結:看多、看空 或 中性。僅引用新聞重點,不要捏造未出現的內容。"),
        risk=(
            "你是投資委員會的風險經理。請使用 get_risk_metrics 取得年化波動率與最大回撤,"
            "評估下檔風險,並對其他分析師過於樂觀之處提出質疑。請以繁體中文、精簡作答"
            "(120字以內)。切勿捏造數字。"),
        skeptic=(
            "你是委員會的唱反調者(魔鬼代言人),沒有任何工具。你的任務是挑戰目前浮現的"
            "共識、找出論點的弱點與盲點,避免團體迷思。請以繁體中文、犀利但具體地提出"
            "2-3 個反對理由(120字以內)。"),
        chair=(
            "你是投資委員會的主席。你會收到各委員的意見與彼此的質詢答辯,必須做出單一的"
            "最終結論。請完全以繁體中文,並嚴格依下列格式輸出:第一行「建議: 買進｜持有｜賣出」"
            "(三擇一),第二行「信心: NN%」,接著一段引用各委員論點的理由。除委員提供的"
            "數字外,不得自行捏造數字。"),
        verifier=(
            "你是委員會的查核員。你會看到主席的結論與委員引用的數據。請以繁體中文檢查結論"
            "是否與實際數據一致、推理是否合理,並指出任何沒有數據支持或前後矛盾之處。"
            "若全部一致,請回覆『查核通過』;否則簡要列出問題。"),
    )


def tw_templates() -> Templates:
    return Templates(
        analyst=("請從你的專業角度分析台股 {stock}。請先使用你的工具取得真實資料,"
                 "再給出精簡看法,並以 看多/看空/中性 的傾向作結。"),
        challenge=("以下是各分析師對台股 {stock} 的意見。請從你的角度提出質疑與風險,"
                   "挑戰其中過於樂觀或證據不足的論點。"),
        rebuttal=("風險經理與唱反調者提出了上述質疑。請針對與你專業相關的部分,"
                  "用一段話回應或修正你先前對台股 {stock} 的看法。"),
        reflect=("以下是你對台股 {stock} 的初步結論。請重新檢視自己的推理:論點是否紮實、前後是否一致、"
                 "每個數字是否有委員引用的數據支持。若發現問題請修正,然後**只輸出**改良後的最終建議,"
                 "並嚴格維持原本格式(第一行「建議: 買進｜持有｜賣出」、第二行「信心: NN%」、接著理由);"
                 "不得加入格式以外的說明,也不得捏造新數字。"),
        verify=("請檢視委員會對台股 {stock} 的結論是否與各委員引用的數據一致,"
                "指出任何沒有數據支持的數字或前後矛盾之處;若無問題請回覆「查核通過」。"),
        correction=("查核發現以下數字未獲數據支持:{figures}。請重新修正對台股 {stock} 的建議,"
                    "只使用有數據支持的數字,並維持原本的輸出格式。"),
    )


def tw_tool_descriptions() -> ToolDescriptions:
    return ToolDescriptions(
        stock_param="Taiwan stock code, e.g. 2330",
        get_valuation="Get P/E, P/B and dividend yield for a Taiwan stock from TWSE.",
        get_technical_indicators=("Get moving averages (MA5/20/60), trend, period % change, "
                                  "average volume and momentum oscillators (RSI14, KD, MACD) "
                                  "for a Taiwan stock, computed from TWSE daily prices."),
        get_institutional_flows="取得台股某檔最近交易日的三大法人(外資/投信/自營商)買賣超股數。",
        get_monthly_revenue="取得台股某檔最新月營收與年增率(YoY);若最新批次未涵蓋該股,會回報資料暫無。",
        get_risk_metrics="取得台股某檔的風險指標:年化波動率與最大回撤(由日收盤價計算)。",
        get_relative_strength=("取得台股某檔相對大盤(加權指數)的表現:期間個股報酬率、大盤報酬率、"
                               "超額報酬(excess_return_pct,>0 代表強於大盤)與 beta。"),
        get_financials=("取得台股某檔最新一季財報基本面:營收、毛利率、營業利益率、稅後淨利、"
                        "ROE、EPS 與每股淨值;若最新批次未涵蓋該股,會回報資料暫無。"),
        search_news="搜尋某主題的近期新聞標題與摘要(用於輿情分析)。",
    )
```

- [ ] **Step 2: Refactor `agents.py` to take a `Prompts` (default = TW)**

In `committee/agents.py`: delete the module-level `_*_PROMPT` and
`*_TASK_TEMPLATE` constants. Change `build_committee` to:

```python
from typing import List, Optional
from committee.markets.base import Prompts


def build_committee(prompts: Optional[Prompts] = None) -> Committee:
    if prompts is None:
        from committee.markets.tw import tw_prompts
        prompts = tw_prompts()
    fundamental = Agent(name="fundamental", role="Fundamental Analyst",
                        system_prompt=prompts.fundamental, model=MODEL_TOOL_CALLER,
                        fallback_models=MODEL_TOOL_CALLER_FALLBACKS,
                        tool_names=["get_valuation", "get_monthly_revenue", "get_financials"])
    technical = Agent(name="technical", role="Technical Analyst",
                      system_prompt=prompts.technical, model=MODEL_TOOL_CALLER,
                      fallback_models=MODEL_TOOL_CALLER_FALLBACKS,
                      tool_names=["get_technical_indicators", "get_relative_strength"])
    institutional = Agent(name="institutional", role="Institutional Flow Analyst",
                          system_prompt=prompts.institutional, model=MODEL_TOOL_CALLER,
                          fallback_models=MODEL_TOOL_CALLER_FALLBACKS,
                          tool_names=["get_institutional_flows"])
    news = Agent(name="news", role="News Analyst", system_prompt=prompts.news,
                 model=MODEL_TOOL_CALLER, fallback_models=MODEL_TOOL_CALLER_FALLBACKS,
                 tool_names=["search_news"])
    risk = Agent(name="risk", role="Risk Manager", system_prompt=prompts.risk,
                 model=MODEL_REASONER, fallback_models=MODEL_REASONER_FALLBACKS,
                 tool_names=["get_risk_metrics"])
    skeptic = Agent(name="skeptic", role="Skeptic", system_prompt=prompts.skeptic,
                    model=MODEL_REASONER, fallback_models=MODEL_REASONER_FALLBACKS, tool_names=[])
    chair = Agent(name="chair", role="Chair", system_prompt=prompts.chair,
                  model=MODEL_REASONER, fallback_models=MODEL_REASONER_FALLBACKS, tool_names=[])
    verifier = Agent(name="verifier", role="Verifier", system_prompt=prompts.verifier,
                     model=MODEL_REASONER, fallback_models=MODEL_REASONER_FALLBACKS, tool_names=[])
    return Committee(research=[fundamental, technical, institutional, news],
                     challengers=[risk, skeptic], chair=chair, verifier=verifier)
```

Keep the `Committee` dataclass as-is.

- [ ] **Step 3: Run the existing roster tests (must stay green)**

Run: `pytest tests/test_agents_def.py -v`
Expected: PASS (no-arg `build_committee()` still returns the TW roster).

- [ ] **Step 4: Verify nothing else imports the removed constants yet**

Run: `pytest -q`
Expected: `main.py`/`gui.py`/`web/server.py` are not imported by tests, so the
suite passes. (Those imports are fixed in Phase 6.) If any test fails on a missing
`ANALYST_TASK_TEMPLATE` import, it indicates a test imports it — re-export it
temporarily from `agents.py` via `from committee.markets.tw import tw_templates`.

- [ ] **Step 5: Commit**

```bash
git add committee/agents.py committee/markets/tw.py
git commit -m "refactor: build_committee takes Prompts; TW prompts move to markets/tw"
```

---

### Task 9: Make `build_registry` accept `ToolDescriptions` (default = TW)

**Files:**
- Modify: `committee/domain_tools.py`
- Test: `tests/test_domain_tools.py` (existing — must stay green)

- [ ] **Step 1: Refactor `build_registry`**

Change the signature and source the descriptions from the dataclass:

```python
from typing import Any, Optional
from committee.markets.base import ToolDescriptions


def build_registry(client: Any, descriptions: Optional[ToolDescriptions] = None) -> ToolRegistry:
    if descriptions is None:
        from committee.markets.tw import tw_tool_descriptions
        descriptions = tw_tool_descriptions()
    d = descriptions
    stock_param = {"type": "string", "description": d.stock_param}
    reg = ToolRegistry()

    reg.register(Tool(name="get_valuation", description=d.get_valuation,
                      parameters={"type": "object", "properties": {"stock_no": stock_param},
                                  "required": ["stock_no"]},
                      fn=lambda stock_no: client.valuation(stock_no)))
    # ... repeat for the other 7 tools, replacing the hardcoded description with
    # d.<tool_name> and the inline _STOCK_NO with stock_param, and keeping the
    # existing fn bodies (the _indicators / _risk / _relative_strength closures
    # and int(months) coercion) unchanged.
    return reg
```

Rename the local `twse` parameter to `client` throughout, but keep every `fn`
body identical (still calls `.valuation`, `.price_history`, etc.). Keep the
`get_technical_indicators`, `get_risk_metrics`, and `get_relative_strength`
`months` parameter schemas and their `int(months)` coercion exactly as they are.

- [ ] **Step 2: Run the existing tool tests**

Run: `pytest tests/test_domain_tools.py tests/test_tools.py -v`
Expected: PASS (`build_registry(_FakeTwse())` still works with the TW default).

- [ ] **Step 3: Run full suite**

Run: `pytest -q`
Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add committee/domain_tools.py
git commit -m "refactor: build_registry takes ToolDescriptions; TW default"
```

---

## Phase 5 — Report builder market-awareness

### Task 10: Bilingual rating parse + `build_html(labels=...)`

**Files:**
- Modify: `committee/report.py`
- Test: `tests/test_report.py`

- [ ] **Step 1: Add a failing English-rating test**

Append to `tests/test_report.py` (reuse its existing collector fake; mirror an
existing rating test for structure):

```python
def test_rating_parses_english_verdict():
    from committee.report import _rating
    r = _rating("Recommendation: BUY\nConfidence: 60%\nStrong fundamentals.")
    assert r["label"] == "BUY"
    assert r["cls"] == "buy"
    assert r["confidence"] == "60%"
```

- [ ] **Step 2: Run, verify failure**

Run: `pytest tests/test_report.py::test_rating_parses_english_verdict -v`
Expected: FAIL — `_rating` only matches the Chinese `建議/信心`.

- [ ] **Step 3: Make `_rating` bilingual**

In `committee/report.py`, extend `_RATING_CLASS` and `_rating`:

```python
_RATING_CLASS = {"買進": "buy", "持有": "hold", "賣出": "sell",
                 "BUY": "buy", "HOLD": "hold", "SELL": "sell"}


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
```

- [ ] **Step 4: Run, verify pass**

Run: `pytest tests/test_report.py -v`
Expected: PASS (English + existing Chinese rating tests).

- [ ] **Step 5: Commit**

```bash
git add committee/report.py tests/test_report.py
git commit -m "feat: report rating parser handles English verdicts"
```

---

### Task 11: Thread `ReportLabels` through `build_html` / `save_report`

**Files:**
- Modify: `committee/report.py`
- Modify: `committee/markets/tw.py` (add `tw_labels()`)
- Test: `tests/test_report.py`

- [ ] **Step 1: Add `tw_labels()` to `markets/tw.py`**

This carries the strings currently hardcoded in `report.py`. Keep the exact
Chinese text from `report.py` (`_AGENT_ZH`, `_PHASE_ZH`, `_DISCLAIMER`, the card
titles and row labels, the section `<h2>` titles).

```python
# committee/markets/tw.py  (append)
from committee.markets.base import ReportLabels

_TW_TEXT = {
    "eyebrow": "AI 投資委員會 · 個股研究報告",
    "title": "個股研究報告",
    "header_fallback": "台股個股分析",
    "generated_at": "產出時間",
    "rating": "投資評等", "confidence": "信心度", "last_close": "參考收盤",
    "thesis": "投資論點摘要", "dashboard": "關鍵數據儀表板",
    "chart": "近期股價走勢", "aspect": "分面分析",
    "risk": "風險與空方觀點", "integrity": "資料完整性查核",
    "integrity_support": "數據支持", "integrity_unsupported": "未獲數據支持(已標記)",
    "card_valuation": "估值", "row_pe": "本益比 (PE)", "row_pb": "股價淨值比 (PB)",
    "row_dy": "殖利率",
    "card_financials": "獲利能力", "row_gm": "毛利率", "row_om": "營業利益率",
    "row_roe": "ROE", "row_eps": "EPS",
    "card_technical": "技術指標", "row_close": "收盤", "row_ma20": "MA20",
    "row_rsi": "RSI14", "row_kd": "KD", "row_macd": "MACD", "row_chg": "期間漲跌",
    "card_relative": "相對大盤", "row_stock_ret": "個股報酬",
    "row_index_ret": "大盤報酬", "row_excess": "超額報酬", "row_beta": "Beta",
    "card_institutional": "三大法人(張)", "row_foreign": "外資", "row_trust": "投信",
    "row_dealer": "自營商", "row_total": "合計",
    "card_risk": "風險", "row_vol": "年化波動率", "row_mdd": "最大回撤",
    "card_revenue": "月營收", "row_rev": "當月營收", "row_yoy": "年增率 (YoY)",
    "row_mom": "月增率 (MoM)",
    "chart_caption": "收盤價 · MA20(虛線)", "chart_close": "收盤",
}


def tw_labels() -> ReportLabels:
    return ReportLabels(
        lang="zh-TW", text=_TW_TEXT,
        rating_class={"買進": "buy", "持有": "hold", "賣出": "sell"},
        recommend_label="建議", confidence_label="信心",
        agent_names={"fundamental": "基本面分析師", "technical": "技術面分析師",
                     "institutional": "籌碼面分析師", "news": "新聞輿情分析師",
                     "risk": "風險經理", "skeptic": "唱反調者", "chair": "主席",
                     "verifier": "查核員", "system": "系統"},
        phase_names={"RESEARCH": "研究分析", "CHALLENGE": "質詢", "REBUTTAL": "答辯",
                     "VERDICT": "最終結論", "REFLECT": "自我反省", "VERIFY": "自我查核"},
        aspect_order=[("fundamental", "基本面分析"), ("technical", "技術面分析"),
                      ("institutional", "籌碼面分析"), ("news", "新聞輿情分析")],
        institutional_kind="lots", revenue_kind="monthly",
        disclaimer=("免責聲明:本報告由 AI 投資委員會自動產生,所有數據取自公開資料來源(TWSE 等),"
                    "僅供研究與技術展示參考,不構成任何投資建議或要約。投資人應自行判斷並承擔風險。"))
```

- [ ] **Step 2: Write a failing test for `build_html(labels=...)`**

```python
def test_build_html_uses_tw_labels_by_default_and_renders():
    from committee.report import build_html
    from tests.test_report import _make_collector  # or inline the existing fake
    # Build a minimal collector with a verdict; reuse the file's existing helper.
    html = build_html("2330", _make_collector(verdict="建議: 買進\n信心: 70%"))
    assert 'lang="zh-TW"' in html
    assert "關鍵數據儀表板" in html or "投資論點摘要" in html
```

> If `tests/test_report.py` has no reusable collector helper, inline the same
> minimal fake collector the existing tests use (copy its shape from the top of
> the file) rather than importing a private helper.

- [ ] **Step 3: Refactor `report.py` to read from `labels`**

- Add `labels: Optional[ReportLabels] = None` to `build_html` and `save_report`;
  default to `tw_labels()` when `None`:

```python
def build_html(stock_no, collector, ledger=None, generated_at=None, twse=None,
               months=3, labels=None):
    if labels is None:
        from committee.markets.tw import tw_labels
        labels = tw_labels()
    L = labels.text
    ...
```

- Replace every hardcoded label/title/disclaimer with `L[...]`,
  `labels.disclaimer`, `labels.lang`, `labels.agent_names`, `labels.phase_names`,
  and `labels.aspect_order`. Pass `labels` into `_dashboard`, `_aspect_sections`,
  `_risk_box`, and `_transcript` (replace the module-level `_AGENT_ZH`/`_PHASE_ZH`
  reads with `labels.agent_names`/`labels.phase_names`).
- In `_dashboard`, branch the two substituted cards on `labels.institutional_kind`
  and `labels.revenue_kind`:

```python
    if "institutional" in m:
        i = m["institutional"]
        if labels.institutional_kind == "ownership":
            rows = [(L["row_inst_own"], _num(i.get("inst_ownership_pct"), 2, "%"))]
            rows += [(h.get("holder"), _num(h.get("pct"), 2, "%"))
                     for h in (i.get("top_holders") or [])]
            cards.append(_card(L["card_institutional"], rows))
        else:
            cards.append(_card(L["card_institutional"], [
                (L["row_foreign"], _lots(i.get("foreign_net"))),
                (L["row_trust"], _lots(i.get("trust_net"))),
                (L["row_dealer"], _lots(i.get("dealer_net"))),
                (L["row_total"], _lots(i.get("total_net")))]))
    if "revenue" in m and m["revenue"].get("available", True):
        rv = m["revenue"]
        rows = [(L["row_rev"], _num(rv.get("revenue"), 0)),
                (L["row_yoy"], _num(rv.get("yoy_pct"), 2, "%"))]
        if labels.revenue_kind == "monthly":
            rows.append((L["row_mom"], _num(rv.get("mom_pct"), 2, "%")))
        cards.append(_card(L["card_revenue"] + " · " + _esc(rv.get("period", "")), rows))
```

Keep `_rating` (already bilingual from Task 10) and the SVG chart shared. Keep
`save_report` passing `labels` through to `build_html`.

- [ ] **Step 4: Run the report tests**

Run: `pytest tests/test_report.py -v`
Expected: PASS (default TW labels reproduce current output; new test passes).

- [ ] **Step 5: Commit**

```bash
git add committee/report.py committee/markets/tw.py tests/test_report.py
git commit -m "refactor: report reads ReportLabels; TW labels move to markets/tw"
```

---

### Task 12: `markets/us.py` — English profile, and `get_profile`

**Files:**
- Create: `committee/markets/us.py`
- Modify: `committee/markets/__init__.py` (add `get_profile`, `build_tw_profile`, `build_us_profile`)
- Test: `tests/test_markets.py`

- [ ] **Step 1: Write failing wiring tests**

```python
# tests/test_markets.py  (append)
from committee.markets import get_profile


def test_get_profile_tw_is_chinese_with_twse_client():
    p = get_profile("tw")
    assert p.market == "tw" and p.lang == "zh-TW"
    assert p.labels.institutional_kind == "lots"
    assert type(p.client).__name__ == "TwseClient"
    assert [a.name for a in p.committee.research] == ["fundamental", "technical",
                                                      "institutional", "news"]


def test_get_profile_us_is_english_with_us_client():
    p = get_profile("us")
    assert p.market == "us" and p.lang == "en"
    assert p.labels.institutional_kind == "ownership"
    assert p.labels.revenue_kind == "quarterly"
    assert type(p.client).__name__ == "UsClient"
    assert "Recommendation" in p.committee.chair.system_prompt
    assert p.templates.analyst.find("{stock}") >= 0


def test_get_profile_unknown_market_raises():
    import pytest
    with pytest.raises(ValueError):
        get_profile("jp")
```

- [ ] **Step 2: Run, verify failure**

Run: `pytest tests/test_markets.py -k get_profile -v`
Expected: FAIL — no `get_profile`.

- [ ] **Step 3: Implement `markets/us.py`**

```python
# committee/markets/us.py
"""US market profile: English prompts, templates, tool descriptions, labels."""
from committee.markets.base import Prompts, Templates, ToolDescriptions, ReportLabels


def us_prompts() -> Prompts:
    return Prompts(
        fundamental=(
            "You are a fundamentals analyst covering US equities. Use get_valuation for "
            "P/E, P/B and dividend yield, get_monthly_revenue for the latest QUARTERLY "
            "revenue and YoY growth (US firms report quarterly), and get_financials for the "
            "latest gross margin, operating margin, ROE and EPS. Weigh valuation, "
            "profitability and growth together. Answer in English, concise (under 80 words), "
            "ending with a clear stance: Bullish, Bearish, or Neutral. Never fabricate "
            "numbers; if a tool fails or data is unavailable, say so plainly."),
        technical=(
            "You are a technical analyst covering US equities. Use get_technical_indicators "
            "for moving averages, trend, momentum and oscillators (RSI14, KD, MACD), and "
            "get_relative_strength for excess return vs the S&P 500 and beta. Judge trend, "
            "overbought/oversold, relative strength and entry timing. Answer in English, "
            "concise (under 80 words), ending with: Bullish, Bearish, or Neutral. Never "
            "fabricate numbers; if an indicator is null (insufficient data), say so."),
        institutional=(
            "You are an ownership/positioning analyst for US equities. Use "
            "get_institutional_flows for the institutional ownership percentage and the top "
            "institutional holders, and judge whether smart money is concentrated or light. "
            "Answer in English, concise (under 80 words), ending with: Bullish, Bearish, or "
            "Neutral. Never fabricate numbers."),
        news=(
            "You are a news/sentiment analyst for US equities. Use search_news to find "
            "recent company news and summarize bullish/bearish catalysts and market "
            "sentiment. Answer in English, concise (under 80 words), ending with: Bullish, "
            "Bearish, or Neutral. Cite only what appears in the news; invent nothing."),
        risk=(
            "You are the committee's risk manager. Use get_risk_metrics for annualized "
            "volatility and max drawdown, assess downside risk, and challenge any analyst "
            "who is too optimistic. Answer in English, concise (under 80 words). Never "
            "fabricate numbers."),
        skeptic=(
            "You are the committee's devil's advocate, with no tools. Challenge the emerging "
            "consensus, expose weaknesses and blind spots, and guard against groupthink. In "
            "English, give 2-3 sharp, specific counterarguments (under 80 words)."),
        chair=(
            "You are the committee chair. You receive each member's view and their "
            "challenges and rebuttals, and must deliver a single final verdict. Respond "
            "entirely in English and STRICTLY in this format: first line "
            "'Recommendation: BUY|HOLD|SELL' (choose one), second line 'Confidence: NN%', "
            "then a paragraph of reasoning citing members' points. Use no numbers beyond "
            "those members provided; fabricate nothing."),
        verifier=(
            "You are the committee's verifier. You see the chair's verdict and the figures "
            "members cited. In English, check the verdict is consistent with the actual "
            "data and the reasoning is sound, and flag anything unsupported or "
            "contradictory. If all consistent, reply 'VERIFIED'; otherwise list the issues."),
    )


def us_templates() -> Templates:
    return Templates(
        analyst=("Analyze US stock {stock} from your area of expertise. First use your "
                 "tools to gather real data, then give a concise view ending with a "
                 "Bullish/Bearish/Neutral stance."),
        challenge=("Below are the analysts' views on US stock {stock}. From your angle, "
                   "raise challenges and risks, attacking points that are too optimistic "
                   "or weakly evidenced."),
        rebuttal=("The risk manager and skeptic raised the above challenges. Responding "
                  "only where it concerns your expertise, reply or revise your earlier "
                  "view on US stock {stock} in one paragraph."),
        reflect=("Below is your draft verdict on US stock {stock}. Re-examine your "
                 "reasoning: are the points solid, internally consistent, and is every "
                 "figure supported by data members cited? Fix any problems, then OUTPUT "
                 "ONLY the improved final recommendation in the exact original format "
                 "(first line 'Recommendation: BUY|HOLD|SELL', second line 'Confidence: "
                 "NN%', then reasoning); add nothing outside the format and invent no "
                 "new numbers."),
        verify=("Check whether the committee's verdict on US stock {stock} is consistent "
                "with the figures members cited; flag any unsupported number or "
                "contradiction. If there are none, reply 'VERIFIED'."),
        correction=("Verification found these figures unsupported by data: {figures}. "
                    "Revise the recommendation on US stock {stock} using only "
                    "data-supported numbers, keeping the original output format."),
    )


def us_tool_descriptions() -> ToolDescriptions:
    return ToolDescriptions(
        stock_param="US stock ticker, e.g. AAPL",
        get_valuation="Get P/E, P/B and dividend yield for a US stock (Yahoo Finance).",
        get_technical_indicators=("Get moving averages (MA5/20/60), trend, period % change, "
                                  "average volume and momentum oscillators (RSI14, KD, MACD) "
                                  "for a US stock, computed from daily prices."),
        get_institutional_flows=("Get the institutional ownership percentage and top "
                                 "institutional holders for a US stock."),
        get_monthly_revenue=("Get a US stock's latest QUARTERLY revenue and YoY growth "
                             "(US firms report quarterly, not monthly); reports unavailable "
                             "if data is missing."),
        get_risk_metrics="Get a US stock's risk metrics: annualized volatility and max drawdown.",
        get_relative_strength=("Get a US stock's performance vs the S&P 500: stock return, "
                               "index return, excess_return_pct (>0 means stronger than the "
                               "market) and beta."),
        get_financials=("Get a US stock's latest-quarter fundamentals from SEC filings: "
                        "revenue, gross/operating margin, net income, ROE and EPS; reports "
                        "unavailable if not in EDGAR."),
        search_news="Search recent news headlines and snippets for a topic (for sentiment).",
    )


_US_TEXT = {
    "eyebrow": "AI Investment Committee · Equity Research",
    "title": "Equity Research Report", "header_fallback": "US Equity Analysis",
    "generated_at": "Generated", "rating": "Rating", "confidence": "Confidence",
    "last_close": "Last Close", "thesis": "Investment Thesis",
    "dashboard": "Key Data Dashboard", "chart": "Recent Price Trend",
    "aspect": "Aspect Analysis", "risk": "Risks & Bear Case",
    "integrity": "Data Integrity Check", "integrity_support": "Figures supported",
    "integrity_unsupported": "Unsupported (flagged)",
    "card_valuation": "Valuation", "row_pe": "P/E", "row_pb": "P/B", "row_dy": "Dividend Yield",
    "card_financials": "Profitability", "row_gm": "Gross Margin", "row_om": "Operating Margin",
    "row_roe": "ROE", "row_eps": "EPS",
    "card_technical": "Technicals", "row_close": "Close", "row_ma20": "MA20",
    "row_rsi": "RSI14", "row_kd": "KD", "row_macd": "MACD", "row_chg": "Period Change",
    "card_relative": "vs S&P 500", "row_stock_ret": "Stock Return",
    "row_index_ret": "Index Return", "row_excess": "Excess Return", "row_beta": "Beta",
    "card_institutional": "Institutional Ownership", "row_inst_own": "Institutional %",
    "card_risk": "Risk", "row_vol": "Annualized Volatility", "row_mdd": "Max Drawdown",
    "card_revenue": "Quarterly Revenue", "row_rev": "Revenue", "row_yoy": "YoY",
    "chart_caption": "Close · MA20 (dashed)", "chart_close": "Close",
    # keys present in TW but unused for US cards still need safe lookups:
    "row_foreign": "", "row_trust": "", "row_dealer": "", "row_total": "", "row_mom": "",
}


def us_labels() -> ReportLabels:
    return ReportLabels(
        lang="en", text=_US_TEXT,
        rating_class={"BUY": "buy", "HOLD": "hold", "SELL": "sell"},
        recommend_label="Recommendation", confidence_label="Confidence",
        agent_names={"fundamental": "Fundamentals Analyst", "technical": "Technical Analyst",
                     "institutional": "Ownership Analyst", "news": "News Analyst",
                     "risk": "Risk Manager", "skeptic": "Skeptic", "chair": "Chair",
                     "verifier": "Verifier", "system": "System"},
        phase_names={"RESEARCH": "Research", "CHALLENGE": "Challenge", "REBUTTAL": "Rebuttal",
                     "VERDICT": "Verdict", "REFLECT": "Reflect", "VERIFY": "Verify"},
        aspect_order=[("fundamental", "Fundamentals"), ("technical", "Technicals"),
                      ("institutional", "Ownership"), ("news", "News & Sentiment")],
        institutional_kind="ownership", revenue_kind="quarterly",
        disclaimer=("Disclaimer: This report is generated automatically by an AI investment "
                    "committee. All figures come from public sources (Yahoo Finance, SEC "
                    "EDGAR) and are for research and demonstration only — not investment "
                    "advice. Invest at your own risk."))
```

- [ ] **Step 4: Implement `get_profile` + profile builders in `__init__.py`**

Append to `committee/markets/__init__.py`:

```python
from committee.config import CACHE_DIR


def build_tw_profile() -> "MarketProfile":
    from committee.agents import build_committee
    from committee.data.twse import TwseClient
    from committee.markets.base import MarketProfile
    from committee.markets.tw import tw_prompts, tw_templates, tw_labels
    return MarketProfile(market="tw", lang="zh-TW", client=TwseClient(cache_dir=CACHE_DIR),
                         committee=build_committee(tw_prompts()), templates=tw_templates(),
                         labels=tw_labels())


def build_us_profile() -> "MarketProfile":
    from committee.agents import build_committee
    from committee.data.us_market import UsClient
    from committee.markets.base import MarketProfile
    from committee.markets.us import us_prompts, us_templates, us_labels
    return MarketProfile(market="us", lang="en", client=UsClient(cache_dir=CACHE_DIR),
                         committee=build_committee(us_prompts()), templates=us_templates(),
                         labels=us_labels())


def get_profile(market: str):
    if market == "tw":
        return build_tw_profile()
    if market == "us":
        return build_us_profile()
    raise ValueError("unknown market: {}".format(market))
```

Add `from committee.markets.base import MarketProfile` at the top if you prefer an
eager import; the string annotation above avoids a circular import at module load.

- [ ] **Step 5: Run, verify pass**

Run: `pytest tests/test_markets.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add committee/markets/us.py committee/markets/__init__.py tests/test_markets.py
git commit -m "feat: US market profile + get_profile factory"
```

---

## Phase 6 — Front-end + collector wiring + dependency

### Task 13: Add `yfinance` dependency

**Files:**
- Modify: `requirements.txt`

- [ ] **Step 1: Add the dependency**

Append `yfinance` to `requirements.txt` (one line, unpinned to match the file's
existing style; pin if the file pins others).

- [ ] **Step 2: Install and import-check**

Run: `pip install -r requirements.txt && python -c "import yfinance; print('ok')"`
Expected: prints `ok`.

- [ ] **Step 3: Commit**

```bash
git add requirements.txt
git commit -m "build: add yfinance dependency for US market data"
```

---

### Task 14: Wire `main.py` (CLI) to profiles

**Files:**
- Modify: `main.py`

- [ ] **Step 1: Replace TW-specific construction with the profile**

Update imports and `run()`:

```python
from committee.markets import detect_market, get_profile
from committee.config import API_KEY_ENV, BASE_URL, REFLECTION_PASSES
from committee.domain_tools import build_registry
from committee.report import save_report
# remove: committee.agents template imports, committee.data.twse, CACHE_DIR (now in profile)


def run(stock_no: str) -> str:
    bus = EventBus()
    bus.subscribe(TerminalRenderer())
    collector = ReportCollector()
    bus.subscribe(collector)
    ledger = EvidenceLedger()
    llm = LLMClient(base_url=BASE_URL, api_key_env=API_KEY_ENV)

    profile = get_profile(detect_market(stock_no))
    registry = build_registry(profile.client, _us_tool_descriptions_or_tw(profile))
    t = profile.templates
    committee = profile.committee
    orch = Orchestrator(research=committee.research, challengers=committee.challengers,
                        chair=committee.chair, verifier=committee.verifier,
                        analyst_task_template=t.analyst, challenge_task_template=t.challenge,
                        rebuttal_task_template=t.rebuttal, reflect_task_template=t.reflect,
                        reflection_passes=REFLECTION_PASSES, verify_task_template=t.verify,
                        correction_task_template=t.correction)
    verdict = orch.run(stock_no=stock_no, llm=llm, registry=registry, bus=bus, ledger=ledger)
    path = save_report(stock_no, collector, ledger=ledger, twse=profile.client,
                       labels=profile.labels)
    print("\n[report] saved to: {}".format(path))
    return verdict
```

To give the registry the right tool descriptions, add a tiny helper near the top
of `main.py` (or better: have `get_profile` also expose descriptions). Simplest:
store descriptions on the profile.

> **Decision:** add a `descriptions: ToolDescriptions` field to `MarketProfile`
> rather than a helper. Do this now: add the field in `markets/base.py`, set it in
> `build_tw_profile`/`build_us_profile` (`tw_tool_descriptions()`/
> `us_tool_descriptions()`), then call `build_registry(profile.client,
> profile.descriptions)`. Re-run `pytest tests/test_markets.py` after the field
> add to confirm construction still passes (update the `MarketProfile(...)`
> calls in both builders).

Final `main.py` registry line:

```python
    registry = build_registry(profile.client, profile.descriptions)
```

- [ ] **Step 2: Smoke-run the CLI offline path (TW, cached or expected network)**

Run: `python main.py 2330` (needs network + API key) OR, if offline, run:
`python -c "import main; from committee.markets import get_profile; p=get_profile('us'); print(p.market, p.descriptions.get_valuation[:20])"`
Expected: `us Get P/E, P/B and div`.

- [ ] **Step 3: Run full suite**

Run: `pytest -q`
Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add main.py committee/markets/base.py committee/markets/__init__.py
git commit -m "feat: CLI routes by market via MarketProfile"
```

---

### Task 15: Wire `gui.py` and `web/server.py`

**Files:**
- Modify: `gui.py`
- Modify: `web/server.py`

- [ ] **Step 1: Apply the same profile wiring**

In both files, replace the `TwseClient` + `build_registry(twse)` +
`build_committee()` + module-template construction with:

```python
from committee.markets import detect_market, get_profile
...
profile = get_profile(detect_market(symbol))
registry = build_registry(profile.client, profile.descriptions)
t = profile.templates
committee = profile.committee
orch = Orchestrator(research=committee.research, challengers=committee.challengers,
                    chair=committee.chair, verifier=committee.verifier,
                    analyst_task_template=t.analyst, challenge_task_template=t.challenge,
                    rebuttal_task_template=t.rebuttal, reflect_task_template=t.reflect,
                    reflection_passes=REFLECTION_PASSES, verify_task_template=t.verify,
                    correction_task_template=t.correction)
...
save_report(symbol, collector, ledger=ledger, twse=profile.client, labels=profile.labels)
```

Keep the existing threading model (worker thread → `queue.Queue` → `root.after`
for Tk; WebSocket worker for the server) exactly as-is. Only the engine
construction changes. Remove now-unused imports (`TwseClient`, the template
constants, `CACHE_DIR`).

- [ ] **Step 2: Import-check both front-ends**

Run: `python -c "import gui" && python -c "import web.server" && echo ok`
Expected: `ok` (no ImportError from the removed template constants).

- [ ] **Step 3: Run web tests**

Run: `pytest tests/test_web.py -v`
Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add gui.py web/server.py
git commit -m "feat: GUI and web front-ends route by market"
```

---

### Task 16: Route the deterministic collector by market

**Files:**
- Modify: `scripts/collect_stock_data.py`

- [ ] **Step 1: Replace the hardcoded `TwseClient` with the detected client**

```python
from committee.markets import detect_market, get_profile
...
def main():
    stock = sys.argv[1] if len(sys.argv) > 1 else "2330"
    months = int(sys.argv[2]) if len(sys.argv) > 2 else 6

    client = get_profile(detect_market(stock)).client
    out = {"stock_no": stock, "months": months, "market": detect_market(stock)}

    prices = safe(lambda: client.price_history(stock, months=months))
    index = safe(lambda: client.index_history(months=months))
    ...
    out["valuation"] = safe(lambda: client.valuation(stock))
    ...
    out["institutional_flows"] = safe(lambda: client.institutional_flows(stock))
    out["monthly_revenue"] = safe(lambda: client.monthly_revenue(stock))
    out["financials"] = safe(lambda: client.financials(stock))
    out["news"] = safe(lambda: search_news("{} {}".format(out["company_name"], stock).strip()))
    ...
```

Replace every `twse.` with `client.`; keep the `safe()` wrapper, the
`compute_*` indicator calls, and the JSON dump exactly as-is.

- [ ] **Step 2: Smoke-run offline construction**

Run: `python -c "import scripts.collect_stock_data as c; print('ok')"`
Expected: `ok`.

- [ ] **Step 3: Commit**

```bash
git add scripts/collect_stock_data.py
git commit -m "feat: collector routes by market"
```

---

### Task 17: Full-suite green + README note

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Run the whole suite**

Run: `pytest -q`
Expected: PASS, no failures.

- [ ] **Step 2: Add a short README line about US support**

Under the intro or "Three front-ends" section, add: that the same commands accept
a US ticker (e.g. `python main.py AAPL`), market is auto-detected, US reports are
in English, and US data comes from Yahoo Finance + SEC EDGAR. Keep it to 2-3
sentences matching the README's existing tone.

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs: note US stock support in README"
```

- [ ] **Step 4 (optional): Live smoke**

Run: `python main.py AAPL` (needs network + API key)
Expected: an English HTML report under `reports/AAPL_<ts>.html`.

---

## Self-Review Notes

- **Spec coverage:** detection (T1), profile interface (T2), UsClient incl. both
  substitutions + EDGAR financials (T3–7), prompts/templates/tool-descriptions/
  labels per market (T8, T11, T12), report market-awareness (T10–11), all three
  front-ends + collector (T14–16), dependency (T13). All spec sections map to a
  task.
- **Backward compatibility:** `build_committee()`, `build_registry(client)`, and
  `build_html(...)` keep TW defaults so existing tests stay green through the
  refactor (verified at T8, T9, T11).
- **Type consistency:** `MarketProfile` gains a `descriptions` field in T14;
  `tw_labels`/`us_labels` share the same `text` keys (US fills unused TW keys with
  `""` to keep `_dashboard` lookups safe). Tool *names* are identical across
  markets so `report._TOOL_BUCKET` is unchanged.
- **Known follow-ups (out of scope, per spec):** the JS workflow, options/intraday
  data, manual market override.
