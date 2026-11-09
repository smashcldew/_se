from __future__ import annotations

import queue
import tkinter as tk
from datetime import date, timedelta
from decimal import Decimal
from threading import Thread
from tkinter import messagebox, ttk

from .indicators import kdj_series, moving_averages
from .signals import Signal, detect_kdj_signals
from .providers import DataProviderError, StockProvider, clear_cache
from .dashboard import industry_changes, market_breadth
from .storage import PriceStore, StorageError
from .tables import leaderboard_rows
from .industries import ALL_INDUSTRIES, INDUSTRIES, UNKNOWN_INDUSTRY


def _money(value: Decimal | None) -> str:
    return "-" if value is None else f"{value:,.2f}"


def _stock_report(item, bars: list) -> str:
    averages = moving_averages(bars)
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


def _latest_signal_text(ohlc: list, signals: list[Signal]) -> str:
    if not signals:
        return "上一次交叉：此範圍無訊號｜建議：-｜交叉價格：-"
    signal = max(signals, key=lambda item: item.date)
    label, action = ("G", "買進") if signal.type == "golden_cross" else ("D", "賣出")
    close = next(item[4] for item in ohlc if item[0] == signal.date)
    return f"上一次交叉：{label}（{signal.date:%Y/%m/%d}）｜建議{action}（{label}）｜交叉價格：{close:,.2f}"


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


