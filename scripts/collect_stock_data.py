"""Deterministic one-shot collector: pull every analysis aspect for a Taiwan
stock from the committee data layer and dump one JSON blob to stdout.

No LLM, no network beyond TWSE/DDGS. Used to feed real data into the
multi-aspect analysis workflow (committee data layer is the source of truth).

Usage:
    python scripts/collect_stock_data.py 2330 [months]
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    sys.stdout.reconfigure(encoding="utf-8")  # avoid cp950 mangling on Windows
except Exception:
    pass

from committee.markets import detect_market, get_profile
from committee.data.indicators import (
    compute_indicators,
    compute_oscillators,
    compute_relative_strength,
    compute_risk,
)
from committee.data.news import search_news


def safe(fn):
    try:
        return fn()
    except Exception as e:  # per-aspect failure must not abort the whole run
        return {"error": "{}: {}".format(type(e).__name__, e)}


def main():
    stock = sys.argv[1] if len(sys.argv) > 1 else "2330"
    months = int(sys.argv[2]) if len(sys.argv) > 2 else 6

    client = get_profile(detect_market(stock)).client
    out = {"stock_no": stock, "months": months, "market": detect_market(stock)}

    prices = safe(lambda: client.price_history(stock, months=months))
    index = safe(lambda: client.index_history(months=months))
    have_prices = isinstance(prices, list) and len(prices) > 0
    have_index = isinstance(index, list) and len(index) > 0

    out["valuation"] = safe(lambda: client.valuation(stock))
    name = out["valuation"].get("name") if isinstance(out["valuation"], dict) else None
    out["company_name"] = name or ""

    out["technical"] = (
        safe(lambda: {**compute_indicators(prices), **compute_oscillators(prices)})
        if have_prices else {"error": "price history unavailable"}
    )
    out["risk"] = (
        safe(lambda: compute_risk(prices))
        if have_prices else {"error": "price history unavailable"}
    )
    out["relative_strength"] = (
        safe(lambda: compute_relative_strength(prices, index))
        if have_prices and have_index else {"error": "price or index history unavailable"}
    )
    out["institutional_flows"] = safe(lambda: client.institutional_flows(stock))
    out["monthly_revenue"] = safe(lambda: client.monthly_revenue(stock))
    out["financials"] = safe(lambda: client.financials(stock))
    out["news"] = safe(lambda: search_news("{} {}".format(out["company_name"], stock).strip()))

    if have_prices:
        out["price_points"] = len(prices)
        out["price_tail"] = prices[-12:]

    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
