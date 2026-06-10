# Markdown + Thinking Separation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Render each agent's output as markdown and split the model's `<thought>`/`<think>` reasoning into a collapsible expander, in the web live debate and the saved HTML report.

**Architecture:** A small, dependency-free markdown subset renderer + a `split_thinking` helper, implemented once in Python (`committee/markdown.py`, for the report) and mirrored in JS (`web/static/md.js`, for the live feed). HTML is escaped before rendering (XSS-safe). `report.py` and `app.js` call these to render the answer as markdown and wrap the reasoning in a collapsed `<details>`.

**Tech Stack:** Python 3.12 (`.venv/bin/python`), vanilla JS, pytest. No new dependencies.

**Spec:** `docs/superpowers/specs/2026-06-10-markdown-thinking-design.md`

**Conventions:**
- Test with `.venv/bin/python -m pytest`. Run on branch `feat/markdown-thinking`.
- The JS renderer mirrors the Python one line-for-line in structure; the Python one is the tested source of truth.

---

## File Structure

**Create:**
- `committee/markdown.py` — `split_thinking(text)`, `render_markdown(text)` (Python)
- `web/static/md.js` — `MD.splitThinking(text)`, `MD.renderMarkdown(text)` (JS mirror)
- `tests/test_markdown.py`

**Modify:**
- `committee/report.py` — render messages/verdict via the helpers; collapsible thinking; CSS
- `committee/markets/tw.py`, `committee/markets/us.py` — add `thinking_label` to `ReportLabels.text` and to the `ui` dict
- `web/static/app.js`, `web/static/index.html`, `web/static/style.css` — markdown + thinking in the live feed
- `tests/test_report.py` — assert markdown + thinking rendering

---

## Task 1: `split_thinking` (Python)

**Files:** Create `committee/markdown.py`; Test `tests/test_markdown.py`

- [ ] **Step 1: Write failing tests** — `tests/test_markdown.py`:

```python
from committee.markdown import split_thinking


def test_no_tags_returns_text_as_answer():
    assert split_thinking("just an answer") == ("just an answer", "")


def test_extracts_thought_block():
    a, t = split_thinking("<thought>reasoning here</thought>The answer.")
    assert a == "The answer."
    assert t == "reasoning here"


def test_extracts_think_block_case_insensitive():
    a, t = split_thinking("<THINK>r</THINK>ans")
    assert a == "ans" and t == "r"


def test_multiple_blocks_joined():
    a, t = split_thinking("<thought>one</thought>mid<thought>two</thought>end")
    assert a == "midend"
    assert t == "one\n\ntwo"


def test_unclosed_trailing_open_tag_is_thinking():
    a, t = split_thinking("answer text <thought>truncated reasoning")
    assert a == "answer text"
    assert t == "truncated reasoning"


def test_empty_input():
    assert split_thinking("") == ("", "")
    assert split_thinking(None) == ("", "")
```

- [ ] **Step 2: Run, verify fail** — `.venv/bin/python -m pytest tests/test_markdown.py -k thinking -v` → FAIL (module missing).

- [ ] **Step 3: Implement** — create `committee/markdown.py`:

```python
"""Tiny, dependency-free markdown subset renderer + reasoning splitter.

Used by the HTML report (and mirrored in web/static/md.js for the live feed).
HTML is escaped before any markdown is applied, so rendering untrusted model
output is safe.
"""
import re

_TAG = re.compile(r"<(thought|think)\b[^>]*>(.*?)</\1>", re.IGNORECASE | re.DOTALL)
_OPEN = re.compile(r"<(thought|think)\b[^>]*>(.*)$", re.IGNORECASE | re.DOTALL)


def split_thinking(text):
    """Return (answer, thinking). Extracts <thought>/<think> blocks (including a
    single unclosed trailing one) as `thinking`; the remainder is `answer`."""
    text = text or ""
    thoughts = []

    def _grab(m):
        thoughts.append(m.group(2).strip())
        return ""

    answer = _TAG.sub(_grab, text)
    m = _OPEN.search(answer)
    if m:
        thoughts.append(m.group(2).strip())
        answer = answer[:m.start()]
    thinking = "\n\n".join(t for t in thoughts if t).strip()
    return answer.strip(), thinking
```

