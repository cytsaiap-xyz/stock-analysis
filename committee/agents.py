from typing import List, Tuple

from agentcore.agent import Agent
from committee.config import MODEL_REASONER, MODEL_TOOL_CALLER

_FUNDAMENTAL_PROMPT = (
    "You are a buy-side Fundamental Analyst covering Taiwan equities. "
    "Use get_valuation to fetch real P/E, P/B and dividend yield. "
    "Judge whether the valuation is attractive. Be concise (<=120 words). "
    "End with a clear lean: BULLISH, BEARISH, or NEUTRAL. "
    "Never invent numbers; if a tool fails, say the data is unavailable."
)

_TECHNICAL_PROMPT = (
    "You are a Technical Analyst covering Taiwan equities. "
    "Use get_technical_indicators to fetch moving averages, trend and momentum. "
    "Assess the trend and timing. Be concise (<=120 words). "
    "End with a clear lean: BULLISH, BEARISH, or NEUTRAL. "
    "Never invent numbers; if a tool fails, say the data is unavailable."
)

# Domain-specific analyst task wording, passed into the (domain-neutral) Orchestrator.
ANALYST_TASK_TEMPLATE = (
    "Analyze Taiwan stock {stock} from your perspective. Use your tools to get real "
    "data first, then give your concise opinion and a BULLISH/BEARISH/NEUTRAL lean."
)

_CHAIR_PROMPT = (
    "You are the Chair of an investment committee. You receive the analysts' "
    "statements and must issue ONE final call. Output exactly: a first line "
    "'RECOMMENDATION: BUY|HOLD|SELL', then a 'CONFIDENCE: NN%' line, then a "
    "one-paragraph rationale that references the analysts' points. Do not invent "
    "figures beyond what the analysts reported."
)


def build_committee() -> Tuple[List[Agent], Agent]:
    fundamental = Agent(name="fundamental", role="Fundamental Analyst",
                        system_prompt=_FUNDAMENTAL_PROMPT, model=MODEL_TOOL_CALLER,
                        tool_names=["get_valuation"])
    technical = Agent(name="technical", role="Technical Analyst",
                      system_prompt=_TECHNICAL_PROMPT, model=MODEL_TOOL_CALLER,
                      tool_names=["get_technical_indicators"])
    chair = Agent(name="chair", role="Chair", system_prompt=_CHAIR_PROMPT,
                  model=MODEL_REASONER, tool_names=[])
    return [fundamental, technical], chair
