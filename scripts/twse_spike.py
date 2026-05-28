"""One-off: fetch real TWSE endpoints and print their JSON shape.
Run manually: python scripts/twse_spike.py
TWSE endpoints (documented shapes the parsers assume):
  STOCK_DAY : data rows = [ROC date, volume, turnover, open, high, low, close, change, txns]
  BWIBBU_ALL: data rows = [code, name, dividend_yield, dividend_year, pe, pb, fin_period]
"""
import requests

HEADERS = {"User-Agent": "Mozilla/5.0 (committee-mvp spike)"}


def show(name, url, params):
    r = requests.get(url, params=params, headers=HEADERS, timeout=20)
    print("=" * 60)
    print(name, "->", r.status_code, r.url)
    body = r.json()
    if isinstance(body, dict):
        print("keys:", list(body.keys()))
        print("fields:", body.get("fields"))
        rows = body.get("data") or []
        print("first row:", rows[0] if rows else "(none)")
    else:
        print("first item:", body[0] if body else "(none)")


def main():
    show(
        "STOCK_DAY 2330",
        "https://www.twse.com.tw/exchangeReport/STOCK_DAY",
        {"response": "json", "date": "20260501", "stockNo": "2330"},
    )
    show(
        "BWIBBU_ALL",
        "https://www.twse.com.tw/exchangeReport/BWIBBU_ALL",
        {"response": "json"},
    )


if __name__ == "__main__":
    main()
