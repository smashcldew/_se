import tempfile
import unittest
from datetime import date
from decimal import Decimal
from pathlib import Path

from stockfollower.models import DailyBar, Quote
from stockfollower.storage import PriceStore


def quote(symbol='2330', close=Decimal('1000'), percent=Decimal('1.5')):
    return Quote(symbol, '台積電', 'TWSE', close, 12345, Decimal('5'), percent, '半導體業')


def bar(day, close):
    return DailyBar(date(2026, 10, day), Decimal('100'), Decimal('110'),
                    Decimal('90'), Decimal(close), 1000, Decimal('1'))


class StorageTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.store = PriceStore(Path(self.directory.name) / 'prices.db')

    def test_schema_created_on_init(self):
        self.assertTrue(self.store.path.exists())
        self.assertEqual(self.store.saved_quotes(date(2026, 10, 1)), [])
        self.assertEqual(self.store.recent_prices('2330'), [])

    def test_save_quote_round_trip_preserves_decimals(self):
        self.store.save_quote(quote(percent=Decimal('15') / Decimal('1435') * 100), date(2026, 10, 1))
        stored = self.store.saved_quotes(date(2026, 10, 1))
        self.assertEqual(len(stored), 1)
        self.assertEqual(stored[0].symbol, '2330')
        self.assertEqual(stored[0].close, Decimal('1000'))
        self.assertEqual(stored[0].volume, 12345)
        self.assertEqual(stored[0].change_percent, Decimal('15') / Decimal('1435') * 100)
        self.assertEqual(stored[0].industry, '半導體業')

    def test_save_quote_is_upsert_on_symbol_and_date(self):
        self.store.save_quote(quote(close=Decimal('1000')), date(2026, 10, 1))
        self.store.save_quote(quote(close=Decimal('1234.5')), date(2026, 10, 1))
        stored = self.store.saved_quotes(date(2026, 10, 1))
        self.assertEqual(len(stored), 1)
        self.assertEqual(stored[0].close, Decimal('1234.5'))

    def test_quotes_are_separated_by_trade_date(self):
        self.store.save_quote(quote(), date(2026, 10, 1))
        self.store.save_quote(quote(), date(2026, 10, 2))
        self.assertEqual(len(self.store.saved_quotes(date(2026, 10, 1))), 1)
        self.assertEqual(len(self.store.saved_quotes(date(2026, 10, 2))), 1)

    def test_save_bars_round_trip_and_recent_order(self):
        bars = [bar(1, '101'), bar(2, '102'), bar(5, '105')]
        self.store.save_bars('2330', bars)
        recent = self.store.recent_prices('2330', limit=2)
        self.assertEqual([b.trade_date for b in recent], [date(2026, 10, 5), date(2026, 10, 2)])
        self.assertEqual(recent[0].close, Decimal('105'))
        self.assertEqual(recent[0].high, Decimal('110'))
        self.assertEqual(recent[0].volume, 1000)

    def test_save_bars_is_upsert(self):
        self.store.save_bars('2330', [bar(1, '101')])
        self.store.save_bars('2330', [bar(1, '999')])
        recent = self.store.recent_prices('2330')
        self.assertEqual(len(recent), 1)
        self.assertEqual(recent[0].close, Decimal('999'))

    def test_empty_saves_are_noops(self):
        self.store.save_quotes([], date(2026, 10, 1))
        self.store.save_bars('2330', [])
        self.assertEqual(self.store.saved_quotes(date(2026, 10, 1)), [])
        self.assertEqual(self.store.recent_prices('2330'), [])


if __name__ == '__main__':
    unittest.main()
