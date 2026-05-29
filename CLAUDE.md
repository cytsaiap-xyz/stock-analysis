# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

An **Agentic Investment Committee** — a 7-agent LLM committee that analyzes a single
Taiwan stock through a structured debate (research → challenge → rebuttal → verdict),
then runs a self-verification (VERIFY) step before delivering an analyst-grade result.
All output is **Traditional Chinese**. Three front-ends share the same engine: a CLI
(`main.py`), a Tkinter desktop GUI (`gui.py`), and a FastAPI + WebSocket web app
(`web/server.py`).

## Commands

Setup once:
```bash
pip install -r requirements.txt
# Put your NVIDIA key in .env (.env is gitignored):
echo NVIDIA_API_KEY=nvapi-... > .env
```

Run (all three front-ends share the same engine and produce the same `reports/<stock>_<ts>.html`):
```bash
python main.py 2330                          # CLI, terminal renderer
python gui.py                                # Tkinter window, pipeline cards + live streaming
python -m uvicorn web.server:app             # Web → http://localhost:8000
```

Tests — pytest defaults to deselecting the live test:
```bash
pytest -q                                    # full suite, no network
pytest tests/test_orchestrator.py -v         # single file
pytest tests/test_agent.py::test_tool_exception_is_fed_back_not_raised -v   # single test
pytest -m live -v                            # run the live smoke (needs NVIDIA_API_KEY + network)
```

Three one-off **spike scripts** (manual; they hit real TWSE/DuckDuckGo to verify endpoint
shapes — re-run them whenever those upstreams change):
```bash
python scripts/twse_spike.py                 # STOCK_DAY, BWIBBU_ALL shapes (Phase 1)
python scripts/spike_phase2.py               # T86, monthly revenue, ddgs news (Phase 2)
python scripts/spike_phase3.py               # MI_5MINS_HIST (TAIEX), income stmt + balance sheet (Phase 3)
```

## Architecture — the load-bearing ideas

### Two layers, strictly separated

- **`agentcore/`** is a *generic, reusable* multi-agent core with **zero stock-market
  knowledge**. It owns: `EventBus`, `EvidenceLedger`, `Tool/ToolRegistry`, `LLMClient`
  (NVIDIA OpenAI-compatible, streaming + tool-call assembly + retry/backoff), `Agent`
  (tool-calling loop), `Orchestrator` (RESEARCH→CHALLENGE→REBUTTAL→VERDICT→REFLECT→VERIFY),
  `verify.check_grounding`, `ReportCollector`.
- **`committee/`** is the *Taiwan-stock* domain layer: agent prompts + roster
  (`build_committee` returns a `Committee` dataclass), the 6 tools (`build_registry`),
  TWSE/DDGS data clients, and the HTML report builder.

Anything market-specific (the word "Taiwan", agent names, tool function bodies) belongs
in `committee/`. If you find domain language leaking into `agentcore/`, it's a bug —
`tests/test_orchestrator.py::test_default_templates_are_domain_neutral` enforces this.

### Everything flows through EventBus

`Agent.run` and `Orchestrator.run` never write to any UI directly. They emit typed
events on the bus; everyone else (terminal printer, Tk widgets, WebSocket, report
collector) is a **subscriber**. To add a new front-end you write *one function*
`def __call__(self, event: Event)` and `bus.subscribe(it)` — the engine is untouched.
This is why the system has three front-ends from the same code.

Event types (the protocol): `phase`, `token`, `tool_call`, `tool_result`, `message`,
`error`, `verdict`, `verification`, `report`. See `agentcore/events.py` and the handler
switches in `main.py:TerminalRenderer`, `gui.py:_handle`, `web/static/app.js:handleEvent`.

### The Orchestrator is the only place that knows about debate phases

Templates (`analyst_task_template`, `challenge_task_template`, `rebuttal_task_template`,
`reflect_task_template`, `verify_task_template`, `correction_task_template`) are injected
by the domain layer (`committee/agents.py`). The orchestrator's defaults are deliberately
domain-neutral English so the core stays reusable. Each phase emits a `phase` event with
the phase name — front-end pipelines key their step cards on these names (so a new phase
like REFLECT must be added to the GUI `steps`/`PHASE_ZH` and web `_PHASE_ZH`/`app.js`).

**REFLECT is an optional Chair self-reflection (Self-Refine) phase** between VERDICT and
VERIFY: after the draft verdict, the Chair re-examines its own reasoning and rewrites an
improved verdict in the same format. It is gated by `Orchestrator.reflection_passes`
(core default **0 = off**, so the generic core stays unchanged); the committee turns it on
via `REFLECTION_PASSES` env (default 1, set 0 to disable). The refined `verdict` event
carries a `reflected: True` flag (mirrors `corrected: True`).

### VERIFY is two-part, by design

1. **Deterministic** `check_grounding(verdict, ledger)` extracts data-like figures
   (decimals / thousands-grouped numbers) from the verdict and confirms each is
   present (within tolerance) in some recorded tool result. It deliberately ignores
   plain ints like "信心: 55%" (reasoning artifacts).
2. **LLM verifier** does a consistency pass.
3. If deterministic grounding fails → **one** correction round to the Chair. Per the
   spec, unsupported figures are always **flagged in the final report, never silently
   removed**.

### Model strategy — two tiers, two providers, env-driven

`committee/config.py` resolves **provider + role → model** from env via the pure
`resolve(env)` (unit-tested in `tests/test_config.py`). Both providers are
OpenAI-compatible, so switching is just `base_url` + api-key env + model ids.

