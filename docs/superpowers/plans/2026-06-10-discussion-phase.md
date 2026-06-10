# Dynamic DISCUSSION Phase Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a dynamic DISCUSSION phase where the 6 debaters argue round-robin (bounded by `DISCUSSION_ROUNDS`) before the Chair's verdict, with each turn deterministically grounding-checked.

**Architecture:** A new branch in the existing synchronous `Orchestrator.run` (no framework): when `discussion_rounds > 0`, run round-robin debate turns over the 4 analysts + 2 challengers in place of the scripted CHALLENGE→REBUTTAL; after each turn, `check_grounding` flags unsourced figures via a new `grounding_flag` event. Reuses `Agent.run`, the EventBus, the EvidenceLedger, the report, and all three front-ends.

**Tech Stack:** Python 3.12 (`.venv/bin/python`), vanilla JS, Tkinter, Django, pytest.

**Spec:** `docs/superpowers/specs/2026-06-10-discussion-phase-design.md`

**Conventions:** Test with `.venv/bin/python -m pytest`. Branch `feat/discussion-phase`. Orchestrator tests use hand-rolled `_StubAgent` (no mocks).

---

## File Structure

**Modify:**
- `agentcore/orchestrator.py` — DISCUSSION phase + per-turn `grounding_flag`
- `agentcore/events.py` — document the `grounding_flag` event type
- `committee/markets/base.py` — `Templates.discussion` field
- `committee/markets/tw.py`, `us.py` — discussion prompt, `DISCUSSION` phase label, `unverified_label`
- `committee/config.py` — `DISCUSSION_ROUNDS`
- `main.py`, `gui.py`, `committee_web/run.py` — pass `discussion_rounds`/`discussion_task_template`
- `committee_web/views.py` — `committee_info` returns `discussion_rounds`
- `committee/report.py` — render DISCUSSION turns + grounding flags in the transcript
- `web/static/app.js`, `gui.py` — conditional pipeline + grounding-flag rendering
- Tests: `test_orchestrator.py`, `test_markets.py`, `test_config.py`, `test_django_web.py`, `test_report.py`

---

## Task 1: Orchestrator DISCUSSION phase + grounding flags

**Files:** Modify `agentcore/orchestrator.py`, `agentcore/events.py`; Test `tests/test_orchestrator.py`

- [ ] **Step 1: Write failing tests** — append to `tests/test_orchestrator.py`:

```python
def test_discussion_phase_replaces_challenge_rebuttal_when_enabled():
    fund = _StubAgent("fundamental", "PE 合理。看多")
    tech = _StubAgent("technical", "站上季線。看多")
    risk = _StubAgent("risk", "波動偏高。")
    skeptic = _StubAgent("skeptic", "別追高。")
    chair = _StubAgent("chair", "建議: 持有\n信心: 60%")
    orch = _orch([fund, tech], [risk, skeptic], chair, discussion_rounds=2)
    bus, ledger = EventBus(), EvidenceLedger()
    events = []
    bus.subscribe(events.append)

    orch.run(stock_no="2330", llm=None, registry=None, bus=bus, ledger=ledger)

    phases = [e.data.get("phase") for e in events if e.type == "phase" and "phase" in e.data]
    assert phases == ["RESEARCH", "DISCUSSION", "VERDICT"]
    # research analysts: 1 RESEARCH turn + 2 discussion turns; challengers: 2 discussion turns
    assert len(fund.tasks) == 3 and len(risk.tasks) == 2
    # the Chair sees the discussion turns
    assert "別追高" in chair.tasks[0]["task"]


def test_discussion_turn_with_unsourced_figure_is_flagged():
    fund = _StubAgent("fundamental", "PE 約 30.52,偏高")   # 30.52 not in the (empty) ledger
    skeptic = _StubAgent("skeptic", "看空")                 # no figure -> no flag
    chair = _StubAgent("chair", "建議: 賣出")
    orch = _orch([fund], [skeptic], chair, discussion_rounds=1)
    bus, ledger = EventBus(), EvidenceLedger()
    events = []
    bus.subscribe(events.append)

    orch.run(stock_no="2330", llm=None, registry=None, bus=bus, ledger=ledger)

    flags = [e for e in events if e.type == "grounding_flag"]
    assert any(e.agent == "fundamental" and 30.52 in e.data["unsupported"] for e in flags)
    assert not any(e.agent == "skeptic" for e in flags)


def test_discussion_disabled_by_default_keeps_challenge_rebuttal():
    fund = _StubAgent("fundamental", "看多")
    risk = _StubAgent("risk", "風險偏高。")
    chair = _StubAgent("chair", "建議: 持有")
    orch = _orch([fund], [risk], chair)   # discussion_rounds defaults to 0
    bus, ledger = EventBus(), EvidenceLedger()
    events = []
    bus.subscribe(events.append)

    orch.run(stock_no="2330", llm=None, registry=None, bus=bus, ledger=ledger)

    phases = [e.data.get("phase") for e in events if e.type == "phase" and "phase" in e.data]
    assert phases == ["RESEARCH", "CHALLENGE", "REBUTTAL", "VERDICT"]
```