- [ ] **Step 4: Run, verify pass** — `.venv/bin/python -m pytest tests/test_markdown.py -k thinking -v` → PASS.

- [ ] **Step 5: Commit**

```bash
git add committee/markdown.py tests/test_markdown.py
git commit -m "feat: split_thinking extracts <thought>/<think> reasoning"
```

---

## Task 2: `render_markdown` (Python)

**Files:** Modify `committee/markdown.py`; Test `tests/test_markdown.py`

- [ ] **Step 1: Write failing tests** — append to `tests/test_markdown.py`:

```python
from committee.markdown import render_markdown


def test_escapes_html():
    out = render_markdown("<script>alert(1)</script>")
    assert "<script>" not in out and "&lt;script&gt;" in out


def test_bold_italic_code():
    out = render_markdown("a **b** c *d* e `f`")
    assert "<strong>b</strong>" in out
    assert "<em>d</em>" in out
    assert "<code>f</code>" in out


def test_unordered_list():
    out = render_markdown("- one\n- two")
    assert out == "<ul><li>one</li><li>two</li></ul>"


def test_ordered_list():
    out = render_markdown("1. one\n2. two")
    assert out == "<ol><li>one</li><li>two</li></ol>"


def test_heading():
    assert render_markdown("# Title") == "<h3>Title</h3>"
    assert render_markdown("## Sub") == "<h4>Sub</h4>"


def test_paragraph_and_linebreak():
    assert render_markdown("a\nb") == "<p>a<br>b</p>"
    assert render_markdown("a\n\nb") == "<p>a</p><p>b</p>"


def test_fenced_code_block_keeps_content_literal():
    out = render_markdown("```\nx = **not bold**\n```")
    assert out == "<pre><code>x = **not bold**</code></pre>"


def test_http_link_rendered_other_schemes_literal():
    assert '<a href="https://x.com" target="_blank" rel="noopener">t</a>' in render_markdown("[t](https://x.com)")
    assert render_markdown("[t](javascript:alert(1))") == "<p>[t](javascript:alert(1))</p>"


def test_snake_case_not_italicized():
    # single underscores in identifiers must not become <em>
    assert render_markdown("get_monthly_revenue") == "<p>get_monthly_revenue</p>"
```

- [ ] **Step 2: Run, verify fail** — `.venv/bin/python -m pytest tests/test_markdown.py -k "markdown or list or heading or link or escapes or bold or paragraph or fenced or snake" -v` → FAIL (`render_markdown` missing).

- [ ] **Step 3: Implement** — append to `committee/markdown.py`:

