# Markdown Rendering + Thinking Separation — Design Spec

**Date:** 2026-06-10
**Status:** Approved
**Topic:** Render agent output as markdown and split model "thinking" from the answer, in the web live debate and the saved HTML report.

## Goal

Make the committee's agent output readable: render each agent's message as
**markdown** instead of plain text, and **separate the model's reasoning preamble**
(`<thought>…</thought>`, emitted by gemma; `<think>…</think>` by other reasoning
models) from the actual answer, showing the reasoning in a collapsed expander.

Applies to the **web live debate** (`web/static/app.js`) and the **saved HTML
report** (`committee/report.py`). The desktop GUI stays plain text (Tkinter can't
render HTML easily).

## Decisions (locked)

1. **Thinking presentation:** collapsible `<details>`, collapsed by default; the
   markdown answer is shown prominently above it.
2. **Scope:** web live debate **and** saved report. Desktop GUI out of scope.
3. **Markdown renderer:** a minimal, dependency-free renderer implemented to a
   shared spec — once in JS (live feed), once in Python (report). HTML is escaped
   first, so rendering untrusted model output is XSS-safe by construction. No new
   dependencies; works offline.
4. **Streaming:** tokens stream as plain text live (progress visible); on the final
   `message` event the streamed text is replaced with the rendered markdown +
   collapsible thinking. (Rendering partial markdown mid-stream looks broken.)

## Shared building blocks (one JS impl, one Python impl, same behavior)

### `split_thinking(text) -> {thinking, answer}`

- Extracts the contents of all `<thought>…</thought>` and `<think>…</think>`
  blocks (case-insensitive, dot-matches-newline). `thinking` = the block contents
  joined by a blank line, trimmed. `answer` = the text with those blocks removed,
  trimmed.
- No tags → `thinking = ""`, `answer = text`.
- **Unclosed trailing open tag** (e.g. a truncated `<thought>…` with no close):
  everything from the open tag to end is treated as `thinking`; `answer` is the
  text before it. (Guards against truncated reasoning output.)

### `render_markdown(text) -> html`

Escape `&<>` first, then apply this fixed subset (anything outside it renders as
plain escaped text):

- Fenced code blocks ```` ``` ```` → `<pre><code>…</code></pre>` (content escaped, no
  inner markdown).
- Headings `#`/`##`/`###` at line start → `<h3>`/`<h4>`/`<h5>` (kept small to fit
  the feed/report).
- Unordered lists (`-` or `*` + space) → `<ul><li>…</li></ul>`.
- Ordered lists (`N.` + space) → `<ol><li>…</li></ol>`.
- Inline, applied within paragraphs/list items: `**bold**` → `<strong>`,
  `*italic*`/`_italic_` → `<em>`, `` `code` `` → `<code>`,
  `[text](url)` → `<a href="url" target="_blank" rel="noopener">text</a>` **only
  when url starts with `http://`/`https://`** (otherwise rendered as literal text).
- Blank-line-separated blocks → `<p>`; single newlines inside a block → `<br>`.

This subset covers what the analysts emit (short notes with bold, lists, the odd
heading/code). Tables, nested lists, and blockquotes are intentionally unsupported.

## Web live debate

**Files:** `web/static/md.js` (new — `splitThinking` + `renderMarkdown`),
`web/static/app.js`, `web/static/index.html`, `web/static/style.css`.

- `index.html` loads `md.js` before `app.js`.
- `app.js`:
  - `streamToken` is unchanged (plain-text live streaming into the message body).
  - On the `message` event, instead of appending plain text, build the final
    message element: `splitThinking(text)`, set the body's `innerHTML` to
    `renderMarkdown(answer)`, and if `thinking` is non-empty append a
    `<details class="thinking"><summary>…</summary><div>renderMarkdown(thinking)</div></details>`.
    The same applies whether the message followed a token stream (replace the
    streamed plain body with rendered markdown) or arrived without streaming.
  - The **verdict** banner and **verifier** text run `splitThinking` first so the
    headline/线 isn't polluted by the reasoning block (render the answer part;
    `verdictHeadline`/`detectLean` operate on the answer).
- `style.css`: styles for `.thinking` (dimmed `<summary>`, smaller text) and the
  markdown elements inside a message (`ul/ol/li`, `code`, `pre`, `strong`, `em`,
  `h3-h5`, `p` spacing).
- The `summary` label text comes from the market **`ui` dict** (a new
  `thinking_label` key, e.g. `思考過程` / `Thinking`, added to `tw_ui()`/`us_ui()`)
  so it localizes; `committee_info` already returns `ui`, so `app.js` reads
  `ui.thinking_label`.

## Saved report

**Files:** `committee/markdown.py` (new — `split_thinking` + `render_markdown`),
`committee/report.py`, plus the new `ui.thinking_label` consumed via labels.

- `committee/markdown.py` implements the two helpers per the shared spec above.
- `report.py`:
  - `_aspect_sections` and the transcript message rendering: run each agent message
    through `split_thinking`, render the answer with `render_markdown`, and wrap any
    thinking in a collapsed `<details>` (a `_thought_details(thinking, label)`
    helper).
  - The thesis/verdict block and the verifier text: same treatment (render the
    answer markdown; thinking collapsed).
  - `_rating`/grounding figure extraction already scan the whole verdict text, so
    they keep working; rendering only affects display.
  - The report CSS (`_css`) gains rules for `.thinking` and markdown elements,
    mirroring the live view.
- The report reads its summary label from **`ReportLabels.text["thinking_label"]`**
  (added to `tw_labels()`/`us_labels()`), so the report `<details>` summary
  localizes with the report language. (The web `ui` dict and the report
  `ReportLabels.text` are separate label stores — `thinking_label` is added to
  both, per market.)

## Testing

- `tests/test_markdown.py` (new):
  - `split_thinking`: no tags; one `<thought>` block; `<think>` block; multiple
    blocks; an unclosed trailing `<thought>`; thinking trimmed; answer trimmed.
  - `render_markdown`: bold/italic/inline-code, fenced code block, unordered and
    ordered lists, headings, a link with `http(s)` (rendered) and a non-http link
    (literal), and **HTML escaping** (`<script>` becomes inert text).
- `tests/test_report.py` (extend): an aspect/message containing a `<thought>` block
  renders the answer as HTML (e.g. a `<strong>` or `<li>`) and emits a
  `<details>` containing the thinking; the verdict thesis with `<thought>` shows
  the answer, not the raw tag.
- JS (`md.js`, `app.js`) has no unit harness — verified by a browser smoke (run a
  ticker, confirm markdown answers render and the thinking expander appears) and by
  mirroring the tested Python renderer's behavior.
- Full suite stays green; TW report output for messages **without** thinking and
  with plain text stays equivalent (plain text renders as a single `<p>`), which the
  report tests confirm.

## Risks / notes

- **Two implementations of the renderer** (JS + Python) must stay behaviorally
  aligned. Mitigation: a fixed, small, documented subset; the Python side is unit
  tested and the JS side mirrors it line-for-line in structure.
- **Safety:** both renderers escape HTML before applying markdown, and links are
  restricted to `http(s)`, so model output cannot inject active HTML.
- **Existing report tests** assert raw message substrings appear in the HTML; after
  markdown rendering, a plain message still appears verbatim inside a `<p>` (no
  markdown chars to transform), so those assertions hold. Any that check exact
  wrapping are updated minimally.

## Out of scope

- Desktop GUI markdown (stays plain text).
- Full markdown (tables, nested lists, blockquotes, images).
- Re-rendering markdown live during streaming (plain until the final message).
