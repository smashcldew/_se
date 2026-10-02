from __future__ import annotations

import tkinter as tk
from datetime import date, timedelta
from decimal import Decimal
from threading import Thread
from tkinter import messagebox, ttk

from .indicators import kdj_series, moving_averages
from .providers import DataProviderError, TwseProvider


def _money(value: Decimal | None) -> str:
    return "-" if value is None else f"{value:,.2f}"


def _chart_bars(bars: list, interval: str) -> list[tuple[date, float, float, float, float]]:  # type: ignore[type-arg]
    """Return OHLC bars, grouped to the selected calendar interval."""
    if interval == "Day":
        return [(bar.trade_date, float(bar.open), float(bar.high), float(bar.low), float(bar.close)) for bar in bars]

    grouped: dict[date, list] = {}
    for bar in bars:
        if interval == "Week":
            period = bar.trade_date - timedelta(days=bar.trade_date.weekday())
        elif interval == "Month":
            period = bar.trade_date.replace(day=1)
        else:
            period = bar.trade_date.replace(month=1, day=1)
        grouped.setdefault(period, []).append(bar)
    return [
        (period, float(items[0].open), max(float(item.high) for item in items), min(float(item.low) for item in items), float(items[-1].close))
        for period, items in grouped.items()
    ]


def _chart_month_starts(dates: list[date]) -> list[int]:
    if not dates:
        return []
    positions = [0]
    for index in range(1, len(dates)):
        if dates[index].month != dates[index - 1].month:
            positions.append(index)
    return positions


def _chart_year_starts(dates: list[date]) -> list[int]:
    if not dates:
        return []
    positions = [0]
    for index in range(1, len(dates)):
        if dates[index].year != dates[index - 1].year:
            positions.append(index)
    return positions


def _chart_day_ticks(dates: list[date]) -> tuple[list[int], list[str]]:
    """One tick per trading day, labeled with the day of month."""
    if not dates:
        return [], []
    positions = list(range(len(dates)))
    labels = [str(trade_date.day) for trade_date in dates]
    return positions, labels


