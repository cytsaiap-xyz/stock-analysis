# AutoGen Dynamic Discussion Routing — Design Spec

**Date:** 2026-06-14
**Status:** Approved (pending spec review)
**Topic:** Add a **dynamic speaker-routing** mode to the DISCUSSION phase by running it as a Microsoft AutoGen `SelectorGroupChat`, surgically — the rest of the engine, the 8 tools, the report, and the 3 front-ends stay as they are.

## Goal

Today the DISCUSSION phase is a fixed **sequential round-robin**: the 6 debaters speak once each per round, in roster order, for `DISCUSSION_ROUNDS` rounds. There is no moderator choosing who speaks and no way for the debate to end early.

Add an **opt-in dynamic mode** where a selector (an LLM moderator) decides who speaks next based on the running debate, and the debate can stop early once the committee converges — delivered via AutoGen's `SelectorGroupChat`. This is the one capability AutoGen genuinely provides out of the box that the round-robin loop does not.

## Why surgical (and an honest note on what AutoGen provides here)

A full migration of `agentcore/` to AutoGen would mean an async rewrite of the synchronous core, re-bridging the EventBus across CLI/GUI/Django + the report, re-wrapping all 8 tools, and re-validating gemma end-to-end — to obtain a feature that lives entirely in one phase. So we replace **only** the DISCUSSION phase, behind the existing phase boundary, and keep everything else synchronous and unchanged.

**Honest scope note.** Because the chosen failure behavior is *per-turn* fallback (see Decisions), the speaker-selection logic lives in **our** `selector_func`, not in AutoGen's internal selector loop. In this design AutoGen supplies the **team runtime, the message protocol, and the termination conditions**; the resilient speaker-picking is ours. This is the right trade for per-turn resilience, but it means AutoGen is doing less than "it picks the speakers" — the spec states this plainly so the value is clear-eyed.

## Decisions (locked)

