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


class _FakeTickerHolders(_FakeTicker):
    def __init__(self, symbol):
        super().__init__(symbol)
        self.info = {"longName": "Apple Inc.", "heldPercentInstitutions": 0.612}

    def get_institutional_holders(self):
        return [{"Holder": "Vanguard", "pctHeld": 0.084},
                {"Holder": "BlackRock", "pctHeld": 0.066}]


class _FakeYfHolders(_FakeYf):
    def Ticker(self, symbol):
        return _FakeTickerHolders(symbol)


def test_institutional_flows_returns_ownership_and_top_holders():
    c = UsClient(cache_dir=tempfile.mkdtemp(), yf=_FakeYfHolders())
    out = c.institutional_flows("AAPL")
    assert out["available"] is True
    assert abs(out["inst_ownership_pct"] - 61.2) < 1e-9
    assert out["top_holders"][0] == {"holder": "Vanguard", "pct": 8.4}


def test_institutional_flows_missing_data_is_graceful():
    class _Empty(_FakeYf):
        def Ticker(self, symbol):
            t = _FakeTicker(symbol)
            t.info = {}
            t.get_institutional_holders = lambda: None
            return t
    c = UsClient(cache_dir=tempfile.mkdtemp(), yf=_Empty())
    out = c.institutional_flows("AAPL")
    assert out["available"] is False


class _FakeTickerRevenue(_FakeTicker):
    def get_quarterly_revenue(self):
        # most-recent first: [(period, revenue, year-ago revenue)]
        return [("2026Q1", 95_000_000_000.0, 81_000_000_000.0)]


class _FakeYfRevenue(_FakeYf):
    def Ticker(self, symbol):
        return _FakeTickerRevenue(symbol)


def test_monthly_revenue_returns_latest_quarter_and_yoy():
    c = UsClient(cache_dir=tempfile.mkdtemp(), yf=_FakeYfRevenue())
    out = c.monthly_revenue("AAPL")
    assert out["available"] is True
    assert out["period"] == "2026Q1"
    assert out["revenue"] == 95_000_000_000.0
    # (95 - 81) / 81 * 100 = 17.28%
    assert abs(out["yoy_pct"] - 17.2840) < 1e-3


def test_monthly_revenue_missing_is_graceful():
    class _Empty(_FakeYf):
        def Ticker(self, symbol):
            t = _FakeTicker(symbol)
            t.get_quarterly_revenue = lambda: []
            return t
    out = UsClient(cache_dir=tempfile.mkdtemp(), yf=_Empty()).monthly_revenue("AAPL")
    assert out["available"] is False


