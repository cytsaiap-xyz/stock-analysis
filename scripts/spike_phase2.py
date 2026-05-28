"""Phase 2 spike: confirm the shapes of the new data sources before coding.

Run manually: python scripts/spike_phase2.py
Covers:
  - T86         三大法人買賣超日報 (institutional flows)   -> www.twse.com.tw/fund/T86
  - monthly rev 上市公司每月營收     (fundamental)         -> openapi.twse.com.tw opendata
  - ddgs news   DuckDuckGo search    (news/sentiment)
"""
import json

import requests

HEADERS = {"User-Agent": "Mozilla/5.0 (committee-phase2 spike)"}


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
        elif isinstance(body, list):
            print("list length:", len(body))
            if body:
                print("first item keys:", list(body[0].keys()))
                print("first item:", json.dumps(body[0], ensure_ascii=False)[:400])
    except Exception as exc:  # noqa
        print(name, "FAILED:", type(exc).__name__, exc)


def show_news():
    print("=" * 70)
    print("ddgs news: 台積電 2330")
    try:
        from ddgs import DDGS
        with DDGS() as d:
            hits = list(d.text("台積電 2330 新聞", max_results=3))
        print("hits:", len(hits))
        for h in hits:
            print("  keys:", list(h.keys()))
            print("  ", json.dumps(h, ensure_ascii=False)[:200])
            break
    except Exception as exc:  # noqa
        print("ddgs FAILED:", type(exc).__name__, exc)


def main():
    show_twse("T86 institutional (ALLBUT0999)",
              "https://www.twse.com.tw/fund/T86",
              {"response": "json", "date": "20260504", "selectType": "ALLBUT0999"})
    show_twse("monthly revenue t187ap05_P (上市)",
              "https://openapi.twse.com.tw/v1/opendata/t187ap05_P", {})
    show_news()


if __name__ == "__main__":
    main()
