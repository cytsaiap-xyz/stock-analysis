# committee/markets/base.py
"""Market-profile interface: the bundle of market-specific config every market
fills in. agentcore/ stays domain-neutral; all market text lives behind these."""
from dataclasses import dataclass
from typing import Any, Dict, List, Tuple


@dataclass
class Templates:
    """The six domain task templates injected into the (neutral) Orchestrator."""
    analyst: str
    challenge: str
    rebuttal: str
    reflect: str
    verify: str
    correction: str
    discussion: str


@dataclass
class Prompts:
    """System prompts for the 8 committee roles."""
    fundamental: str
    technical: str
    institutional: str
    news: str
    risk: str
    skeptic: str
    chair: str
    verifier: str


@dataclass
class ToolDescriptions:
    """LLM-facing descriptions for each registered tool + the stock_no param.

    Tool *names* are identical across markets so report buckets and the roster
    stay shared; only the descriptions localize.
    """
    stock_param: str
    get_valuation: str
    get_technical_indicators: str
    get_institutional_flows: str
    get_monthly_revenue: str
    get_risk_metrics: str
    get_relative_strength: str
    get_financials: str
    search_news: str


@dataclass
class ReportLabels:
    """Everything the HTML report needs to render in one language."""
    lang: str                          # "zh-TW" | "en"
    text: Dict[str, str]               # UI label strings, keyed (see tw.py/us.py)
    rating_class: Dict[str, str]       # verdict word -> css class (buy/hold/sell)
    recommend_label: str               # "建議" | "Recommendation"
    confidence_label: str              # "信心" | "Confidence"
    agent_names: Dict[str, str]        # agent id -> display name
    phase_names: Dict[str, str]        # phase id -> display name
    aspect_order: List[Tuple[str, str]]  # (agent id, section title)
    institutional_kind: str            # "lots" | "ownership"
    revenue_kind: str                  # "monthly" | "quarterly"
    disclaimer: str


@dataclass
class MarketProfile:
    """Self-contained config for analyzing one market. Front-ends consume this."""
    market: str                        # "tw" | "us"
    lang: str                          # "zh-TW" | "en"
    client: Any                        # MarketDataClient (duck-typed)
    committee: Any                     # committee.agents.Committee
    templates: Templates
    labels: ReportLabels
    descriptions: ToolDescriptions
    ui: Dict[str, str]
    stocklist: list
