"""Shared leaderboard row values for the desktop table."""

from .models import Quote


def leaderboard_rows(quotes: list[Quote]) -> list[list[str]]:
    return [
        [str(rank), row.symbol, row.name, f"{row.close:,.2f}",
         "-" if row.change_percent is None else f"{row.change_percent:+.2f}%",
         f"{row.volume:,}", row.industry]
        for rank, row in enumerate(quotes, start=1)
    ]
