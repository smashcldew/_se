import tempfile
import tkinter as tk
import unittest
from datetime import date
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from stockfollower import gui, providers
from stockfollower.storage import PriceStore


class RegressionTests(unittest.TestCase):
    def test_leaderboard_render_preserves_stock_output_and_chart(self):
        window = object.__new__(gui.StockFollowerWindow)
        window.output = Mock()
        window.content = Mock()
        window.status = Mock()
        window.leaderboard_status = Mock()
        window.leaderboard_title = Mock()
        window.leaderboard_table = Mock()
        window.leaderboard_table.get_children.return_value = ('old-row',)
        row = ['1', '2330', '台積電', '100.00', '+1.00%', '1,000', '半導體業']
        window._show_leaderboard_result(('Top 20', [row]))
        window.leaderboard_table.delete.assert_called_once_with('old-row')
        window.leaderboard_table.insert.assert_called_once_with('', tk.END, values=row)
        self.assertEqual(window.output.mock_calls, [])
        self.assertEqual(window.content.mock_calls, [])
        self.assertEqual(window.status.mock_calls, [])

    def test_leaderboard_error_does_not_change_stock_status(self):
        import queue
        window = object.__new__(gui.StockFollowerWindow)
        window.status = Mock()
        window.root = SimpleNamespace()
        window._results = queue.Queue()
        board_status = Mock()
        def thread(*, target, daemon):
            return SimpleNamespace(start=target)
        with patch.object(gui, 'Thread', side_effect=thread), patch.object(gui.messagebox, 'showerror') as error:
            window._run(Mock(side_effect=providers.DataProviderError('failed')), status=board_status)
            callback, payload = window._results.get_nowait()
            callback(payload)
            error.assert_called_once()
        self.assertEqual(window.status.mock_calls, [])
        self.assertEqual(board_status.set.call_args.args, ('Request failed.',))

    def test_cache_cleanup_and_reuse(self):
        with tempfile.TemporaryDirectory() as directory:
            cache = Path(directory)
            old = cache / 'twse_quotes_20260101.json'
            old.write_text('[]')
            unrelated = cache / 'notes.json'
            unrelated.write_text('{}')
            with patch.object(providers, 'CACHE_DIR', cache), patch.object(providers, '_get_json', return_value=[]) as fetch:
                providers.clear_cache()
                self.assertFalse(old.exists())
                self.assertTrue(unrelated.exists())
                provider = providers.TwseProvider()
                provider.latest_quotes()
                provider.latest_quotes()
                self.assertEqual(fetch.call_count, 1)
                providers.clear_cache()
                provider.latest_quotes()
                self.assertEqual(fetch.call_count, 2)

    def test_gui_clears_cache_before_window_creation(self):
        events = []
        class StopBeforeWindow(Exception):
            pass
        def create_window():
            events.append('window')
            raise StopBeforeWindow()
        with patch.object(gui, 'clear_cache', side_effect=lambda: events.append('clear')), patch.object(gui.tk, 'Tk', side_effect=create_window):
            with self.assertRaises(StopBeforeWindow):
                gui.StockFollowerWindow()
        self.assertEqual(events, ['clear', 'window'])

    def test_history_change_field_and_non_comparable_price(self):
        with tempfile.TemporaryDirectory() as directory:
            for value, expected in [('+2.00', Decimal('2')), ('-2.00', Decimal('-2')), ('X0.00', None), ('--', None)]:
                with self.subTest(value=value):
                    payload = {'stat': 'OK', 'data': [['115/10/01', '1,000', '100,000', '100', '105', '99', '102', value, '321']]}
                    with patch.object(providers, 'CACHE_DIR', Path(directory)), patch.object(providers, '_get_json', return_value=payload):
                        bar = providers.TwseProvider().history('2330', months=1, refresh=True)[0]
                    self.assertEqual(bar.change, expected)
                    self.assertEqual(bar.volume, 1000)

    def test_deferred_error_callbacks(self):
        import queue
        for error in [providers.DataProviderError('download failed'), RuntimeError('unexpected')]:
            with self.subTest(error=error):
                window = object.__new__(gui.StockFollowerWindow)
                window.status = Mock()
                window._results = queue.Queue()
                window._show_error = Mock()
                def thread(*, target, daemon):
                    return SimpleNamespace(start=target)
                with patch.object(gui, 'Thread', side_effect=thread):
                    window._run(Mock(side_effect=error))
                callback, payload = window._results.get_nowait()
                callback(payload)
                self.assertIn(str(error), window._show_error.call_args.args[0])

    def test_invalid_months_do_not_start_query(self):
        for value in ['', 'abc', '1.5', '0', '25']:
            with self.subTest(value=value):
                window = object.__new__(gui.StockFollowerWindow)
                window._symbol = lambda: '2330'
                window.refresh = Mock()
                window.history_months = tk.StringVar(master=tk.Tcl())
                window.history_months.set(value)
                window._show_error = Mock()
                window._run = Mock()
                window.show_history()
                window._show_error.assert_called_once()
                window._run.assert_not_called()

    def test_interval_redraw_uses_loaded_symbol_and_current_interval(self):
        window = object.__new__(gui.StockFollowerWindow)
        bars = [SimpleNamespace(trade_date=date(2026, 10, 1), open=100, high=110, low=90, close=105)]
        window._history_chart_data = (bars, '2330')
        window.symbol = Mock()
        window.symbol.get.return_value = '2330'
        window.latest_signal = Mock()
        window.chart_interval = Mock()
        window.chart_interval.get.return_value = 'Week'
        window._show_history_chart = Mock()
        window._redraw_history_chart()
        window._show_history_chart.assert_called_once_with(bars, '2330', 'Week')
        self.assertIn('此範圍無訊號', window.latest_signal.set.call_args.args[0])

    def test_search_updates_chart_and_latest_close_ignoring_stale_symbol(self):
        window = object.__new__(gui.StockFollowerWindow)
        window.symbol = Mock()
        window.symbol.get.return_value = '2330'
        window.refresh = Mock()
        window.refresh.get.return_value = False
        window.history_months = Mock()
        window.history_months.get.return_value = '3'
        window.provider = Mock()
        window.store = None
        bars = [SimpleNamespace(trade_date=date(2026, 10, day),
                                open=Decimal('1000'), high=Decimal('1250'),
                                low=Decimal('990'), close=Decimal(close), volume=1000)
                for day, close in [(2, '1234.5'), (1, '1000')]]
        window.provider.history.return_value = bars
        window.provider.get_quote.return_value = SimpleNamespace(
            symbol='2330', name='TSMC', market='TWSE', close=Decimal('1234.5'),
            change_percent=Decimal('1.2'), volume=1000)
        window.latest_close = Mock()
        window._show_result = Mock()
        window._redraw_history_chart = Mock()
        window.status = Mock()
        window._run = Mock()

        window.show_history()
        work, on_success = window._run.call_args.args
        result = work()
        window.provider.history.assert_called_once_with('2330', months=3, refresh=False)
        on_success(result)
        window.latest_close.set.assert_called_once_with('上一次收盤價：1,234.50')
        self.assertEqual(window._history_chart_data, (sorted(bars, key=lambda bar: bar.trade_date), '2330'))
        window._show_result.assert_called_once()
        self.assertIn('TSMC Stock Report', window._show_result.call_args.args[0])
        window._redraw_history_chart.assert_called_once()

        window.latest_close.reset_mock()
        window._redraw_history_chart.reset_mock()
        window.symbol.get.return_value = '2317'
        on_success(result)
        window.latest_close.set.assert_not_called()
        window._redraw_history_chart.assert_not_called()

    def test_history_query_persists_quote_and_bars_to_store(self):
        with tempfile.TemporaryDirectory() as directory:
            window = object.__new__(gui.StockFollowerWindow)
            window.store = PriceStore(Path(directory) / 'prices.db')
            window.symbol = Mock()
            window.symbol.get.return_value = '2330'
            window.refresh = Mock(get=lambda: False)
            window.history_months = Mock(get=lambda: '3')
            window.provider = Mock()
            from stockfollower.models import DailyBar
            bars = [DailyBar(date(2026, 10, day), Decimal('100'), Decimal('110'),
                             Decimal('90'), Decimal(close), 1000, Decimal('1'))
                    for day, close in [(1, '1000'), (2, '1234.5')]]
            window.provider.history.return_value = bars
            window.provider.get_quote.return_value = SimpleNamespace(
                symbol='2330', name='TSMC', market='TWSE', close=Decimal('1234.5'),
                change=Decimal('5'), change_percent=Decimal('1.2'), volume=1000,
                industry='半導體業')
            window._show_result = Mock()
            window._redraw_history_chart = Mock()
            window.latest_close = Mock()
            window.status = Mock()
            window._run = Mock()
            window.show_history()
            work, _on_success = window._run.call_args.args
            work()
            # The quote is stored under the latest bar's trade date, with bars.
            stored = window.store.saved_quotes(date(2026, 10, 2))
            self.assertEqual(len(stored), 1)
            self.assertEqual(stored[0].close, Decimal('1234.5'))
            self.assertEqual([b.trade_date for b in window.store.recent_prices('2330')],
                             [date(2026, 10, 2), date(2026, 10, 1)])

    def test_same_day_repeat_query_reads_db_instead_of_api(self):
        from stockfollower.models import DailyBar
        with tempfile.TemporaryDirectory() as directory:
            window = object.__new__(gui.StockFollowerWindow)
            window.store = PriceStore(Path(directory) / 'prices.db')
            window.symbol = Mock()
            window.symbol.get.return_value = '2330'
            window.refresh = Mock(get=lambda: False)
            window.history_months = Mock(get=lambda: '3')
            window.provider = Mock()
            window._show_result = Mock()
            window._redraw_history_chart = Mock()
            window.latest_close = Mock()
            window.status = Mock()
            window._run = Mock()
            today = date.today()
            bars = [DailyBar(today, Decimal('100'), Decimal('110'), Decimal('90'),
                             Decimal('105'), 1000, Decimal('1'))]
            window.provider.history.return_value = bars
            window.provider.get_quote.return_value = SimpleNamespace(
                symbol='2330', name='TSMC', market='TWSE', close=Decimal('105'),
                change=Decimal('1'), change_percent=Decimal('1.0'), volume=1000,
                industry='半導體業')

            # First query of the day: hits the API and populates the DB.
            window.show_history()
            first_work, _ = window._run.call_args.args
            _report, _bars, first_source = first_work()
            self.assertEqual(first_source, '現場下載')
            self.assertEqual(window.provider.history.call_count, 1)

            # Second query, same day: reads the DB, no further API calls.
            window.show_history()
            second_work, _ = window._run.call_args.args
            _report2, bars2, second_source = second_work()
            self.assertIn('資料庫', second_source)
            self.assertEqual(window.provider.history.call_count, 1)
            self.assertEqual(window.provider.get_quote.call_count, 1)
            self.assertEqual(bars2[0].close, Decimal('105'))

            # Refresh cache forces the API even on the same day.
            window.refresh = Mock(get=lambda: True)
            window.show_history()
            third_work, _ = window._run.call_args.args
            _report3, _bars3, third_source = third_work()
            self.assertEqual(third_source, '現場下載')
            self.assertEqual(window.provider.history.call_count, 2)

    def test_latest_cross_summary_uses_detector_date_and_matching_close(self):
        ohlc = [(date(2026, 10, day), 100, 110, 90, close)
                for day, close in [(1, 101), (2, 102), (5, 105)]]
        golden = gui.Signal(date(2026, 10, 1), 'golden_cross')
        death = gui.Signal(date(2026, 10, 2), 'death_cross')
        summary = gui._latest_signal_text(ohlc, [death, golden])
        self.assertIn('上一次交叉：D（2026/10/02）', summary)
        self.assertIn('建議賣出（D）', summary)
        self.assertIn('交叉價格：102.00', summary)
        summary = gui._latest_signal_text(ohlc, [golden])
        self.assertIn('建議買進（G）', summary)
        self.assertIn('交叉價格：101.00', summary)
        self.assertIn('此範圍無訊號', gui._latest_signal_text(ohlc, []))


if __name__ == '__main__':
    unittest.main()
