from dataclasses import dataclass
from typing import List, Optional

from agentcore.agent import Agent
from committee.config import (MODEL_REASONER, MODEL_REASONER_FALLBACKS,
                              MODEL_TOOL_CALLER, MODEL_TOOL_CALLER_FALLBACKS)
from committee.markets.base import Prompts


@dataclass
class Committee:
    research: List[Agent]      # fundamental, technical, institutional, news
    challengers: List[Agent]   # risk, skeptic
    chair: Agent
    verifier: Agent


def build_committee(prompts: Optional[Prompts] = None) -> Committee:
    if prompts is None:
        from committee.markets.tw import tw_prompts
        prompts = tw_prompts()
    fundamental = Agent(name="fundamental", role="Fundamental Analyst",
                        system_prompt=prompts.fundamental, model=MODEL_TOOL_CALLER,
                        fallback_models=MODEL_TOOL_CALLER_FALLBACKS,
                        tool_names=["get_valuation", "get_monthly_revenue", "get_financials"])
    technical = Agent(name="technical", role="Technical Analyst",
                      system_prompt=prompts.technical, model=MODEL_TOOL_CALLER,
                      fallback_models=MODEL_TOOL_CALLER_FALLBACKS,
                      tool_names=["get_technical_indicators", "get_relative_strength"])
    institutional = Agent(name="institutional", role="Institutional Flow Analyst",
                          system_prompt=prompts.institutional, model=MODEL_TOOL_CALLER,
                          fallback_models=MODEL_TOOL_CALLER_FALLBACKS,
                          tool_names=["get_institutional_flows"])
    news = Agent(name="news", role="News Analyst", system_prompt=prompts.news,
                 model=MODEL_TOOL_CALLER, fallback_models=MODEL_TOOL_CALLER_FALLBACKS,
                 tool_names=["search_news"])
    risk = Agent(name="risk", role="Risk Manager", system_prompt=prompts.risk,
                 model=MODEL_REASONER, fallback_models=MODEL_REASONER_FALLBACKS,
                 tool_names=["get_risk_metrics"])
    skeptic = Agent(name="skeptic", role="Skeptic", system_prompt=prompts.skeptic,
                    model=MODEL_REASONER, fallback_models=MODEL_REASONER_FALLBACKS, tool_names=[])
    chair = Agent(name="chair", role="Chair", system_prompt=prompts.chair,
                  model=MODEL_REASONER, fallback_models=MODEL_REASONER_FALLBACKS, tool_names=[])
    verifier = Agent(name="verifier", role="Verifier", system_prompt=prompts.verifier,
                     model=MODEL_REASONER, fallback_models=MODEL_REASONER_FALLBACKS, tool_names=[])
    return Committee(research=[fundamental, technical, institutional, news],
                     challengers=[risk, skeptic], chair=chair, verifier=verifier)
