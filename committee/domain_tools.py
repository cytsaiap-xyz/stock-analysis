from typing import Any

from agentcore.tools import Tool, ToolRegistry
from committee.data.indicators import compute_indicators

_STOCK_NO = {"type": "string", "description": "Taiwan stock code, e.g. 2330"}


def build_registry(twse: Any) -> ToolRegistry:
    reg = ToolRegistry()

    reg.register(Tool(
        name="get_valuation",
        description="Get P/E, P/B and dividend yield for a Taiwan stock from TWSE.",
        parameters={"type": "object",
                    "properties": {"stock_no": _STOCK_NO},
                    "required": ["stock_no"]},
        fn=lambda stock_no: twse.valuation(stock_no),
    ))

    def _indicators(stock_no: str, months: int = 3):
        # LLMs often pass numeric args as strings ("3"); coerce defensively.
        return compute_indicators(twse.price_history(stock_no, months=int(months)))

    reg.register(Tool(
        name="get_technical_indicators",
        description=("Get moving averages (MA5/20/60), trend, period % change and "
                     "average volume for a Taiwan stock, computed from TWSE daily prices."),
        parameters={"type": "object",
                    "properties": {"stock_no": _STOCK_NO,
                                   "months": {"type": "integer",
                                              "description": "recent months of data",
                                              "default": 3}},
                    "required": ["stock_no"]},
        fn=_indicators,
    ))

    return reg
