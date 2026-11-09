import unittest
from decimal import Decimal
from unittest.mock import Mock

from stockfollower import gui
from stockfollower.dashboard import industry_changes, market_breadth
from stockfollower.models import Quote


def quote(symbol, percent, industry='半導體業', volume=1000):
    change = None if percent is None else Decimal('1')
    pct = None if percent is None else Decimal(str(percent))
    return Quote(symbol, 'N', 'TWSE', Decimal('100'), volume, change, pct, industry)


class MarketBreadthTests(unittest.TestCase):
    def test_counts_spread_limits_and_totals(self):
        quotes = [
            quote('1', '9.9', volume=100),    # limit up
            quote('2', '3.0', volume=200),
            quote('3', '-9.95', volume=300),  # limit down
            quote('4', '-1.0', volume=400),
            quote('5', '0', volume=500),      # flat
            quote('6', None, volume=600),     # no change data
        ]
        b = market_breadth(quotes)
        self.assertEqual(b['total'], 6)
        self.assertEqual(b['counted'], 5)
        self.assertEqual(b['advancers'], 2)
        self.assertEqual(b['decliners'], 2)
        self.assertEqual(b['unchanged'], 1)
        self.assertEqual(b['limit_up'], 1)
        self.assertEqual(b['limit_down'], 1)
        self.assertEqual(b['total_volume'], 2100)  # includes the no-data row's volume
        self.assertEqual(b['advance_decline_ratio'], Decimal('1'))
        self.assertEqual(b['avg_change_percent'],
                         (Decimal('9.9') + Decimal('3.0') + Decimal('-9.95') + Decimal('-1.0') + Decimal('0')) / 5)

    def test_empty_and_no_decliners_are_safe(self):
        empty = market_breadth([])
        self.assertEqual(empty['counted'], 0)
        self.assertIsNone(empty['avg_change_percent'])
        self.assertIsNone(empty['advance_decline_ratio'])
        only_up = market_breadth([quote('1', '1.0'), quote('2', '2.0')])
        self.assertIsNone(only_up['advance_decline_ratio'])  # no decliners -> guarded


class IndustryChangesTests(unittest.TestCase):
    def test_average_per_industry_sorted_strongest_first(self):
        quotes = [
            quote('1', '2.0', '半導體業'),
            quote('2', '4.0', '半導體業'),
            quote('3', '-1.0', '航運業'),
            quote('4', None, '金融保險'),   # dropped: no data
        ]
        rows = industry_changes(quotes)
        self.assertEqual([(name, count) for name, _avg, count in rows],
                         [('半導體業', 2), ('航運業', 1)])
        self.assertEqual(rows[0][1], Decimal('3.0'))   # (2+4)/2
        self.assertEqual(rows[1][1], Decimal('-1.0'))

    def test_empty(self):
        self.assertEqual(industry_changes([]), [])


class DashboardWiringTests(unittest.TestCase):
    def test_show_dashboard_work_computes_breadth_and_industries(self):
        window = object.__new__(gui.StockFollowerWindow)
        window.leaderboard_refresh = Mock(get=lambda: False)
        window.leaderboard_status = Mock()
        window.provider = Mock()
        window.provider.leaderboard_quotes.return_value = [
            quote('2330', '2.0', '半導體業'), quote('2603', '-1.0', '航運業')]
        captured = {}
        window._run = lambda work, callback, **kwargs: captured.update(result=work(), callback=callback)
        window.show_dashboard()
        window.provider.leaderboard_quotes.assert_called_once_with(False)
        breadth, industries = captured['result']
        self.assertEqual(breadth['advancers'], 1)
        self.assertEqual(breadth['decliners'], 1)
        self.assertEqual(industries[0][0], '半導體業')
        self.assertEqual(captured['callback'], window._render_dashboard)


if __name__ == '__main__':
    unittest.main()
