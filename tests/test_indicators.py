from committee.data.indicators import compute_indicators, compute_risk


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