- [ ] **Step 2: Run, verify fail** — `.venv/bin/python -m pytest tests/test_orchestrator.py -k "discussion" -v` → FAIL (`discussion_rounds` not a field).

- [ ] **Step 3: Edit `agentcore/orchestrator.py`.**

(a) Add the default template near the other `_DEFAULT_*` templates:
```python
_DEFAULT_DISCUSSION_TASK = (
    "Here is the committee discussion so far. From your perspective, challenge the "
    "points you disagree with and defend or revise your own view on {stock}, in one "
    "short paragraph. Cite only figures supported by the data your tools returned; "
    "never invent numbers."
)
```

(b) Add two fields to the `Orchestrator` dataclass (after `rebuttal_task_template`):
```python
    discussion_rounds: int = 0          # 0 = off (scripted challenge/rebuttal); N = round-robin debate
    discussion_task_template: str = _DEFAULT_DISCUSSION_TASK
```

(c) In `run(...)`, replace the existing CHALLENGE + REBUTTAL blocks (the
`phase("CHALLENGE")` … through the REBUTTAL loop) with this branch. RESEARCH above
and `phase("VERDICT")` below stay exactly as they are:
```python
        if self.discussion_rounds > 0:
            phase("DISCUSSION")
            debaters = list(self.research) + list(self.challengers)
            for _ in range(self.discussion_rounds):
                for a in debaters:
                    text = run_agent(a, self.discussion_task_template.format(stock=stock_no),
                                     context=_join(transcript))
                    transcript.append((a.name, text))
                    g = check_grounding(text, ledger)
                    if not g["grounded"]:
                        bus.emit(Event(type="grounding_flag", agent=a.name,
                                       data={"unsupported": g["unsupported"]}))
        else:
            phase("CHALLENGE")
            research_summary = _join(transcript)
            challenger_names = set()
            for c in self.challengers:
                challenger_names.add(c.name)
                text = run_agent(c, self.challenge_task_template.format(stock=stock_no),
                                 context=research_summary)
                transcript.append((c.name, text))

            phase("REBUTTAL")
            challenge_summary = _join([t for t in transcript if t[0] in challenger_names])
            for a in self.research:
                text = run_agent(a, self.rebuttal_task_template.format(stock=stock_no),
                                 context=challenge_summary)
                transcript.append((a.name + " (答辯)", text))
```
(`check_grounding` and `Event` are already imported at the top of the file.)

- [ ] **Step 4: Document the event** in `agentcore/events.py` — update the `type` field comment on the `Event` dataclass to include `grounding_flag`:
```python
    type: str            # phase|message|token|tool_call|tool_result|verdict|verification|grounding_flag|error
```

- [ ] **Step 5: Run, verify pass** — `.venv/bin/python -m pytest tests/test_orchestrator.py -v` → all PASS (new + existing, incl. `test_default_templates_are_domain_neutral`). Full suite `.venv/bin/python -m pytest -q` → PASS.

- [ ] **Step 6: Commit**
```bash
git add agentcore/orchestrator.py agentcore/events.py tests/test_orchestrator.py
git commit -m "feat: dynamic DISCUSSION phase with per-turn grounding flags"
```

---

## Task 2: Per-market templates + labels

**Files:** Modify `committee/markets/base.py`, `tw.py`, `us.py`; Test `tests/test_markets.py`

