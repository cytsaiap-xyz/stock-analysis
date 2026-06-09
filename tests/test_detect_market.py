# tests/test_detect_market.py
import pytest

from committee.markets import detect_market


@pytest.mark.parametrize("symbol", ["2330", "0050", "00878", "6488", " 2330 ", "2330.TW", "2454.TWO"])
def test_taiwan_codes_detected_as_tw(symbol):
    assert detect_market(symbol) == "tw"


@pytest.mark.parametrize("symbol", ["AAPL", "aapl", "TSLA", "NVDA", "BRK.B", "BRK-B", "F", "GOOGL"])
def test_us_tickers_detected_as_us(symbol):
    assert detect_market(symbol) == "us"


def test_empty_symbol_raises():
    with pytest.raises(ValueError):
        detect_market("")
