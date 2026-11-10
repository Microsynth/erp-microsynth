import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from test_assignment_paths import load_function


class TestInvoicePositions(unittest.TestCase):
    def setUp(self):
        self.frappe = Mock()
        self.frappe.DoesNotExistError = LookupError
        self.frappe.throw.side_effect = lambda message, error: self.raise_error(message, error)
        self.create = load_function('microsynth/microsynth/invoicing.py', 'create_position_list',
                                    {'frappe': self.frappe})
        self.records = {
            'Oligo': [{'name': 'O1', 'web_id': '1', 'oligo_name': 'First'},
                      {'name': 'O2', 'web_id': '2', 'oligo_name': 'Second'}],
            'Oligo Item': [{'parent': 'O1', 'item_code': 'A', 'qty': 2},
                           {'parent': 'O2', 'item_code': 'A', 'qty': 1}],
            'Sample': [{'name': 'S1', 'web_id': '3', 'sample_name': 'Sample'}],
            'Sample Item': [{'parent': 'S1', 'item_code': 'A', 'qty': 1}],
        }
        self.frappe.get_all.side_effect = self.get_all

    def get_all(self, doctype, filters, **kwargs):
        field = 'parent' if doctype.endswith(' Item') else 'name'
        names = filters[field][1]
        return [row for row in self.records[doctype] if row[field] in names]

    @staticmethod
    def raise_error(message, error):
        raise error(message)

    @staticmethod
    def invoice(oligos=(), samples=(), taxes=True):
        return SimpleNamespace(
            oligos=[SimpleNamespace(oligo=name) for name in oligos],
            samples=[SimpleNamespace(sample=name) for name in samples],
            web_order_id='WEB', taxes=[SimpleNamespace(rate=10)] if taxes else [],
            items=[SimpleNamespace(item_code='A', item_name='Service', qty=10, rate=5,
                                   amount=50, idx=1, stock_uom='Pcs', item_group='Service'),
                   SimpleNamespace(item_code='SHIP', item_name='Shipping', qty=1, rate=3,
                                   amount=3, idx=2, stock_uom='Pcs', item_group='Shipping')])

    def test_positions_preserve_order_duplicates_and_remaining_quantities(self):
        positions = self.create(self.invoice(['O2', 'O1', 'O2'], ['S1']), False)
        self.assertEqual([row['item'] for row in positions],
                         ['WEB-2', 'WEB-1', 'WEB-2', 'WEB-3', 'A', 'SHIP'])
        self.assertEqual([row['number'] for row in positions], [1, 2, 3, 4, 5, 6])
        self.assertEqual([row['amount'] for row in positions], [5, 10, 5, 5, 50, 3])
        self.assertEqual(positions[4]['quantity'], 5)
        self.assertEqual(positions[1]['description'], 'First')
        self.assertEqual(positions[3]['description'], 'Sample')
        self.assertEqual(positions[1]['tax_amount'], 1)
        self.assertEqual(self.frappe.get_all.call_count, 4)
        self.frappe.get_doc.assert_not_called()
        self.assertEqual(self.frappe.get_all.call_args_list[0].kwargs['filters'],
                         {'name': ['in', ['O2', 'O1']]})
        self.assertEqual(self.frappe.get_all.call_args_list[1].kwargs['filters'],
                         {'parent': ['in', ['O2', 'O1']], 'parenttype': 'Oligo', 'parentfield': 'items'})

    def test_invoice_name_loads_document(self):
        invoice = self.invoice(['O1'], ['S1'])
        self.frappe.get_doc.return_value = invoice
        expected = self.create(invoice, True)

        positions = self.create('SI-BAL-26026916', True)

        self.assertEqual(positions, expected)
        self.assertNotIn('SHIP', [row['item'] for row in positions])
        self.frappe.get_doc.assert_called_once_with('Sales Invoice', 'SI-BAL-26026916')

    def test_missing_invoice_raises(self):
        self.frappe.get_doc.side_effect = LookupError('Sales Invoice missing')

        with self.assertRaisesRegex(LookupError, 'Sales Invoice missing'):
            self.create('missing', True)

        self.frappe.get_all.assert_not_called()

    def test_query_count_is_constant(self):
        for count in (1, 100):
            with self.subTest(count=count):
                self.frappe.reset_mock()
                self.create(self.invoice(['O1'] * count, ['S1'] * count), True)
                self.assertEqual(self.frappe.get_all.call_count, 4)
                self.frappe.get_doc.assert_not_called()

    def test_many_distinct_records_use_four_queries(self):
        self.records['Oligo'] = [
            {'name': f'O{index}', 'web_id': str(index), 'oligo_name': f'Oligo {index}'}
            for index in range(100)]
        self.records['Sample'] = [
            {'name': f'S{index}', 'web_id': str(index), 'sample_name': f'Sample {index}'}
            for index in range(100)]
        self.records['Oligo Item'] = [
            {'parent': row['name'], 'item_code': 'A', 'qty': 1}
            for row in self.records['Oligo']]
        self.records['Sample Item'] = [
            {'parent': row['name'], 'item_code': 'A', 'qty': 1}
            for row in self.records['Sample']]
        positions = self.create(self.invoice(
            [row['name'] for row in self.records['Oligo']],
            [row['name'] for row in self.records['Sample']]), True)
        self.assertEqual(len(positions), 200)
        self.assertEqual(self.frappe.get_all.call_count, 4)
        self.frappe.get_doc.assert_not_called()

    def test_empty_links_do_not_query(self):
        positions = self.create(self.invoice(taxes=False), True)
        self.frappe.get_all.assert_not_called()
        self.assertEqual(len(positions), 1)
        self.assertEqual(positions[0]['item'], 'A')
        self.assertEqual(positions[0]['tax_amount'], 0)

    def test_single_record_type_and_empty_child_rows(self):
        self.records['Oligo Item'] = []
        positions = self.create(self.invoice(['O1']), True)
        self.assertEqual(self.frappe.get_all.call_count, 2)
        self.assertEqual([row['item'] for row in positions], ['A'])

    def test_missing_linked_record_raises(self):
        self.records['Sample'] = []
        with self.assertRaisesRegex(LookupError, 'Sample S1 not found'):
            self.create(self.invoice(samples=['S1']), False)


if __name__ == '__main__':
    unittest.main()