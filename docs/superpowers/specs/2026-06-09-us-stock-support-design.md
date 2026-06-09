# US Stock Support — Design Spec

**Date:** 2026-06-09
**Status:** Approved (pending spec review)
**Topic:** Add US-stock analysis alongside the existing Taiwan-stock committee

## Goal

Let the committee engine analyze **both** Taiwan-listed and US-listed stocks. The
market is auto-detected from the ticker. TW reports stay in Traditional Chinese;
US reports are in English. All three front-ends (CLI, GUI, Web) and the
deterministic data collector work for either market with no new user-facing
arguments.

## Decisions (locked)

1. **Market routing** — auto-detect from the ticker format (no flag, no UI control).
2. **US data source** — `yfinance` (Yahoo) for market data + **SEC EDGAR** for
   authoritative financial statements. No paid API; yfinance needs no key, EDGAR
   needs only a `User-Agent`.
3. **Analyst parity** — the two TW-only analysts get US substitutes (not dropped,
   not N/A): institutional flows → institutional ownership %; monthly revenue →
   quarterly revenue & YoY. The 8-role roster is identical across markets.
4. **Output language** — English for US, Traditional Chinese for TW.

## Architecture — a `MarketProfile` per market

New package `committee/markets/`:

```
committee/markets/
  __init__.py     detect_market(symbol) -> "tw"|"us";  get_profile(market) -> MarketProfile
  base.py         MarketProfile / Templates / ReportLabels dataclasses (the interface)
  tw.py           build_tw_profile()  — TwseClient + Chinese prompts/labels
  us.py           build_us_profile()  — UsClient + English prompts/labels
```

A `MarketProfile` bundles everything market-specific so front-ends and the report
stay market-agnostic:

```python
@dataclass
class MarketProfile:
    market: str                  # "tw" | "us"
    lang: str                    # "zh-TW" | "en"
    client: MarketDataClient     # data client (protocol below)
    committee: Committee         # agents carrying the right-language prompts
    templates: Templates         # the 6 task templates, right language
    labels: ReportLabels         # card titles, rating keywords, disclaimer, agent names
```

**`agentcore/` is untouched** — it stays a domain-neutral, reusable multi-agent
core. `committee/data/twse.py`, `committee/data/indicators.py`, and
`committee/data/news.py` are unchanged. `committee/agents.py`,
`committee/domain_tools.py`, and `committee/report.py` are refactored so their
TW-specific text moves into `markets/tw.py` and they accept the profile/labels.

## Components

### 1. Market detection — `markets/__init__.py: detect_market`

Pure function, no network. Normalize (strip, upper). All-digits (optionally with a
`.TW` / `.TWO` suffix) → `"tw"`; contains any letter → `"us"`. TW codes are 4–6
digits; US tickers are 1–5 letters with optional `.`/`-` (e.g. `BRK.B`).
Unit-tested with both markets and edge cases. No manual override (per decision 1).

### 2. Data client protocol — `MarketDataClient`

Both clients expose the **same six methods** so `build_registry(client)` and the
report price chart work for either market:

`valuation`, `price_history`, `institutional_flows`, `monthly_revenue`,
`index_history`, `financials`.

`TwseClient` already matches this shape. `UsClient` implements the same method
names. `search_news` remains a standalone, market-agnostic function (the query
text is supplied by the analyst prompt, so it localizes naturally).

The protocol is documented as a `typing.Protocol` in `markets/base.py` for
clarity; clients are still passed as `Any`/duck-typed to match the existing
codebase style.

### 3. US data client — `committee/data/us_market.py: UsClient`

yfinance for market data, SEC EDGAR for financial statements. Mirrors
`TwseClient`'s disk-cache pattern: each call's **parsed dict** is cached to a JSON
file in `cache/`, keyed by method + symbol + date, so a symbol is fetched once per
day and reused across the run.

| Method | Source | Returns | Shape vs TW |
|---|---|---|---|
| `valuation(symbol)` | yfinance `.info` (`trailingPE`, `priceToBook`, `dividendYield`, `longName`) | `{stock_no, name, pe, pb, dividend_yield}` | **same** |
| `price_history(symbol, months)` | yfinance `.history` | `[{date, open, high, low, close, volume}]` | **same** (so `indicators.py` is unchanged) |
| `index_history(months)` | yfinance `^GSPC` (S&P 500) | `[{date, close}]` | **same** (benchmark = S&P 500 instead of TAIEX) |
| `financials(symbol)` | **SEC EDGAR** companyfacts (ticker→CIK via cached `company_tickers.json`) | `{available, name, period, revenue, gross_margin_pct, operating_margin_pct, net_income, roe_pct, eps, book_value_per_share}` | **same** |
| `institutional_flows(symbol)` | yfinance institutional ownership | `{available, name, inst_ownership_pct, top_holders:[{holder, pct}]}` | **substituted** (not daily lots) |
| `monthly_revenue(symbol)` | yfinance quarterly income | `{available, name, period:"YYYYQn", revenue, yoy_pct}` | **substituted** (quarterly, not monthly) |

The two substituted methods return a different shape than TW, so their tool
description, the corresponding analyst prompt, and one report card each become
market-aware. Everything else is shared.

**Dividend yield normalization:** yfinance has historically returned
`dividendYield` as either a fraction (`0.012`) or a percent (`1.2`) depending on
version. `UsClient.valuation` normalizes to a percent value to match the TW
field's meaning, with a unit test pinning the chosen convention.

### 4. Prompts & templates per market — `agents.py` + `markets/*.py`

