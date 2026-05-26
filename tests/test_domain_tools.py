from committee.domain_tools import build_registry


class _FakeTwse:
    def valuation(self, stock_no):
        return {"stock_no": stock_no, "name": "台積電", "pe": 22.5,
                "pb": 6.3, "dividend_yield": 1.85}

    def price_history(self, stock_no, months=3):
        return [{"date": "2026-05-0{}".format(i + 1), "open": 10 + i, "high": 10 + i,
                 "low": 10 + i, "close": 10 + i, "volume": 1000} for i in range(5)]


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