class _FakeEdgarSession:
    """Returns canned JSON for the two EDGAR URLs UsClient calls."""
    def __init__(self):
        self.tickers = {"0": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."}}
        self.facts = {
            "entityName": "Apple Inc.",
            "facts": {"us-gaap": {
                "Revenues": {"units": {"USD": [
                    {"end": "2026-03-31", "val": 95000000000, "form": "10-Q", "fp": "Q1", "fy": 2026}]}},
                "GrossProfit": {"units": {"USD": [
                    {"end": "2026-03-31", "val": 42000000000, "form": "10-Q", "fp": "Q1", "fy": 2026}]}},
                "OperatingIncomeLoss": {"units": {"USD": [
                    {"end": "2026-03-31", "val": 30000000000, "form": "10-Q", "fp": "Q1", "fy": 2026}]}},
                "NetIncomeLoss": {"units": {"USD": [
                    {"end": "2026-03-31", "val": 24000000000, "form": "10-Q", "fp": "Q1", "fy": 2026}]}},
                "StockholdersEquity": {"units": {"USD": [
                    {"end": "2026-03-31", "val": 80000000000, "form": "10-Q", "fp": "Q1", "fy": 2026}]}},
                "EarningsPerShareBasic": {"units": {"USD/shares": [
                    {"end": "2026-03-31", "val": 1.5, "form": "10-Q", "fp": "Q1", "fy": 2026}]}},
            }},
        }

    def get(self, url, headers=None, timeout=None):
        body = self.tickers if "company_tickers" in url else self.facts
        return _FakeResp(body)


class _FakeResp:
    def __init__(self, body):
        self._body = body

    def raise_for_status(self):
        pass

    def json(self):
        return self._body


def test_financials_from_edgar_computes_margins_and_roe():
    c = UsClient(cache_dir=tempfile.mkdtemp(), yf=_FakeYf(), session=_FakeEdgarSession())
    out = c.financials("AAPL")
    assert out["available"] is True
    assert out["revenue"] == 95000000000
    assert abs(out["gross_margin_pct"] - 44.21) < 0.1     # 42/95
    assert abs(out["operating_margin_pct"] - 31.58) < 0.1  # 30/95
    assert abs(out["roe_pct"] - 30.0) < 0.1                # 24/80
    assert out["eps"] == 1.5


def test_financials_unknown_ticker_is_graceful():
    c = UsClient(cache_dir=tempfile.mkdtemp(), yf=_FakeYf(), session=_FakeEdgarSession())
    out = c.financials("ZZZZ")
    assert out["available"] is False


# --- Regression tests for production shapes surfaced by live data ---

def test_institutional_flows_handles_dataframe_from_real_yfinance():
    """Production yfinance returns get_institutional_holders() as a DataFrame
    (not a list); pct/ownership must still parse without a truth-value error."""
    import pandas as pd

    class _DFTicker(_FakeTicker):
        def __init__(self, symbol):
            super().__init__(symbol)
            self.info = {"longName": "Apple Inc.", "heldPercentInstitutions": 0.658}

        def get_institutional_holders(self):
            return pd.DataFrame([
                {"Holder": "Blackrock Inc.", "pctHeld": 0.0779},
                {"Holder": "Vanguard", "pctHeld": 0.0649}])

    class _DFYf(_FakeYf):
        def Ticker(self, symbol):
            return _DFTicker(symbol)

    out = UsClient(cache_dir=tempfile.mkdtemp(), yf=_DFYf()).institutional_flows("AAPL")
    assert out["available"] is True
    assert abs(out["inst_ownership_pct"] - 65.8) < 1e-6
    assert out["top_holders"][0] == {"holder": "Blackrock Inc.", "pct": 7.79}


def test_valuation_passes_through_modern_percent_yield():
    """yfinance 1.x returns dividendYield already as a percent (0.36 -> 0.36%),
    so a sub-1 value that isn't tiny must NOT be multiplied by 100."""
    class _PctTicker(_FakeTicker):
        def __init__(self, symbol):
            super().__init__(symbol)
            self.info = {"longName": "Apple Inc.", "trailingPE": 35.0,
                         "priceToBook": 40.0, "dividendYield": 0.36}

    class _PctYf(_FakeYf):
        def Ticker(self, symbol):
            return _PctTicker(symbol)

    out = UsClient(cache_dir=tempfile.mkdtemp(), yf=_PctYf()).valuation("AAPL")
    assert out["dividend_yield"] == 0.36


class _FakeEdgarStaleRevenue:
    """EDGAR session where the legacy 'Revenues' tag is years stale (2018) and
    current figures live under 'RevenueFromContractWithCustomerExcludingAssessedTax'
    (the real Apple situation). financials() must pick the newest revenue."""
    def __init__(self):
        self.tickers = {"0": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."}}
        span = {"start": "2025-12-28", "end": "2026-03-28", "form": "10-Q", "fp": "Q2", "fy": 2026}
        old = {"start": "2018-07-01", "end": "2018-09-29", "form": "10-K", "fp": "FY", "fy": 2018}
        self.facts = {"entityName": "Apple Inc.", "facts": {"us-gaap": {
            "Revenues": {"units": {"USD": [dict(old, val=62900000000)]}},
            "RevenueFromContractWithCustomerExcludingAssessedTax": {"units": {"USD": [
                dict(span, val=111184000000)]}},
            "GrossProfit": {"units": {"USD": [dict(span, val=54781000000)]}},
            "OperatingIncomeLoss": {"units": {"USD": [dict(span, val=35885000000)]}},
            "NetIncomeLoss": {"units": {"USD": [dict(span, val=29578000000)]}},
            "StockholdersEquity": {"units": {"USD": [{"end": "2026-03-28", "val": 66000000000,
                                                      "form": "10-Q", "fp": "Q2", "fy": 2026}]}},
            "EarningsPerShareBasic": {"units": {"USD/shares": [dict(span, val=1.97)]}},
        }}}

    def get(self, url, headers=None, timeout=None):
        return _FakeResp(self.tickers if "company_tickers" in url else self.facts)


def test_financials_picks_newest_revenue_tag_not_stale_legacy():
    c = UsClient(cache_dir=tempfile.mkdtemp(), yf=_FakeYf(), session=_FakeEdgarStaleRevenue())
    out = c.financials("AAPL")
    assert out["available"] is True
    assert out["revenue"] == 111184000000          # 2026 Q2, not stale 2018 62.9B
    assert out["period"] == "2026Q2"
    assert out["name"] == "Apple Inc."
    assert abs(out["gross_margin_pct"] - 49.27) < 0.1   # 54.781/111.184
    assert abs(out["operating_margin_pct"] - 32.28) < 0.1
