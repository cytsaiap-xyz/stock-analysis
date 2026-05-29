from committee.domain_tools import build_registry


class _FakeTwse:
    def valuation(self, stock_no):
        return {"stock_no": stock_no, "name": "台積電", "pe": 22.5,
                "pb": 6.3, "dividend_yield": 1.85}

    def price_history(self, stock_no, months=3):
        return [{"date": "2026-05-0{}".format(i + 1), "open": 10 + i, "high": 10 + i,
                 "low": 10 + i, "close": 10 + i, "volume": 1000} for i in range(5)]

    def institutional_flows(self, stock_no):
        return {"stock_no": stock_no, "foreign_net": 12000, "trust_net": 3000,
                "dealer_net": -1500, "total_net": 13500}

    def monthly_revenue(self, stock_no):
        return {"stock_no": stock_no, "available": True, "yoy_pct": "39.0"}

    def index_history(self, months=3):
        return [{"date": "2026-05-0{}".format(i + 1), "close": 100 + i} for i in range(5)]

    def financials(self, stock_no):
        return {"stock_no": stock_no, "available": True, "period": "115Q1",
                "gross_margin_pct": 60.0, "roe_pct": 10.0, "eps": 13.94}


def test_registry_exposes_mvp_tools():
    reg = build_registry(_FakeTwse())
    schemas = {s["function"]["name"] for s in
               reg.schemas(["get_valuation", "get_technical_indicators"])}
    assert schemas == {"get_valuation", "get_technical_indicators"}


def test_get_valuation_tool_runs():
    reg = build_registry(_FakeTwse())
    out = reg.get("get_valuation").fn(stock_no="2330")
    assert out["pe"] == 22.5


def test_get_technical_indicators_tool_runs():
    reg = build_registry(_FakeTwse())
    out = reg.get("get_technical_indicators").fn(stock_no="2330", months=1)
    assert out["last_close"] == 14.0  # close of last (10+4) row
    assert "trend" in out


def test_get_technical_indicators_coerces_string_months():
    # Regression: the live LLM passed months="3" (a string). The real TwseClient
    # does integer math on months, so a string raised TypeError. The tool must coerce.
    class _IntMonthsTwse(_FakeTwse):
        def price_history(self, stock_no, months=3):
            _ = list(range(months))  # would raise TypeError if months is a str
            return super().price_history(stock_no, months=months)

    reg = build_registry(_IntMonthsTwse())
    out = reg.get("get_technical_indicators").fn(stock_no="2330", months="3")
    assert "trend" in out


def test_technical_indicators_includes_oscillators():
    reg = build_registry(_FakeTwse())
    out = reg.get("get_technical_indicators").fn(stock_no="2330", months=1)
    # MA-based keys plus RSI/KD/MACD oscillators, merged into one tool result.
    assert "trend" in out
    for key in ("rsi14", "kd_k", "kd_d", "macd", "macd_signal", "macd_hist"):
        assert key in out


def test_registry_exposes_all_phase2_tools():
    reg = build_registry(_FakeTwse())
    names = {"get_valuation", "get_technical_indicators", "get_institutional_flows",
             "get_monthly_revenue", "get_risk_metrics", "search_news"}
    got = {s["function"]["name"] for s in reg.schemas(list(names))}
    assert got == names


def test_institutional_and_revenue_tools_run():
    reg = build_registry(_FakeTwse())
    assert reg.get("get_institutional_flows").fn(stock_no="2330")["foreign_net"] == 12000
    assert reg.get("get_monthly_revenue").fn(stock_no="2330")["yoy_pct"] == "39.0"


def test_risk_metrics_tool_runs_and_coerces_months():
    reg = build_registry(_FakeTwse())
    out = reg.get("get_risk_metrics").fn(stock_no="2330", months="3")
    assert "volatility_annual_pct" in out and "max_drawdown_pct" in out


def test_relative_strength_tool_runs_and_coerces_months():
    reg = build_registry(_FakeTwse())
    out = reg.get("get_relative_strength").fn(stock_no="2330", months="3")
    assert "excess_return_pct" in out and "stock_return_pct" in out


def test_financials_tool_runs():
    reg = build_registry(_FakeTwse())
    out = reg.get("get_financials").fn(stock_no="2330")
    assert out["gross_margin_pct"] == 60.0 and out["roe_pct"] == 10.0


def test_registry_exposes_phase3_tools():
    reg = build_registry(_FakeTwse())
    names = {"get_relative_strength", "get_financials"}
    got = {s["function"]["name"] for s in reg.schemas(list(names))}
    assert got == names
