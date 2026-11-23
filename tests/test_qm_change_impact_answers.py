import ast
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock


ROOT = Path(__file__).resolve().parents[1]
STATES = ('Assessment & Classification', 'Planning', 'Implementation')


class TestQMChangeImpactAnswers(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = ROOT / 'microsynth/qms/doctype/qm_change/qm_change.py'
        tree = ast.parse(path.read_text())
        nodes = [node for node in tree.body if (
            isinstance(node, ast.ClassDef) and node.name == 'QMChange'
        ) or (isinstance(node, ast.FunctionDef) and node.name == '_references')]
        cls.frappe = Mock()
        cls.frappe.whitelist.return_value = lambda function: function
        cls.frappe.PermissionError = PermissionError
        cls.frappe.throw.side_effect = lambda message, error: (_ for _ in ()).throw(error(message))
        cls.has_role = Mock()
        namespace = {'Document': object, 'frappe': cls.frappe, 'user_has_role': cls.has_role}
        exec(compile(ast.Module(body=nodes, type_ignores=[]), str(path), 'exec'), namespace)
        cls.change_class = namespace['QMChange']
        document_path = ROOT.parent / 'frappe/frappe/model/document.py'
        document_tree = ast.parse(document_path.read_text())
        document_class = next(node for node in document_tree.body
                      if isinstance(node, ast.ClassDef) and node.name == 'Document')
        dispatcher = next(node for node in document_class.body
                  if isinstance(node, ast.FunctionDef) and node.name == 'run_before_save_methods')
        exec(compile(ast.Module(body=[dispatcher], type_ignores=[]), str(document_path), 'exec'), namespace)
        cls.change_class.run_before_save_methods = namespace['run_before_save_methods']

    def setUp(self):
        self.frappe.reset_mock()
        self.frappe.session.user = 'creator@example.com'
        self.has_role.reset_mock()
        self.has_role.return_value = False

    def change(self, status, answer='yes', old_status=None, old_answer='no'):
        old = SimpleNamespace(status=old_status or status, created_by='creator@example.com')
        old.impact = [{'qm_change_impact': 'Quality', 'impact_answer': old_answer}]
        old.get = lambda field: getattr(old, field, None)
        change = self.change_class()
        change.status = status
        change.created_by = 'creator@example.com'
        change.impact = [{'qm_change_impact': 'Quality', 'impact_answer': answer}]
        change.get = lambda field: getattr(change, field, None)
        change.get_doc_before_save = lambda: old
        return change

    def test_creator_cannot_change_answers_on_save_or_update(self):
        for status in STATES:
            for hook in ('validate', 'before_update_after_submit'):
                for old_answer, answer in (('no', 'yes'), ('yes', 'no'), ('', 'yes'), ('yes', '')):
                    with self.subTest(status=status, hook=hook, old_answer=old_answer, answer=answer):
                        change = self.change(status, answer=answer, old_answer=old_answer)
                        with self.assertRaises(PermissionError):
                            getattr(change, hook)()
                        self.has_role.assert_called_with('creator@example.com', 'QAU')

    def test_qau_can_change_answers_on_save_or_update(self):
        self.frappe.session.user = 'qau@example.com'
        self.has_role.return_value = True
        for status in STATES:
            for hook in ('validate', 'before_update_after_submit'):
                with self.subTest(status=status, hook=hook):
                    change = self.change(status)
                    getattr(change, hook)()
                    self.assertEqual(change.impact[0]['impact_answer'], 'yes')
                    self.has_role.assert_called_with('qau@example.com', 'QAU')

    def test_creator_can_read_answers_and_edit_other_fields(self):
        for status in STATES:
            for hook in ('validate', 'before_update_after_submit'):
                with self.subTest(status=status, hook=hook):
                    change = self.change(status, answer='no')
                    change.closure_comments = 'Updated comment'
                    getattr(change, hook)()
                    self.assertEqual(change.impact[0]['impact_answer'], 'no')
        self.has_role.assert_not_called()

    def test_status_changes_cannot_bypass_answer_guard(self):
        for status in STATES:
            for old_status, new_status in ((status, 'Draft'), ('Created', status)):
                with self.subTest(old_status=old_status, new_status=new_status):
                    with self.assertRaises(PermissionError):
                        self.change(new_status, old_status=old_status).validate()

    def test_frappe_save_dispatcher_enforces_answer_guard(self):
        for status in STATES:
            for action in ('save', 'submit', 'update_after_submit'):
                for is_qau in (False, True):
                    with self.subTest(status=status, action=action, is_qau=is_qau):
                        self.has_role.return_value = is_qau
                        self.frappe.session.user = 'qau@example.com' if is_qau else 'creator@example.com'
                        change = self.change(status)
                        change._action = action
                        change.flags = SimpleNamespace(ignore_validate=False)
                        change.reset_seen = Mock()
                        change.set_title_field = Mock()
                        change.run_method = lambda method: getattr(change, method, lambda: None)()
                        if is_qau:
                            change.run_before_save_methods()
                        else:
                            with self.assertRaises(PermissionError):
                                change.run_before_save_methods()

    def test_answered_rows_cannot_be_removed_or_replaced(self):
        for status in STATES:
            for replacement in ([], [{'qm_change_impact': 'Safety', 'impact_answer': 'no'}]):
                with self.subTest(status=status, replacement=replacement):
                    change = self.change(status, answer='no')
                    change.impact = replacement
                    with self.assertRaises(PermissionError):
                        change.before_update_after_submit()

    def test_blank_rows_and_reordering_do_not_change_answers(self):
        for status in STATES:
            with self.subTest(status=status):
                change = self.change(status, answer='no')
                change.impact.insert(0, {'qm_change_impact': 'Safety', 'impact_answer': ''})
                change.validate()
                change.impact.reverse()
                change.before_update_after_submit()

    def test_duplicate_impact_rows_cannot_swap_answers(self):
        for status in STATES:
            with self.subTest(status=status):
                change = self.change(status, answer='no')
                old = change.get_doc_before_save()
                old.impact = [
                    {'name': 'row-1', 'qm_change_impact': 'Quality', 'impact_answer': 'yes'},
                    {'name': 'row-2', 'qm_change_impact': 'Quality', 'impact_answer': 'no'},
                ]
                change.impact = [dict(row) for row in reversed(old.impact)]
                change.before_update_after_submit()
                for row in change.impact:
                    row['impact_answer'] = 'no' if row['impact_answer'] == 'yes' else 'yes'
                with self.assertRaises(PermissionError):
                    change.before_update_after_submit()

    def test_new_document_with_answers_is_guarded(self):
        for status in STATES:
            with self.subTest(status=status):
                change = self.change(status)
                change.get_doc_before_save = lambda: None
                with self.assertRaises(PermissionError):
                    change.validate()

    def test_unaffected_states_keep_existing_behavior(self):
        for status in ('Draft', 'Created', 'Trial', 'Completed'):
            with self.subTest(status=status):
                self.change(status).validate()
        self.has_role.assert_not_called()


if __name__ == '__main__':
    unittest.main()