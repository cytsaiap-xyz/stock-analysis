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
