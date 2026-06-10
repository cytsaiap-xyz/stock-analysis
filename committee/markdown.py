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
