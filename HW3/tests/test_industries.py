import contextlib
import io
import tempfile
import unittest
from argparse import Namespace
from decimal import Decimal
from pathlib import Path
from unittest.mock import Mock, patch

from stockfollower import cli, gui, providers
from stockfollower.industries import ALL_INDUSTRIES, UNKNOWN_INDUSTRY, industry_name
from stockfollower.models import Quote
from stockfollower.tables import display_width, format_table, leaderboard_rows


def quote(symbol, industry, volume=1, percent=Decimal('1')):
    return Quote(symbol, '台積電', 'TWSE', Decimal('100'), volume, Decimal('1'), percent, industry)


class IndustryTests(unittest.TestCase):
    def test_official_mapping_and_unknown_codes(self):
        self.assertEqual(industry_name('24'), '半導體業')
        self.assertEqual(industry_name(' 1 '), '水泥工業')
        self.assertEqual(industry_name(None), UNKNOWN_INDUSTRY)
        self.assertIn('99', industry_name('99'))

    def test_company_join_cache_refresh_and_startup_cleanup(self):
        payload = [{'公司代號': '2330', '產業別': '24'}]
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(providers, 'CACHE_DIR', Path(directory)), patch.object(providers, '_get_json', return_value=payload) as fetch:
                provider = providers.TwseProvider()
                with patch.object(provider, 'latest_quotes', return_value=[quote('2330', UNKNOWN_INDUSTRY), quote('9999', UNKNOWN_INDUSTRY)]):
                    rows = provider.leaderboard_quotes()
                    self.assertEqual(rows[0].industry, '半導體業')
                    self.assertEqual(rows[1].industry, UNKNOWN_INDUSTRY)
                    provider.leaderboard_quotes()
                    self.assertEqual(fetch.call_count, 1)
                    provider.leaderboard_quotes(refresh=True)
                    self.assertEqual(fetch.call_count, 2)
                    providers.clear_cache()
                    self.assertFalse((Path(directory) / 'twse_industries.json').exists())

    def test_bad_metadata_is_not_cached(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(providers, 'CACHE_DIR', Path(directory)), patch.object(providers, '_get_json', return_value=[{'error': 'unavailable'}]):
                with self.assertRaises(providers.DataProviderError):
                    providers.TwseProvider().company_industries()
                self.assertFalse((Path(directory) / 'twse_industries.json').exists())

    def window(self, rows, industry, ranking='Volume'):
        window = object.__new__(gui.StockFollowerWindow)
        window.leaderboard_refresh = Mock(get=lambda: False)
        window.leaderboard_status = Mock()
        window.ranking = Mock(get=lambda: ranking)
        window.industry = Mock(get=lambda: industry)
        window.industry_filter = Mock()
        window.provider = Mock()
        window.provider.leaderboard_quotes.return_value = rows
        window._show_leaderboard_result = Mock()
        window._run = lambda work, callback, **kwargs: callback(work())
        return window

    def test_filter_before_top_twenty_and_rerank_all_modes(self):
        others = [quote(str(1000 + i), '航運業', 1000) for i in range(25)]
        selected = [quote('2330', '半導體業', 20, Decimal('2')), quote('2303', '半導體業', 10, Decimal('-3'))]
        for mode, expected in [('Volume', '2330'), ('Gainers', '2330'), ('Losers', '2303')]:
            with self.subTest(mode=mode):
                window = self.window(others + selected, '半導體業', mode)
                window.show_leaderboard()
                title, rows = window._show_leaderboard_result.call_args.args[0]
                self.assertIn('半導體業', title)
                self.assertEqual(len(rows), 2)
                self.assertEqual(rows[0][0:2], ['1', expected])
                self.assertTrue(all(row[6] == '半導體業' for row in rows))

    def test_all_and_empty_filter(self):
        rows = [quote('2330', '半導體業')]
        for industry, count in [(ALL_INDUSTRIES, 1), ('航運業', 0)]:
            window = self.window(rows, industry)
            window.show_leaderboard()
            self.assertEqual(len(window._show_leaderboard_result.call_args.args[0][1]), count)

    def test_old_filter_response_does_not_replace_new_selection(self):
        window = self.window([quote('2330', '半導體業')], '半導體業')
        def run(work, callback, **kwargs):
            result = work()
            window.industry.get = lambda: '航運業'
            callback(result)
        window._run = run
        window.show_leaderboard()
        window._show_leaderboard_result.assert_not_called()

    def test_cli_and_seven_column_alignment(self):
        rows = [quote('2330', '半導體業'), quote('2603', '航運業')]
        output = io.StringIO()
        with patch.object(cli, '_provider') as provider, contextlib.redirect_stdout(output):
            provider.return_value.leaderboard_quotes.return_value = rows
            cli.leaderboard(Namespace(refresh=False, by='volume', limit=20))
        self.assertIn('行業', output.getvalue())
        self.assertIn('半導體業', output.getvalue())
        table = format_table(['排名', '代號', '名稱', '收盤', '漲跌幅', '成交量', '行業'], leaderboard_rows(rows))
        self.assertEqual(len({display_width(line) for line in table.splitlines()}), 1)


if __name__ == '__main__':
    unittest.main()
