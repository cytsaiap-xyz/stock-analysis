# committee/data/us_market.py
"""US market data client: yfinance for market data, SEC EDGAR for financial
statements. Mirrors TwseClient's method shape and disk-cache pattern so the
committee tools and report work for either market. Never raises on missing
data — returns {"available": False, "note": ...}."""
import json
import os
from datetime import date
from typing import Any, Dict, List, Optional

_EDGAR = "https://data.sec.gov"
_EDGAR_TICKERS = "https://www.sec.gov/files/company_tickers.json"
# SEC requires a descriptive UA with contact info; requests without it are blocked.
_HEADERS = {"User-Agent": "tw-stock-analysis committee (contact: research@example.com)"}


def _f(v: Any) -> Optional[float]:
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _norm_yield(raw: Any) -> Optional[float]:
    """yfinance returns dividendYield as a fraction (0.0045) or percent (0.45)
    depending on version. Normalize to a percent to match TW's field meaning."""
    if raw is None:
        return None
    try:
        v = float(raw)
    except (TypeError, ValueError):
        return None
    return round(v * 100, 4) if v < 1 else round(v, 4)


class UsClient:
    def __init__(self, cache_dir: str = "cache", yf: Any = None,
                 session: Any = None, today: Optional[date] = None) -> None:
        self._cache_dir = cache_dir
        self._today = today or date.today()
        self._yf = yf  # injected in tests; lazily imported in production
        if session is not None:
            self._session = session
        else:
            import requests
            self._session = requests.Session()
        os.makedirs(self._cache_dir, exist_ok=True)

    def _yfinance(self) -> Any:
        if self._yf is None:
            import yfinance
            self._yf = yfinance
        return self._yf

    def _cache(self, key: str, build) -> Any:
        """Return cached JSON for key, else call build(), cache, and return it."""
        path = os.path.join(self._cache_dir, key + ".json")
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as fh:
                return json.load(fh)
        value = build()
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(value, fh, ensure_ascii=False, default=str)
        return value

    def valuation(self, stock_no: str) -> Dict[str, Any]:
        def build():
            info = self._yfinance().Ticker(stock_no).info or {}
            return {"stock_no": stock_no, "name": info.get("longName") or stock_no,
                    "pe": info.get("trailingPE"), "pb": info.get("priceToBook"),
                    "dividend_yield": _norm_yield(info.get("dividendYield"))}
        return self._cache("us_valuation_{}_{}".format(stock_no, self._today.strftime("%Y%m%d")), build)

    _PERIOD = {1: "1mo", 2: "3mo", 3: "3mo", 6: "6mo", 12: "1y"}

    def _history(self, symbol: str, months: int) -> List[Dict[str, Any]]:
        period = self._PERIOD.get(int(months), "6mo")
        df = self._yfinance().Ticker(symbol).history(period=period, interval="1d")
        rows: List[Dict[str, Any]] = []
        for r in df.itertuples():
            rows.append({"date": r.Index.strftime("%Y-%m-%d"),
                         "open": _f(r.Open), "high": _f(r.High), "low": _f(r.Low),
                         "close": _f(r.Close), "volume": int(r.Volume or 0)})
        rows.sort(key=lambda x: x["date"])
        return rows

    def price_history(self, stock_no: str, months: int = 3) -> List[Dict[str, Any]]:
        key = "us_stock_day_{}_{}_{}".format(stock_no, int(months), self._today.strftime("%Y%m%d"))
        return self._cache(key, lambda: self._history(stock_no, months))

    def index_history(self, months: int = 3) -> List[Dict[str, Any]]:
        key = "us_index_{}_{}".format(int(months), self._today.strftime("%Y%m%d"))
        rows = self._cache(key, lambda: self._history("^GSPC", months))
        return [{"date": r["date"], "close": r["close"]} for r in rows]

    def _quarterly_revenue(self, ticker: Any):
        """Return [(period_str, revenue, year_ago_revenue)], most-recent first.

        Tests inject `ticker.get_quarterly_revenue`; production reads
        yfinance's quarterly_income_stmt (Total Revenue row, newest column
        first) and pairs each quarter with the one 4 quarters earlier."""
        if hasattr(ticker, "get_quarterly_revenue"):
            return ticker.get_quarterly_revenue()
        stmt = getattr(ticker, "quarterly_income_stmt", None)
        if stmt is None or getattr(stmt, "empty", True):
            return []
        try:
            row = stmt.loc["Total Revenue"]
        except Exception:
            return []
        cols = list(row.index)  # newest first
        out = []
        for i, col in enumerate(cols):
            rev = _f(row[col])
            prior = _f(row[cols[i + 4]]) if i + 4 < len(cols) else None
            period = col.strftime("%YQ%q") if hasattr(col, "strftime") else str(col)
            out.append((period, rev, prior))
        return out

    def monthly_revenue(self, stock_no: str) -> Dict[str, Any]:
        def build():
            rows = self._quarterly_revenue(self._yfinance().Ticker(stock_no))
            if not rows:
                return {"stock_no": stock_no, "available": False,
                        "note": "Quarterly revenue data unavailable"}
            period, rev, prior = rows[0]
            yoy = round((rev - prior) / prior * 100, 4) if (rev is not None and prior) else None
            return {"stock_no": stock_no, "available": True, "period": period,
                    "revenue": rev, "yoy_pct": yoy}
        return self._cache("us_qrev_{}_{}".format(stock_no, self._today.strftime("%Y%m")), build)

    def institutional_flows(self, stock_no: str) -> Dict[str, Any]:
        def build():
            t = self._yfinance().Ticker(stock_no)
            info = t.info or {}
            pct = info.get("heldPercentInstitutions")
            holders = t.get_institutional_holders() or []
            top = [{"holder": h.get("Holder"), "pct": round(float(h.get("pctHeld")) * 100, 4)}
                   for h in holders if h.get("pctHeld") is not None][:5]
            if pct is None and not top:
                return {"stock_no": stock_no, "available": False,
                        "note": "Institutional ownership data unavailable"}
            return {"stock_no": stock_no, "available": True,
                    "name": info.get("longName") or stock_no,
                    "inst_ownership_pct": round(float(pct) * 100, 4) if pct is not None else None,
                    "top_holders": top}
        return self._cache("us_inst_{}_{}".format(stock_no, self._today.strftime("%Y%m%d")), build)

    def _cik(self, stock_no: str) -> Optional[str]:
        body = self._cache("us_cik_map", lambda: self._session.get(
            _EDGAR_TICKERS, headers=_HEADERS, timeout=20).json())
        for row in (body or {}).values():
            if str(row.get("ticker", "")).upper() == stock_no.upper():
                return "{:010d}".format(int(row["cik_str"]))
        return None

    def financials(self, stock_no: str) -> Dict[str, Any]:
        def build():
            cik = self._cik(stock_no)
            if cik is None:
                return {"stock_no": stock_no, "available": False,
                        "note": "Ticker not found in SEC EDGAR"}
            resp = self._session.get(
                _EDGAR + "/api/xbrl/companyfacts/CIK{}.json".format(cik),
                headers=_HEADERS, timeout=20)
            resp.raise_for_status()
            facts = (resp.json() or {}).get("facts", {}).get("us-gaap", {})

            def latest(tag, unit="USD"):
                series = facts.get(tag, {}).get("units", {}).get(unit, [])
                if not series:
                    return None, None
                row = sorted(series, key=lambda r: r.get("end", ""))[-1]
                return _f(row.get("val")), row

            revenue, rev_row = latest("Revenues")
            if revenue is None:
                revenue, rev_row = latest("RevenueFromContractWithCustomerExcludingAssessedTax")
            gross, _ = latest("GrossProfit")
            operating, _ = latest("OperatingIncomeLoss")
            net, _ = latest("NetIncomeLoss")
            equity, _ = latest("StockholdersEquity")
            eps, _ = latest("EarningsPerShareBasic", "USD/shares")
            if revenue is None and net is None:
                return {"stock_no": stock_no, "available": False,
                        "note": "No us-gaap financial facts available"}
            period = ""
            if rev_row:
                period = "{}{}".format(rev_row.get("fy", ""), rev_row.get("fp", ""))

            def pct(num, den):
                return round(num / den * 100, 2) if (num is not None and den) else None

            return {"stock_no": stock_no, "available": True,
                    "name": stock_no, "period": period, "revenue": revenue,
                    "gross_margin_pct": pct(gross, revenue),
                    "operating_margin_pct": pct(operating, revenue),
                    "net_income": net, "roe_pct": pct(net, equity), "eps": eps,
                    "book_value_per_share": None}
        return self._cache("us_fin_{}_{}".format(stock_no, self._today.strftime("%Y%m")), build)
