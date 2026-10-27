"""Persistent SQLite store for fetched quotes and daily OHLC bars.

The database lives outside the JSON market cache, so `clear_cache()` never
removes it: records accumulate across runs. Each operation opens its own
connection, which keeps writes safe from the GUI's background threads.
"""

from __future__ import annotations

import sqlite3
from datetime import date
from decimal import Decimal
from pathlib import Path

from .models import DailyBar, Quote

# Anchor the database under the project root (HW3) so it is the same file no
# matter which working directory the program is launched from.
DB_PATH = Path(__file__).resolve().parent.parent / "data" / "stockfollower.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS quotes (
    symbol TEXT NOT NULL,
    name TEXT,
    market TEXT,
    trade_date TEXT NOT NULL,
    close TEXT,
    change TEXT,
    change_percent TEXT,
    volume INTEGER,
    industry TEXT,
    PRIMARY KEY (symbol, trade_date)
);
CREATE TABLE IF NOT EXISTS daily_bars (
    symbol TEXT NOT NULL,
    trade_date TEXT NOT NULL,
    open TEXT,
    high TEXT,
    low TEXT,
    close TEXT,
    volume INTEGER,
    change TEXT,
    PRIMARY KEY (symbol, trade_date)
);
CREATE TABLE IF NOT EXISTS fetch_log (
    symbol TEXT PRIMARY KEY,
    last_fetched TEXT NOT NULL
);
"""


class StorageError(RuntimeError):
    pass


def _text(value: Decimal | None) -> str | None:
    return None if value is None else str(value)


def _decimal(value: str | None) -> Decimal | None:
    return None if value is None else Decimal(value)


class PriceStore:
    """Read and write stock prices in a local SQLite database."""

    def __init__(self, path: Path | str = DB_PATH) -> None:
        self.path = Path(path)
        with self._connect() as connection:
            connection.executescript(_SCHEMA)

    def _connect(self):  # type: ignore[no-untyped-def]
        """Yield a committed-and-closed connection for one operation."""
        from contextlib import contextmanager

        @contextmanager
        def opener():
            try:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                connection = sqlite3.connect(self.path)
            except (sqlite3.Error, OSError) as exc:
                raise StorageError(f"無法開啟資料庫：{exc}") from exc
            try:
                connection.row_factory = sqlite3.Row
                yield connection
                connection.commit()
            except sqlite3.Error as exc:
                connection.rollback()
                raise StorageError(f"資料庫操作失敗：{exc}") from exc
            finally:
                connection.close()

        return opener()

    def save_quote(self, quote: Quote, trade_date: date | None = None) -> None:
        self.save_quotes([quote], trade_date)

    def save_quotes(self, quotes: list[Quote], trade_date: date | None = None) -> None:
        stamp = (trade_date or date.today()).isoformat()
        rows = [
            (quote.symbol, quote.name, quote.market, stamp, _text(quote.close),
             _text(quote.change), _text(quote.change_percent), quote.volume, quote.industry)
            for quote in quotes
        ]
        if not rows:
            return
        with self._connect() as connection:
            connection.executemany(
                """
                INSERT INTO quotes (symbol, name, market, trade_date, close, change, change_percent, volume, industry)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(symbol, trade_date) DO UPDATE SET
                    name=excluded.name, market=excluded.market, close=excluded.close,
                    change=excluded.change, change_percent=excluded.change_percent,
                    volume=excluded.volume, industry=excluded.industry
                """,
                rows,
            )

    def save_bars(self, symbol: str, bars: list[DailyBar]) -> None:
        rows = [
            (symbol, bar.trade_date.isoformat(), _text(bar.open), _text(bar.high),
             _text(bar.low), _text(bar.close), bar.volume, _text(bar.change))
            for bar in bars
        ]
        if not rows:
            return
        with self._connect() as connection:
            connection.executemany(
                """
                INSERT INTO daily_bars (symbol, trade_date, open, high, low, close, volume, change)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(symbol, trade_date) DO UPDATE SET
                    open=excluded.open, high=excluded.high, low=excluded.low,
                    close=excluded.close, volume=excluded.volume, change=excluded.change
                """,
                rows,
            )

    def record_fetch(self, symbol: str, day: date) -> None:
        """Remember the calendar date this symbol was last fetched from the API."""
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO fetch_log (symbol, last_fetched) VALUES (?, ?) "
                "ON CONFLICT(symbol) DO UPDATE SET last_fetched=excluded.last_fetched",
                (symbol, day.isoformat()),
            )

    def last_fetch(self, symbol: str) -> str | None:
        """ISO date this symbol was last fetched from the API, or None."""
        with self._connect() as connection:
            row = connection.execute(
                "SELECT last_fetched FROM fetch_log WHERE symbol = ?", (symbol,)
            ).fetchone()
        return None if row is None else row["last_fetched"]

    def _bars_from_rows(self, rows) -> list[DailyBar]:  # type: ignore[no-untyped-def]
        return [
            DailyBar(date.fromisoformat(row["trade_date"]), _decimal(row["open"]),
                     _decimal(row["high"]), _decimal(row["low"]), _decimal(row["close"]),
                     row["volume"], _decimal(row["change"]))
            for row in rows
        ]

    def recent_prices(self, symbol: str, limit: int = 20) -> list[DailyBar]:
        """Stored daily bars for a symbol, most recent first."""
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT trade_date, open, high, low, close, volume, change "
                "FROM daily_bars WHERE symbol = ? ORDER BY trade_date DESC LIMIT ?",
                (symbol, limit),
            ).fetchall()
        return self._bars_from_rows(rows)

    def prices_since(self, symbol: str, start: date) -> list[DailyBar]:
        """Stored daily bars for a symbol on or after `start`, oldest first."""
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT trade_date, open, high, low, close, volume, change "
                "FROM daily_bars WHERE symbol = ? AND trade_date >= ? ORDER BY trade_date ASC",
                (symbol, start.isoformat()),
            ).fetchall()
        return self._bars_from_rows(rows)

    def latest_quote(self, symbol: str) -> Quote | None:
        """Most recently stored quote summary for a symbol, or None."""
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM quotes WHERE symbol = ? ORDER BY trade_date DESC LIMIT 1",
                (symbol,),
            ).fetchone()
        if row is None:
            return None
        return Quote(row["symbol"], row["name"], row["market"], _decimal(row["close"]),
                     row["volume"], _decimal(row["change"]), _decimal(row["change_percent"]),
                     row["industry"])

    def saved_quotes(self, trade_date: date | None = None) -> list[Quote]:
        """Stored quote summaries for a trading day (default: today)."""
        stamp = (trade_date or date.today()).isoformat()
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM quotes WHERE trade_date = ? ORDER BY symbol", (stamp,)
            ).fetchall()
        return [
            Quote(row["symbol"], row["name"], row["market"], _decimal(row["close"]),
                  row["volume"], _decimal(row["change"]), _decimal(row["change_percent"]),
                  row["industry"])
            for row in rows
        ]
