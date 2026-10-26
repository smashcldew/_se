"""Market-wide dashboard metrics derived from the TWSE full-market quotes.

These functions are pure (no Tk, no network) so they can be unit tested;
`gui.py` renders their output as KPI cards and an industry chart.
"""

from __future__ import annotations

from decimal import Decimal

from .models import Quote

# Taiwan's daily price limit is about ±10%; tick rounding lands just under it.
LIMIT_PERCENT = Decimal("9.9")


def market_breadth(quotes: list[Quote]) -> dict:
    """Advancers/decliners spread, limit hits, turnover and average change."""
    advancers = decliners = unchanged = limit_up = limit_down = 0
    total_volume = 0
    changes: list[Decimal] = []
    for quote in quotes:
        total_volume += quote.volume
        percent = quote.change_percent
        if percent is None:
            continue
        changes.append(percent)
        if percent > 0:
            advancers += 1
        elif percent < 0:
            decliners += 1
        else:
            unchanged += 1
        if percent >= LIMIT_PERCENT:
            limit_up += 1
        elif percent <= -LIMIT_PERCENT:
            limit_down += 1
    counted = len(changes)
    return {
        "total": len(quotes),
        "counted": counted,
        "advancers": advancers,
        "decliners": decliners,
        "unchanged": unchanged,
        "limit_up": limit_up,
        "limit_down": limit_down,
        "total_volume": total_volume,
        "avg_change_percent": (sum(changes) / counted) if counted else None,
        "advance_decline_ratio": (Decimal(advancers) / Decimal(decliners)) if decliners else None,
    }


def industry_changes(quotes: list[Quote]) -> list[tuple[str, Decimal, int]]:
    """Per-industry average change percent and sample size, strongest first."""
    buckets: dict[str, list[Decimal]] = {}
    for quote in quotes:
        if quote.change_percent is None:
            continue
        buckets.setdefault(quote.industry, []).append(quote.change_percent)
    rows = [(name, sum(values) / len(values), len(values)) for name, values in buckets.items()]
    rows.sort(key=lambda row: row[1], reverse=True)
    return rows
