from committee.data.indicators import (
    compute_indicators,
    compute_oscillators,
    compute_relative_strength,
    compute_risk,
)


def _series(closes):
    return [{"date": "2026-05-{:02d}".format(i + 1),
             "open": c, "high": c, "low": c, "close": c, "volume": 1000 + i}
            for i, c in enumerate(closes)]


def test_moving_averages_and_trend_up():
    closes = list(range(1, 26))  # 1..25, strictly rising
    out = compute_indicators(_series(closes))
    assert out["last_close"] == 25.0
    assert round(out["ma5"], 2) == 23.0       # mean(21..25)
    assert round(out["ma20"], 2) == 15.5      # mean(6..25)
    assert out["ma60"] is None                # not enough data
    assert out["trend"] == "up"               # last_close > ma20


def test_trend_down_when_below_ma20():
    closes = list(range(25, 0, -1))  # 25..1, falling
    out = compute_indicators(_series(closes))
    assert out["trend"] == "down"


def test_empty_series_returns_nulls():
    out = compute_indicators([])
    assert out["last_close"] is None and out["ma5"] is None and out["trend"] == "flat"


def test_compute_risk_rising_series_has_no_drawdown():
    out = compute_risk(_series(list(range(1, 26))))
    assert out["samples"] == 25
    assert out["max_drawdown_pct"] == 0.0
    assert out["volatility_annual_pct"] is not None


def test_compute_risk_reports_max_drawdown():
    # closes 10,12,9,11 -> running max 10,12,12,12 -> worst (9-12)/12 = -25%
    out = compute_risk(_series([10, 12, 9, 11]))
    assert out["max_drawdown_pct"] == -25.0


def test_compute_risk_empty_series():
    assert compute_risk([]) == {"volatility_annual_pct": None,
                                "max_drawdown_pct": None, "samples": 0}


def test_oscillators_empty_series_returns_nulls():
    out = compute_oscillators([])
    assert out == {"rsi14": None, "kd_k": None, "kd_d": None,
                   "macd": None, "macd_signal": None, "macd_hist": None}


def test_oscillators_insufficient_data_returns_nulls():
    # 5 closes: too few for RSI(14), KD(9) or MACD(26).
    out = compute_oscillators(_series([10, 11, 12, 11, 10]))
    assert out["rsi14"] is None and out["kd_k"] is None and out["macd"] is None


def test_rsi_is_100_on_strictly_rising_series():
    out = compute_oscillators(_series(list(range(1, 26))))  # all gains, no losses
    assert out["rsi14"] == 100.0


def test_rsi_is_0_on_strictly_falling_series():
    out = compute_oscillators(_series(list(range(25, 0, -1))))  # all losses
    assert out["rsi14"] == 0.0


def test_kd_high_on_sustained_uptrend():
    out = compute_oscillators(_series(list(range(1, 26))))
    assert out["kd_k"] > 80 and out["kd_d"] > 80


def test_kd_low_on_sustained_downtrend():
    out = compute_oscillators(_series(list(range(25, 0, -1))))
    assert out["kd_k"] < 20 and out["kd_d"] < 20


def test_macd_positive_in_uptrend_and_has_signal_hist():
    out = compute_oscillators(_series(list(range(1, 41))))  # >= 26 points
    assert out["macd"] > 0
    assert out["macd_signal"] is not None and out["macd_hist"] is not None


def test_macd_none_when_fewer_than_26_points():
    out = compute_oscillators(_series(list(range(1, 21))))  # 20 points
    assert out["macd"] is None and out["macd_signal"] is None


def _closes(dates_closes):
    return [{"date": d, "close": c} for d, c in dates_closes]


def test_relative_strength_outperformance():
    stock = _closes([("2026-05-01", 100.0), ("2026-05-02", 120.0)])   # +20%
    index = _closes([("2026-05-01", 100.0), ("2026-05-02", 110.0)])   # +10%
    out = compute_relative_strength(stock, index)
    assert out["stock_return_pct"] == 20.0
    assert out["index_return_pct"] == 10.0
    assert out["excess_return_pct"] == 10.0   # outperformed the market


def test_relative_strength_underperformance_is_negative():
    stock = _closes([("2026-05-01", 100.0), ("2026-05-02", 105.0)])   # +5%
    index = _closes([("2026-05-01", 100.0), ("2026-05-02", 110.0)])   # +10%
    out = compute_relative_strength(stock, index)
    assert out["excess_return_pct"] == -5.0


def test_relative_strength_empty_series_returns_nulls():
    out = compute_relative_strength([], [])
    assert out["stock_return_pct"] is None and out["excess_return_pct"] is None


def test_relative_strength_beta_computed_when_enough_aligned_days():
    # stock daily return is exactly 2x the index's each day -> beta == 2.0
    idx = _closes([("d1", 100.0), ("d2", 110.0), ("d3", 104.5), ("d4", 125.4)])
    stk = _closes([("d1", 100.0), ("d2", 120.0), ("d3", 108.0), ("d4", 151.2)])
    out = compute_relative_strength(stk, idx)
    assert out["beta"] is not None and round(out["beta"], 1) == 2.0
