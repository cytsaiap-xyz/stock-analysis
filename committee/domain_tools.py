from typing import Any

from agentcore.tools import Tool, ToolRegistry
from committee.data.indicators import compute_indicators, compute_risk
from committee.data.news import search_news as _search_news

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

    reg.register(Tool(
        name="get_institutional_flows",
        description="取得台股某檔最近交易日的三大法人(外資/投信/自營商)買賣超股數。",
        parameters={"type": "object",
                    "properties": {"stock_no": _STOCK_NO},
                    "required": ["stock_no"]},
        fn=lambda stock_no: twse.institutional_flows(stock_no),
    ))

    reg.register(Tool(
        name="get_monthly_revenue",
        description="取得台股某檔最新月營收與年增率(YoY);若最新批次未涵蓋該股,會回報資料暫無。",
        parameters={"type": "object",
                    "properties": {"stock_no": _STOCK_NO},
                    "required": ["stock_no"]},
        fn=lambda stock_no: twse.monthly_revenue(stock_no),
    ))

    def _risk(stock_no: str, months: int = 3):
        return compute_risk(twse.price_history(stock_no, months=int(months)))

    reg.register(Tool(
        name="get_risk_metrics",
        description="取得台股某檔的風險指標:年化波動率與最大回撤(由日收盤價計算)。",
        parameters={"type": "object",
                    "properties": {"stock_no": _STOCK_NO,
                                   "months": {"type": "integer",
                                              "description": "近幾個月資料",
                                              "default": 3}},
                    "required": ["stock_no"]},
        fn=_risk,
    ))

    reg.register(Tool(
        name="search_news",
        description="搜尋某主題的近期新聞標題與摘要(用於輿情分析)。",
        parameters={"type": "object",
                    "properties": {"query": {"type": "string",
                                             "description": "搜尋關鍵字,例如:台積電 2330"}},
                    "required": ["query"]},
        fn=lambda query: _search_news(query),
    ))

    return reg
