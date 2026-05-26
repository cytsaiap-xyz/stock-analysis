import json
import os
from datetime import date
from typing import Any, Dict, List, Optional

_BASE = "https://www.twse.com.tw"
_HEADERS = {"User-Agent": "Mozilla/5.0 (committee-mvp)"}


def roc_to_iso(roc: str) -> str:
    """'115/05/02' (ROC year) -> '2026-05-02'."""
    y, m, d = roc.split("/")
    return "{:04d}-{}-{}".format(int(y) + 1911, m, d)


def to_float(raw: str) -> Optional[float]:
    raw = (raw or "").replace(",", "").replace("+", "").strip()
    if raw in ("", "--", "X0.00", "null", "None"):
        return None
    try:
        return float(raw)
    except ValueError:
        return None


class TwseClient:
    def __init__(self, cache_dir: str = "cache", session: Any = None,
                 today: Optional[date] = None) -> None:
        self._cache_dir = cache_dir
        self._today = today or date.today()
        if session is not None:
            self._session = session
        else:
            import requests
            self._session = requests.Session()
        os.makedirs(self._cache_dir, exist_ok=True)

    def _get_json(self, endpoint: str, params: Dict[str, str], cache_key: str) -> Dict[str, Any]:
        path = os.path.join(self._cache_dir, cache_key + ".json")
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as fh:
                return json.load(fh)
        url = _BASE + "/exchangeReport/" + endpoint
        resp = self._session.get(url, params=params, headers=_HEADERS, timeout=20)
        resp.raise_for_status()
        body = resp.json()
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(body, fh, ensure_ascii=False)
        return body

    def valuation(self, stock_no: str) -> Dict[str, Any]:
        key = "bwibbu_all_" + self._today.strftime("%Y%m%d")
        body = self._get_json("BWIBBU_ALL", {"response": "json"}, key)
        for row in body.get("data") or []:
            if row and row[0] == stock_no:
                return {"stock_no": stock_no, "name": row[1],
                        "pe": to_float(row[2]), "dividend_yield": to_float(row[3]),
                        "pb": to_float(row[4])}
        raise ValueError("No valuation row for stock " + stock_no)

    def price_history(self, stock_no: str, months: int = 3) -> List[Dict[str, Any]]:
        rows: List[Dict[str, Any]] = []
        for yyyymm in self._recent_months(months):
            key = "stock_day_{}_{}".format(stock_no, yyyymm)
            body = self._get_json(
                "STOCK_DAY",
                {"response": "json", "date": yyyymm + "01", "stockNo": stock_no},
                key,
            )
            for row in body.get("data") or []:
                rows.append({
                    "date": roc_to_iso(row[0]),
                    "open": to_float(row[3]), "high": to_float(row[4]),
                    "low": to_float(row[5]), "close": to_float(row[6]),
                    "volume": int(float((row[1] or "0").replace(",", ""))),
                })
        rows.sort(key=lambda r: r["date"])
        return rows

    def _recent_months(self, months: int) -> List[str]:
        out: List[str] = []
        y, m = self._today.year, self._today.month
        for _ in range(months):
            out.append("{:04d}{:02d}".format(y, m))
            m -= 1
            if m == 0:
                m = 12
                y -= 1
        return list(reversed(out))
