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


class _FakeHistory:
    """Mimics the DataFrame returned by yfinance Ticker.history(): iterable rows
    via .itertuples() with Index (Timestamp-like) + OHLCV attributes."""
    def __init__(self, rows):
        self._rows = rows  # list of dicts with date/open/high/low/close/volume

    def itertuples(self):
        class _Row:
            pass
        for r in self._rows:
            row = _Row()
            row.Index = _FakeTs(r["date"])
            row.Open, row.High, row.Low = r["open"], r["high"], r["low"]
            row.Close, row.Volume = r["close"], r["volume"]
            yield row


class _FakeTs:
    def __init__(self, iso):
        self._iso = iso

    def strftime(self, fmt):  # only "%Y-%m-%d" is used
        return self._iso


class _FakeTickerWithHistory(_FakeTicker):
    def history(self, period=None, interval=None):
        return _FakeHistory([
            {"date": "2026-05-0{}".format(i + 1), "open": 10 + i, "high": 11 + i,
             "low": 9 + i, "close": 10 + i, "volume": 1000 + i} for i in range(5)])


class _FakeYfHistory(_FakeYf):
    def Ticker(self, symbol):
        return _FakeTickerWithHistory(symbol)


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


def test_price_history_returns_ohlcv_rows_sorted_by_date():
    c = UsClient(cache_dir=tempfile.mkdtemp(), yf=_FakeYfHistory())
    rows = c.price_history("AAPL", months=1)
    assert rows[0]["date"] == "2026-05-01"
    assert rows[-1]["close"] == 14.0
    assert set(rows[0]) == {"date", "open", "high", "low", "close", "volume"}


def test_index_history_uses_sp500_close_series():
    c = UsClient(cache_dir=tempfile.mkdtemp(), yf=_FakeYfHistory())
    idx = c.index_history(months=1)
    assert idx[0]["date"] == "2026-05-01"
    assert "close" in idx[0] and len(idx[0]) == 2
