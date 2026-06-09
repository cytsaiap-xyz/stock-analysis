# tests/test_us_market.py
import tempfile

from committee.data.us_market import UsClient


class _FakeTicker:
    def __init__(self, symbol):
        self.symbol = symbol
        self.info = {"longName": "Apple Inc.", "trailingPE": 30.5,
                     "priceToBook": 45.2, "dividendYield": 0.0045}


class _FakeYf:
    """Stand-in for the yfinance module."""
    def Ticker(self, symbol):
        return _FakeTicker(symbol)


def _client(**kw):
    return UsClient(cache_dir=tempfile.mkdtemp(), yf=_FakeYf(), **kw)


def test_valuation_maps_info_fields_and_normalizes_yield_to_percent():
    out = _client().valuation("AAPL")
    assert out["stock_no"] == "AAPL"
    assert out["name"] == "Apple Inc."
    assert out["pe"] == 30.5
    assert out["pb"] == 45.2
    # 0.0045 fraction -> 0.45 percent (TW field semantics are a percent)
    assert abs(out["dividend_yield"] - 0.45) < 1e-9
