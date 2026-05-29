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


_EMPTY_OSC = {"rsi14": None, "kd_k": None, "kd_d": None,
              "macd": None, "macd_signal": None, "macd_hist": None}


def _rsi(closes: "pd.Series", period: int = 14) -> Optional[float]:
    deltas = closes.diff().dropna()
    if len(deltas) < period:
        return None
    gains = deltas.clip(lower=0)
    losses = -deltas.clip(upper=0)
    avg_gain = float(gains.ewm(alpha=1 / period, adjust=False).mean().iloc[-1])
    avg_loss = float(losses.ewm(alpha=1 / period, adjust=False).mean().iloc[-1])
    if avg_gain == 0 and avg_loss == 0:
        return None              # flat series — no momentum to measure
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return round(100 - 100 / (1 + rs), 2)


def _kd(df: "pd.DataFrame", period: int = 9):
    if len(df) < period:
        return None, None
    low_min = df["low"].astype(float).rolling(period).min()
    high_max = df["high"].astype(float).rolling(period).max()
    span = (high_max - low_min)
    rsv = ((df["close"].astype(float) - low_min) / span * 100).where(span != 0, 50.0)
    k, d = 50.0, 50.0
    for value in rsv.dropna():
        k = 2 / 3 * k + 1 / 3 * float(value)
        d = 2 / 3 * d + 1 / 3 * k
    return round(k, 2), round(d, 2)


def _macd(closes: "pd.Series"):
    if len(closes) < 26:
        return None, None, None
    ema12 = closes.ewm(span=12, adjust=False).mean()
    ema26 = closes.ewm(span=26, adjust=False).mean()
    macd = ema12 - ema26
    signal = macd.ewm(span=9, adjust=False).mean()
    hist = macd - signal
    return (round(float(macd.iloc[-1]), 2),
            round(float(signal.iloc[-1]), 2),
            round(float(hist.iloc[-1]), 2))


def compute_oscillators(ohlcv: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Momentum oscillators: RSI(14), KD(9), MACD(12/26/9) from daily OHLC.
    Each is None when there is not enough data to compute it."""
    if not ohlcv:
        return dict(_EMPTY_OSC)

    df = pd.DataFrame(ohlcv).sort_values("date").reset_index(drop=True)
    closes = df["close"].astype(float).reset_index(drop=True)
    k, d = _kd(df)
    macd, signal, hist = _macd(closes)
    return {"rsi14": _rsi(closes), "kd_k": k, "kd_d": d,
            "macd": macd, "macd_signal": signal, "macd_hist": hist}


def _period_return_pct(df: "pd.DataFrame") -> Optional[float]:
    closes = df["close"].astype(float)
    first, last = float(closes.iloc[0]), float(closes.iloc[-1])
    return None if first == 0 else round((last - first) / first * 100, 2)


def compute_relative_strength(stock_ohlcv: List[Dict[str, Any]],
                              index_ohlcv: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Stock performance relative to the market index: period excess return and beta.

    excess_return_pct > 0 means the stock outperformed the index over the window.
    beta needs >= 3 days that exist in BOTH series; otherwise it is None.
    """
    nulls = {"stock_return_pct": None, "index_return_pct": None,
             "excess_return_pct": None, "beta": None, "samples": 0}
    if not stock_ohlcv or not index_ohlcv:
        return nulls

    stock = pd.DataFrame(stock_ohlcv).sort_values("date").reset_index(drop=True)
    index = pd.DataFrame(index_ohlcv).sort_values("date").reset_index(drop=True)
    stock_ret = _period_return_pct(stock)
    index_ret = _period_return_pct(index)
    excess = (None if stock_ret is None or index_ret is None
              else round(stock_ret - index_ret, 2))

    merged = stock[["date", "close"]].merge(index[["date", "close"]], on="date",
                                            suffixes=("_s", "_i"))
    beta = None
    if len(merged) >= 3:
        ret_s = merged["close_s"].astype(float).pct_change().dropna()
        ret_i = merged["close_i"].astype(float).pct_change().dropna()
        var_i = float(ret_i.var())
        if var_i > 0:
            beta = round(float(ret_s.cov(ret_i)) / var_i, 2)

    return {"stock_return_pct": stock_ret, "index_return_pct": index_ret,
            "excess_return_pct": excess, "beta": beta, "samples": int(len(merged))}


def compute_risk(ohlcv: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Annualized volatility and maximum drawdown from a daily close series."""
    if not ohlcv:
        return {"volatility_annual_pct": None, "max_drawdown_pct": None, "samples": 0}

    df = pd.DataFrame(ohlcv).sort_values("date")
    closes = df["close"].astype(float).reset_index(drop=True)

    returns = closes.pct_change().dropna()
    vol = float(returns.std() * (252 ** 0.5) * 100) if len(returns) >= 2 else None

    running_max = closes.cummax()
    drawdown = (closes - running_max) / running_max
    mdd = float(drawdown.min() * 100) if len(closes) else None

    return {
        "volatility_annual_pct": round(vol, 2) if vol is not None else None,
        "max_drawdown_pct": round(mdd, 2) if mdd is not None else None,
        "samples": int(len(closes)),
    }
