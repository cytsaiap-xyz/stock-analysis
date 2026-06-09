from typing import Any, Optional

from agentcore.tools import Tool, ToolRegistry
from committee.data.indicators import (
    compute_indicators,
    compute_oscillators,
    compute_relative_strength,
    compute_risk,
)
from committee.data.news import search_news as _search_news
from committee.markets.base import ToolDescriptions


def build_registry(client: Any, descriptions: Optional[ToolDescriptions] = None) -> ToolRegistry:
    if descriptions is None:
        from committee.markets.tw import tw_tool_descriptions
        descriptions = tw_tool_descriptions()
    d = descriptions
    stock_param = {"type": "string", "description": d.stock_param}
    reg = ToolRegistry()

    reg.register(Tool(
        name="get_valuation",
        description=d.get_valuation,
        parameters={"type": "object", "properties": {"stock_no": stock_param},
                    "required": ["stock_no"]},
        fn=lambda stock_no: client.valuation(stock_no),
    ))

    def _indicators(stock_no: str, months: int = 3):
        # LLMs often pass numeric args as strings ("3"); coerce defensively.
        prices = client.price_history(stock_no, months=int(months))
        return {**compute_indicators(prices), **compute_oscillators(prices)}

    reg.register(Tool(
        name="get_technical_indicators",
        description=d.get_technical_indicators,
        parameters={"type": "object",
                    "properties": {"stock_no": stock_param,
                                   "months": {"type": "integer",
                                              "description": "recent months of data",
                                              "default": 3}},
                    "required": ["stock_no"]},
        fn=_indicators,
    ))

    reg.register(Tool(
        name="get_institutional_flows",
        description=d.get_institutional_flows,
        parameters={"type": "object", "properties": {"stock_no": stock_param},
                    "required": ["stock_no"]},
        fn=lambda stock_no: client.institutional_flows(stock_no),
    ))

    reg.register(Tool(
        name="get_monthly_revenue",
        description=d.get_monthly_revenue,
        parameters={"type": "object", "properties": {"stock_no": stock_param},
                    "required": ["stock_no"]},
        fn=lambda stock_no: client.monthly_revenue(stock_no),
    ))

    def _risk(stock_no: str, months: int = 3):
        return compute_risk(client.price_history(stock_no, months=int(months)))

    reg.register(Tool(
        name="get_risk_metrics",
        description=d.get_risk_metrics,
        parameters={"type": "object",
                    "properties": {"stock_no": stock_param,
                                   "months": {"type": "integer",
                                              "description": "近幾個月資料",
                                              "default": 3}},
                    "required": ["stock_no"]},
        fn=_risk,
    ))

    def _relative_strength(stock_no: str, months: int = 3):
        return compute_relative_strength(client.price_history(stock_no, months=int(months)),
                                         client.index_history(months=int(months)))

    reg.register(Tool(
        name="get_relative_strength",
        description=d.get_relative_strength,
        parameters={"type": "object",
                    "properties": {"stock_no": stock_param,
                                   "months": {"type": "integer",
                                              "description": "近幾個月資料",
                                              "default": 3}},
                    "required": ["stock_no"]},
        fn=_relative_strength,
    ))

    reg.register(Tool(
        name="get_financials",
        description=d.get_financials,
        parameters={"type": "object", "properties": {"stock_no": stock_param},
                    "required": ["stock_no"]},
        fn=lambda stock_no: client.financials(stock_no),
    ))

    reg.register(Tool(
        name="search_news",
        description=d.search_news,
        parameters={"type": "object",
                    "properties": {"query": {"type": "string",
                                             "description": "搜尋關鍵字,例如:台積電 2330"}},
                    "required": ["query"]},
        fn=lambda query: _search_news(query),
    ))

    return reg
