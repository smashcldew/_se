from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal


@dataclass(frozen=True)
class DailyBar:
    trade_date: date
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int
    change: Decimal | None = None


@dataclass(frozen=True)
class Quote:
    symbol: str
    name: str
    market: str
    close: Decimal
    volume: int
    change: Decimal | None
    change_percent: Decimal | None
    industry: str = "未分類"
