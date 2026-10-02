import tempfile
import tkinter as tk
import unittest
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from stockfollower import cli, gui, providers


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
        callbacks = []
        window = object.__new__(gui.StockFollowerWindow)
        window.status = Mock()
        window.root = SimpleNamespace(after=lambda delay, callback: callbacks.append(callback))
        board_status = Mock()
        def thread(*, target, daemon):
            return SimpleNamespace(start=target)
        with patch.object(gui, 'Thread', side_effect=thread), patch.object(gui.messagebox, 'showerror') as error:
            window._run(Mock(side_effect=providers.DataProviderError('failed')), status=board_status)
            callbacks[0]()
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

    def test_cli_clears_cache_before_query(self):
        events = []
        with patch('sys.argv', ['stockfollower', 'quote', '2330']), patch.object(cli, 'clear_cache', side_effect=lambda: events.append('clear')), patch.object(cli, 'quote', side_effect=lambda args: events.append('query')):
            cli.main()
        self.assertEqual(events, ['clear', 'query'])

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
        for error in [providers.DataProviderError('download failed'), RuntimeError('unexpected')]:
            with self.subTest(error=error):
                callbacks = []
                window = object.__new__(gui.StockFollowerWindow)
                window.status = Mock()
                window.root = SimpleNamespace(after=lambda delay, callback: callbacks.append(callback))
                window._show_error = Mock()
                def thread(*, target, daemon):
                    return SimpleNamespace(start=target)
                with patch.object(gui, 'Thread', side_effect=thread):
                    window._run(Mock(side_effect=error))
                callbacks[0]()
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
        bars = [object()]
        window._history_chart_data = (bars, '2330')
        window.chart_interval = Mock()
        window.chart_interval.get.return_value = 'Week'
        window._show_history_chart = Mock()
        window._redraw_history_chart()
        window._show_history_chart.assert_called_once_with(bars, '2330', 'Week')


if __name__ == '__main__':
    unittest.main()
