import ast
from datetime import date, timedelta
from pathlib import Path
import sqlite3
from types import SimpleNamespace
import unittest


class TestPriceListRate(unittest.TestCase):
    def setUp(self):
        self.connection = sqlite3.connect(':memory:')
        self.addCleanup(self.connection.close)
        self.connection.row_factory = sqlite3.Row
        self.connection.create_function('CURDATE', 0, lambda: date.today().isoformat())
        self.connection.executescript('''
            CREATE TABLE `tabPrice List` (name TEXT, enabled INTEGER, currency TEXT);
            CREATE TABLE `tabItem Price` (
                name TEXT, price_list TEXT, item_code TEXT, min_qty REAL,
                price_list_rate REAL, currency TEXT, valid_from TEXT,
                valid_upto TEXT, modified TEXT, creation TEXT
            );
            INSERT INTO `tabPrice List` VALUES ('Customer CHF', 1, 'CHF');
        ''')
        source = Path(__file__).resolve().parents[1] / 'microsynth/microsynth/pricing.py'
        tree = ast.parse(source.read_text())
        function = next(node for node in tree.body
                        if isinstance(node, ast.FunctionDef) and node.name == 'get_price_list_rate')
        namespace = {'frappe': SimpleNamespace(db=SimpleNamespace(sql=self.sql))}
        exec(compile(ast.Module(body=[function], type_ignores=[]), str(source), 'exec'), namespace)
        self.get_rate = namespace['get_price_list_rate']

    def sql(self, query, values, as_dict):
        self.assertTrue(as_dict)
        return [dict(row) for row in self.connection.execute(query.replace('%s', '?'), values)]

    def add_price(self, name='base', min_qty=1, rate=10, currency='CHF',
                  price_list='Customer CHF', item_code='00123', valid_from=None, valid_upto=None):
        self.connection.execute(
            'INSERT INTO `tabItem Price` VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
            (name, price_list, item_code, min_qty, rate, currency, valid_from, valid_upto,
             '2026-01-01', '2026-01-01'),
        )

    def test_quantity_tiers(self):
        self.add_price()
        self.add_price(name='bulk', min_qty=10, rate=8)
        for qty, expected in ((0, None), (1, 10), (9.5, 10), (10, 8), (100, 8)):
            with self.subTest(qty=qty):
                self.assertEqual(self.get_rate('Customer CHF', '00123', qty), expected)

    def test_disabled_or_missing_price_list(self):
        self.add_price()
        self.connection.execute('UPDATE `tabPrice List` SET enabled = 0')
        self.assertIsNone(self.get_rate('Customer CHF', '00123', 10))
        self.add_price(name='orphan', price_list='Missing')
        self.assertIsNone(self.get_rate('Missing', '00123', 10))

    def test_currency_mismatch_is_excluded_before_tier_selection(self):
        self.add_price()
        self.add_price(name='wrong-currency', min_qty=10, rate=8, currency='EUR')
        self.assertEqual(self.get_rate('Customer CHF', '00123', 10), 10)
        self.connection.execute("DELETE FROM `tabItem Price` WHERE currency = 'CHF'")
        self.assertIsNone(self.get_rate('Customer CHF', '00123', 10))

    def test_only_requested_item_and_price_list_match(self):
        self.add_price(item_code='other')
        self.add_price(name='other-list', price_list='Other CHF')
        self.assertIsNone(self.get_rate('Customer CHF', '00123', 10))

    def test_zero_rate_is_returned(self):
        self.add_price(rate=0)
        self.assertEqual(self.get_rate('Customer CHF', '00123', 1), 0)

    def test_validity_dates_and_latest_valid_from(self):
        today = date.today()
        yesterday = (today - timedelta(days=1)).isoformat()
        tomorrow = (today + timedelta(days=1)).isoformat()
        self.add_price()
        self.add_price(name='expired', min_qty=10, rate=2, valid_upto=yesterday)
        self.add_price(name='future', min_qty=10, rate=3, valid_from=tomorrow)
        self.add_price(name='old', rate=9, valid_from=yesterday)
        self.add_price(name='current', rate=8, valid_from=today.isoformat(),
                       valid_upto=today.isoformat())
        self.assertEqual(self.get_rate('Customer CHF', '00123', 10), 8)

    def test_names_are_bound_as_parameters(self):
        price_list = "Customer's CHF"
        item_code = "item's code"
        self.connection.execute('INSERT INTO `tabPrice List` VALUES (?, 1, ?)', (price_list, 'CHF'))
        self.add_price(price_list=price_list, item_code=item_code)
        self.assertEqual(self.get_rate(price_list, item_code, 1), 10)


if __name__ == '__main__':
    unittest.main()