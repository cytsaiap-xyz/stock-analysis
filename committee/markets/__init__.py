# committee/markets/__init__.py
"""Market routing: detect a symbol's market and build its MarketProfile."""
import re
from committee.config import CACHE_DIR

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


def build_tw_profile():
    from committee.agents import build_committee
    from committee.data.twse import TwseClient
    from committee.markets.base import MarketProfile
    from committee.markets.tw import tw_prompts, tw_templates, tw_labels
    return MarketProfile(market="tw", lang="zh-TW", client=TwseClient(cache_dir=CACHE_DIR),
                         committee=build_committee(tw_prompts()), templates=tw_templates(),
                         labels=tw_labels())


def build_us_profile():
    from committee.agents import build_committee
    from committee.data.us_market import UsClient
    from committee.markets.base import MarketProfile
    from committee.markets.us import us_prompts, us_templates, us_labels
    return MarketProfile(market="us", lang="en", client=UsClient(cache_dir=CACHE_DIR),
                         committee=build_committee(us_prompts()), templates=us_templates(),
                         labels=us_labels())


def get_profile(market: str):
    if market == "tw":
        return build_tw_profile()
    if market == "us":
        return build_us_profile()
    raise ValueError("unknown market: {}".format(market))