class StockFollowerWindow:
    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title("StockFollower - Taiwan Stock Desktop")
        self.root.minsize(760, 650)
        self.provider = TwseProvider()
        self.symbol = tk.StringVar(value="2330")
        self.refresh = tk.BooleanVar(value=False)
        self.ranking = tk.StringVar(value="Volume")
        self.chart_interval = tk.StringVar(value="Day")
        self.history_months = tk.IntVar(value=3)
        self.status = tk.StringVar(value="Enter a stock symbol to get started.")
        self._build()

    def _build(self) -> None:
        frame = ttk.Frame(self.root, padding=16)
        frame.pack(fill=tk.BOTH, expand=True)

        controls = ttk.Frame(frame)
        controls.pack(fill=tk.X)
        ttk.Label(controls, text="Symbol:").pack(side=tk.LEFT)
        entry = ttk.Entry(controls, width=12, textvariable=self.symbol)
        entry.pack(side=tk.LEFT)
        entry.bind("<Return>", lambda _event: self.show_quote())
        ttk.Checkbutton(controls, text="Refresh cache", variable=self.refresh).pack(side=tk.LEFT, padx=(12, 16))
        ttk.Button(controls, text="Latest close", command=self.show_quote).pack(side=tk.LEFT, padx=3)
        ttk.Button(controls, text="History", command=self.show_history).pack(side=tk.LEFT, padx=3)
        ttk.Button(controls, text="Report", command=self.show_report).pack(side=tk.LEFT, padx=3)
        ttk.Label(controls, text="Leaderboard:").pack(side=tk.LEFT, padx=(12, 0))
        ttk.Combobox(
            controls, textvariable=self.ranking, values=("Volume", "Gainers", "Losers"), width=7, state="readonly"
        ).pack(side=tk.LEFT)
        ttk.Button(controls, text="Show leaderboard", command=self.show_leaderboard).pack(side=tk.LEFT, padx=3)

        chart_controls = ttk.Frame(frame)
        chart_controls.pack(fill=tk.X, pady=(8, 0))
        ttk.Label(chart_controls, text="Chart interval:").pack(side=tk.LEFT)
        ttk.Combobox(
            chart_controls, textvariable=self.chart_interval, values=("Day", "Week", "Month", "Year"), width=5, state="readonly"
        ).pack(side=tk.LEFT)
        ttk.Label(chart_controls, text="  Range:").pack(side=tk.LEFT)
        ttk.Spinbox(chart_controls, from_=1, to=24, width=4, textvariable=self.history_months).pack(side=tk.LEFT)
        ttk.Label(chart_controls, text="months").pack(side=tk.LEFT)
        ttk.Label(chart_controls, text="(Chart redraws when the interval changes.)").pack(side=tk.LEFT, padx=8)

        self.content = ttk.PanedWindow(frame, orient=tk.VERTICAL)
        self.content.pack(fill=tk.BOTH, expand=True, pady=(14, 8))
        self.output = tk.Text(self.content, wrap=tk.WORD, font=("Consolas", 11), state=tk.DISABLED, height=12)
        self.chart_frame = ttk.Frame(self.content)
        ttk.Label(
            self.chart_frame,
            text="Run a history query to display the embedded candlestick chart here.",
            anchor=tk.CENTER,
        ).pack(fill=tk.BOTH, expand=True)
        self.content.add(self.output, weight=1)
        self.content.add(self.chart_frame, weight=2)
        ttk.Label(frame, textvariable=self.status).pack(anchor=tk.W)
        entry.focus_set()

    def _symbol(self) -> str:
        symbol = self.symbol.get().strip()
        if not (symbol.isdigit() and len(symbol) == 4):
            raise ValueError("Stock symbol must be a 4-digit number, e.g. 2330.")
        return symbol

    def _run(self, work, on_success=None) -> None:  # type: ignore[no-untyped-def]
        self.status.set("Loading...")

        def runner() -> None:
            try:
                result = work()
            except (DataProviderError, ValueError) as exc:
                self.root.after(0, lambda: self._show_error(str(exc)))
            except Exception as exc:  # pragma: no cover - unexpected UI failure
                self.root.after(0, lambda: self._show_error(f"Unexpected error: {exc}"))
            else:
                callback = on_success or self._show_result
                self.root.after(0, lambda: callback(result))

        Thread(target=runner, daemon=True).start()

    def _show_result(self, text: str) -> None:
        self._show_text_output()
        self.output.configure(state=tk.NORMAL)
        self.output.delete("1.0", tk.END)
        self.output.insert(tk.END, text)
        self.output.configure(state=tk.DISABLED)
        self.status.set("Done.")

    def _show_text_output(self) -> None:
        if str(self.output) not in self.content.panes():
            self.content.insert(0, self.output, weight=1)

    def _hide_text_output(self) -> None:
        if str(self.output) in self.content.panes():
            self.content.forget(self.output)

    def _show_error(self, text: str) -> None:
        self.status.set("Request failed.")
        messagebox.showerror("StockFollower", text, parent=self.root)

    def show_quote(self) -> None:
        try:
            symbol = self._symbol()
        except ValueError as exc:
            self._show_error(str(exc))
            return
        refresh = self.refresh.get()

        def work() -> str:
            quotes = self.provider.latest_quotes(refresh)
            item = next((row for row in quotes if row.symbol == symbol), None)
            if item is None:
                raise DataProviderError(f"Listed stock {symbol} was not found.")
            averages = moving_averages(self.provider.history(symbol, months=3, refresh=refresh))
            pct = "-" if item.change_percent is None else f"{item.change_percent:+.2f}%"
            lines = [
                f"{item.symbol} {item.name} ({item.market})",
                f"Close: {_money(item.close)}",
                f"Change: {_money(item.change)}  Change %: {pct}",
                f"Volume: {item.volume:,} shares",
                "",
                "  ".join(f"MA{period}: {_money(value)}" for period, value in averages.items()),
            ]
            return "\n".join(lines)

        self._run(work)

    def show_history(self) -> None:
        try:
            symbol = self._symbol()
        except ValueError as exc:
            self._show_error(str(exc))
            return
        refresh = self.refresh.get()
        interval = self.chart_interval.get()
        months = self.history_months.get()
        if not 1 <= months <= 24:
            self._show_error("History range must be between 1 and 24 months.")
            return

        def work() -> tuple[str, list]:
            bars = self.provider.history(symbol, months=months, refresh=refresh)
            if not bars:
                raise DataProviderError("No historical price data is available.")
            rows = ["Date        Open    High    Low     Close       Volume"]
            rows.extend(
                f"{bar.trade_date:%Y-%m-%d}  {bar.open:>6}  {bar.high:>6}  {bar.low:>6}  {bar.close:>6}  {bar.volume:>12,}"
                for bar in bars[-20:]
            )
            rows.append("")
            rows.append("  ".join(f"MA{period}: {_money(value)}" for period, value in moving_averages(bars).items()))
            return "\n".join(rows), bars

        def show_history_result(result: tuple[str, list]) -> None:
            _, bars = result
            self._hide_text_output()
            self._show_history_chart(bars, symbol, interval)
            self.status.set("Done.")

        self._run(work, show_history_result)

    def _show_history_chart(self, bars: list, symbol: str, interval: str) -> None:  # type: ignore[type-arg]
        try:
            from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
            from matplotlib.figure import Figure
        except ImportError:
            self._show_error("Matplotlib is not installed. Run: python -m pip install -e .")
            return

        for child in self.chart_frame.winfo_children():
            child.destroy()
        figure = Figure(figsize=(8, 6), dpi=100)
        price_axis = figure.add_subplot(211)
        kdj_axis = figure.add_subplot(212, sharex=price_axis)
        ohlc = _chart_bars(bars, interval)
        dates = [item[0] for item in ohlc]
        highs = [item[2] for item in ohlc]
        lows = [item[3] for item in ohlc]
        closes = [item[4] for item in ohlc]
        # Use sequential positions so weekends and market holidays do not create empty gaps.
        x_values = list(range(len(ohlc)))
        for x_value, (_, opening, high, low, close) in zip(x_values, ohlc):
            color = "#d32f2f" if close >= opening else "#2e7d32"
            price_axis.vlines(x_value, low, high, color=color, linewidth=1)
            price_axis.bar(
                x_value,
                max(abs(close - opening), 0.01),
                bottom=min(opening, close),
                width=0.9,
                color=color,
                edgecolor=color,
                linewidth=0.7,
            )
        k_values, d_values, j_values = kdj_series(highs, lows, closes)
        for label, values, color in (("K", k_values, "#1565c0"), ("D", d_values, "#f9a825"), ("J", j_values, "#8e24aa")):
            kdj_axis.plot(
                x_values,
                values,
                color=color,
                linewidth=1.5,
                label=label,
            )
        price_axis.set_title(f"{symbol} History ({interval})")
        price_axis.set_ylabel("Price")
        kdj_axis.set_xlabel("Date")
        kdj_axis.set_ylabel("KDJ")
        valid_kdj = [value for series in (k_values, d_values, j_values) for value in series if value is not None]
        if valid_kdj:
            kdj_axis.set_ylim(min(0, min(valid_kdj)) - 5, max(100, max(valid_kdj)) + 5)
        else:
            kdj_axis.set_ylim(0, 100)
        kdj_axis.axhline(80, color="#bdbdbd", linewidth=0.8, linestyle="--")
        kdj_axis.axhline(20, color="#bdbdbd", linewidth=0.8, linestyle="--")
        price_axis.margins(x=0)
        price_axis.set_xlim(-0.5, len(ohlc) - 0.5)
        day_positions, day_labels = _chart_day_ticks(dates)
        month_positions = _chart_month_starts(dates)
        year_positions = _chart_year_starts(dates)
        price_axis.set_xticks(day_positions)
        price_axis.set_xticklabels([])
        price_axis.tick_params(axis="x", which="major", length=4, labelbottom=False)
        kdj_axis.set_xticks(day_positions)
        kdj_axis.set_xticklabels(day_labels, fontsize=7 if len(day_labels) > 40 else 8)
        if len(day_labels) > 40:
            for label in kdj_axis.get_xticklabels():
                label.set_rotation(90)
                label.set_ha("center")
        price_axis.grid(True, axis="y", alpha=0.3)
        kdj_axis.grid(True, axis="y", alpha=0.3)

        month_axis = kdj_axis.twiny()
        month_axis.set_xlim(kdj_axis.get_xlim())
        month_axis.set_frame_on(False)
        month_axis.xaxis.set_ticks_position("bottom")
        month_axis.xaxis.set_label_position("bottom")
        month_axis.spines["bottom"].set_position(("outward", 16))
        for spine in ("top", "left", "right"):
            month_axis.spines[spine].set_visible(False)
        month_axis.patch.set_alpha(0)
        month_axis.set_xticks(month_positions)
        month_axis.set_xticklabels([f"{dates[position].month:02d}" for position in month_positions])
        month_axis.tick_params(axis="x", which="major", length=8, pad=2)

        year_axis = kdj_axis.twiny()
        year_axis.set_xlim(kdj_axis.get_xlim())
        year_axis.set_frame_on(False)
        year_axis.xaxis.set_ticks_position("bottom")
        year_axis.xaxis.set_label_position("bottom")
        year_axis.spines["bottom"].set_position(("outward", 32))
        for spine in ("top", "left", "right"):
            year_axis.spines[spine].set_visible(False)
        year_axis.patch.set_alpha(0)
        year_axis.set_xticks(year_positions)
        year_axis.set_xticklabels([str(dates[position].year) for position in year_positions])
        year_axis.tick_params(axis="x", which="major", length=12, pad=2)

        figure.subplots_adjust(bottom=0.32 if len(day_labels) > 40 else 0.28, hspace=0.08)
        kdj_axis.legend(loc="upper left")
        canvas = FigureCanvasTkAgg(figure, master=self.chart_frame)
        canvas.draw()
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

    def show_report(self) -> None:
        try:
            symbol = self._symbol()
        except ValueError as exc:
            self._show_error(str(exc))
            return
        refresh = self.refresh.get()

        def work() -> str:
            quotes = self.provider.latest_quotes(refresh)
            item = next((row for row in quotes if row.symbol == symbol), None)
            if item is None:
                raise DataProviderError(f"Listed stock {symbol} was not found.")
            averages = moving_averages(self.provider.history(symbol, months=6, refresh=refresh))
            technical = "\n".join(
                f"- MA{period}: {_money(value)} ({'insufficient data' if value is None else 'close above MA' if item.close > value else 'close below MA'})"
                for period, value in averages.items()
            )
            pct = "-" if item.change_percent is None else f"{item.change_percent:+.2f}%"
            return (
                f"# {item.symbol} {item.name} Stock Report\n\n"
                f"Market: {item.market}\nClose: {_money(item.close)}\nDaily change %: {pct}\nVolume: {item.volume:,} shares\n\n"
                f"Technical\n{technical}\n\nNews Sentiment\n- No news data source is connected yet, so no sentiment summary is available.\n\n"
                "Disclaimer\n- This report summarizes public data and rule-based technical indicators only. It is not investment advice."
            )

        self._run(work)

    def show_leaderboard(self) -> None:
        refresh = self.refresh.get()
        ranking = self.ranking.get()

        def work() -> str:
            rows = self.provider.latest_quotes(refresh)
            if ranking == "Volume":
                rows.sort(key=lambda row: row.volume, reverse=True)
                title = "Volume"
            else:
                rows = [row for row in rows if row.change_percent is not None]
                rows.sort(key=lambda row: row.change_percent or Decimal("0"), reverse=ranking == "Gainers")
                title = ranking
            lines = [f"TWSE Top 20 by {title}", "Rank  Symbol  Name          Close       Change %        Volume"]
            for rank, row in enumerate(rows, start=1):
                pct = "-" if row.change_percent is None else f"{row.change_percent:+.2f}%"
                lines.append(f"{rank:>2}  {row.symbol}  {row.name:<10.10}  {row.close:>8}  {pct:>9}  {row.volume:>12,}")
                if rank == 20:
                    break
            return "\n".join(lines)

        self._run(work)

    def run(self) -> None:
        self.root.mainloop()


def launch() -> None:
    StockFollowerWindow().run()
