import ast
import sqlite3
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock


class TestCreateStockEntry(unittest.TestCase):
    def setUp(self):
        source = Path(__file__).resolve().parents[1] / 'microsynth/microsynth/stock.py'
        tree = ast.parse(source.read_text())
        function = next(node for node in tree.body
                        if isinstance(node, ast.FunctionDef) and node.name == 'create_stock_entry')
        self.doc = Mock()
        self.items = []
        self.doc.append.side_effect = lambda field, row: self.items.append(row)
        self.doc.insert.side_effect = self.assert_explicit_batches
        self.doc.submit.side_effect = self.assert_explicit_batches
        self.frappe = Mock()
        self.frappe.new_doc.return_value = self.doc
        self.frappe.db.get_value.return_value = 'Test Company'
        self.frappe.throw.side_effect = ValueError
        namespace = {'frappe': self.frappe}
        exec(compile(ast.Module(body=[function], type_ignores=[]), str(source), 'exec'), namespace)
        self.create_stock_entry = namespace['create_stock_entry']
        self.item = SimpleNamespace(name='TEST-ITEM', stock_uom='Unit')

    def assert_explicit_batches(self):
        for row in self.items:
            self.assertEqual(row['use_serial_batch_fields'], 1)
            self.assertTrue(row['batch_no'])
            self.assertNotIn('serial_and_batch_bundle', row)

    def test_issue_and_receipt_preserve_explicit_batches(self):
        for purpose in ('Material Issue', 'Material Receipt'):
            with self.subTest(purpose=purpose):
                self.items.clear()
                self.doc.reset_mock()
                rows = [{'batch_no': 'BATCH-B', 'qty': 3},
                        {'batch_no': 'BATCH-C', 'qty': 2.5, 'rate': 4.25}]

                result = self.create_stock_entry(self.item, 'Stores - TEST', rows, purpose)

                self.assertIs(result, self.doc)
                self.assertEqual(self.doc.company, 'Test Company')
                self.assertEqual(self.doc.stock_entry_type, purpose)
                self.assertEqual([row['batch_no'] for row in self.items], ['BATCH-B', 'BATCH-C'])
                self.assertEqual([row['qty'] for row in self.items], [3, 2.5])
                self.assertEqual([row['basic_rate'] for row in self.items], [0, 4.25])
                for row in self.items:
                    self.assertEqual(row['item_code'], self.item.name)
                    self.assertEqual(row['uom'], self.item.stock_uom)
                    self.assertEqual(row['conversion_factor'], 1)
                    self.assertEqual(row['s_warehouse'],
                                     'Stores - TEST' if purpose == 'Material Issue' else None)
                    self.assertEqual(row['t_warehouse'],
                                     'Stores - TEST' if purpose == 'Material Receipt' else None)
                self.doc.insert.assert_called_once_with()
                self.doc.submit.assert_called_once_with()
                self.assertLess(self.doc.mock_calls.index(unittest.mock.call.insert()),
                                self.doc.mock_calls.index(unittest.mock.call.submit()))

    def test_missing_warehouse_company_still_prevents_creation(self):
        self.frappe.db.get_value.return_value = None
        with self.assertRaises(ValueError):
            self.create_stock_entry(self.item, 'Stores - TEST',
                                    [{'batch_no': 'BATCH-B', 'qty': 3}], 'Material Issue')
        self.frappe.throw.assert_called_once_with(
            'Warehouse Stores - TEST does not have a company assigned.')
        self.doc.insert.assert_not_called()
        self.doc.submit.assert_not_called()