def _months_cutoff(today: date, months: int) -> date:
    """First day of the earliest month an `months`-long history query covers."""
    offset = months - 1
    year = today.year + ((today.month - 1 - offset) // 12)
    month = (today.month - 1 - offset) % 12 + 1
    return date(year, month, 1)


def _cjk_font():  # type: ignore[no-untyped-def]
    """A FontProperties able to render Chinese, or None to use the default."""
    from matplotlib.font_manager import FontProperties, findfont
    for family in ("Microsoft JhengHei", "Microsoft YaHei", "PingFang TC",
                   "Noto Sans CJK TC", "Noto Sans CJK SC", "SimHei"):
        try:
            if findfont(FontProperties(family=family), fallback_to_default=False):
                return FontProperties(family=family)
        except Exception:
            continue
    return None


def _chart_starts(dates: list[date], key) -> list[int]:
    """Positions where `key(date)` changes, e.g. the first bar of each month."""
    return [index for index in range(len(dates))
            if index == 0 or key(dates[index]) != key(dates[index - 1])]


def _draw_signal_markers(axis, dates: list[date], signals: list[Signal]) -> None:
    """Render detector output at the same trading positions as the candles."""
    positions = {trade_date: index for index, trade_date in enumerate(dates)}
    styles = {
        "golden_cross": ("G", "#b07800", "--"),
        "death_cross": ("D", "#1565c0", ":"),
    }
    for signal in signals:
        position = positions.get(signal.date)
        if position is None or signal.type not in styles:
            continue
        label, color, linestyle = styles[signal.type]
        axis.axvline(position, ymin=0, ymax=0.91, color=color,
                     linestyle=linestyle, linewidth=0.9, alpha=0.55, zorder=1)
        # Data coordinates on x follow pan/zoom; axes coordinates on y keep
        # the small labels in the reserved space above the price bars.
        axis.text(position, 0.95, label, transform=axis.get_xaxis_transform(),
                  ha="center", va="center", fontsize=9, fontweight="bold",
                  color=color, clip_on=True, zorder=4)


class StockFollowerWindow:
    def __init__(self) -> None:
        clear_cache()
        self._history_chart_data = None
        # Background work hands results back through this queue; only the main
        # thread (the poller) touches Tk, which keeps the UI responsive.
        self._results: queue.Queue = queue.Queue()
        self.root = tk.Tk()
        self.root.title("StockFollower - Taiwan Stock Desktop")
        self.root.geometry("1400x800")
        self.root.minsize(1100, 650)
        self.provider = StockProvider()
        try:
            self.store: PriceStore | None = PriceStore()
        except StorageError:
            self.store = None  # persistence is optional; the UI still works
        self.symbol = tk.StringVar(value="2330")
        self.latest_close = tk.StringVar(value="上一次收盤價：-")
        self.latest_signal = tk.StringVar(value="上一次交叉：-｜建議：-｜交叉價格：-")
        self.symbol.trace_add("write", self._clear_search_summary)
        self.refresh = tk.BooleanVar(value=False)
        self.leaderboard_refresh = tk.BooleanVar(value=False)
        self.ranking = tk.StringVar(value="Volume")
        self.industry = tk.StringVar(value=ALL_INDUSTRIES)
        self.chart_interval = tk.StringVar(value="Day")
        self.history_months = tk.StringVar(value="3")
        self.status = tk.StringVar(value="Enter a stock symbol to get started.")
        self.leaderboard_status = tk.StringVar(value="Choose a ranking to get started.")
        self.leaderboard_title = tk.StringVar(value="TWSE Top 20")
        self._build()
        self.root.after(50, self._poll_results)

    def _build(self) -> None:
        frame = ttk.Frame(self.root, padding=16)
        frame.pack(fill=tk.BOTH, expand=True)
        frame.rowconfigure(0, weight=1)
        # A shared uniform group keeps the total column widths at 7:3,
        # independently of the requested widths of charts and tables.
        frame.columnconfigure(0, weight=7, uniform="main")
        frame.columnconfigure(1, weight=3, uniform="main")
        self.stock_container = ttk.LabelFrame(frame, text="個股", padding=10)
        self.stock_container.grid(row=0, column=0, sticky="nsew")
        self.leaderboard_container = ttk.LabelFrame(frame, text="排行榜", padding=10)
        self.leaderboard_container.grid(row=0, column=1, sticky="nsew")
        self.stock_container.grid_propagate(False)
        self.leaderboard_container.grid_propagate(False)
        self.stock_container.columnconfigure(0, weight=1)
        self.stock_container.rowconfigure(3, weight=1)
        self.leaderboard_container.columnconfigure(0, weight=1)
        self.leaderboard_container.rowconfigure(3, weight=1)

        controls = ttk.Frame(self.stock_container)
        controls.grid(row=0, column=0, sticky="ew")
        controls.columnconfigure(4, weight=1)
        ttk.Label(controls, text="代號：").grid(row=0, column=0)
        entry = ttk.Entry(controls, width=12, textvariable=self.symbol)
        entry.grid(row=0, column=1)
        entry.bind("<Return>", lambda _event: self.show_history())
        ttk.Button(controls, text="搜尋", command=self.show_history).grid(row=0, column=2, padx=(6, 12))
        ttk.Label(controls, textvariable=self.latest_close).grid(row=0, column=3, sticky="w")
        signal_label = ttk.Label(controls, textvariable=self.latest_signal, wraplength=360)
        signal_label.grid(row=0, column=4, sticky="w", padx=(12, 0))
        signal_label.bind("<Configure>", lambda event: signal_label.configure(wraplength=max(160, controls.winfo_width() - signal_label.winfo_x())))

        ranking_controls = ttk.Frame(self.leaderboard_container)
        ranking_controls.grid(row=0, column=0, sticky="ew")
        ttk.Label(ranking_controls, text="Leaderboard:").pack(side=tk.LEFT)
        ttk.Combobox(
            ranking_controls, textvariable=self.ranking, values=("Volume", "Gainers", "Losers"), width=9, state="readonly"
        ).pack(side=tk.LEFT)
        leaderboard_controls = ttk.Frame(self.leaderboard_container)
        leaderboard_controls.grid(row=1, column=0, sticky="ew", pady=(8, 0))
        ttk.Button(leaderboard_controls, text="Show leaderboard", command=self.show_leaderboard).pack(anchor=tk.W)
        ttk.Button(leaderboard_controls, text="市場儀表板", command=self.show_dashboard).pack(anchor=tk.W, pady=(4, 0))
        ttk.Label(leaderboard_controls, text="行業篩選：").pack(anchor=tk.W, pady=(4, 0))
        self.industry_filter = ttk.Combobox(
            leaderboard_controls, textvariable=self.industry,
            values=(ALL_INDUSTRIES, *INDUSTRIES.values(), UNKNOWN_INDUSTRY), width=20, state="readonly",
        )
        self.industry_filter.pack(anchor=tk.W)
        self.industry_filter.bind("<<ComboboxSelected>>", lambda _event: self.show_leaderboard())
        ttk.Checkbutton(leaderboard_controls, text="Refresh cache", variable=self.leaderboard_refresh).pack(anchor=tk.W, pady=(4, 0))

        chart_controls = ttk.Frame(self.stock_container)
        chart_controls.grid(row=2, column=0, sticky="ew", pady=(8, 0))
        ttk.Label(chart_controls, text="Chart interval:").pack(side=tk.LEFT)
        interval_selector = ttk.Combobox(
            chart_controls, textvariable=self.chart_interval, values=("Day", "Week", "Month", "Year"), width=5, state="readonly"
        )
        interval_selector.pack(side=tk.LEFT)
        interval_selector.bind("<<ComboboxSelected>>", self._redraw_history_chart)
        ttk.Label(chart_controls, text="  Range:").pack(side=tk.LEFT)
        ttk.Spinbox(chart_controls, from_=1, to=24, width=4, textvariable=self.history_months).pack(side=tk.LEFT)
        ttk.Label(chart_controls, text="months").pack(side=tk.LEFT)
        ttk.Checkbutton(chart_controls, text="Refresh cache", variable=self.refresh).pack(side=tk.LEFT, padx=12)

        self.content = ttk.Frame(self.stock_container)
        self.content.grid(row=3, column=0, sticky="nsew", pady=(14, 8))
        self.content.columnconfigure(0, weight=1)
        for row in range(3):
            self.content.rowconfigure(row, weight=1, uniform="stock_sections")
        self.report_frame = ttk.LabelFrame(self.content, text="Report")
        self.report_frame.grid(row=0, column=0, sticky="nsew")
        self.report_frame.grid_propagate(False)
        self.report_frame.rowconfigure(0, weight=1)
        self.report_frame.columnconfigure(0, weight=1)
        self.output = tk.Text(self.report_frame, wrap=tk.WORD, font=("Consolas", 10), state=tk.DISABLED, height=1)
        self.output.grid(row=0, column=0, sticky="nsew")
        report_scroll = ttk.Scrollbar(self.report_frame, orient=tk.VERTICAL, command=self.output.yview)
        report_scroll.grid(row=0, column=1, sticky="ns")
        self.output.configure(yscrollcommand=report_scroll.set)
        self.chart_frame = ttk.Frame(self.content)
        self.chart_frame.grid(row=1, column=0, rowspan=2, sticky="nsew")
        self.chart_frame.pack_propagate(False)
        ttk.Label(
            self.chart_frame,
            text="Run a history query to display the embedded candlestick chart here.",
            anchor=tk.CENTER,
        ).pack(fill=tk.BOTH, expand=True)
        output_scroll = ttk.Scrollbar(self.stock_container, orient=tk.HORIZONTAL, command=self.output.xview)
        output_scroll.grid(row=4, column=0, sticky="ew")
        self.output.configure(xscrollcommand=output_scroll.set)
        ttk.Label(self.stock_container, textvariable=self.status).grid(row=5, column=0, sticky="w")

        ttk.Label(self.leaderboard_container, textvariable=self.leaderboard_title).grid(row=2, column=0, sticky="w", pady=8)
        table_frame = ttk.Frame(self.leaderboard_container)
        table_frame.grid(row=3, column=0, sticky="nsew")
        table_frame.rowconfigure(0, weight=1)
        table_frame.columnconfigure(0, weight=1)
        columns = ("rank", "symbol", "name", "close", "change", "volume", "industry")
        self.leaderboard_table = ttk.Treeview(table_frame, columns=columns, show="headings")
        for column, heading, width in zip(columns, ("排名", "代號", "名稱", "收盤", "漲跌幅", "成交量", "行業"), (48, 64, 110, 90, 85, 110, 140)):
            anchor = tk.W if column in ("symbol", "name", "industry") else tk.E
            self.leaderboard_table.heading(column, text=heading, anchor=anchor)
            self.leaderboard_table.column(column, width=width, minwidth=width, stretch=False, anchor=anchor)
        self.leaderboard_table.grid(row=0, column=0, sticky="nsew")
        table_vertical = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=self.leaderboard_table.yview)
        table_vertical.grid(row=0, column=1, sticky="ns")
        table_horizontal = ttk.Scrollbar(table_frame, orient=tk.HORIZONTAL, command=self.leaderboard_table.xview)
        table_horizontal.grid(row=1, column=0, sticky="ew")
        self.leaderboard_table.configure(yscrollcommand=table_vertical.set, xscrollcommand=table_horizontal.set)
        ttk.Label(self.leaderboard_container, textvariable=self.leaderboard_status).grid(row=4, column=0, sticky="w", pady=(8, 0))
        entry.focus_set()

    def _symbol(self) -> str:
        symbol = self.symbol.get().strip()
        if not (symbol.isdigit() and len(symbol) == 4):
            raise ValueError("Stock symbol must be a 4-digit number, e.g. 2330.")
        return symbol

    def _poll_results(self) -> None:
        # Runs on the main thread: deliver any finished work to the widgets.
        try:
            while True:
                callback, payload = self._results.get_nowait()
                callback(payload)
        except queue.Empty:
            pass
        self.root.after(50, self._poll_results)

    def _run(self, work, on_success=None, *, status=None) -> None:
        target_status = self.status if status is None else status
        target_status.set("Loading...")

        def runner() -> None:
            # Tk is touched only by the main-thread poller, never from here.
            try:
                result = work()
            except (DataProviderError, ValueError) as exc:
                self._results.put((lambda message: self._show_error(message, status), str(exc)))
            except Exception as exc:  # pragma: no cover - unexpected UI failure
                self._results.put((lambda message: self._show_error(message, status), f"Unexpected error: {exc}"))
            else:
                self._results.put((on_success or self._show_result, result))

        Thread(target=runner, daemon=True).start()

    def _show_result(self, text: str) -> None:
        self.report_frame.grid()
        self.output.configure(state=tk.NORMAL, wrap=tk.WORD)
        self.output.delete("1.0", tk.END)
        self.output.insert(tk.END, text)
        self.output.configure(state=tk.DISABLED)
        self.status.set("Done.")

    def _clear_search_summary(self, *_args) -> None:
        self.latest_close.set("上一次收盤價：-")
        self.latest_signal.set("上一次交叉：-｜建議：-｜交叉價格：-")

    def _show_error(self, text: str, status: tk.StringVar | None = None) -> None:
        (self.status if status is None else status).set("Request failed.")
        messagebox.showerror("StockFollower", text, parent=self.root)

    def _store_history(self, item, bars: list) -> None:
        # Saving fetched prices is best-effort and must not block a query.
        if self.store is None:
            return
        try:
            trade_date = max(bars, key=lambda bar: bar.trade_date).trade_date
            self.store.save_quote(item, trade_date)
            self.store.save_bars(item.symbol, bars)
            self.store.record_fetch(item.symbol, date.today())
        except StorageError:
            pass

    def show_history(self) -> None:
        try:
            symbol = self._symbol()
        except ValueError as exc:
            self._show_error(str(exc))
            return
        refresh = self.refresh.get()
        try:
            months = int(self.history_months.get())
        except (tk.TclError, ValueError):
            self._show_error("History range must be a whole number between 1 and 24 months.")
            return
        if not 1 <= months <= 24:
            self._show_error("History range must be between 1 and 24 months.")
            return

        def work() -> tuple[str, list, str]:
            today = date.today()
            # Same-day repeat query for this symbol reuses the database; the
            # first query of a new day (or Refresh cache) re-downloads from the API.
            if not refresh and self.store is not None and self.store.last_fetch(symbol) == today.isoformat():
                bars = self.store.prices_since(symbol, _months_cutoff(today, months))
                item = self.store.latest_quote(symbol)
                if bars and item is not None:
                    return _stock_report(item, bars), bars, f"資料庫（{today:%Y/%m/%d} 已更新）"
            bars = sorted(self.provider.history(symbol, months=months, refresh=refresh), key=lambda bar: bar.trade_date)
            if not bars:
                raise DataProviderError("No historical price data is available.")
            item = self.provider.get_quote(symbol, refresh)
            self._store_history(item, bars)
            return _stock_report(item, bars), bars, "現場下載"

        def show_history_result(result: tuple[str, list, str]) -> None:
            # Do not show an earlier search's price beside a different symbol.
            if self.symbol.get().strip() != symbol:
                return
            report, bars, source = result
            latest_bar = max(bars, key=lambda bar: bar.trade_date)
            self.latest_close.set(f"上一次收盤價：{_money(latest_bar.close)}")
            self._show_result(report)
            self._history_chart_data = (bars, symbol)
            self._redraw_history_chart()
            self.status.set(f"來源：{source}")

        self._run(work, show_history_result)

    def _redraw_history_chart(self, _event=None) -> None:
        if self._history_chart_data is not None:
            bars, symbol = self._history_chart_data
            interval = self.chart_interval.get()
            ohlc = _chart_bars(bars, interval)
            dates = [item[0] for item in ohlc]
            series = kdj_series([item[2] for item in ohlc], [item[3] for item in ohlc], [item[4] for item in ohlc])
            signals = detect_kdj_signals(dates, series[0], series[1])
            self._history_chart_technical = (ohlc, series, signals)
            if self.symbol.get().strip() == symbol:
                self.latest_signal.set(_latest_signal_text(ohlc, signals))
            self._show_history_chart(bars, symbol, interval)

    def _show_history_chart(self, bars: list, symbol: str, interval: str) -> None:  # type: ignore[type-arg]
        try:
            from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
            from matplotlib.figure import Figure
        except ImportError:
            self._show_error("Matplotlib is not installed. Run: python -m pip install -e .")
            return

        for child in self.chart_frame.winfo_children():
            child.destroy()
        figure = Figure(figsize=(8, 6), dpi=100)
        price_axis = figure.add_subplot(211)
        kdj_axis = figure.add_subplot(212, sharex=price_axis)
        ohlc, (k_values, d_values, j_values), signals = self._history_chart_technical
        dates = [item[0] for item in ohlc]
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
        price_axis.margins(y=0.18)
        _draw_signal_markers(price_axis, dates, signals)
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
        day_positions = list(range(len(dates)))  # one tick per trading day
        day_labels = [str(trade_date.day) for trade_date in dates]
        month_positions = _chart_starts(dates, lambda d: d.month)
        year_positions = _chart_starts(dates, lambda d: d.year)
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

        # Calendar labels must follow the shared price/KDJ range too. These
        # auxiliary axes should not intercept toolbar zoom and pan gestures.
        month_axis.set_navigate(False)
        year_axis.set_navigate(False)

        def sync_calendar_axes(axis):
            for calendar_axis in (month_axis, year_axis):
                calendar_axis.set_xlim(axis.get_xlim())

        price_axis.callbacks.connect("xlim_changed", sync_calendar_axes)
        kdj_axis.callbacks.connect("xlim_changed", sync_calendar_axes)

        figure.subplots_adjust(bottom=0.32 if len(day_labels) > 40 else 0.28, hspace=0.08)
        kdj_axis.legend(loc="upper left")
        canvas = FigureCanvasTkAgg(figure, master=self.chart_frame)
        toolbar = NavigationToolbar2Tk(canvas, self.chart_frame, pack_toolbar=False)
        toolbar.update()
        toolbar.pack(side=tk.BOTTOM, fill=tk.X)
        canvas.draw()
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

    def show_leaderboard(self) -> None:
        refresh = self.leaderboard_refresh.get()
        ranking = self.ranking.get()
        industry = self.industry.get()

        def work() -> tuple[str, list[list[str]], list[str]]:
            rows = self.provider.leaderboard_quotes(refresh)
            available = sorted({row.industry for row in rows})
            if industry != ALL_INDUSTRIES:
                rows = [row for row in rows if row.industry == industry]
            if ranking == "Volume":
                rows.sort(key=lambda row: row.volume, reverse=True)
                title = "Volume"
            else:
                rows = [row for row in rows if row.change_percent is not None]
                rows.sort(key=lambda row: row.change_percent or Decimal("0"), reverse=ranking == "Gainers")
                title = ranking
            return f"TWSE Top 20 by {title} — {industry}", leaderboard_rows(rows[:20]), available

        def on_success(result) -> None:
            # A slower previous selection must not overwrite the current filter.
            if self.industry.get() != industry or self.ranking.get() != ranking:
                return
            title, rows, available = result
            self.industry_filter.configure(values=(ALL_INDUSTRIES, *dict.fromkeys([*INDUSTRIES.values(), *available, UNKNOWN_INDUSTRY])))
            self._show_leaderboard_result((title, rows))

        self._run(work, on_success, status=self.leaderboard_status)

    def _show_leaderboard_result(self, result: tuple[str, list[list[str]]]) -> None:
        title, rows = result
        self.leaderboard_title.set(title)
        for item in self.leaderboard_table.get_children():
            self.leaderboard_table.delete(item)
        for row in rows:
            self.leaderboard_table.insert("", tk.END, values=row)
        self.leaderboard_status.set("Done." if rows else "此篩選條件沒有可用的排行資料。")

    def show_dashboard(self) -> None:
        refresh = self.leaderboard_refresh.get()

        def work() -> tuple[dict, list]:
            quotes = self.provider.leaderboard_quotes(refresh)
            return market_breadth(quotes), industry_changes(quotes)

        self._run(work, self._render_dashboard, status=self.leaderboard_status)

    def _render_dashboard(self, result: tuple[dict, list]) -> None:
        try:
            from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
            from matplotlib.figure import Figure
        except ImportError:
            self._show_error("Matplotlib is not installed. Run: python -m pip install -e .",
                             self.leaderboard_status)
            return

        breadth, industries = result
        window = getattr(self, "_dashboard_win", None)
        if window is not None and window.winfo_exists():
            for child in window.winfo_children():
                child.destroy()
        else:
            window = tk.Toplevel(self.root)
            self._dashboard_win = window
        window.title("市場儀表板（上市）")
        window.geometry("920x720")

        adr = breadth["advance_decline_ratio"]
        avg = breadth["avg_change_percent"]
        cards = [
            ("上漲 / 下跌 / 平盤", f"{breadth['advancers']} / {breadth['decliners']} / {breadth['unchanged']}"),
            ("漲停 / 跌停（≥±9.9%）", f"{breadth['limit_up']} / {breadth['limit_down']}"),
            ("騰落比 A/D", "-" if adr is None else f"{adr:.2f}"),
            ("平均漲跌幅", "-" if avg is None else f"{avg:+.2f}%"),
            ("總成交量", f"{breadth['total_volume']:,} 股"),
            ("有效樣本 / 全部", f"{breadth['counted']} / {breadth['total']}"),
        ]
        header = ttk.Frame(window, padding=12)
        header.pack(fill=tk.X)
        for column, (label, value) in enumerate(cards):
            header.columnconfigure(column, weight=1)
            cell = ttk.Frame(header, padding=8)
            cell.grid(row=0, column=column, sticky="nsew")
            ttk.Label(cell, text=value, font=("Microsoft JhengHei", 15, "bold")).pack()
            ttk.Label(cell, text=label).pack()

        font = _cjk_font()
        figure = Figure(figsize=(8, 5.5), dpi=100)
        axis = figure.add_subplot(111)
        top = industries[:15]
        if top:
            names = [row[0] for row in top]
            values = [float(row[1]) for row in top]
            # Taiwan convention: red for gains, green for losses.
            colors = ["#d32f2f" if value >= 0 else "#2e7d32" for value in values]
            positions = list(range(len(top)))
            axis.barh(positions, values, color=colors)
            axis.set_yticks(positions)
            axis.set_yticklabels(names, fontproperties=font)
            axis.invert_yaxis()  # strongest industry on top
            axis.axvline(0, color="#888888", linewidth=0.8)
            axis.set_xlabel("平均漲跌幅 (%)", fontproperties=font)
            for position, value in zip(positions, values):
                axis.text(value, position, f" {value:+.2f}", va="center",
                          ha="left" if value >= 0 else "right", fontsize=8)
        else:
            axis.text(0.5, 0.5, "無可用產業資料", ha="center", va="center",
                      fontproperties=font, transform=axis.transAxes)
            axis.set_axis_off()
        axis.set_title("各產業當日平均漲跌幅", fontproperties=font)
        figure.subplots_adjust(left=0.22, right=0.97, top=0.92, bottom=0.1)

        canvas = FigureCanvasTkAgg(figure, master=window)
        canvas.draw()
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        self.leaderboard_status.set("Done.")

    def run(self) -> None:
        self.root.mainloop()


def launch() -> None:
    StockFollowerWindow().run()
