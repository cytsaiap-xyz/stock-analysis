# TW/US Market Switch (Web + Desktop GUI) — Design Spec

**Date:** 2026-06-10
**Status:** Approved (pending spec review)
**Topic:** A TW/US toggle in the web app and desktop GUI that sets both the UI
language and the analyzed market.

## Goal

Add a **TW / US toggle** to the web app and the Tkinter desktop GUI. The toggle
is the **single source of truth**: it sets the UI language (page title, agent and
phase labels, live status text) and **forces the analyzed market** — the ticker
format is ignored, so the web/GUI front-ends call `get_profile(<chosen market>)`
directly instead of `detect_market(ticker)`.

Today the title (`台股投資委員會`) and all live-view labels are hardcoded
Chinese, so a US run shows English analysis inside Chinese chrome. This makes the
chrome follow the chosen market.

## Decisions (locked)

1. **Switch is source of truth** — sets UI language AND forces the market; ticker
   format is not used for routing in these front-ends.
2. **Scope** — web app **and** desktop GUI. CLI (`main.py`) keeps auto-detect and
   is out of scope.
3. **Default on load** — TW (matches current behavior).
4. **UI strings live in the market profile** — the single per-market source.

## Key idea: the market profile owns the UI strings

All live-view chrome that is currently hardcoded Chinese moves into the per-market
profile so TW and US each carry their own set.

- **Already present** in `committee/markets/tw.py` / `us.py` via `ReportLabels`:
  - `labels.agent_names` — e.g. `基本面分析師` / `Fundamentals Analyst`
  - `labels.phase_names` — e.g. `研究分析` / `Research`
- **New:** a `ui: Dict[str, str]` added to each profile, built in `tw.py` / `us.py`,
  holding the strings the *live view* needs (kept separate from the report-focused
  `ReportLabels`):
  - `title`, `subtitle` — page/window heading
  - `example_ticker` — `2330` / `AAPL`
  - `run_button` — `開始分析` / `Analyze` (exact current TW wording taken from
    `index.html`/`gui.py`)
  - status verbs used during streaming: `thinking`, `writing`, `done`, `calling`,
    `received` — TW reproduces the current `思考中` / `撰寫中` / `完成` /
    `呼叫` / `已取得` wording verbatim; US gives English equivalents.

### Where `ui` is added

- `committee/markets/base.py`: add `ui: Dict[str, str]` as the last field of
  `MarketProfile`.
- `committee/markets/__init__.py`: `build_tw_profile` / `build_us_profile` set
  `ui=tw_ui()` / `ui=us_ui()`.
- `committee/markets/tw.py` / `us.py`: add `tw_ui()` / `us_ui()` returning the dict.

This keeps a single source per market and means a future front-end localizes for
free.

## Web app

### `web/static/index.html`
- Add a TW/US segmented toggle (two radio buttons or a segmented control) near the
  ticker input.
- Give the `<title>`, the `<h1>` heading, the subtitle `<span>`, the run button,
  and the ticker `<input>` stable `id`s so `app.js` can set their text/placeholder.

### `web/server.py`
- `GET /api/committee?market=tw|us` (default `tw`): build the roster from
  `get_profile(market)` and return, per agent, `name`, the **market** display name
  (from `labels.agent_names`), `model`, `tools`, `group`; plus `phase_names` (from
  `labels.phase_names`) and the `ui` dict. Replaces the module-level `_AGENT_ZH` /
  `_PHASE_ZH` hardcoded maps (delete them).
- `WS /ws/run/{market}/{stock_no}`: market path segment added. `_run_committee`
  takes `market` and builds the run via `get_profile(market)` — **forcing** the
  market (no `detect_market`).
- The FastAPI app `title=` and any other module-level Chinese string become
  market-neutral (e.g. an English app title) since they are not user-facing chrome.

### `web/static/app.js`
- On load and on every toggle change: `fetch('/api/committee?market=' + market)`,
  rebuild the cards, and set the page title, subtitle, run-button text, and the
  status verbs from the response. Status strings (`thinking`/`writing`/… ) come
  from `ui` instead of hardcoded Chinese literals.
- Phase/agent labels in the stream come from the fetched `phase_names` /
  `agent_names` maps (already per-market).
- On run: open `'/ws/run/' + market + '/' + ticker`.
- Toggling swaps the ticker input to the market's `example_ticker` when the field
  is empty or still holds the other market's example.

## Desktop GUI (`gui.py`)

- Add a TW/US control (a `tk` radio/segmented control) at the top.
- On toggle: rebuild the pipeline cards from `get_profile(market)` labels and set
  the window title from `ui`.
- On run: use `get_profile(selected_market)` (forced market).
- The streaming `_handle` status strings (`思考中` etc.) and the roster card labels
  read from the selected profile's `labels`/`ui` instead of the hardcoded `_zh`
  map and Chinese literals.

## What stays the same

- The engine, `EventBus`, report builder, and `agentcore/` are untouched.
- The final HTML report already localizes via the profile — unchanged.
- The CLI (`main.py`) keeps `detect_market` auto-detection.
- `detect_market` and `get_profile` are unchanged; the front-ends simply call
  `get_profile(chosen_market)`.

## Error handling

- `committee_info` / the WS route validate `market` against `{"tw","us"}` and fall
  back to `tw` on an unknown value (mirrors `get_profile`'s `ValueError`, but the
  HTTP/WS layer should not 500 on a bad query param).
- Forcing the market against a mismatched ticker (e.g. US + `2330`) is the user's
  explicit choice; data tools degrade to their existing `available: False` paths,
  never crashing. The example-ticker swap reduces accidental mismatches.

## Testing

Hand-rolled-fake style, no mocks; web routes tested as plain functions (the repo
avoids `starlette.TestClient`).

- `web/server.py`:
  - `committee_info("us")` returns English agent names, English `phase_names`, and
    an English `ui.title`; `committee_info("tw")` returns the Chinese equivalents.
  - Unknown market falls back to `tw` without raising.
  - The run wiring uses the forced market (a US market value builds a `UsClient`).
- `gui.py`: extend `test_gui_format` so the label/status formatting takes a
  market's labels and renders English for US, Chinese for TW.
- Full suite stays green; TW web/GUI behavior unchanged when the toggle is on TW.

## Scope

**In:** web app (`index.html`, `web/server.py`, `app.js`) + desktop GUI (`gui.py`);
the new `MarketProfile.ui` + `tw_ui()`/`us_ui()`.

**Out (follow-on):** CLI localization; a manual market override that still
auto-detects; persisting the last-used market across sessions.
