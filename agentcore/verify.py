"""Deterministic grounding check for the VERIFY step.

Confirms that the data-like figures cited in a verdict (prices, ratios, percentages,
thousands-grouped share counts) actually trace back to a tool result recorded in the
EvidenceLedger. This is the non-LLM half of self-verification; an LLM verifier handles
reasoning consistency separately.
"""
import json
import re
from typing import Any, Dict, List

# A figure that looks like real data: has a decimal point, or is thousands-grouped.
_DATA_LIKE = re.compile(r"-?\d{1,3}(?:,\d{3})+(?:\.\d+)?|-?\d+\.\d+")
# Any numeric token (used to scan the evidence side).
_ANY_NUM = re.compile(r"-?[\d,]*\.?\d+")


def _to_float(token: str):
    token = token.replace(",", "").strip()
    if token in ("", ".", "-"):
        return None
    try:
        return float(token)
    except ValueError:
        return None


def _data_like_floats(text: str) -> List[float]:
    out = []
    for tok in _DATA_LIKE.findall(text or ""):
        f = _to_float(tok)
        if f is not None:
            out.append(f)
    return out


def _evidence_floats(ledger: Any) -> List[float]:
    blob = " ".join(
        json.dumps(e.result, ensure_ascii=False, default=str) for e in ledger.entries())
    out = []
    for tok in _ANY_NUM.findall(blob):
        f = _to_float(tok)
        if f is not None:
            out.append(f)
    return out


def check_grounding(verdict_text: str, ledger: Any, tol: float = 0.01) -> Dict[str, Any]:
    """Return a grounding report for the data-like figures cited in verdict_text.

    A figure is 'supported' if it matches (within a small tolerance) any number that
    appears in the EvidenceLedger's recorded tool results.
    """
    claimed = _data_like_floats(verdict_text)
    evidence = _evidence_floats(ledger)
    unsupported = []
    for c in claimed:
        if not any(abs(c - e) <= max(tol, abs(c) * tol) for e in evidence):
            unsupported.append(c)
    return {
        "checked": len(claimed),
        "supported": len(claimed) - len(unsupported),
        "unsupported": unsupported,
        "grounded": not unsupported,
    }