```python
def _esc(s):
    return (s.replace("&", "&amp;").replace("<", "&lt;")
             .replace(">", "&gt;").replace('"', "&quot;"))


_CODE = re.compile(r"`([^`]+)`")
_LINK = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
_BOLD = re.compile(r"\*\*([^*]+)\*\*")
_ITAL = re.compile(r"\*([^*]+)\*")  # only *...* (not _..._), so snake_case is safe


def _inline(s):
    """Inline markdown on already-escaped text: code, links, bold, italic."""
    s = _CODE.sub(lambda m: "<code>" + m.group(1) + "</code>", s)

    def _link(m):
        text, url = m.group(1), m.group(2)
        if url.startswith("http://") or url.startswith("https://"):
            return '<a href="{}" target="_blank" rel="noopener">{}</a>'.format(url, text)
        return m.group(0)

    s = _LINK.sub(_link, s)
    s = _BOLD.sub(lambda m: "<strong>" + m.group(1) + "</strong>", s)
    s = _ITAL.sub(lambda m: "<em>" + m.group(1) + "</em>", s)
    return s


_HEADING = re.compile(r"^(#{1,3})\s+(.*)$")
_ULI = re.compile(r"^[-*]\s+(.*)$")
_OLI = re.compile(r"^\d+\.\s+(.*)$")


def render_markdown(text):
    """Render a small, safe markdown subset to HTML. Escapes HTML first; supports
    fenced code, #/##/### headings, -/* and N. lists, **bold**, *italic*, `code`,
    http(s) links, and blank-line paragraphs (single newline -> <br>)."""
    lines = _esc(text or "").split("\n")
    out = []
    i, n = 0, len(lines)
    while i < n:
        line = lines[i]
        stripped = line.strip()
        if stripped.startswith("```"):
            i += 1
            code = []
            while i < n and not lines[i].strip().startswith("```"):
                code.append(lines[i])
                i += 1
            i += 1  # skip closing fence
            out.append("<pre><code>" + "\n".join(code) + "</code></pre>")
            continue
        if stripped == "":
            i += 1
            continue
        m = _HEADING.match(line)
        if m:
            level = len(m.group(1)) + 2  # '#' -> h3
            out.append("<h{0}>{1}</h{0}>".format(level, _inline(m.group(2).strip())))
            i += 1
            continue
        if _ULI.match(line):
            items = []
            while i < n and _ULI.match(lines[i]):
                items.append("<li>" + _inline(_ULI.match(lines[i]).group(1).strip()) + "</li>")
                i += 1
            out.append("<ul>" + "".join(items) + "</ul>")
            continue
        if _OLI.match(line):
            items = []
            while i < n and _OLI.match(lines[i]):
                items.append("<li>" + _inline(_OLI.match(lines[i]).group(1).strip()) + "</li>")
                i += 1
            out.append("<ol>" + "".join(items) + "</ol>")
            continue
        para = []
        while (i < n and lines[i].strip() != "" and not _HEADING.match(lines[i])
               and not _ULI.match(lines[i]) and not _OLI.match(lines[i])
               and not lines[i].strip().startswith("```")):
            para.append(_inline(lines[i].strip()))
            i += 1
        out.append("<p>" + "<br>".join(para) + "</p>")
    return "".join(out)
```

- [ ] **Step 4: Run, verify pass** — `.venv/bin/python -m pytest tests/test_markdown.py -v` → all PASS. Then `.venv/bin/python -m pytest -q` → full suite PASS.

- [ ] **Step 5: Commit**

```bash
git add committee/markdown.py tests/test_markdown.py
git commit -m "feat: dependency-free markdown subset renderer"
```

---

## Task 3: Report integration (`report.py` + labels)

**Files:** Modify `committee/report.py`, `committee/markets/tw.py`, `committee/markets/us.py`; Test `tests/test_report.py`

- [ ] **Step 1: Add `thinking_label` to the report label sets.** In `committee/markets/tw.py`, inside the `_TW_TEXT` dict, add: `"thinking_label": "思考過程",`. In `committee/markets/us.py`, inside `_US_TEXT`, add: `"thinking_label": "Thinking",`.

- [ ] **Step 2: Write failing tests** — append to `tests/test_report.py`:

```python
def test_aspect_message_renders_markdown_and_collapsible_thinking():
    from committee.report import build_html
    c = ReportCollector()
    c(Event(type="message", agent="fundamental",
            data={"text": "<thought>my reasoning</thought>Verdict: **Bullish**\n- strong margins"}))
    html = build_html("AAPL", c, generated_at="2026-06-10 10:00:00")
    assert "<strong>Bullish</strong>" in html      # answer rendered as markdown
    assert "<li>strong margins</li>" in html
    assert "<details class=\"thinking\">" in html   # reasoning collapsed
    assert "my reasoning" in html
    assert "<thought>" not in html                  # raw tag not shown


def test_plain_message_without_thinking_has_no_details():
    from committee.report import build_html
    c = ReportCollector()
    c(Event(type="message", agent="technical", data={"text": "Neutral stance"}))
    html = build_html("AAPL", c, generated_at="2026-06-10 10:00:00")
    assert "Neutral stance" in html
    # no thinking expander when there is no <thought>
    assert html.count('<details class="thinking">') == 0
```

- [ ] **Step 3: Run, verify fail** — `.venv/bin/python -m pytest tests/test_report.py -k "markdown or collapsible or plain_message" -v` → FAIL.

- [ ] **Step 4: Implement in `committee/report.py`:**

(a) Add the import at the top (near the other imports):
```python
from committee.markdown import render_markdown, split_thinking
```

(b) Add a helper near `_esc`:
```python
def _thought_details(thinking: str, label: str) -> str:
    if not thinking:
        return ""
    return ('<details class="thinking"><summary>' + _esc(label)
            + '</summary>' + render_markdown(thinking) + '</details>')
```

(c) `_aspect_sections` — replace the block that builds each aspect (currently
`'<div class="aspect"><h3>{}</h3><p>{}</p></div>'.format(_esc(title), _esc(txt))`)
with markdown + thinking. The function has `labels`; read the label once:
```python
def _aspect_sections(msgs: Dict[str, str], labels: Any) -> str:
    tlabel = labels.text.get("thinking_label", "")
    blocks = []
    for agent, title in labels.aspect_order:
        txt = msgs.get(agent)
        if txt:
            answer, thinking = split_thinking(txt)
            blocks.append('<div class="aspect"><h3>{}</h3>{}{}</div>'.format(
                _esc(title), render_markdown(answer), _thought_details(thinking, tlabel)))
    if not blocks:
        return ""
    return '<section><h2>' + _esc(labels.text["aspect"]) + '</h2>' + "".join(blocks) + "</section>"
```
(Keep the existing section-title source the function already uses — match the current code's title key; if it currently uses a different `L[...]`/constant for the "分面分析" heading, keep that exact source rather than the line above.)

(d) `_risk_box` — render each risk/skeptic message with markdown + thinking the same
way (replace `_esc(txt)` with `render_markdown(answer)` + `_thought_details(...)`,
after `answer, thinking = split_thinking(txt)`), keeping the surrounding
`<li><b>name:</b> …</li>` structure.

(e) Thesis/verdict block — the current code does:
```python
    if collector.verdict_text:
        p.append('<section class="thesis"><h2>' + _esc(L["thesis"]) + '</h2><pre>'
                 + _esc(collector.verdict_text) + '</pre></section>')
```
Replace with split + markdown (drop the `<pre>`):
```python
    if collector.verdict_text:
        v_answer, v_thinking = split_thinking(collector.verdict_text)
        p.append('<section class="thesis"><h2>' + _esc(L["thesis"]) + '</h2>'
                 + '<div class="thesis-body">' + render_markdown(v_answer) + '</div>'
                 + _thought_details(v_thinking, L.get("thinking_label", "")) + '</section>')
```

(f) `_transcript` — where it renders message text (`_esc(txt)` inside
`<div class="msg">…`), apply `answer, thinking = split_thinking(txt)` and render
`render_markdown(answer)` + `_thought_details(thinking, label)`; keep the `[who]`
prefix span. (`_transcript` has `labels`; read `labels.text.get("thinking_label","")`.)

(g) CSS — in `_css()`, append rules (inside the returned string) for the thinking
expander and markdown elements:
```python
        '.thinking{margin:6px 0;border-left:3px solid var(--line);padding-left:10px;}'
        '.thinking summary{cursor:pointer;color:var(--muted);font-size:.85em;}'
        '.thinking p,.thinking li{color:var(--muted);}'
        '.aspect ul,.aspect ol,.thesis-body ul,.thesis-body ol{margin:6px 0;padding-left:22px;}'
        '.aspect code,.thesis-body code{background:#f3f4f6;padding:1px 4px;border-radius:4px;'
        'font-family:Consolas,monospace;font-size:.92em;}'
        '.aspect pre,.thesis-body pre{background:#f6f8fa;padding:10px;border-radius:8px;overflow:auto;}'
        '.thesis-body p{margin:.4em 0;}'
```
(Append these to the existing big CSS string literal, before its closing.)

- [ ] **Step 5: Run, verify pass** — `.venv/bin/python -m pytest tests/test_report.py -v` → all PASS (new + existing). Full suite `.venv/bin/python -m pytest -q` → PASS. If a pre-existing report test asserted the raw `<pre>…verdict…</pre>` wrapping, update that assertion to match the new `thesis-body` markdown rendering (the verdict text still appears).

- [ ] **Step 6: Commit**

```bash
git add committee/report.py committee/markets/tw.py committee/markets/us.py tests/test_report.py
git commit -m "feat: report renders markdown + collapsible thinking"
```

---

## Task 4: JS renderer (`web/static/md.js`)

**Files:** Create `web/static/md.js`

- [ ] **Step 1: Create `web/static/md.js`** — a structural mirror of the Python helpers, exposing `window.MD`:

```javascript
"use strict";
// Mirror of committee/markdown.py: splitThinking + a small safe markdown subset.
(function (global) {
  const TAG = /<(thought|think)\b[^>]*>([\s\S]*?)<\/\1>/gi;
  const OPEN = /<(thought|think)\b[^>]*>([\s\S]*)$/i;

  function splitThinking(text) {
    text = text || "";
    const thoughts = [];
    let answer = text.replace(TAG, (m, tag, body) => { thoughts.push(body.trim()); return ""; });
    const m = answer.match(OPEN);
    if (m) { thoughts.push(m[2].trim()); answer = answer.slice(0, m.index); }
    const thinking = thoughts.filter(Boolean).join("\n\n").trim();
    return { answer: answer.trim(), thinking: thinking };
  }

  function esc(s) {
    return (s || "").replace(/&/g, "&amp;").replace(/</g, "&lt;")
      .replace(/>/g, "&gt;").replace(/"/g, "&quot;");
  }

  function inline(s) {
    s = s.replace(/`([^`]+)`/g, (m, c) => "<code>" + c + "</code>");
    s = s.replace(/\[([^\]]+)\]\(([^)]+)\)/g, (m, t, u) =>
      (u.indexOf("http://") === 0 || u.indexOf("https://") === 0)
        ? '<a href="' + u + '" target="_blank" rel="noopener">' + t + "</a>" : m);
    s = s.replace(/\*\*([^*]+)\*\*/g, (m, t) => "<strong>" + t + "</strong>");
    s = s.replace(/\*([^*]+)\*/g, (m, t) => "<em>" + t + "</em>");
    return s;
  }

  const HEADING = /^(#{1,3})\s+(.*)$/;
  const ULI = /^[-*]\s+(.*)$/;
  const OLI = /^\d+\.\s+(.*)$/;

  function renderMarkdown(text) {
    const lines = esc(text || "").split("\n");
    const out = [];
    let i = 0;
    const n = lines.length;
    while (i < n) {
      const line = lines[i];
      const stripped = line.trim();
      if (stripped.indexOf("```") === 0) {
        i++;
        const code = [];
        while (i < n && lines[i].trim().indexOf("```") !== 0) { code.push(lines[i]); i++; }
        i++;
        out.push("<pre><code>" + code.join("\n") + "</code></pre>");
        continue;
      }
      if (stripped === "") { i++; continue; }
      const h = line.match(HEADING);
      if (h) { const lvl = h[1].length + 2; out.push("<h" + lvl + ">" + inline(h[2].trim()) + "</h" + lvl + ">"); i++; continue; }
      if (ULI.test(line)) {
        const items = [];
        while (i < n && ULI.test(lines[i])) { items.push("<li>" + inline(lines[i].match(ULI)[1].trim()) + "</li>"); i++; }
        out.push("<ul>" + items.join("") + "</ul>");
        continue;
      }
      if (OLI.test(line)) {
        const items = [];
        while (i < n && OLI.test(lines[i])) { items.push("<li>" + inline(lines[i].match(OLI)[1].trim()) + "</li>"); i++; }
        out.push("<ol>" + items.join("") + "</ol>");
        continue;
      }
      const para = [];
      while (i < n && lines[i].trim() !== "" && !HEADING.test(lines[i]) && !ULI.test(lines[i])
             && !OLI.test(lines[i]) && lines[i].trim().indexOf("```") !== 0) {
        para.push(inline(lines[i].trim())); i++;
      }
      out.push("<p>" + para.join("<br>") + "</p>");
    }
    return out.join("");
  }

  global.MD = { splitThinking: splitThinking, renderMarkdown: renderMarkdown };
})(window);
```

- [ ] **Step 2: Structural verification** (no JS test harness) — confirm the file parses as a module and exposes the API by checking with node if available, else a grep:

```bash
cd /Users/steventsai/Documents/Claude_Project/stock-ana/stock-analysis
node -e "global.window={}; require('./web/static/md.js'); const r=window.MD.renderMarkdown('**b**\n- x'); const s=window.MD.splitThinking('<thought>t</thought>a'); console.log(r); console.log(JSON.stringify(s)); if(r!=='<p><strong>b</strong></p><ul><li>x</li></ul>'||s.answer!=='a'||s.thinking!=='t'){process.exit(1)}" 2>/dev/null && echo "md.js ok" || .venv/bin/python -c "s=open('web/static/md.js').read(); assert 'global.MD = {' in s and 'splitThinking' in s and 'renderMarkdown' in s; print('md.js present (node not available; structural check only)')"
```
Expected: `md.js ok` (if node present) or the structural-check message.

- [ ] **Step 3: Commit**

```bash
git add web/static/md.js
git commit -m "feat: web markdown renderer (mirror of committee/markdown.py)"
```

---

## Task 5: Live feed wiring (`app.js` + `index.html` + `style.css`) + UI label

**Files:** Modify `web/static/index.html`, `web/static/app.js`, `web/static/style.css`, `committee/markets/tw.py`, `committee/markets/us.py`

- [ ] **Step 1: Load `md.js` before `app.js`** in `web/static/index.html` — add, immediately above the existing `<script src="/static/app.js"></script>`:
```html
<script src="/static/md.js"></script>
```

- [ ] **Step 2: Add `thinking_label` to the web UI labels.** In `committee/markets/tw.py` `tw_ui()` dict add `"thinking_label": "思考過程",`; in `committee/markets/us.py` `us_ui()` dict add `"thinking_label": "Thinking",`. (Both `ui` dicts must keep identical key sets — `tests/test_markets.py::test_profiles_carry_localized_ui_text` asserts `set(tw)==set(us)`.)

- [ ] **Step 3: Make the streamed message body a block element.** In `web/static/app.js` `streamToken`, change the streaming element markup from `<span class="body"></span>` to `<div class="body"></div>` (so block markdown can later replace it):
```javascript
    el.innerHTML = `<span class="who">[${escapeHtml(agentLabel(agent))}]</span><div class="body"></div>`;
