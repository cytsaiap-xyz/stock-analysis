from typing import Any, Dict, List, Optional

import pandas as pd


def _ma(closes: "pd.Series", window: int) -> Optional[float]:
    if len(closes) < window:
        return None
    return float(closes.tail(window).mean())


def compute_indicators(ohlcv: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not ohlcv:
        return {"last_close": None, "ma5": None, "ma20": None, "ma60": None,
                "pct_change_period": None, "avg_volume": None, "trend": "flat"}

    df = pd.DataFrame(ohlcv).sort_values("date")
    closes = df["close"].astype(float).reset_index(drop=True)
    last_close = float(closes.iloc[-1])
    ma20 = _ma(closes, 20)

    if ma20 is None:
        trend = "flat"
    elif last_close > ma20:
        trend = "up"
    elif last_close < ma20:
        trend = "down"
    else:
        trend = "flat"

    first_close = float(closes.iloc[0])
    pct = None if first_close == 0 else round((last_close - first_close) / first_close * 100, 2)

    return {
        "last_close": last_close,
        "ma5": _ma(closes, 5),
        "ma20": ma20,
        "ma60": _ma(closes, 60),
        "pct_change_period": pct,
        "avg_volume": float(df["volume"].astype(float).mean()),
        "trend": trend,
    }
