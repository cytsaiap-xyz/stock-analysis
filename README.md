# Agentic Investment Committee — Taiwan Stock Analysis

An **agentic investment committee**: a 7-agent LLM committee that analyzes a single
Taiwan-listed stock through a structured debate — **research → challenge → rebuttal →
verdict** — then runs a **self-verification (VERIFY)** pass before delivering an
analyst-grade research note. All output is in **Traditional Chinese (繁體中文)**.

Every figure in the final report is pulled from real data collected during the run
(TWSE / TPEx market data + DuckDuckGo news). The committee never invents numbers: a
deterministic grounding check confirms each figure traces back to a recorded data
source, and anything unsupported is **flagged in the report, never silently removed**.

## Three front-ends, one engine

All three share the same engine and produce the same `reports/<stock>_<ts>.html`:

| Front-end | Command | What you get |
|---|---|---|
| **CLI** | `python main.py 2330` | Terminal renderer with live streaming |
| **Desktop GUI** | `python gui.py` | Tkinter window, pipeline cards + live tokens |
| **Web app** | `python manage.py runserver` | Django + Channels WebSocket UI at http://localhost:8000 (auto-reloads) |

## Setup

Requires **Python 3.9+** and an NVIDIA API key (or an OpenRouter key — see below).

```bash
pip install -r requirements.txt

# Put your key in .env (.env is gitignored):
echo NVIDIA_API_KEY=nvapi-... > .env
```

```bash
python main.py 2330                          # CLI
python gui.py                                # desktop GUI
python manage.py runserver                   # web → http://localhost:8000 (Django, auto-reloads)
./start-web.sh   # or  .\start-web.ps1       # web launcher (HOST/PORT overridable)
```

## Markets — Taiwan and US, auto-detected

The same commands accept either a **Taiwan** code or a **US** ticker — the market is
inferred from the symbol (4–6 digits → TW, e.g. `2330`; letters → US, e.g. `AAPL`):

```bash
python main.py 2330      # Taiwan — report in 繁體中文, data from TWSE
python main.py AAPL      # US — report in English, data from Yahoo Finance + SEC EDGAR
```

The web app and desktop GUI also have a **TW / US switch** that sets the UI language
(title, labels, live status) and forces the analyzed market — so a US run shows an
English live debate, not just an English report.

TW reports are written in Traditional Chinese; US reports in English. US fundamentals
come from SEC EDGAR (XBRL company facts) and prices/ownership/quarterly revenue from
Yahoo Finance (`yfinance`), with relative strength measured against the S&P 500. Two
TW-only analysts are substituted for US: institutional **flows** → institutional
**ownership %** + top holders, and **monthly** revenue → latest **quarterly** revenue
& YoY. Everything else (the 7-agent debate, grounding, the report layout) is shared.

## How it works

The committee runs a structured debate orchestrated as a phase pipeline:

```
RESEARCH → CHALLENGE → REBUTTAL → VERDICT → REFLECT → VERIFY
```

- **Research analysts** (4) each investigate one aspect using tool calls — valuation,
  technicals, institutional flows, monthly revenue, risk, news, relative strength,
  financials.
- **Skeptic** challenges the bull case; analysts rebut.
- **Chair** writes the draft verdict, then (optionally) re-examines its own reasoning
  in a **REFLECT** self-refinement pass.
- **VERIFY** is two-part: a deterministic `check_grounding` confirms every data-like
  figure in the verdict is present (within tolerance) in some recorded tool result,
  followed by an LLM consistency pass. A failed grounding triggers **one** correction
  round to the Chair.

The final HTML report is a sell-side-style research note built **with no extra LLM
calls** — rating banner, key-data dashboard, per-aspect sections, risk box, an inline
price chart (close + MA20), and a collapsible appendix with the full debate transcript
and evidence table.

## Architecture

Two strictly separated layers:

- **`agentcore/`** — a generic, reusable multi-agent core with **zero stock-market
  knowledge**: `EventBus`, `EvidenceLedger`, `Tool`/`ToolRegistry`, an
  OpenAI-compatible `LLMClient` (streaming + tool-call assembly + retry/backoff +
  cross-model fallback), `Agent` (tool-calling loop), `Orchestrator`, grounding
  verification, and the report collector.
- **`committee/`** — the Taiwan-stock domain layer: agent prompts + roster, the 8
  analysis tools, TWSE/DDGS data clients, and the HTML report builder.

**Everything flows through the EventBus.** The engine never writes to any UI directly —
it emits typed events (`phase`, `token`, `tool_call`, `tool_result`, `message`,
`verdict`, `verification`, `report`, …) and every front-end is just a subscriber. Adding
a new front-end means writing one event handler; the engine is untouched. This is why
the same code drives a CLI, a desktop GUI, and a web app.

There is also a second, JS-orchestrated analysis path —
`.claude/workflows/tw_stock_analyzed_workflow.js` — a [Claude Code](https://claude.com/claude-code)
workflow that reuses the Python data layer (via `scripts/collect_stock_data.py`) and runs
an independent collect → analyze → synthesize → verify → finalize pipeline.

## Models — two tiers, two providers, env-driven

Both providers are OpenAI-compatible, so switching is just a base URL + key + model ids.

| Provider | tool_caller tier (analysts) | reasoner tier (Chair/Risk/Skeptic/Verifier) |
|---|---|---|
| `nvidia` *(default)* | `meta/llama-3.3-70b-instruct` | `moonshotai/kimi-k2.6` |
| `openrouter` | `qwen/qwen3-coder:free` | `deepseek/deepseek-v4-flash:free` |

```bash
# .env — switch to OpenRouter
LLM_PROVIDER=openrouter
OPENROUTER_API_KEY=sk-or-...
# per-provider model overrides (comma-separated = primary + fallbacks)
OPENROUTER_MODEL_REASONER=moonshotai/kimi-k2.6:free,openai/gpt-oss-120b:free
```

A model env may be a comma-separated list — the first is primary, the rest are
fallbacks tried on transient (429/5xx/timeout) or 404 errors. Per-provider model vars
never leak across providers; flipping `LLM_PROVIDER` automatically uses that provider's
models.

> ⚠️ OpenRouter `:free` models are heavily contended and frequently return 429. A full
> committee run is dozens of LLM calls, so a free-tier run can abort mid-debate. Probe
> live availability before relying on a specific `:free` id.

## Tests

```bash
pytest -q                                    # full suite, no network
pytest tests/test_orchestrator.py -v         # single file
pytest -m live -v                            # live smoke (needs NVIDIA_API_KEY + network)
```

The live test is deselected by default (`pytest.ini` sets `-m "not live"`).

## Project layout

```
agentcore/   reusable multi-agent core (no domain knowledge)
committee/   Taiwan-stock domain: agents, tools, data clients, report builder
web/         FastAPI + WebSocket front-end
scripts/     TWSE spike scripts + deterministic data collector
tests/       pytest suite (hand-rolled fakes, no mocks)
main.py      CLI front-end
gui.py       Tkinter desktop front-end
```

## License

No license file is included; all rights reserved unless stated otherwise.