1. **Scope: surgical.** Replace only the DISCUSSION phase. RESEARCH / VERDICT / REFLECT / VERIFY stay synchronous and unchanged; tools, report, and all three front-ends are untouched.
2. **AutoGen track:** `autogen-agentchat` **0.4+** (the current/maintained line), run inside a single `asyncio.run(...)` at the DISCUSSION boundary so the rest of the engine stays synchronous. (Not the legacy `pyautogen` 0.2.)
3. **Selector model:** the existing **reasoner tier** (`MODEL_REASONER`, same one the Chair/Risk/Skeptic use).
4. **Termination: turn budget + early stop.** The selector routes freely up to a hard cap `DISCUSSION_MAX_TURNS` (default 12), but the debate ends early on a `<CONSENSUS>` sentinel.
5. **Fallback: per-turn round-robin pick.** If the *selector* call fails/returns an unparseable name on a given turn, that turn's speaker is chosen by round-robin and the dynamic debate continues. (Plus a phase-level guard: if AutoGen can't import/build, the whole phase falls back to the existing round-robin discussion.)
6. **Grounding flags kept.** Each discussion turn is still deterministically grounding-checked against the RESEARCH-populated `EvidenceLedger`; unsourced figures raise the existing `grounding_flag` event.
7. **Tool-free discussion agents (AutoGen path).** The dynamic-mode debaters argue over the evidence RESEARCH already gathered; they do not call tools. This avoids re-wrapping the 8 tools as AutoGen `FunctionTool`s. (Tool use during discussion is a possible later extension.)
8. **Opt-in, non-breaking.** A new env `DISCUSSION_MODE` selects `roundrobin` (**default**, today's proven path) or `dynamic` (AutoGen). The existing round-robin behavior is the default and is preserved exactly.

## Architecture

```
DISCUSSION_MODE = roundrobin (default)            DISCUSSION_MODE = dynamic
------------------------------------              ------------------------------------
RESEARCH (sync)                                   RESEARCH (sync)
DISCUSSION: round-robin loop (today)              DISCUSSION: asyncio.run(SelectorGroupChat)
VERDICT / REFLECT / VERIFY (sync)                 VERDICT / REFLECT / VERIFY (sync)
```

The orchestrator gains a `discussion_mode` field and a single dispatch point. The current discussion loop is extracted verbatim into `_run_discussion_roundrobin(...)`. When `discussion_mode == "dynamic"`, the orchestrator calls into a new module that runs the AutoGen team and returns the produced turns, which are appended back into the same synchronous `transcript` the Chair consumes at VERDICT.

### Data flow (dynamic mode)

```
RESEARCH (sync) -> transcript + EvidenceLedger
DISCUSSION  (one asyncio.run at the phase boundary):
   build SelectorGroupChat(participants=6 AutoGen agents,
                           selector_func=resilient_pick,
                           termination=MaxMessageTermination(MAX_TURNS)
                                       | TextMentionTermination("<CONSENSUS>"))
   stream the team:
       selector_func: reasoner picks next speaker
                      (exception / empty / unknown name  ->  round-robin next)
       chosen speaker produces a turn
       bridge turn -> message Event on EventBus
                   -> check_grounding(text, ledger) -> grounding_flag if unsourced
   stop on <CONSENSUS> or MAX_TURNS
   append every turn into the sync `transcript`
VERDICT / REFLECT / VERIFY (sync, unchanged)
```

## Components

### 1. `agentcore/discussion_autogen.py` (new)

Self-contained module that owns all AutoGen knowledge so the rest of `agentcore/` stays framework-free. Responsibilities:

- **Model client:** an `OpenAIChatCompletionClient` pointed at the same Gemini-compatible `base_url`/key the engine already uses. Because gemma is not an OpenAI model, AutoGen 0.4 **requires an explicit `model_info`** — set `vision=False`, `function_calling=False`, `json_output` per capability, `family="unknown"`. (Wrong `model_info` is the most likely first-run failure; called out here deliberately.)
- **Agents:** wrap the 6 debaters as `AssistantAgent`s, each with `system_message` = the agent's existing persona (`system_prompt`) and a role-anchored task framing consistent with the current round-robin prompts (role + others' points + own stance + "answer in your own words, don't repeat others"). The framing also tells each agent: **if it believes the committee has converged and it has nothing new to add, reply with exactly `<CONSENSUS>`** — this is what drives early stop (caught by `TextMentionTermination`). No tools (Decision 7).
- **`resilient_pick(messages) -> str`** (the `selector_func`): builds a selector prompt from the running messages + the candidate roster, calls the reasoner model to return a single speaker name, parses it; on **any** exception, empty result, or name not in the roster, returns the **round-robin next** speaker (tracked by an internal counter). Never returns `None` (so AutoGen never falls back to its own internal selector). Early termination is **agent-driven** via the `<CONSENSUS>` sentinel (above), not decided by the selector — the selector only chooses *who* speaks, never *whether to stop*.
- **`run_dynamic_discussion(debaters, stock_no, agent_labels, max_turns, emit, ledger) -> List[Tuple[str, str]]`**: the public entry point. Builds the team, runs it with `asyncio.run`, bridges each produced message via the `emit` callback (which the orchestrator wires to the EventBus + grounding check), strips the `<CONSENSUS>` sentinel, and returns the list of `(speaker_name, text)` turns. Raises only on construction/import failure (so the orchestrator can guard at the phase level).

### 2. `agentcore/orchestrator.py`

- Add field `discussion_mode: str = "roundrobin"`.
- Extract the existing dynamic-prompt round-robin loop into `_run_discussion_roundrobin(...)` (behavior unchanged).
- At the DISCUSSION dispatch point:
  ```
  if self.discussion_rounds > 0:
      phase("DISCUSSION")
      if self.discussion_mode == "dynamic":
          try:
              turns = run_dynamic_discussion(debaters, stock_no, self.agent_labels,
                                             self.discussion_max_turns, emit, ledger)
              transcript.extend(turns)
          except Exception:               # import/construction failure
              emit_note("dynamic discussion unavailable; using round-robin")
              self._run_discussion_roundrobin(...)   # phase-level fallback
      else:
          self._run_discussion_roundrobin(...)
  ```
- Add field `discussion_max_turns: int = 12`. The grounding-flag emission + EventBus `message` events are produced by the bridge callback the orchestrator passes in, so the event protocol is identical to today.

### 3. `committee/config.py`