class TestBatchBalances(unittest.TestCase):
    def setUp(self):
        source = Path(__file__).resolve().parents[1] / 'microsynth/microsynth/stock.py'
        tree = ast.parse(source.read_text())
        functions = [node for node in tree.body if isinstance(node, ast.FunctionDef)
                     and node.name in ('correct_stock', 'get_batches_with_qty')]
        for function in functions:
            function.decorator_list = []
        self.frappe = Mock()
        self.frappe.get_roles.return_value = ['Stock User']
        self.frappe.parse_json.side_effect = lambda value: value
        self.frappe.db.exists.return_value = True
        self.frappe.get_doc.return_value = SimpleNamespace(
            name='TEST', item_name='Test Item', material_code='TEST')
        self.get_qty = Mock(return_value=10)
        self.create_entry = Mock(return_value=SimpleNamespace(name='ENTRY-TEST'))
        self.print_labels = Mock()
        namespace = {
            'frappe': self.frappe,
            'get_batch_stock_qty': self.get_qty,
            'flt': lambda value, precision=None: round(float(value), precision)
                if precision is not None else float(value),
            'create_stock_entry': self.create_entry,
            'get_batch_rate': Mock(return_value=2),
            'get_shelf_life_date': Mock(return_value=None),
            'get_internal_code': Mock(return_value='TEST'),
            'print_purchasing_labels': self.print_labels
        }
        exec(compile(ast.Module(body=functions, type_ignores=[]), str(source), 'exec'), namespace)
        self.correct_stock = namespace['correct_stock']
        self.get_batches = namespace['get_batches_with_qty']

    def test_correction_uses_authoritative_batch_balance(self):
        for target, purpose, qty in ((7, 'Material Issue', 3), (0, 'Material Issue', 10),
                                     (12, 'Material Receipt', 2)):
            with self.subTest(target=target):
                self.create_entry.reset_mock()
                result = self.correct_stock('TEST', 'Stores', [
                    {'batch_no': 'BATCH-B', 'current_qty': 0, 'new_qty': target}])
                self.assertTrue(result['success'])
                self.assertEqual(self.create_entry.call_args.args[3], purpose)
                self.assertEqual(self.create_entry.call_args.args[2][0]['qty'], qty)
                self.assertEqual(self.create_entry.call_args.args[2][0]['batch_no'], 'BATCH-B')
                self.get_qty.assert_called_with('TEST', 'Stores', 'BATCH-B')
                self.frappe.db.sql.assert_not_called()

    def test_unchanged_target_does_not_create_entry(self):
        result = self.correct_stock('TEST', 'Stores', [{'batch_no': 'BATCH-B', 'new_qty': 10}])
        self.assertFalse(result['success'])
        self.create_entry.assert_not_called()
        self.print_labels.assert_not_called()

    def test_display_uses_same_balance_api_including_generic_batch(self):
        self.frappe.get_all.return_value = [SimpleNamespace(
            name='BATCH-B', manufacturing_date=None, expiry_date=None)]
        self.frappe._dict.side_effect = lambda values: SimpleNamespace(**values)
        self.get_qty.side_effect = [10, 0]
        result = self.get_batches('TEST', 'Stores')
        self.assertEqual([row['current_qty'] for row in result], [10, 0])
        self.assertEqual([row['new_qty'] for row in result], [10, 0])
        self.assertEqual(result[1]['batch_no'], '[NA]-TEST')
        self.assertEqual(self.get_qty.call_count, 2)
        self.assertEqual(self.get_qty.call_args_list[0].args, ('TEST', 'Stores', 'BATCH-B'))
        self.assertEqual(self.get_qty.call_args_list[1].args, ('TEST', 'Stores', '[NA]-TEST'))
        self.frappe.db.sql.assert_not_called()


class TestPhysicalBatchQuantity(unittest.TestCase):
    def test_mixed_ledger_movements_are_counted_once(self):
        connection = sqlite3.connect(':memory:')
        self.addCleanup(connection.close)
        connection.executescript('''
            CREATE TABLE `tabStock Ledger Entry` (item_code TEXT, warehouse TEXT,
                batch_no TEXT, actual_qty REAL, serial_and_batch_bundle TEXT, is_cancelled INTEGER);
            CREATE TABLE `tabSerial and Batch Entry` (parent TEXT, batch_no TEXT, qty REAL);
            INSERT INTO `tabStock Ledger Entry` VALUES
                ('TEST', 'Stores', 'B', 10, NULL, 0),
                ('TEST', 'Stores', 'B', -2, '', 0),
                ('TEST', 'Stores', 'B', 5, 'receipt', 0),
                ('TEST', 'Stores', NULL, -3, 'issue', 0),
                ('TEST', 'Other', NULL, 99, 'other', 0),
                ('OTHER', 'Stores', 'B', 99, NULL, 0),
                ('TEST', 'Stores', 'B', 99, NULL, 1),
                ('TEST', 'Stores', NULL, 99, 'cancelled', 1);
            INSERT INTO `tabSerial and Batch Entry` VALUES
                ('receipt', 'B', 5), ('issue', 'B', -3), ('issue', 'C', -7),
                ('other', 'B', 99), ('cancelled', 'B', 99), ('unposted', 'B', 99);
        ''')
        source = Path(__file__).resolve().parents[1] / 'microsynth/microsynth/stock.py'
        tree = ast.parse(source.read_text())
        function = next(node for node in tree.body if isinstance(node, ast.FunctionDef)
                        and node.name == 'get_batch_stock_qty')

        def sql(query, values):
            for name in values:
                query = query.replace('%(' + name + ')s', ':' + name)
            return connection.execute(query, values).fetchall()

        namespace = {'frappe': SimpleNamespace(db=SimpleNamespace(sql=sql)), 'flt': float}
        exec(compile(ast.Module(body=[function], type_ignores=[]), str(source), 'exec'), namespace)
        get_qty = namespace['get_batch_stock_qty']
        self.assertEqual(get_qty('TEST', 'Stores', 'B'), 10)
        self.assertEqual(get_qty('TEST', 'Stores', 'C'), -7)
        self.assertEqual(get_qty('TEST', 'Stores', 'MISSING'), 0)


if __name__ == '__main__':
    unittest.main()