# Dynamic DISCUSSION Phase — Design Spec

**Date:** 2026-06-10
**Status:** Approved (pending spec review)
**Topic:** Let the committee agents argue with each other in a bounded, dynamic discussion phase — built on the existing engine, no agent framework.

## Goal

Add a **DISCUSSION** phase in which the committee's debaters argue with each other
over a bounded number of rounds — each agent sees the full running debate and
challenges / defends / revises positions — before the Chair issues the verdict.

This replaces the current rigid one-shot CHALLENGE → REBUTTAL with genuine
cross-talk, while preserving the EventBus, the grounding discipline, the report,
the tools, and all three front-ends. No new dependencies; the engine stays
synchronous.

## Evaluation note (why not AutoGen)

The goal is the *feature* (agents arguing), not adopting a framework. Microsoft
AutoGen's `SelectorGroupChat` would deliver dynamic debate but at the cost of an
async rewrite of the deliberately framework-free `agentcore/`, re-bridging every
front-end + the report to AutoGen's message model, re-wrapping the 8 tools, and
re-validating the flaky free **gemma** tier through AutoGen's client. A custom
discussion loop reuses the already-hardened sync core for the same user-visible
result. (Full evaluation is in the conversation; chosen approach = "A — custom".)

## Decisions (locked)

1. **Custom** discussion loop in the existing `Orchestrator` (no AutoGen/framework).
2. **Participants:** the **6 debaters** — the 4 research analysts (fundamental,
   technical, institutional, news) + the 2 challengers (risk manager, skeptic). The
   **chair** stays out (it judges at VERDICT) and the **verifier** stays out (it
   audits at VERIFY), keeping their impartial roles.
3. **Speaker order:** round-robin. `discussion_rounds` passes; each pass, the 6
   debaters speak once in roster order (analysts then challengers). Bounded call
   count = `6 × discussion_rounds` (default 2 → 12 turns) — predictable for the
   free gemma tier. No LLM moderator/selector (future enhancement).
4. **Replaces** the scripted CHALLENGE → REBUTTAL when on. Gated by
   `discussion_rounds` (core default `0` = off → old flow; the committee defaults
   it on via env).
5. **Per-turn grounding flags:** the verifier *agent* stays out of the debate, but
   the deterministic `check_grounding` audits every discussion turn — any unsourced
   figure raises a `grounding_flag` shown inline. No extra LLM cost; keeps the
   verifier's impartial final-audit role.

## Components

### 1. `Orchestrator` — the DISCUSSION phase

`agentcore/orchestrator.py`:

- Add fields: `discussion_rounds: int = 0` and
  `discussion_task_template: str = _DEFAULT_DISCUSSION_TASK`.
- Add a domain-neutral default template:
  `_DEFAULT_DISCUSSION_TASK = ("Here is the committee discussion so far. From your "
  "perspective, challenge the points you disagree with and defend or revise your own "
  "view on {stock}, in one short paragraph. Cite only figures supported by the data "
  "your tools returned; never invent numbers.")`
- In `run(...)`, after RESEARCH:
  - **If `discussion_rounds > 0`:** run the DISCUSSION phase (below) — and **skip**
    the existing CHALLENGE and REBUTTAL blocks.
  - **Else:** run the existing CHALLENGE → REBUTTAL unchanged.
- DISCUSSION loop:
  ```
  phase("DISCUSSION")
  debaters = list(self.research) + list(self.challengers)   # the 6
  for _ in range(self.discussion_rounds):
      for a in debaters:
          text = run_agent(a, self.discussion_task_template.format(stock=stock_no),
                           context=_join(transcript))        # full running debate
          transcript.append((a.name, text))
  ```
  Each turn emits the same events `Agent.run` already emits (`phase` start, `token`,
  `tool_call`, `tool_result`, `message`) — so the live feed shows the argument and
  agents keep their tools; the EvidenceLedger keeps recording.
- VERDICT, REFLECT, VERIFY are unchanged (the Chair's VERDICT prompt already
  consumes the full `transcript`, which now includes the discussion).

### 1b. Per-turn grounding flags (discussion integrity)

The verifier *agent* stays out of the argument, but its **auditing function** is
applied to every discussion turn **deterministically** (no LLM call). After each
turn, the orchestrator runs `check_grounding(turn_text, ledger)`; if any figure the
agent cited is not backed by a recorded tool result, it emits a flag:

```python
text = run_agent(a, ...)
transcript.append((a.name, text))
g = check_grounding(text, ledger)
if not g["grounded"]:
    bus.emit(Event(type="grounding_flag", agent=a.name,
                   data={"unsupported": g["unsupported"]}))
```

So a debater that fabricates a number to win a point is flagged the moment it
speaks, while the verifier keeps its impartial *final*-audit role. Wiring:

- `agentcore/events.py`: document the new `grounding_flag` event type.
- `agentcore/report.py` `ReportCollector`: capture `grounding_flag` events so they
  land in the report.
- Front-ends render an inline warning beneath the flagged turn:
  - `web/static/app.js` `handleEvent`: on `grounding_flag`, append a small warning
    line (`⚠ {ui.unverified_label}: <figures>`) in the feed (styled like `.err`).
  - `gui.py` `_handle`: append the same warning line to the feed.
  - `committee/report.py` `_transcript`: render the flag inline after the agent's
    turn in the appendix.
- Label: add `unverified_label` (`未驗證數字` / `unverified figure`) to `tw_ui()` /
  `us_ui()` (web/GUI) and `ReportLabels.text` (report), per market.