```

- [ ] **Step 4: Replace plain message rendering with markdown + thinking.** In `web/static/app.js`, replace the `appendMessage` function with a `finishMessage` that renders the final text (works whether or not tokens streamed):
```javascript
function finishMessage(agent, full) {
  const { answer, thinking } = MD.splitThinking(full);
  let container;
  if (curStreamingAgent === agent && curStreamingMsgEl) {
    container = curStreamingMsgEl.parentElement;          // reuse the streamed .msg
    curStreamingMsgEl.innerHTML = MD.renderMarkdown(answer);
  } else {
    container = document.createElement("div");
    container.className = "msg agent-" + agent;
    container.innerHTML = `<span class="who">[${escapeHtml(agentLabel(agent))}]</span>`
      + `<div class="body">${MD.renderMarkdown(answer)}</div>`;
    messagesEl.appendChild(container);
  }
  if (thinking) {
    const d = document.createElement("details");
    d.className = "thinking";
    d.innerHTML = `<summary>${escapeHtml(ui.thinking_label)}</summary>`
      + `<div class="tbody">${MD.renderMarkdown(thinking)}</div>`;
    container.appendChild(d);
  }
  endStream();
  messagesEl.scrollTop = messagesEl.scrollHeight;
}
```

- [ ] **Step 5: Update the `message` event handler** in `handleEvent` to call `finishMessage` and use the split answer for the card result. Replace the current `if (t === "message") { … }` block with:
```javascript
  if (t === "message") {
    const full = e.data.text || "";
    finishMessage(e.agent, full);
    setStatus(agentLabel(e.agent) + ":" + ui.done_word);
    const ans = MD.splitThinking(full).answer;
    let result;
    if (e.agent === "chair") result = verdictHeadline(ans);
    else if (e.agent === "verifier") result = (ans.split("\n")[0] || ui.done_word).slice(0, 24);
    else result = detectLean(ans);
    setCardResult("agent:" + e.agent, result);
    setCardStatus("agent:" + e.agent, ui.done_badge, "done");
    return;
  }
