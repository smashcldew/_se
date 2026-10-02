import tempfile
import unittest
from datetime import date
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from stockfollower import providers
from stockfollower.models import Quote


class TpexTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.cache = Path(self.directory.name)
        self.cache_patch = patch.object(providers, 'CACHE_DIR', self.cache)
        self.cache_patch.start()
        self.addCleanup(self.cache_patch.stop)

    def test_quote_fields_cache_and_cleanup(self):
        payload = [{'SecuritiesCompanyCode': '6274', 'CompanyName': '台燿',
                    'Close': '1,450.00', 'Change': '15.00', 'TradingShares': '4,920,123'}]
        with patch.object(providers, '_get_json', return_value=payload) as fetch:
            provider = providers.TpexProvider()
            item = provider.latest_quotes()[0]
            self.assertEqual((item.symbol, item.name, item.market), ('6274', '台燿', 'TPEx'))
            self.assertEqual(item.close, Decimal('1450'))
            self.assertEqual(item.volume, 4920123)
            self.assertEqual(item.change_percent, Decimal('15') / Decimal('1435') * 100)
            provider.latest_quotes()
            fetch.assert_called_once_with(providers.TPEX_OPENAPI)
            provider.latest_quotes(refresh=True)
            self.assertEqual(fetch.call_count, 2)
            providers.clear_cache()
            self.assertEqual(list(self.cache.glob('tpex_*.json')), [])

    def test_history_official_table_and_lot_conversion(self):
        # Shape and units verified against the TPEx 6274 September endpoint.
        payload = {'stat': 'ok', 'code': '6274', 'name': '台燿', 'tables': [
            {'fields': ['日期', '成交張數', '成交仟元', '開盤', '最高', '最低', '收盤', '漲跌', '筆數'],
             'data': [['115/09/01', '4,920', '7,152,289', '1,435.00', '1,480.00', '1,430.00', '1,450.00', '15.00', '13,268']]}]}
        with patch.object(providers, '_get_json', return_value=payload) as fetch:
            bar = providers.TpexProvider().history('6274', months=1)[0]
            self.assertEqual(bar.trade_date, date(2026, 9, 1))
            self.assertEqual(bar.volume, 4920000)
            self.assertEqual(bar.change, Decimal('15'))
            self.assertEqual(bar.close, Decimal('1450'))
            self.assertEqual(fetch.call_args.args[0], providers.TPEX_HISTORY)
            self.assertEqual(fetch.call_args.args[1]['code'], '6274')

    def test_route_otc_quote_and_history(self):
        item = Quote('6274', '台燿', 'TPEx', Decimal('1450'), 1, Decimal('15'), Decimal('1'))
        provider = providers.StockProvider()
        with patch.object(provider, 'latest_quotes', return_value=[]), patch.object(provider._tpex, 'latest_quotes', return_value=[item]), patch.object(provider._tpex, 'history', return_value=[]) as history:
            self.assertEqual(provider.get_quote('6274'), item)
            provider.history('6274', 3, True)
            history.assert_called_once_with('6274', 3, True)

    def test_twse_quote_does_not_download_otc_quotes(self):
        item = Quote('2330', '台積電', 'TWSE', Decimal('100'), 1, None, None)
        provider = providers.StockProvider()
        with patch.object(provider, 'latest_quotes', return_value=[item]), patch.object(provider._tpex, 'latest_quotes') as otc:
            self.assertEqual(provider.get_quote('2330'), item)
            otc.assert_not_called()

    def test_otc_history_does_not_require_otc_quote_download(self):
        provider = providers.StockProvider()
        with patch.object(provider, 'latest_quotes', return_value=[]), patch.object(provider._tpex, 'latest_quotes') as quotes, patch.object(provider._tpex, 'history', return_value=[]) as history:
            provider.history('6274', 3)
            quotes.assert_not_called()
            history.assert_called_once_with('6274', 3, False)

    def test_network_failure_is_not_reported_as_unknown_symbol(self):
        provider = providers.StockProvider()
        with patch.object(provider, 'latest_quotes', return_value=[]), patch.object(provider._tpex, 'latest_quotes', side_effect=providers.DataProviderError('connection failed')):
            with self.assertRaisesRegex(providers.DataProviderError, 'connection failed'):
                provider.get_quote('6274')

    def test_unknown_symbol_and_empty_api_are_distinct(self):
        provider = providers.StockProvider()
        with patch.object(provider, 'latest_quotes', return_value=[]), patch.object(provider._tpex, 'latest_quotes', return_value=[]):
            with self.assertRaisesRegex(providers.DataProviderError, '上市及上櫃'):
                provider.get_quote('9999')
        with patch.object(providers, '_get_json', return_value=[]):
            with self.assertRaisesRegex(providers.DataProviderError, '資料格式'):
                provider._tpex.latest_quotes()


if __name__ == '__main__':
    unittest.main()