`build_committee(lang)` builds the same roster (4 research + 2 challengers + chair
+ verifier) from a language-specific prompt set:

- **TW set** (`markets/tw.py`) — the existing Chinese prompts and the 6 task
  templates, moved verbatim from `agents.py`.
- **US set** (`markets/us.py`) — English equivalents. The US Chair prompt emits
  `Recommendation: BUY|HOLD|SELL` then `Confidence: NN%`. The US substituted-analyst
  prompts reference institutional ownership % and quarterly revenue & YoY. Same
  "never invent numbers; report missing data honestly" discipline.

`agents.py` keeps the `Committee` dataclass and the `Agent` wiring; the prompt and
template **strings** relocate to the market modules. Model-tier assignment
(`MODEL_TOOL_CALLER` for the 4 analysts, `MODEL_REASONER` for chair/risk/skeptic/
verifier) is unchanged and market-agnostic.

### 5. Tool registry — `domain_tools.py: build_registry`

`build_registry(client)` is mostly unchanged — the tool fns already just call
`client.<method>(...)`, which works for either client. Tool **descriptions** that
are TW-specific (Chinese, "台股") move to per-market description sets so the
LLM sees market-appropriate, correctly-localized tool docs. The defensive numeric
coercion (`int(months)`) is retained.

### 6. Report builder — `report.py: build_html(..., profile)`

The largest single change. The builder reads labels and rating rules from the
profile instead of hardcoding Chinese:

- **Rating parse** — accept both `建議/信心` (zh) and `Recommendation/Confidence`
  (en); `_RATING_CLASS` maps both `買進/持有/賣出` and `BUY/HOLD/SELL` to
  buy/hold/sell CSS classes.
- **Labels** — card titles, section headings, disclaimer, `<html lang>`, and agent
  display names come from `profile.labels`.
- **Substituted cards** — the institutional card renders 三大法人 lots for TW and
  ownership % + top holders for US; the revenue card renders monthly (YoY/MoM) for
  TW and quarterly (YoY) for US.
- **Shared** — valuation, financials, technical, relative-strength, and risk cards
  plus the inline SVG price chart are shared; only their titles localize.

The US disclaimer cites the data sources used (Yahoo Finance / SEC EDGAR) instead
of TWSE.

### 7. Front-end wiring — `main.py`, `gui.py`, `web/server.py`

Each front-end changes from "build TwseClient + registry + committee + module
templates" to:

```python
profile  = get_profile(detect_market(symbol))
registry = build_registry(profile.client)
orch     = Orchestrator(..., committee=profile.committee, templates=profile.templates)
verdict  = orch.run(stock_no=symbol, llm=llm, registry=registry, bus=bus, ledger=ledger)
path     = save_report(symbol, collector, ledger=ledger, profile=profile)
```

Phase **names** (`RESEARCH … VERIFY`) are unchanged, so the existing GUI/web
phase-card label maps need no per-market work. The LLM provider/model config
(`committee/config.py`) is market-agnostic and unchanged except that the task
templates it helped construct now come from the profile.

### 8. Deterministic collector — `scripts/collect_stock_data.py`

Routes by `detect_market(symbol)` and uses the matching client, so the
LLM-free JSON blob is produced for US symbols too. Per-aspect failures still
degrade to `{"error": ...}` rather than aborting.

## Cross-cutting concerns

- **Dependency:** add `yfinance` to `requirements.txt`. SEC EDGAR uses the existing
  `requests` with a descriptive `User-Agent` (SEC requires one; requests without it
  are blocked).
- **Caching & failure:** mirror `TwseClient` — per-call JSON cache; missing-data
  paths return `{"available": False, "note": ...}` and never raise. `Agent.run`
  must keep never raising (the orchestrator relies on it to survive partial
  failures).
- **Grounding / VERIFY:** `agentcore/verify.check_grounding` is numeric and
  language-neutral, so it validates English verdicts unchanged. No agentcore edits.

## Testing

Follow the existing hand-rolled-fake style (no `unittest.mock`):

- `detect_market` — TW codes, US tickers, suffixed forms, edge cases.
- `UsClient` — parsing for each of the six methods using `_FakeYf` and a fake EDGAR
  session, including the two substitutions and the missing-data fallback, plus the
  dividend-yield normalization.
- `get_profile` / market wiring — correct client, language, templates, labels per
  market.
- `report.py` — English rating parse (`Recommendation: BUY` / `Confidence: 60%`)
  and that US substituted cards render.

All tests run offline (`pytest -q`). An optional `-m live` smoke for a real US
symbol may be added but stays deselected by default.

## Scope

**In scope:** CLI, GUI, and Web all analyze both markets; `collect_stock_data.py`
routes by market.

**Out of scope (follow-on):**
- The JS workflow `.claude/workflows/tw_stock_analyzed_workflow.js` — its prompts
  are TW/Chinese; making it bilingual is a separate effort.
- Options, intraday, and real-time US data.
- A manual market override (auto-detect only, per decision 1).

## Open risks

- **yfinance is unofficial** and can break when Yahoo changes response shapes —
  same fragility the TW spike scripts already guard against for TWSE. Mitigation:
  isolate all yfinance access in `UsClient`, keep parsing defensive, and rely on
  the `{"available": False}` fallback.
- **yfinance `.info` field drift** (e.g. `dividendYield` units) — pinned by a
  normalization step + unit test.
- **SEC EDGAR rate/User-Agent rules** — single cached `company_tickers.json`
  fetch + per-symbol companyfacts cache keeps request volume low.
