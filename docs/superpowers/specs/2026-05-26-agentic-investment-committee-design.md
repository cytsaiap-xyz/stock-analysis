# Design Spec: Agentic Investment Committee (台股投資委員會)

**Date:** 2026-05-26
**Status:** Approved design — ready for implementation planning
**Author:** Brainstormed with Claude (superpowers:brainstorming)

---

## 1. Summary

Build a **general-purpose, multi-agent AI architecture** whose flagship demo is a
**live "investment committee"** of 7 specialist agents that analyze a single Taiwan
stock, debate in real time, and converge on a recommendation. The user watches the
debate unfold in a browser (group-chat style), and the system saves a shareable
HTML analyst report at the end.

The "wow factor" is the **live, adversarial debate** between specialist agents, each
using real tools against real Taiwan market data. The reusable agent core (which has
zero stock knowledge) delivers the "general-purpose architecture" goal: swap the
domain layer and the same engine becomes any multi-agent committee.

### Goals
- Demonstrate genuine agentic behavior: role specialization, autonomous tool use,
  inter-agent communication, orchestration, and convergence.
- Produce a clean, **reusable agent core** independent of the stock domain.
- Use **free NVIDIA-hosted models** (OpenAI-compatible API) and **free TWSE open data**.
- Produce an **analyst-grade HTML report** as the durable artifact.
- **Self-verify before delivering:** fact-check the final verdict against the real
  tool data so no hallucinated figure reaches the user; show a verification summary.

### Non-Goals (YAGNI)
- No live trading, order execution, or brokerage integration. Analysis only.
- No intraday/tick data. EOD (daily) data is sufficient for analyst reports.
- No user accounts, auth, billing, or multi-tenant concerns.
- No PDF/Markdown export in v1 (HTML only).
- No persistence beyond saved report files and a data cache.

---

## 2. Decisions (locked during brainstorming)

| # | Decision | Choice |
|---|----------|--------|
| 1 | Wow moment | **Live multi-agent committee debate**, watched in real time |
| 2 | Stock data source | **TWSE / TPEx official open APIs** (free, no key, EOD) + DuckDuckGo for news |
| 3 | Interface | **Web app** — FastAPI + WebSocket backend, vanilla-JS browser UI |
| 4 | Committee roster | **All 7 agents** (Chair, Fundamental, Technical, Institutional, News, Risk, Skeptic) |
| 5 | Dashboard layout | **Group-Chat Debate Feed** (Layout B); engine also supports Layout A later |
| 6 | Model strategy | **Two-tier**: strong reasoner for Chair/Skeptic/Risk; fast tool-caller for data analysts. Model = per-agent config, model-agnostic core |
| 7 | Agent framework | **Hand-rolled lightweight core** on the OpenAI SDK (no LangGraph/CrewAI/AutoGen) |
| 8 | Python version | Design for **Python 3.9 compatibility** (runs on current 3.9.2; also 3.11+). Upgrade optional |
| 9 | News search | **DuckDuckGo** (`ddgs`), free, no key |
| 10 | Final deliverable | **HTML report only** (self-contained: transcript + tables + charts + verdict) |
| 11 | Self-verification | **Yes** — a VERIFY step fact-checks the verdict against captured tool data before the report is delivered (see §4, §6) |

---

## 3. Architecture

Three layers. The core knows nothing about stocks; the domain layer knows nothing
about HTTP/WebSocket.

