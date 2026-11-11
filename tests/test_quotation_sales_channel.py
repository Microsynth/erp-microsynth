import ast
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
import sys


ROOT = Path(__file__).resolve().parents[1]


def load_functions(relative_path, names, namespace):
    tree = ast.parse((ROOT / relative_path).read_text())
    functions = [node for node in tree.body
                 if isinstance(node, ast.FunctionDef) and node.name in names]
    exec(compile(ast.Module(body=functions, type_ignores=[]), relative_path, 'exec'), namespace)


class TestQuotationSalesChannel(unittest.TestCase):
    def setUp(self):
        self.frappe = Mock()
        self.frappe.db.get_all.side_effect = self.get_all
        self.quotations = []
        self.namespace = {'frappe': self.frappe}
        load_functions('microsynth/microsynth/quotation.py', {
            'get_contract_research_sales_managers',
            'resolve_sales_channel_from_sales_manager',
            'set_sales_order_sales_channel',
        }, self.namespace)
        self.set_channel = self.namespace['set_sales_order_sales_channel']

    def get_all(self, doctype, **kwargs):
        if doctype == 'Quotation':
            return self.quotations
        if doctype == 'QM User Process Assignment':
            return [{'parent': 'CR-settings'}]
        if doctype == 'User Settings':
            return [{'user': 'cr@example.com'}]
        raise AssertionError(doctype)

    @staticmethod
    def order(quotations=(), channel='Sales'):
        return SimpleNamespace(
            items=[SimpleNamespace(prevdoc_docname=name) for name in quotations],
            sales_channel=channel,
        )

    def test_old_quotation_channel_is_not_required(self):
        for channel in (None, '', 'Sales'):
            with self.subTest(quotation_channel=channel):
                self.quotations = [{'sales_manager': 'cr@example.com', 'sales_channel': channel}]
                order = self.order(['OLD-QTN'])
                self.set_channel(order)
                self.assertEqual(order.sales_channel, 'Contract Research')

    def test_any_cr_quotation_takes_precedence(self):
        self.quotations = [
            {'sales_manager': 'sales@example.com'},
            {'sales_manager': 'cr@example.com'},
        ]
        order = self.order(['SALES-QTN', 'CR-QTN'], channel=None)
        self.set_channel(order)
        self.assertEqual(order.sales_channel, 'Contract Research')

    def test_duplicate_links_are_queried_once(self):
        self.quotations = [{'sales_manager': 'cr@example.com'}]
        self.set_channel(self.order(['CR-QTN', 'CR-QTN', None, '']))
        self.frappe.db.get_all.assert_any_call(
            'Quotation', filters={'name': ['in', ['CR-QTN']]}, fields=['sales_manager'])
        self.assertEqual(self.frappe.db.get_all.call_count, 3)

    def test_orders_without_quotation_are_unchanged(self):
        for channel in (None, 'Sales', 'Webshop', 'Contract Research'):
            order = self.order([None, ''], channel)
            self.set_channel(order)
            self.assertEqual(order.sales_channel, channel)
        self.frappe.db.get_all.assert_not_called()

    def test_non_cr_quotation_preserves_existing_channel(self):
        self.quotations = [{'sales_manager': 'sales@example.com'}]
        for channel in (None, 'Sales', 'Webshop', 'Contract Research'):
            order = self.order(['SALES-QTN'], channel)
            self.set_channel(order)
            self.assertEqual(order.sales_channel, channel)

    def test_missing_sales_manager_does_not_promote(self):
        self.quotations = [{'sales_manager': None}]
        order = self.order(['OLD-QTN'])
        self.set_channel(order)
        self.assertEqual(order.sales_channel, 'Sales')

    def test_missing_qm_assignment_does_not_promote(self):
        self.frappe.db.get_all.side_effect = lambda doctype, **kwargs: (
            [{'sales_manager': 'cr@example.com'}] if doctype == 'Quotation' else [])
        order = self.order(['OLD-QTN'])
        self.set_channel(order)
        self.assertEqual(order.sales_channel, 'Sales')

    def test_sales_order_validation_applies_rule(self):
        self.quotations = [{'sales_manager': 'cr@example.com'}]
        namespace = {
            'validate_sales_order_items': Mock(),
            'validate_contact_customer_consistency': Mock(),
        }
        load_functions('microsynth/microsynth/utils.py', {'validate_sales_order'}, namespace)
        module = SimpleNamespace(set_sales_order_sales_channel=self.set_channel)
        order = self.order(['OLD-QTN'])
        with patch.dict(sys.modules, {'microsynth.microsynth.quotation': module}):
            namespace['validate_sales_order'](order, 'validate')
        self.assertEqual(order.sales_channel, 'Contract Research')
        namespace['validate_sales_order_items'].assert_called_once_with(order, 'validate')
        namespace['validate_contact_customer_consistency'].assert_called_once_with(order, 'validate')

    def test_utils_does_not_import_quotation_during_initialization(self):
        tree = ast.parse((ROOT / 'microsynth/microsynth/utils.py').read_text())
        imports = [node.module for node in tree.body if isinstance(node, ast.ImportFrom)]
        self.assertNotIn('microsynth.microsynth.quotation', imports)


if __name__ == '__main__':
    unittest.main()