- `DISCUSSION_MODE = os.environ.get("DISCUSSION_MODE", "roundrobin")` — `roundrobin` | `dynamic`.
- `DISCUSSION_MAX_TURNS = int(os.environ.get("DISCUSSION_MAX_TURNS", "12"))`.
- Wire both into each `Orchestrator(...)` construction site (`main.py`, `gui.py`, `committee_web/run.py`) alongside the existing `discussion_rounds` / `agent_labels`.

### 4. Front-ends

**No changes required.** Dynamic mode only changes *which* agent speaks *when*; turns still arrive as `message` events and the live feed appends them in arrival order. The pipeline cards remain cosmetic. The report renders the transcript by phase as today. Grounding flags flow through unchanged.

### 5. `requirements.txt`

- Add `autogen-agentchat>=0.4` and `autogen-ext[openai]` (pulls in `autogen-core` + transitive deps). First third-party agent framework in the tree; isolated to `discussion_autogen.py`.

## Error handling / degradation (layered)

1. **Phase-level guard:** `autogen-agentchat` missing or team construction fails → log a `message` note, run the existing round-robin discussion. A committee run never hard-breaks because of dynamic mode.
2. **Per-turn selector fallback (Decision 5):** selector exception / empty / unknown name → round-robin next speaker for that turn; the dynamic debate continues.
3. **Per-turn agent failure:** consistent with today's `Agent.run` — a model/tool error becomes a recorded note, not a crash.
4. **Early stop:** a turn containing `<CONSENSUS>` (or reaching `MAX_TURNS`) ends the phase; the sentinel is stripped before display and grounding.
5. **gemma `model_info`:** set explicitly for the non-OpenAI model; documented as the most likely first-run failure point.

## Testing

Mirrors the repo's hand-rolled-fakes convention (no `unittest.mock`); the default suite stays network-free.

- `tests/test_discussion_autogen.py` (new):
  - `resilient_pick` returns a valid selector name when the fake selector yields one; falls back to the **round-robin next** speaker when the fake selector raises or returns an unknown name.
  - The bridge: feeding a synthetic AutoGen-style message through the `emit` path produces a `message` Event and a `grounding_flag` for a figure absent from the ledger; a grounded turn produces no flag.
  - `<CONSENSUS>` sentinel stripping: a turn carrying the sentinel is returned without it and ends the run.
- `tests/test_orchestrator.py`:
  - `discussion_mode="roundrobin"` (default) runs the existing path — all current discussion tests stay green.
  - `discussion_mode="dynamic"` with a stubbed `run_dynamic_discussion` extends the transcript with returned turns and still emits `phase` events `RESEARCH -> DISCUSSION -> VERDICT`; a stubbed construction failure triggers the round-robin phase-level fallback.
- `tests/test_config.py`: `DISCUSSION_MODE` / `DISCUSSION_MAX_TURNS` defaults + env override.
- A real end-to-end AutoGen team run is marked `@pytest.mark.live` (like the existing live smoke), so it is deselected by default.

## Risks / notes

- **Streaming fidelity:** today the feed types token-by-token via `on_token`. The AutoGen path likely streams at **message granularity**, so dynamic-mode turns may appear all at once rather than typing out. Accepted UX delta; wiring token-level streaming through AutoGen's streamed events is a possible follow-up.
- **gemma on AutoGen:** the free tier's shaky output is exactly why the per-turn + phase-level fallbacks exist. Dynamic mode is best with a stronger reasoner; on the free tier expect more frequent round-robin fallbacks.
- **New dependency surface:** `autogen-agentchat` + `autogen-ext` + `autogen-core` and their transitive deps enter the tree. Confined to one module; removable by deleting `discussion_autogen.py` and the `DISCUSSION_MODE` branch.
- **Value honesty:** with selection + fallback in our `selector_func`, AutoGen provides the team runtime, message protocol, and termination — not the picking itself. If, after using it, the framework isn't pulling its weight, the same dynamic routing is ~40–60 lines of pure-Python selector loop with no dependency.

## Out of scope

- Migrating any phase other than DISCUSSION to AutoGen.
- Tool use by the dynamic-mode discussion agents (they argue over RESEARCH evidence; tool calls are a later extension).
- Agent-to-agent explicit handoff routing (a different mechanism; this spec is moderator/selector-driven).
- Token-by-token streaming in the AutoGen path (message-granularity accepted for now).
- Changing the default discussion behavior: `roundrobin` stays the default; `dynamic` is opt-in.