This is deterministic and reuses the existing `check_grounding` — zero extra LLM
cost. (The same check still runs once more on the Chair's final verdict, unchanged.)

### 2. Config + committee wiring

- `committee/config.py`: `DISCUSSION_ROUNDS = int(os.environ.get("DISCUSSION_ROUNDS", "2"))`
  (default 2; `0` disables). Read like `REFLECTION_PASSES`.
- The three front-ends / run worker (`main.py`, `gui.py:_run_worker`,
  `committee_web/run.py`) already build the `Orchestrator`; add
  `discussion_rounds=DISCUSSION_ROUNDS` and
  `discussion_task_template=t.discussion` to each `Orchestrator(...)` call
  (where `t` is `profile.templates`).

### 3. Templates (per market)

- `committee/markets/base.py` `Templates` dataclass: add a `discussion: str` field.
- `committee/markets/tw.py` `tw_templates()`: add a Traditional-Chinese discussion
  prompt (e.g. *"以下是委員會目前的討論。請從你的專業立場,針對你不認同的論點提出質疑,"
  "並捍衛或修正你對 {stock} 的看法(一段話)。只引用工具回傳、有數據支持的數字,不得捏造。"*).
- `committee/markets/us.py` `us_templates()`: the English equivalent.
- (`main.py`/`gui.py`/`committee_web/run.py` pass `t.discussion` as above.)

### 4. Phase label + pipeline display

- `phase_names` (in `tw_labels()` / `us_labels()` `ReportLabels`): add
  `"DISCUSSION": "討論交鋒"` (TW) / `"DISCUSSION": "Discussion"` (US). The report
  transcript and live status pick this up automatically.
- `committee_web/views.py` `committee_info`: return `discussion_rounds`
  (`from committee.config import ... DISCUSSION_ROUNDS`), alongside the existing
  `reflection_passes`.
- `web/static/app.js` `buildPipeline`: when
  `roster.discussion_rounds > 0`, push a single `phase:DISCUSSION` card **in place
  of** `phase:CHALLENGE` + `phase:REBUTTAL`; otherwise keep the two as today
  (mirrors the existing `if (roster.reflection_passes > 0)` REFLECT handling).
- `gui.py` `_build_pipeline`: the same conditional (a DISCUSSION step when
  `REFLECTION_PASSES`-style `DISCUSSION_ROUNDS > 0`, replacing CHALLENGE/REBUTTAL).
- CLI (`main.py` `TerminalRenderer`) needs no change — it prints whatever `phase`
  events arrive.

## Data flow

RESEARCH (each analyst once, with tools) → **DISCUSSION** (6 debaters × N rounds,
each seeing the full transcript, with tools; **each turn deterministically
grounding-checked → `grounding_flag` on unsourced figures**) → VERDICT (Chair
synthesizes the whole transcript) → REFLECT (optional) → VERIFY (grounding +
verifier + one correction). Every figure in the verdict is still checked by the
unchanged `check_grounding`; now every figure *in the debate* is checked too.

## Testing

- `tests/test_orchestrator.py`:
  - With `discussion_rounds=2`, a fake roster, and a scripted fake LLM: a
    `DISCUSSION` phase event is emitted; each of the 6 debaters speaks exactly twice;
    the Chair's VERDICT task receives the discussion turns; CHALLENGE/REBUTTAL phase
    events are **not** emitted.
  - With `discussion_rounds=0` (default), the existing CHALLENGE → REBUTTAL path runs
    unchanged (existing tests stay green).
  - **Grounding flag:** a discussion turn whose text cites a figure absent from the
    ledger emits a `grounding_flag` event for that agent; a fully-grounded turn does
    not. (Fake LLM returns a turn with an unsupported number; assert the event.)
  - `test_default_templates_are_domain_neutral` still passes (the new default
    template is generic English, no market words).
- `tests/test_config.py`: `DISCUSSION_ROUNDS` default is 2; env override respected.
- `tests/test_markets.py`: `phase_names["DISCUSSION"]` present for tw/us;
  `Templates.discussion` non-empty for both; `unverified_label` in both `ui` dicts
  (keeps the `set(tw)==set(us)` check green) and both `ReportLabels.text`.
- `tests/test_django_web.py`: `committee_info` returns `discussion_rounds`.
- `tests/test_report.py`: a transcript containing DISCUSSION turns renders (the
  phase label appears in the appendix); a captured `grounding_flag` renders its
  warning inline in the transcript.
- Front-end pipeline (web/gui) shows a DISCUSSION step when rounds > 0 — browser
  smoke (web) + structural check (gui).
- Full suite stays green.

## Risks / notes

- **Cost on the free gemma tier:** discussion adds `6 × rounds` LLM calls (12 at the
  default). Bounded and env-tunable (`DISCUSSION_ROUNDS=1` for cheap runs, `0` to
  disable). gemma's shaky tool-calling already degrades gracefully (`Agent.run`
  never raises; missing data → "資料暫無").
- **Grounding still holds:** agents are told to cite only tool-sourced numbers, and
  the deterministic `check_grounding` on the final verdict is unchanged, so an agent
  asserting an unsourced figure mid-argument is still caught and flagged.
- **Backward-compatible:** `discussion_rounds=0` preserves the exact current flow,
  so the neutral-core orchestrator tests and the scripted CHALLENGE/REBUTTAL path
  remain valid.

## Out of scope

- An LLM **moderator** that picks the next speaker dynamically (round-robin is
  bounded and reliable; selector is a future enhancement).
- AutoGen or any agent framework.
- Consensus-detection early stop (fixed round count keeps cost predictable).
- CLI pipeline-card changes (the terminal renderer is phase-event driven already).