```
┌─────────────────────────────────────────────────────────┐
│  WEB LAYER   FastAPI + WebSocket  ·  vanilla-JS chat UI   │  shows the live debate
├─────────────────────────────────────────────────────────┤
│  DOMAIN LAYER (Taiwan stocks)                             │
│   • 7 debate agents + Verifier (role + prompt + tools)    │  swap this to re-target
│   • TWSE tools, indicator calcs, HTML report builder      │
├─────────────────────────────────────────────────────────┤
│  AGENT CORE  (generic, reusable, ~300 lines)              │
│   • LLMClient    – NVIDIA OpenAI-compatible API,          │
│                    model-agnostic, streaming + tool-calls │
│   • Tool         – registry: a Python fn + JSON schema    │
│   • Agent        – role, system prompt, model, tool set;  │
│                    runs a tool-calling loop, emits events │
│   • Orchestrator – runs the Chair-led debate rounds       │
│   • EventBus     – every token/tool-call/message streamed │
│   • EvidenceLedger – records every tool call + result so   │
│                    claims can be fact-checked (grounding)  │
└─────────────────────────────────────────────────────────┘
```

### Core components
- **`LLMClient`** — the only component that touches NVIDIA. Wraps the
  OpenAI-compatible endpoint (`https://integrate.api.nvidia.com/v1`), supports
  streaming and function-calling, and is model-agnostic (model passed per call).
  Implements retry with backoff on transient errors.
- **`Tool` / `ToolRegistry`** — wraps an ordinary Python function with a JSON schema
  so the LLM can call it via standard function-calling. Adding a capability = writing
  one function and registering it.
- **`Agent`** — holds a role, system prompt, model id, and a set of tools. Runs the
  tool-calling loop (call LLM → if tool calls, execute and feed results back → repeat
  until a final message). Emits structured events as it works.
- **`Orchestrator`** — drives the debate protocol (Section 4): assigns work, runs
  research in parallel, runs debate rounds sequentially, asks the Chair for the verdict.
- **`EventBus`** — the mechanism that makes it "live." Every agent emits events
  (`token`, `tool_call`, `tool_result`, `message`, `phase`, `verdict`, `verification`).
  The web layer subscribes and forwards them to the browser. A terminal renderer can
  subscribe to the same events with no core changes (enables Layout A later).
- **`EvidenceLedger`** — records every `(tool, args, result)` produced during a run.
  This is the source of truth the verification step checks the verdict against. Lives in
  the core (generic): any committee in any domain gets grounding for free.
- **`Verifier`** — runs after the verdict (Section 4, step 6). Two parts: (a) a
  **deterministic grounding check** that extracts the quantitative claims in the verdict
  and confirms each is consistent with the `EvidenceLedger` (no invented numbers); and
  (b) an **LLM verification pass** (reasoner tier) that checks the verdict is logically
  consistent with the debate and flags contradictions. The grounding check is generic
  (core); the verifier's prompt lives in the domain layer like the other agents.

### Why this shape
- Live feel comes free from `EventBus` — no batching.
- Model choice is pure config — proves the "general-purpose / model-agnostic" claim.
- Core has zero stock knowledge → genuinely reusable for other committee domains.
- Each unit is independently testable (tools are pure-ish fns; Agent runs on a mock
  LLMClient; Orchestrator runs on mock agents).

---

## 4. Committee & debate protocol

### Roster (7 agents)
| Agent | 中文 | Tools | Tier |
|-------|------|-------|------|
| Chair / Moderator | 主席 | (none — orchestrates, synthesizes) | reasoner |
| Fundamental Analyst | 基本面 | `get_valuation`, `get_monthly_revenue` | tool-caller |
| Technical Analyst | 技術面 | `get_price_history`, `compute_indicators` | tool-caller |
| Institutional Flow Analyst | 籌碼面 | `get_institutional_flows` | tool-caller |
| News & Sentiment Analyst | 新聞輿情 | `search_news` | tool-caller |
| Risk Manager | 風險經理 | `get_price_history`, `compute_risk` | reasoner |
| Skeptic / Devil's Advocate | 唱反調者 | (none — pure adversary) | reasoner |

The 7 above are the **debate** members. A **Verifier (查核員)** runs *after* the debate
as a verification step (reasoner tier) — not a debate participant — see step 6 below.