```

- [ ] **Step 6: Split thinking out of the verdict banner.** In the `if (t === "verdict")` block, change the head computation to use the answer only:
```javascript
  if (t === "verdict") {
    const head = verdictHeadline(MD.splitThinking(e.data.text || "").answer);
    verdictEl.textContent = ui.verdict_prefix + head;
    setCardResult("agent:chair", head);
    setStatus(ui.verdict_done);
    return;
  }
```

- [ ] **Step 7: Add CSS** — append to `web/static/style.css`:
```css
.msg .body p { margin: .35em 0; }
.msg .body ul, .msg .body ol { margin: .35em 0; padding-left: 22px; }
.msg .body code { background: #f3f4f6; padding: 1px 4px; border-radius: 4px; font-family: Consolas, monospace; font-size: .92em; }
.msg .body pre { background: #f6f8fa; padding: 10px; border-radius: 8px; overflow: auto; }
.msg details.thinking { margin: 4px 0 8px; border-left: 3px solid #e6e8eb; padding-left: 10px; }
.msg details.thinking summary { cursor: pointer; color: #6b7280; font-size: .82em; }
.msg details.thinking .tbody { color: #6b7280; font-size: .92em; }
```

- [ ] **Step 8: Structural verification**
```bash
cd /Users/steventsai/Documents/Claude_Project/stock-ana/stock-analysis
.venv/bin/python -c "s=open('web/static/index.html').read(); assert '/static/md.js' in s and s.index('md.js') < s.index('app.js'); print('index ok')"
.venv/bin/python -c "s=open('web/static/app.js').read(); assert 'finishMessage' in s and 'MD.splitThinking' in s and 'MD.renderMarkdown' in s and 'appendMessage' not in s; print('app.js ok')"
.venv/bin/python -m pytest -q 2>&1 | tail -1
```
Expected: `index ok`, `app.js ok`, full suite PASS (the `ui` key-set test stays green because `thinking_label` was added to both markets).

- [ ] **Step 9: Manual browser smoke (operator/controller — not a unit test).** Start `manage.py runserver`, run a US ticker, and confirm: analyst answers render as markdown (bold/lists), each message shows a collapsed "Thinking" expander that opens to the reasoning, and the verdict banner shows a clean headline (no `<thought>`).

- [ ] **Step 10: Commit**
```bash
git add web/static/index.html web/static/app.js web/static/style.css committee/markets/tw.py committee/markets/us.py
git commit -m "feat: live debate renders markdown + collapsible thinking"
```

---

## Self-Review Notes

- **Spec coverage:** `split_thinking` (T1), `render_markdown` (T2), report integration + report `thinking_label` + CSS (T3), JS mirror (T4), live-feed wiring + `ui.thinking_label` + CSS + streaming-stays-plain-then-swaps (T5). Verdict/verifier thinking-split covered in T3 (report) and T5 (live). All spec sections map to a task.
- **Placeholder scan:** none — full code in every step; the one "match the current title source" note in T3(c) is a precise instruction to preserve existing behavior, not a placeholder.
- **Type/name consistency:** Python returns `(answer, thinking)` tuple; JS returns `{answer, thinking}` object — used consistently (`MD.splitThinking(full).answer`, `a, t = split_thinking(...)`). `thinking_label` added to BOTH the report label store (`ReportLabels.text`, T3) and the web `ui` dict (T5) per market. `_thought_details(thinking, label)` defined in T3 and used in aspect/risk/thesis/transcript.
- **Safety:** both renderers `_esc` before applying markdown and restrict links to `http(s)` — tested (`test_escapes_html`, `test_http_link_rendered_other_schemes_literal`).
- **Regression guard:** plain messages (no markdown, no `<thought>`) render as a single `<p>` and still contain the verbatim text, so existing report substring assertions hold (T3 updates only an exact-`<pre>`-wrapping assertion if present).
- **Out of scope (per spec):** desktop GUI, full markdown (tables/nested lists/blockquotes), live mid-stream markdown.