- [ ] **Step 1: Write failing tests** — append to `tests/test_markets.py`:

```python
def test_templates_have_discussion_and_phase_label():
    from committee.markets import get_profile
    for m, label in (("tw", "討論交鋒"), ("us", "Discussion")):
        p = get_profile(m)
        assert p.templates.discussion and "{stock}" in p.templates.discussion
        assert p.labels.phase_names["DISCUSSION"] == label


def test_unverified_label_present_in_ui_and_report_labels():
    from committee.markets import get_profile
    for m in ("tw", "us"):
        p = get_profile(m)
        assert p.ui["unverified_label"]
        assert p.labels.text["unverified_label"]
```

- [ ] **Step 2: Run, verify fail** — `.venv/bin/python -m pytest tests/test_markets.py -k "discussion or unverified" -v` → FAIL.

- [ ] **Step 3: Add the `discussion` field** to `Templates` in `committee/markets/base.py` (append after `correction`):
```python
@dataclass
class Templates:
    analyst: str
    challenge: str
    rebuttal: str
    reflect: str
    verify: str
    correction: str
    discussion: str
```

- [ ] **Step 4: Update the dataclass-construction test** in `tests/test_markets.py` — the existing `test_dataclasses_construct_with_expected_fields` builds `Templates(...)`; add the new field so it still constructs. Find the `Templates(analyst="a", ... correction="co")` line and add `, discussion="d"` to it.

- [ ] **Step 5: TW market** — `committee/markets/tw.py`:
  - In `tw_templates()` `Templates(...)`, add:
    ```python
        discussion=("以下是委員會目前的討論。請從你的專業立場,針對你不認同的論點提出質疑,"
                    "並捍衛或修正你對台股 {stock} 的看法(一段話)。只引用工具回傳、有數據支持的"
                    "數字,不得捏造。"),
    ```
  - In `tw_ui()` dict, add: `"unverified_label": "未驗證數字",`
  - In `_TW_TEXT` (the `ReportLabels.text` dict), add: `"unverified_label": "未驗證數字",`
  - In `tw_labels()` `phase_names={...}`, add: `"DISCUSSION": "討論交鋒",`

- [ ] **Step 6: US market** — `committee/markets/us.py`:
  - In `us_templates()` `Templates(...)`, add:
    ```python
        discussion=("Here is the committee discussion so far. From your perspective, "
                    "challenge the points you disagree with and defend or revise your view "
                    "on US stock {stock} in one short paragraph. Cite only figures your "
                    "tools returned; never invent numbers."),
    ```
  - In `us_ui()` dict, add: `"unverified_label": "unverified figure",`
  - In `_US_TEXT`, add: `"unverified_label": "unverified figure",`
  - In `us_labels()` `phase_names={...}`, add: `"DISCUSSION": "Discussion",`

- [ ] **Step 7: Run, verify pass** — `.venv/bin/python -m pytest tests/test_markets.py -v` → all PASS (the `set(tw)==set(us)` ui-parity and dataclass tests stay green because both markets gained the keys). Full suite → PASS.

- [ ] **Step 8: Commit**
```bash
git add committee/markets/base.py committee/markets/tw.py committee/markets/us.py tests/test_markets.py
git commit -m "feat: per-market discussion prompt + DISCUSSION/unverified labels"
```

---

## Task 3: Config + wiring (committee + committee_info)

**Files:** Modify `committee/config.py`, `main.py`, `gui.py`, `committee_web/run.py`, `committee_web/views.py`; Test `tests/test_config.py`, `tests/test_django_web.py`

- [ ] **Step 1: Write failing tests.**

Append to `tests/test_config.py`:
```python
def test_discussion_rounds_default_and_override(monkeypatch):
    import importlib
    import committee.config as cfg
    monkeypatch.delenv("DISCUSSION_ROUNDS", raising=False)
    importlib.reload(cfg)
    assert cfg.DISCUSSION_ROUNDS == 2
    monkeypatch.setenv("DISCUSSION_ROUNDS", "0")
    importlib.reload(cfg)
    assert cfg.DISCUSSION_ROUNDS == 0
```

Append to `tests/test_django_web.py`:
```python
def test_committee_info_returns_discussion_rounds():
    d = _client().get("/api/committee?market=tw").json()
    assert "discussion_rounds" in d and isinstance(d["discussion_rounds"], int)
```

