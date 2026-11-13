import ast
from datetime import date, timedelta
from pathlib import Path
import sqlite3
from types import SimpleNamespace
import unittest


class TestOligoModifierStock(unittest.TestCase):
    def setUp(self):
        self.connection = sqlite3.connect(':memory:')
        self.addCleanup(self.connection.close)
        self.connection.row_factory = sqlite3.Row
        self.connection.create_function('GREATEST', -1, max)
        self.connection.executescript('''
            CREATE TABLE `tabLocation` (name TEXT, lft INTEGER, rgt INTEGER, is_group INTEGER);
            CREATE TABLE `tabLocation Link` (location TEXT, parent TEXT, parenttype TEXT, parentfield TEXT);
            CREATE TABLE `tabItem` (name TEXT, pack_size REAL, pack_uom TEXT, safety_stock REAL,
                min_order_qty REAL, item_name TEXT, material_code TEXT, shelf_life_in_days REAL,
                stock_uom TEXT, disabled INTEGER);
            CREATE TABLE `tabItem Supplier` (parent TEXT, supplier TEXT, supplier_part_no TEXT, substitute_status TEXT);
            CREATE TABLE `tabItem Default` (parent TEXT, default_supplier TEXT, idx INTEGER);
            CREATE TABLE `tabSupplier` (name TEXT, supplier_name TEXT);
            CREATE TABLE `tabBin` (item_code TEXT, actual_qty REAL);
            CREATE TABLE `tabMaterial Request Item` (parent TEXT, item_code TEXT, qty REAL, conversion_factor REAL, ordered_qty REAL);
            CREATE TABLE `tabMaterial Request` (name TEXT, docstatus INTEGER, status TEXT);
            CREATE TABLE `tabPurchase Order Item` (parent TEXT, item_code TEXT, qty REAL, conversion_factor REAL, received_qty REAL);
            CREATE TABLE `tabPurchase Order` (name TEXT, docstatus INTEGER);
            CREATE TABLE `tabStock Entry` (name TEXT, docstatus INTEGER, stock_entry_type TEXT, remarks TEXT, posting_date TEXT);
            CREATE TABLE `tabStock Entry Detail` (parent TEXT, item_code TEXT, transfer_qty REAL);
            INSERT INTO `tabLocation` VALUES ('11-03 Oligo Synthesis', 1, 6, 1), ('Filled', 2, 3, 0), ('Empty', 4, 5, 0);
            INSERT INTO `tabLocation Link` VALUES ('Filled', 'item', 'Item', 'storage_locations');
            INSERT INTO `tabItem` (name, stock_uom, disabled) VALUES ('item', 'g', 0);
        ''')
        source = Path(__file__).resolve().parents[1] / 'microsynth/microsynth/report/oligo_modifier_stock/oligo_modifier_stock.py'
        tree = ast.parse(source.read_text())
        functions = [node for node in tree.body if isinstance(node, ast.FunctionDef)]
        namespace = {'frappe': SimpleNamespace(db=SimpleNamespace(sql=self.sql)), '_': str}
        exec(compile(ast.Module(body=functions, type_ignores=[]), str(source), 'exec'), namespace)
        self.report = SimpleNamespace(**namespace)

    def sql(self, query, as_dict):
        self.assertTrue(as_dict)
        query = query.replace('DATE_SUB(CURDATE(), INTERVAL 89 DAY)', "DATE('now', '-89 days')")
        query = query.replace('CURDATE()', "DATE('now')")
        return [dict(row) for row in self.connection.execute(query)]

    def add_entry(self, name, days_ago, qty, status=1, entry_type='Material Issue', remarks=None, item='item'):
        posting_date = (date.today() - timedelta(days=days_ago)).isoformat()
        self.connection.execute('INSERT INTO `tabStock Entry` VALUES (?, ?, ?, ?, ?)',
                                (name, status, entry_type, remarks, posting_date))
        self.connection.execute('INSERT INTO `tabStock Entry Detail` VALUES (?, ?, ?)', (name, item, qty))

    def test_usage_counts_only_recent_submitted_material_issues(self):
        self.add_entry('today', 0, 3.2)
        self.add_entry('boundary', 89, 2.4)
        self.add_entry('old', 90, 100)
        self.add_entry('future', -1, 100)
        self.add_entry('draft', 1, 100, status=0)
        self.add_entry('cancelled', 1, 100, status=2)
        self.add_entry('receipt', 1, 100, entry_type='Material Receipt')
        self.add_entry('correction', 1, 100, remarks='Stock correction via Correct Stock: adjustment')
        self.add_entry('other', 1, 100, item='other')
        row = self.report.get_filled_locations()[0]
        self.assertEqual(row['stock_usage_3m'], 6)
        self.assertEqual(row['stock_uom'], 'g')

    def test_no_usage_and_empty_location(self):
        self.assertEqual(self.report.get_filled_locations()[0]['stock_usage_3m'], 0)
        row = self.report.get_empty_locations()[0]
        self.assertEqual(set(row), {column['fieldname'] for column in self.report.get_columns()})
        self.assertEqual(row['location'], 'Empty')
        self.assertTrue(all(value is None for field, value in row.items() if field != 'location'))


if __name__ == '__main__':
    unittest.main()