- `LLM_PROVIDER` (`nvidia` *default* | `openrouter`) selects `BASE_URL` and `API_KEY_ENV`
  (`NVIDIA_API_KEY` vs `OPENROUTER_API_KEY`). `main.py`/`gui.py`/`web/server.py` all
  construct `LLMClient(base_url=BASE_URL, api_key_env=API_KEY_ENV)`.
- `MODEL_TOOL_CALLER` — the 4 research analysts (need reliable tool-calling).
- `MODEL_REASONER` — Chair, Risk, Skeptic, Verifier.

Per-provider defaults (override any with `MODEL_*` env):
| provider | tool_caller default | reasoner default |
|---|---|---|
| nvidia | `meta/llama-3.3-70b-instruct` | `moonshotai/kimi-k2.6` |
| openrouter | `qwen/qwen3-coder:free` | `deepseek/deepseek-v4-flash:free` |

```
# .env — switch to OpenRouter free models
LLM_PROVIDER=openrouter
OPENROUTER_API_KEY=sk-or-...
# optional model overrides (e.g. when the default :free models are 429 rate-limited)
MODEL_TOOL_CALLER=openai/gpt-oss-120b:free
MODEL_REASONER=nvidia/nemotron-3-super-120b-a12b:free
```
⚠️ **OpenRouter `:free` models are heavily contended** — popular ones (qwen3-coder,
deepseek-v4-flash) frequently return 429 "rate-limited upstream", and free accounts
have a daily request cap. A full committee run is dozens of LLM calls, so a free-tier
run can abort mid-debate. `agentcore/llm.py` retries 429/5xx with backoff, but that
won't beat a daily cap. Probe live availability before relying on a specific `:free` id.

Agents themselves are model-agnostic — they just take a `model` string.

### Non-obvious quirks worth knowing

- **`pytest.ini` has `addopts = -m "not live" -p no:dash`.** The `-p no:dash` disables
  a broken `dash/plotly` pytest plugin in this Python 3.9 environment. Don't remove it
  unless you've fixed that env.
- **LLMs pass numeric args as strings.** `committee/domain_tools.py` coerces with
  `int(months)` — there's a regression test for this (`test_get_technical_indicators_coerces_string_months`).
  When adding a numeric-arg tool, coerce defensively.
- **TWSE column orders were verified by spike, not docs.** Real `BWIBBU_ALL` is 5
  columns `[code, name, PE, dividend_yield, PB]` — the public docs imply 7. If a TWSE
  endpoint changes shape, re-run the spike before touching parsers.
- **`get_monthly_revenue` has a graceful "資料暫無" fallback** because the
  `t187ap05_P` opendata batch doesn't cover every stock every day. Don't change this to
  raise — the analyst handles it honestly in its prompt.
- **Streaming + tool-calls are assembled by `tc.index`** in `agentcore/llm.py`.
  Multiple tool calls in one response arrive interleaved; the accumulator keys by
  `index` and concatenates `arguments` fragments. Tests use `tests/test_llm.py`'s
  fake chunks; preserve that pattern.
- **`Agent.run` never raises** — tool exceptions become a `{"error": ...}` `tool`
  message fed back to the LLM and an `error` event. The orchestrator depends on this
  to keep debates alive through partial failures.
- **`main.py` reconfigures stdout to UTF-8** in its `__main__` block. Without that,
  Windows cp950 console mangles Chinese / em-dashes in the captured output.
- **GUI Tk threading rule:** the committee runs on a worker thread; events go on a
  `queue.Queue`; widgets are touched **only** from the main thread via `root.after(50, _drain)`.
  Same pattern for the WebSocket worker in `web/server.py`. Don't bypass it.
- **A `GateGuard` hook in this environment blocks the first `Bash` call and every
  file write/edit** until you state a few facts in plain text (what calls the file,
  Glob-confirmed no duplicate, data shape, the user instruction). Expect this — just
  state the facts in your reply and retry the same call.

### Where to wire new things

| You want to add… | Touch |
|---|---|
| A new committee role | `committee/agents.py` (+ prompt + add to `Committee`); cards auto-render in all 3 front-ends from `build_committee()` |
| A new tool | `committee/data/*.py` (data fn) + `committee/domain_tools.py` (`reg.register(Tool(...))`) + give it to an agent via `tool_names` |
| A new model tier | `committee/config.py` constant + reference it from `agents.py` |
| Another front-end | New `EventBus` subscriber; do not touch `agentcore/` |
| A new event type | Add to `agentcore/events.py` docstring, handle in front-ends' switches, and in `ReportCollector` if it should land in the report |

### Tests follow a consistent pattern

Hand-rolled fakes, no `unittest.mock`. The fakes are tiny classes near the top of each
test file (`_ScriptedLLM`, `_StubAgent`, `_FakeTwse`, `_FakeDDGS`, `_FakeSession`).
Match this style for new tests — it stays readable and decouples from library versions
(the web tests, for example, deliberately avoid `starlette.TestClient` because the
installed `httpx`/`starlette` versions disagree on its constructor signature; we test
the route handlers as plain functions instead).

### Design specs

Living design lives in `docs/superpowers/specs/` (the design spec) and
`docs/superpowers/plans/` (the Phase 1 implementation plan). They are *historical/intent*
documents — when the spec disagrees with the code, the code is the source of truth;
update the spec rather than reverting the code.
