"""Phase 3 spike: confirm shapes of NEW data sources before coding parsers.

Run manually: python scripts/spike_phase3.py
Covers:
  - MI_5MINS_HIST  發行量加權股價指數歷史 (TAIEX daily OHLC) -> relative strength vs market
  - t187ap06_L_ci  上市綜合損益表 (income statement)        -> gross margin, EPS
  - t187ap07_L_ci  上市資產負債表 (balance sheet)           -> equity -> ROE

These shapes are NOT trusted from docs; the parsers will be written to match
whatever this prints (cf. the BWIBBU_ALL 5-vs-7 column surprise in CLAUDE.md).
"""
import json

import requests

HEADERS = {"User-Agent": "Mozilla/5.0 (committee-phase3 spike)"}
OPENAPI = "https://openapi.twse.com.tw/v1"


def show_twse(name, url, params):
    try:
        r = requests.get(url, params=params, headers=HEADERS, timeout=20)
        print("=" * 70)
        print(name, "->", r.status_code, r.url)
        body = r.json()
        if isinstance(body, dict):
            print("keys:", list(body.keys()))
            print("stat:", body.get("stat"))
            print("fields:", body.get("fields"))
            rows = body.get("data") or []
            print("row count:", len(rows))
            print("first row:", rows[0] if rows else "(none)")
            print("last row:", rows[-1] if rows else "(none)")
        elif isinstance(body, list):
            print("list length:", len(body))
            if body:
                print("first item keys:", list(body[0].keys()))
                print("first item:", json.dumps(body[0], ensure_ascii=False)[:600])
    except Exception as exc:  # noqa
        print(name, "FAILED:", type(exc).__name__, exc)


def main():
    show_twse("MI_5MINS_HIST TAIEX (發行量加權股價指數歷史)",
              "https://www.twse.com.tw/indicesReport/MI_5MINS_HIST",
              {"response": "json", "date": "20260501"})
    show_twse("income statement t187ap06_L_ci (上市綜合損益表)",
              OPENAPI + "/opendata/t187ap06_L_ci", {})
    show_twse("balance sheet t187ap07_L_ci (上市資產負債表)",
              OPENAPI + "/opendata/t187ap07_L_ci", {})


if __name__ == "__main__":
    main()
