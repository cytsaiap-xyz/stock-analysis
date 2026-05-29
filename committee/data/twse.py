import json
import os
from datetime import date
from typing import Any, Dict, List, Optional

_BASE = "https://www.twse.com.tw"
_OPENAPI = "https://openapi.twse.com.tw/v1"
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


def to_int(raw: str) -> Optional[int]:
    raw = (raw or "").replace(",", "").strip()
    if raw in ("", "--", "null", "None"):
        return None
    try:
        return int(float(raw))
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

    def _fetch(self, url: str, params: Dict[str, str], cache_key: str) -> Any:
        path = os.path.join(self._cache_dir, cache_key + ".json")
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as fh:
                return json.load(fh)
        resp = self._session.get(url, params=params, headers=_HEADERS, timeout=20)
        resp.raise_for_status()
        body = resp.json()
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(body, fh, ensure_ascii=False)
        return body

    def _get_json(self, endpoint: str, params: Dict[str, str], cache_key: str) -> Dict[str, Any]:
        return self._fetch(_BASE + "/exchangeReport/" + endpoint, params, cache_key)

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

    def institutional_flows(self, stock_no: str, max_lookback: int = 7) -> Dict[str, Any]:
        """三大法人買賣超 (T86). Returns the latest trading day's net share figures."""
        from datetime import timedelta
        for delta in range(max_lookback):
            ymd = (self._today - timedelta(days=delta)).strftime("%Y%m%d")
            body = self._fetch(_BASE + "/fund/T86",
                               {"response": "json", "date": ymd, "selectType": "ALLBUT0999"},
                               "t86_" + ymd)
            if body.get("stat") != "OK" or not body.get("data"):
                continue
            for row in body["data"]:
                if row and row[0] == stock_no and len(row) >= 19:
                    return {"stock_no": stock_no, "name": row[1],
                            "foreign_net": to_int(row[4]),
                            "trust_net": to_int(row[10]),
                            "dealer_net": to_int(row[11]),
                            "total_net": to_int(row[18]),
                            "date": body.get("date")}
            raise ValueError("No T86 row for stock " + stock_no)
        raise ValueError("No T86 trading data in the last {} days".format(max_lookback))

    def monthly_revenue(self, stock_no: str) -> Dict[str, Any]:
        """上市公司月營收 (openapi t187ap05_P). Graceful fallback when the stock
        is not in the latest filing batch (coverage is not guaranteed per stock)."""
        body = self._fetch(_OPENAPI + "/opendata/t187ap05_P", {},
                           "monthly_revenue_" + self._today.strftime("%Y%m"))
        for item in body or []:
            if item.get("公司代號") == stock_no:
                return {"stock_no": stock_no, "available": True,
                        "name": item.get("公司名稱"),
                        "period": item.get("資料年月"),
                        "revenue": item.get("營業收入-當月營收"),
                        "yoy_pct": item.get("營業收入-去年同月增減(%)"),
                        "mom_pct": item.get("營業收入-上月比較增減(%)")}
        return {"stock_no": stock_no, "available": False,
                "note": "月營收資料暫無(該股未出現在最新批次)"}

    def index_history(self, months: int = 3) -> List[Dict[str, Any]]:
        """TAIEX daily closes (MI_5MINS_HIST), for relative-strength vs the market."""
        rows: List[Dict[str, Any]] = []
        for yyyymm in self._recent_months(months):
            key = "taiex_hist_" + yyyymm
            body = self._fetch(_BASE + "/indicesReport/MI_5MINS_HIST",
                               {"response": "json", "date": yyyymm + "01"}, key)
            for row in body.get("data") or []:
                rows.append({"date": roc_to_iso(row[0]), "close": to_float(row[4])})
        rows.sort(key=lambda r: r["date"])
        return rows

    def financials(self, stock_no: str) -> Dict[str, Any]:
        """Latest quarterly fundamentals from the listed income statement
        (t187ap06_L_ci) and balance sheet (t187ap07_L_ci) opendata batches.
        Figures are cumulative (year-to-date) for the reported quarter. Graceful
        fallback when the stock is not in the latest batch (coverage varies)."""
        ym = self._today.strftime("%Y%m")
        income = self._fetch(_OPENAPI + "/opendata/t187ap06_L_ci", {}, "income_stmt_" + ym)
        inc = next((r for r in (income or []) if r.get("公司代號") == stock_no), None)
        if inc is None:
            return {"stock_no": stock_no, "available": False,
                    "note": "財報資料暫無(該股未出現在最新批次)"}

        balance = self._fetch(_OPENAPI + "/opendata/t187ap07_L_ci", {},
                              "balance_sheet_" + ym)
        bal = next((r for r in (balance or []) if r.get("公司代號") == stock_no), {})

        revenue = to_float(inc.get("營業收入"))
        gross = (to_float(inc.get("營業毛利（毛損）淨額"))
                 or to_float(inc.get("營業毛利（毛損）")))
        operating = to_float(inc.get("營業利益（損失）"))
        net_income = to_float(inc.get("本期淨利（淨損）"))
        equity = to_float(bal.get("權益總額"))

        def _pct(num: Optional[float], den: Optional[float]) -> Optional[float]:
            if num is None or not den:
                return None
            return round(num / den * 100, 2)

        return {"stock_no": stock_no, "available": True,
                "name": inc.get("公司名稱"),
                "period": "{}Q{}".format(inc.get("年度"), inc.get("季別")),
                "revenue": revenue,
                "gross_margin_pct": _pct(gross, revenue),
                "operating_margin_pct": _pct(operating, revenue),
                "net_income": net_income,
                "roe_pct": _pct(net_income, equity),
                "eps": to_float(inc.get("基本每股盈餘（元）")),
                "book_value_per_share": to_float(bal.get("每股參考淨值"))}

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
