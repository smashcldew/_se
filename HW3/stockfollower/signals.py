from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Literal


@dataclass(frozen=True)
class Signal:
    date: date
    type: Literal["golden_cross", "death_cross"]


def detect_kdj_signals(
    dates: list[date],
    k_values: list[float | None],
    d_values: list[float | None],
) -> list[Signal]:
    """Detect crossings independently of chart rendering.

    Equality keeps the last nonzero direction, so touching and returning to
    the same side does not create a signal. Missing values reset that direction.
    """
    if not (len(dates) == len(k_values) == len(d_values)):
        raise ValueError("date, K, and D series must have the same length")
    signals = []
    previous_direction = 0
    for trade_date, k, d in zip(dates, k_values, d_values):
        if k is None or d is None:
            previous_direction = 0
            continue
        direction = (k > d) - (k < d)
        if direction == 0:
            continue
        if previous_direction and direction != previous_direction:
            signals.append(Signal(trade_date, "golden_cross" if direction > 0 else "death_cross"))
        previous_direction = direction
    return signals
