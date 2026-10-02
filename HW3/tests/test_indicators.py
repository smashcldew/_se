from datetime import date, timedelta
from decimal import Decimal

from stockfollower.indicators import kdj_series, moving_averages, simple_moving_average
from stockfollower.models import DailyBar


def bars(count: int) -> list[DailyBar]:
    return [DailyBar(date(2026, 1, 1) + timedelta(days=index), Decimal(index + 1), Decimal(index + 1), Decimal(index + 1), Decimal(index + 1), 1) for index in range(count)]


def test_simple_moving_average():
    assert simple_moving_average(bars(5), 5) == Decimal("3")


def test_insufficient_bars_returns_none():
    assert moving_averages(bars(4))[5] is None


def test_kdj_series():
    highs = [float(index + 10) for index in range(20)]
    lows = [float(index) for index in range(20)]
    closes = [float(index + 9) for index in range(20)]
    k_values, d_values, j_values = kdj_series(highs, lows, closes)
    assert k_values[8] is not None
    assert d_values[8] is not None
    assert j_values[8] is not None
    assert k_values[7] is None
    assert 0 <= k_values[8] <= 100
    assert 0 <= d_values[8] <= 100