- [ ] **Step 2: Run, verify fail** — `.venv/bin/python -m pytest tests/test_config.py -k discussion tests/test_django_web.py -k discussion_rounds -v` → FAIL.

- [ ] **Step 3: Add the config** in `committee/config.py` — after the `REFLECTION_PASSES = ...` line:
```python
DISCUSSION_ROUNDS = int(os.environ.get("DISCUSSION_ROUNDS", "2"))
```

- [ ] **Step 4: Wire into the three Orchestrator construction sites.** Each already has `t = profile.templates` (the template alias) and constructs `Orchestrator(...)` with the 6 templates + `reflection_passes`. In each file:
  - Add `DISCUSSION_ROUNDS` to the `from committee.config import ...` line.
  - Add these two kwargs to the `Orchestrator(...)` call:
    ```python
                        discussion_rounds=DISCUSSION_ROUNDS,
                        discussion_task_template=t.discussion,
    ```
  Files: `main.py`, `gui.py` (in `_run_worker`), `committee_web/run.py`. (In `main.py`/`committee_web/run.py` the alias is `t`; confirm the alias name in `gui.py`'s worker and use it.)

- [ ] **Step 5: `committee_info` returns it** — `committee_web/views.py`: add `DISCUSSION_ROUNDS` to `from committee.config import REFLECTION_PASSES` and add one key to the JSON, right after `"reflection_passes": REFLECTION_PASSES,`:
```python
        "reflection_passes": REFLECTION_PASSES,
        "discussion_rounds": DISCUSSION_ROUNDS,
```

- [ ] **Step 6: Run, verify pass** — `.venv/bin/python -m pytest tests/test_config.py tests/test_django_web.py -v` → PASS. `.venv/bin/python -c "import main, gui, committee_web.run; print('imports ok')"` → ok. Full suite → PASS.

- [ ] **Step 7: Commit**
```bash
git add committee/config.py main.py gui.py committee_web/run.py committee_web/views.py tests/test_config.py tests/test_django_web.py
git commit -m "feat: DISCUSSION_ROUNDS config wired into the committee + committee_info"
```

---

## Task 4: Report renders DISCUSSION turns + grounding flags

**Files:** Modify `committee/report.py`; Test `tests/test_report.py`

- [ ] **Step 1: Write failing tests** — append to `tests/test_report.py`:

```python
def test_report_renders_discussion_turns_and_grounding_flag():
    from committee.report import build_html
    from committee.markets import get_profile
    c = ReportCollector()
    c(Event(type="phase", agent="system", data={"phase": "DISCUSSION", "stock": "2330"}))
    c(Event(type="message", agent="fundamental", data={"text": "估值合理,看多"}))
    c(Event(type="grounding_flag", agent="fundamental", data={"unsupported": [30.52]}))
    html = build_html("2330", c, generated_at="2026-06-10 10:00:00",
                      labels=get_profile("tw").labels)
    assert "討論交鋒" in html          # DISCUSSION phase label in the appendix
    assert "估值合理,看多" in html
    assert "未驗證數字" in html and "30.52" in html   # grounding flag rendered inline
```

- [ ] **Step 2: Run, verify fail** — `.venv/bin/python -m pytest tests/test_report.py -k discussion -v` → FAIL (DISCUSSION phase not in the appendix order; grounding_flag not rendered).

- [ ] **Step 3: Edit `committee/report.py` `_transcript`.**

(a) Add `DISCUSSION` to the appendix phase order tuple. Find the loop
`for ph in ("RESEARCH", "CHALLENGE", "REBUTTAL", "VERDICT", "REFLECT", "VERIFY"):`
and change it to:
```python
    for ph in ("RESEARCH", "DISCUSSION", "CHALLENGE", "REBUTTAL", "VERDICT", "REFLECT", "VERIFY"):
```

(b) `_transcript` collects events per phase into `by_phase` filtering on
`e.type in ("message", "tool_call", "tool_result", "error", "verdict")`. Add
`"grounding_flag"` to that filter so the flags are kept in their phase bucket.
Find the line `elif e.type in ("message", "tool_call", "tool_result", "error", "verdict"):`
and change it to:
```python
        elif e.type in ("message", "tool_call", "tool_result", "error", "verdict", "grounding_flag"):
```

(c) In the per-event render loop inside `_transcript` (the `for agent, etype, data in items:`
block), add a branch to render the flag. After the existing `error` branch add:
```python
            elif etype == "grounding_flag":
                figs = ", ".join(str(x) for x in data.get("unsupported", []))
                p.append('<div class="err">⚠ {}: {}</div>'.format(
                    _esc(labels.text.get("unverified_label", "")), _esc(figs)))
```

- [ ] **Step 4: Run, verify pass** — `.venv/bin/python -m pytest tests/test_report.py -v` → all PASS (new + existing). Full suite → PASS.

- [ ] **Step 5: Commit**
```bash
git add committee/report.py tests/test_report.py
git commit -m "feat: report shows DISCUSSION turns + inline grounding flags"
```

---

## Task 5: Web front-end (pipeline + grounding flag)

**Files:** Modify `web/static/app.js`

- [ ] **Step 1: Conditional pipeline** in `web/static/app.js` `buildPipeline`. Replace the
fixed CHALLENGE/REBUTTAL block. The current lines are:
```javascript
  push("phase:CHALLENGE", phaseLabel("CHALLENGE"));
  for (const a of roster.challengers) push("agent:" + a.name, a.label, a.model, a.tools);
  push("phase:REBUTTAL", phaseLabel("REBUTTAL"));
```
Replace with:
```javascript
  if (roster.discussion_rounds > 0) {
    push("phase:DISCUSSION", phaseLabel("DISCUSSION"));
    for (const a of roster.challengers) push("agent:" + a.name, a.label, a.model, a.tools);
  } else {
    push("phase:CHALLENGE", phaseLabel("CHALLENGE"));
    for (const a of roster.challengers) push("agent:" + a.name, a.label, a.model, a.tools);
    push("phase:REBUTTAL", phaseLabel("REBUTTAL"));
  }
```

- [ ] **Step 2: Handle the grounding flag** — add a branch in `handleEvent` (place it near the `tool_result` / `error` branches):
```javascript
  if (t === "grounding_flag") {
    endStream();
    const figs = JSON.stringify(e.data.unsupported || []);
    appendTool("err", "  ⚠ " + (ui.unverified_label || "unverified") + ": " + figs);
    setCardResult("agent:" + e.agent, "⚠ " + (ui.unverified_label || ""));
    return;
  }
```

- [ ] **Step 3: Structural verification**
```bash
cd /Users/steventsai/Documents/Claude_Project/stock-ana/stock-analysis
.venv/bin/python -c "s=open('web/static/app.js').read(); assert 'discussion_rounds > 0' in s and 'phase:DISCUSSION' in s and 'grounding_flag' in s and 'ui.unverified_label' in s; print('app.js ok')"
command -v node >/dev/null 2>&1 && node --check web/static/app.js && echo "app.js syntax ok" || echo "(node n/a)"
.venv/bin/python -m pytest -q 2>&1 | tail -1
```
Expected: `app.js ok`, `app.js syntax ok` (if node), full suite PASS.

- [ ] **Step 4: Manual browser smoke (operator/controller).** Start `manage.py runserver`; confirm the pipeline shows a **DISCUSSION** card (since `DISCUSSION_ROUNDS` defaults to 2) in place of CHALLENGE/REBUTTAL; injecting a `grounding_flag` event shows the inline "⚠ unverified figure" warning in the feed.

- [ ] **Step 5: Commit**
```bash
git add web/static/app.js
git commit -m "feat: web pipeline shows DISCUSSION + inline grounding-flag warnings"
```

---

## Task 6: Desktop GUI (pipeline + grounding flag)

**Files:** Modify `gui.py`

- [ ] **Step 1: Import the config** — add `DISCUSSION_ROUNDS` to the `from committee.config import ...` line in `gui.py`.

- [ ] **Step 2: Conditional pipeline** in `_build_pipeline`. Replace the fixed
CHALLENGE/REBUTTAL steps. The current lines are:
```python
        steps.append(("phase:CHALLENGE", pn.get("CHALLENGE", "CHALLENGE"), "system", None, None))
        for a in c.challengers:
            steps.append(("agent:" + a.name, an.get(a.name, a.name), a.name, a.model, a.tool_names))
        steps.append(("phase:REBUTTAL", pn.get("REBUTTAL", "REBUTTAL"), "system", None, None))
```
Replace with:
```python
        if DISCUSSION_ROUNDS > 0:
            steps.append(("phase:DISCUSSION", pn.get("DISCUSSION", "DISCUSSION"), "system", None, None))
            for a in c.challengers:
                steps.append(("agent:" + a.name, an.get(a.name, a.name), a.name, a.model, a.tool_names))
        else:
            steps.append(("phase:CHALLENGE", pn.get("CHALLENGE", "CHALLENGE"), "system", None, None))
            for a in c.challengers:
                steps.append(("agent:" + a.name, an.get(a.name, a.name), a.name, a.model, a.tool_names))
            steps.append(("phase:REBUTTAL", pn.get("REBUTTAL", "REBUTTAL"), "system", None, None))
```

- [ ] **Step 3: Handle the grounding flag** in `_handle`. Read `_handle` to find the
feed-append helper (it appends lines to the feed via an `_append(text, tag)` method).
Add this branch near the top of `_handle` (after the early returns for other event
types), using the actual append helper name:
```python
        if e.type == "grounding_flag":
            figs = ", ".join(str(x) for x in e.data.get("unsupported", []))
            self._append("  ⚠ {}: {}\n".format(self.profile.ui["unverified_label"], figs), "system")
            return
```
(If the feed-append helper in this file is named differently than `_append`, use that
name; match the existing pattern used by the `error`/`tool_result` handling.)

- [ ] **Step 4: Verify**
```bash
cd /Users/steventsai/Documents/Claude_Project/stock-ana/stock-analysis
.venv/bin/python -c "import gui; print('gui import ok')"
.venv/bin/python -m pytest tests/test_gui_format.py -q 2>&1 | tail -1
.venv/bin/python -m pytest -q 2>&1 | tail -1
.venv/bin/python - <<'PY'
src = open("gui.py", encoding="utf-8").read()
assert "DISCUSSION_ROUNDS" in src and 'phase:DISCUSSION' in src and "grounding_flag" in src
assert 'self.profile.ui["unverified_label"]' in src
print("gui discussion ok")
PY
```
Expected: `gui import ok`, gui-format tests PASS, full suite PASS, `gui discussion ok`.

- [ ] **Step 5: Manual GUI smoke (operator).** `.venv/bin/python gui.py` shows a
DISCUSSION step in the pipeline; a `grounding_flag` event appends the warning line.

- [ ] **Step 6: Commit**
```bash
git add gui.py
git commit -m "feat: desktop GUI shows DISCUSSION + grounding-flag warnings"
```

---

## Self-Review Notes

- **Spec coverage:** DISCUSSION loop + participants (T1), per-turn `grounding_flag` (T1), templates/labels incl. `phase_names["DISCUSSION"]` + `unverified_label` (T2), `DISCUSSION_ROUNDS` config + 3 wiring sites + `committee_info` (T3), report rendering of DISCUSSION turns + flags (T4), web pipeline + flag (T5), GUI pipeline + flag (T6). All spec sections map to a task.
- **Backward-compat:** `discussion_rounds` defaults to `0` in the neutral `Orchestrator`, so the existing CHALLENGE→REBUTTAL tests stay green; the committee turns it on via `DISCUSSION_ROUNDS` (default 2). `unverified_label` added to BOTH `ui` dicts (keeps `set(tw)==set(us)`); `Templates` gains a required `discussion` field and the one dataclass-construct test is updated (T2 Step 4).
- **Type/name consistency:** the event type is `grounding_flag` with `data={"unsupported": [...]}` everywhere (orchestrator T1, report T4, app.js T5, gui T6); `discussion_rounds`/`discussion_task_template` are the Orchestrator fields (T1) set from `DISCUSSION_ROUNDS`/`t.discussion` (T3); `unverified_label` lives in both `ui` and `ReportLabels.text` (T2) and is read in app.js/gui/report.
- **No extra LLM cost for flags:** `check_grounding` is deterministic; called once per discussion turn + once on the final verdict (unchanged).
- **Out of scope (per spec):** LLM moderator/selector, consensus early-stop, AutoGen, CLI pipeline cards.