### Debate flow
```
1. OPEN      Chair states the question, assigns the analysts.
2. RESEARCH  Fundamental, Technical, Institutional, News run IN PARALLEL —
   (parallel)   each calls its tools, posts an opening statement + initial lean.
3. CHALLENGE Risk Manager + Skeptic read those statements and attack weak points.
   (sequential)
4. REBUTTAL  Analysts get ONE bounded round to defend / revise.
   (sequential)
5. VERDICT   Chair synthesizes → BUY / HOLD / SELL, target price, confidence %,
                and the 3 biggest risks.
6. VERIFY    Verifier fact-checks the verdict against the EvidenceLedger:
                (a) deterministic grounding check of every cited number,
                (b) LLM consistency check vs. the debate.
                • All grounded + consistent → pass, emit a verification summary.
                • Unsupported claim found → ONE correction round back to the Chair;
                  if still unsupported, the figure is flagged/annotated, not hidden.
7. REPORT    Report builder compiles transcript + data + verdict + verification
                summary into HTML.
```

**Design choices:** research is parallel (fast + impressive); debate is sequential so
agents react to each other; rounds are **bounded** (one challenge + one rebuttal) to
keep cost, latency, and tokens predictable. (Possible later enhancement: let the Chair
trigger a second round if the committee is split — out of scope for v1.)

### Data flow / streaming
```
Browser --WS--> FastAPI --> Orchestrator --> Agent.run()
                                               │ LLMClient (stream=True)
                                               │ emits token/tool_call/tool_result/message
                              EventBus <───────┘
Browser <--WS-- FastAPI <-- EventBus   (every event forwarded instantly)
```

---

## 5. Tools & data sources

All built on free TWSE open APIs (no key) plus one free search tool.

| Tool function | Data source | Used by |
|---|---|---|
| `get_price_history(stock_no, months)` | TWSE `STOCK_DAY` (daily OHLCV, per-month JSON) | Technical, Risk |
| `get_valuation(stock_no)` | TWSE `BWIBBU_ALL` (P/E, P/B, 殖利率) | Fundamental |
| `get_monthly_revenue(stock_no)` | TWSE/MOPS monthly revenue open data (月營收 YoY/MoM) | Fundamental |
| `get_institutional_flows(stock_no, days)` | TWSE `T86` (三大法人 net buy/sell) | Institutional |
| `search_news(query)` | DuckDuckGo (`ddgs`, free, no key) | News/Sentiment |
| `compute_indicators(ohlcv)` | pure `pandas` (MA5/20/60, volume, support/resistance) | Technical |
| `compute_risk(ohlcv)` | pure `pandas` (volatility, max drawdown, β vs TAIEX) | Risk |

### Notes & risks
- **Caching:** TWSE responses cached to disk per (endpoint, stock, date) for instant
  re-runs and to avoid hammering TWSE. Pure-compute tools need no network.
- **Feasibility risk — `get_monthly_revenue` and `search_news`:** these two sources can
  change shape. Each is isolated behind a tool function, so a source swap (or, worst
  case, dropping that single tool) requires **no change to any agent or the core**. The
  exact endpoint URLs/parameters are to be verified during implementation; if monthly
  revenue cannot be reliably sourced from TWSE open data, an alternative free source
  will be wired behind the same `get_monthly_revenue` interface.
- **New dependency:** `ddgs` (DuckDuckGo search) is the only added runtime dep beyond
  what is already installed.

---

## 6. Error handling

The debate must never crash.
- **Tool errors** are caught and returned to the LLM as a structured "tool failed"
  result; the agent adapts or honestly states the data gap (visible in the feed). No
  hallucinated numbers when data is missing.
- **LLM errors:** retry with backoff on rate-limit/5xx. A model that tool-calls poorly
  is swappable via config (per-agent model mapping).
- **TWSE / network:** request timeouts + cached fallback; missing data → the analyst
  explicitly states the gap.
- **WebSocket disconnect:** the run continues server-side; the client reconnects and
  replays buffered events.
