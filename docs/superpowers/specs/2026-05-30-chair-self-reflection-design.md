# Chair Self-Reflection (Self-Refine) — Design

**Date:** 2026-05-30
**Status:** Approved (design); implementation pending

## Problem

The committee produces a Chair verdict in one shot. There is no step where the
Chair re-examines its *own* reasoning before the verdict is finalized. CHALLENGE
(peers attack) and VERIFY (an external verifier + deterministic grounding) already
exist, but neither is the Chair reflecting on itself. Adding a Self-Refine pass
improves final-verdict quality (soundness, internal consistency, data support).

## Decisions (from brainstorming)

1. **Layer:** Chair self-reflects before finalizing the verdict.
2. **Placement:** REFLECT runs *after* the draft verdict and *before* VERIFY, so the
   deterministic grounding check remains the final safety net over the refined text.
3. **Iterations:** single pass by default, env-configurable.

## Flow

```
RESEARCH → CHALLENGE → REBUTTAL → VERDICT (draft) → REFLECT (new) → VERIFY
```

## Core changes — `agentcore/orchestrator.py` (stays domain-neutral)

- Add fields:
  - `reflect_task_template: str = _DEFAULT_REFLECT_TASK` (neutral English default).
  - `reflection_passes: int = 0` — **default 0 = off**, so existing orchestrator tests
    (which construct `Orchestrator` with defaults and assert exact phase lists /
    `chair.tasks` counts) are unaffected. Mirrors the optional `verifier=None` pattern.
- After the draft verdict, if `reflection_passes > 0`:
  - emit `phase` event `REFLECT`;
  - loop `reflection_passes` times: one Chair call per pass, `context` = the current
    verdict; the template instructs the Chair to check whether its reasoning is sound,
    internally consistent, and data-supported, then output **only** the improved
    recommendation in the exact same format (建議/信心/理由). The self-critique folds
    into the 理由 line — it must NOT emit a separate free-form critique, to avoid
    polluting the verdict format (the gpt-oss English-scratchpad failure mode).
- The `verdict` event is emitted **after** the reflection loop, carrying a
  `reflected: True` flag (mirrors the existing `corrected: True`). With
  `reflection_passes == 0` the observable behavior is byte-identical to today (one
  draft verdict event, no REFLECT phase).

## Domain layer

- `committee/agents.py`: add Traditional-Chinese `REFLECT_TASK_TEMPLATE`.
- `committee/config.py`: `REFLECTION_PASSES = int(env.get("REFLECTION_PASSES", "1"))`
  (default on; set `REFLECTION_PASSES=0` to disable).
- `main.py` / `gui.py` / `web/server.py`: pass
  `reflect_task_template=REFLECT_TASK_TEMPLATE, reflection_passes=REFLECTION_PASSES`
  when constructing the `Orchestrator`.

## Observability

Reuse existing event types — `phase` emits `REFLECT`; the refined verdict flows
through the existing `verdict` event (with the `reflected` flag). **No new event type**,
so `ReportCollector` needs no changes. The terminal renderer prints phase headers
generically, so REFLECT shows automatically. The GUI and web build *fixed* pipeline
cards keyed on phase name, so they each gain a conditional REFLECT card (shown only when
`reflection_passes > 0`): GUI `PHASE_ZH` + `steps`; web `_PHASE_ZH` + `/api/committee`
`reflection_passes` + `app.js`. Card status transitions are handled by the existing
generic phase handler, and missing-card lookups are already null-safe.

## Testing (TDD)

- `reflection_passes=1`: phase sequence includes `REFLECT`; Chair runs one extra
  time; the returned verdict is the reflected one.
- `reflection_passes=0` (default): phase sequence and Chair-call count unchanged
  (covered by existing tests).
- With a verifier present + reflection on: order is
  RESEARCH → CHALLENGE → REBUTTAL → VERDICT → REFLECT → VERIFY.
- The new `_DEFAULT_REFLECT_TASK` is domain-neutral (`"Taiwan"` absent, `{stock}`
  present) — extend `test_default_templates_are_domain_neutral`.
- `committee/config.py`: `REFLECTION_PASSES` defaults to 1 and is env-overridable.

## Out of scope (YAGNI)

- Multi-pass reflection loops (single pass only; env can raise it).
- New event types / front-end UI changes.
- A separate draft-vs-reflected comparison artifact in the report.
