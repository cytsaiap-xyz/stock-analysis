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