- **Startup:** fail fast with a clear message if `NVIDIA_API_KEY` is missing.
- **Verification failure:** if the Verifier finds an unsupported claim, the Chair gets
  **one** correction round; if it still can't be grounded, the report ships with that
  figure explicitly flagged as unverified (never silently dropped or hidden).

---

## 7. Project structure

```
llm-test/
  agentcore/          # GENERIC reusable core — zero stock knowledge
    __init__.py
    llm.py            #   LLMClient
    tools.py          #   Tool + ToolRegistry
    agent.py          #   Agent (tool-calling loop, emits events)
    orchestrator.py   #   Orchestrator (debate rounds + verify step)
    events.py         #   EventBus + event types
    evidence.py       #   EvidenceLedger (records tool calls + results)
    verify.py         #   deterministic grounding check (claims vs ledger)
  committee/          # DOMAIN layer — Taiwan stocks
    __init__.py
    agents.py         #   the 7 debate agents + the Verifier definition
    config.py         #   agent→model mapping (two-tier), settings
    data/
      twse.py         #   TWSE client + disk cache
      indicators.py   #   pandas indicator/risk math
    domain_tools.py   #   the 7 tool functions
    report.py         #   HTML report builder
  web/
    server.py         #   FastAPI app + WebSocket endpoint
    static/
      index.html      #   group-chat dashboard (Layout B)
      app.js          #   WS client: renders messages / tool-chips / verdict
      style.css
  tests/
    test_tools.py
    test_agent.py
    test_orchestrator.py
    test_twse.py
  reports/            # generated HTML reports (gitignored)
  cache/              # cached TWSE responses (gitignored)
  pyproject.toml      # or requirements.txt
  .env.example        # NVIDIA_API_KEY
  test_kimi.py        # existing NVIDIA connectivity smoke test (kept)
```

---

## 8. Testing strategy (TDD, 80%+ coverage)

- **Unit:** tool functions (mock TWSE HTTP via recorded fixtures), indicator/risk math
  (deterministic), HTML report builder.
- **Agent:** run against a **mock LLMClient** returning scripted tool-calls/messages →
  assert the emitted event sequence.
- **Orchestrator:** mock agents → assert phases run in order, research is parallel,
  rounds are bounded, a verdict event is emitted.
- **Verification:** grounding checker is deterministic — feed a verdict with a planted
  hallucinated number + an EvidenceLedger and assert it's flagged; feed a fully grounded
  verdict and assert it passes. Assert the one-round correction path and the
  "flag-not-hide" behavior on persistent failure.
- **Integration (optional, marked):** one live smoke test hitting real NVIDIA + TWSE for
  a known ticker (e.g. `2330`).
- Follow TDD: write the failing test first, implement minimally, refactor.

---

## 9. Phasing

Each phase runs end-to-end on its own.

1. **MVP** — core + `LLMClient` + `EvidenceLedger` + 3 tools (`get_price_history`,
   `get_valuation`, `get_institutional_flows`) + 3 agents (Fundamental, Technical,
   Chair). Events printed to the terminal. Proves the engine end-to-end against real data
   + a real model. (Ledger is cheap and earns its keep in Phase 2.)
2. **Full committee + verification** — all 7 agents + remaining tools +
   challenge/rebuttal rounds + the **VERIFY step** (deterministic grounding check +
   LLM consistency pass + one correction round).
3. **Web UI** — FastAPI + WebSocket + the group-chat dashboard (Layout B).
4. **Report + polish** — HTML report builder, disk caching, embedded charts.

---

## 10. Open items to resolve during implementation

- Verify exact TWSE endpoint URLs/params for `STOCK_DAY`, `BWIBBU_ALL`, `T86`, and a
  reliable free monthly-revenue source (`get_monthly_revenue`).
- Confirm which specific NVIDIA free models are reliable tool-callers and finalize the
  two-tier mapping in `committee/config.py`.
- Decide the charting approach for the HTML report (e.g. lightweight inline SVG/JS
  charts vs. a small charting lib) during Phase 4.
