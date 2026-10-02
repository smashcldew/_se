from __future__ import annotations

from collections.abc import Iterable
from decimal import Decimal

from .models import DailyBar


def simple_moving_average(bars: Iterable[DailyBar], period: int) -> Decimal | None:
    """計算最後 `period` 根日線的簡單移動平均。"""
    if period <= 0:
        raise ValueError("period 必須大於 0")
    recent = list(bars)[-period:]
    if len(recent) < period:
        return None
    return sum((bar.close for bar in recent), Decimal("0")) / Decimal(period)


def moving_averages(bars: Iterable[DailyBar], periods: tuple[int, ...] = (5, 10, 20, 60)) -> dict[int, Decimal | None]:
    values = list(bars)
    return {period: simple_moving_average(values, period) for period in periods}


def kdj_series(
    highs: list[float],
    lows: list[float],
    closes: list[float],
    period: int = 9,
) -> tuple[list[float | None], list[float | None], list[float | None]]:
    """Return K, D, and J lines using the standard RSV smoothing (9, 3, 3)."""
    if period <= 0:
        raise ValueError("period must be greater than 0")
    if not (len(highs) == len(lows) == len(closes)):
        raise ValueError("high, low, and close series must have the same length")

    k_values: list[float | None] = [None] * len(closes)
    d_values: list[float | None] = [None] * len(closes)
    j_values: list[float | None] = [None] * len(closes)

    k = 50.0
    d = 50.0
    for index in range(len(closes)):
        if index + 1 < period:
            continue
        window_high = max(highs[index + 1 - period : index + 1])
        window_low = min(lows[index + 1 - period : index + 1])
        if window_high == window_low:
            rsv = 50.0
        else:
            rsv = (closes[index] - window_low) / (window_high - window_low) * 100
        k = k * 2 / 3 + rsv / 3
        d = d * 2 / 3 + k / 3
        j = 3 * k - 2 * d
        k_values[index] = k
        d_values[index] = d
        j_values[index] = j

    return k_values, d_values, j_values
