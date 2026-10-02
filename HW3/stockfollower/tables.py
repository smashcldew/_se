"""Shared leaderboard values and terminal column formatting."""

import unicodedata

from .models import Quote


def leaderboard_rows(quotes: list[Quote]) -> list[list[str]]:
    return [
        [str(rank), row.symbol, row.name, f"{row.close:,.2f}",
         "-" if row.change_percent is None else f"{row.change_percent:+.2f}%",
         f"{row.volume:,}", row.industry]
        for rank, row in enumerate(quotes, start=1)
    ]


def display_width(text: str) -> int:
    return sum(0 if unicodedata.combining(char) else
               2 if unicodedata.east_asian_width(char) in ("W", "F") else 1
               for char in text)


def format_table(headers: list[str], rows: list[list[str]]) -> str:
    widths = [max(display_width(row[column]) for row in [headers, *rows])
              for column in range(len(headers))]
    lines = []
    for row in [headers, *rows]:
        cells = []
        for column, value in enumerate(row):
            padding = " " * (widths[column] - display_width(value))
            cells.append(value + padding if column in (1, 2, 6) else padding + value)
        lines.append("  ".join(cells))
    return "\n".join(lines)
