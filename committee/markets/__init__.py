# committee/markets/__init__.py
"""Market routing: detect a symbol's market and build its MarketProfile."""
import re

_TW_RE = re.compile(r"^\d{4,6}(\.TWO?)?$")


def detect_market(symbol: str) -> str:
    """Return "tw" or "us" for a stock symbol, inferred from its format.

    Taiwan codes are 4-6 digits (optionally suffixed .TW/.TWO); anything
    containing letters is treated as a US ticker.
    """
    s = (symbol or "").strip().upper()
    if not s:
        raise ValueError("empty symbol")
    if _TW_RE.match(s):
        return "tw"
    return "us"
