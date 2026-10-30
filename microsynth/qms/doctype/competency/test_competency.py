# -*- coding: utf-8 -*-
# Copyright (c) 2026, Microsynth
# See license.txt
from __future__ import unicode_literals

import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from microsynth.qms.doctype.competency import competency


class TestCompetency(unittest.TestCase):
	def setUp(self):
		frappe_patch = patch.object(competency, "frappe", Mock())
		frappe_patch.start()
		self.addCleanup(frappe_patch.stop)
		competency.frappe.bold.side_effect = lambda text: text
		translation_patch = patch.object(competency, "_", side_effect=lambda text: text)
		translation_patch.start()
		self.addCleanup(translation_patch.stop)
		self.source = SimpleNamespace(
			name="COMP-0001", docstatus=1, status="Invalid",
			qm_documents=[SimpleNamespace(qm_document="SOP 1.1.01.001-01", title="Old title")],
		)
		self.versions = ("COMP-0001", 0, [(0, "COMP-0001", "Invalid", 1)])

	def test_invalidation_preserves_links_and_does_not_touch_assignments(self):
		source = Mock(docstatus=1, status="Valid")
		source.name = "COMP-0001"
		with patch.object(competency.frappe, "get_all", return_value=[{"parent": source.name}] * 2), \
				patch.object(competency.frappe, "get_doc", return_value=source), \
				patch.object(competency, "_create_qm_document_replacement") as renew:
			competency.invalidate_competencies_for_qm_document("SOP 1.1.01.001-01")

		self.assertEqual(source.status, "Invalid")
		source.save.assert_called_once_with(ignore_permissions=True)
		source.db_set.assert_not_called()
		source.add_comment.assert_called_once()
		self.assertIn("SOP 1.1.01.001-01", source.add_comment.call_args.args[1])
		renew.assert_called_once_with(source)

	def test_replacement_is_submitted_with_new_document_version(self):
		new_doc = Mock()
		new_doc.qm_documents = [SimpleNamespace(qm_document="SOP 1.1.01.001-01", title="Old title")]
		with patch.object(competency, "get_versioned_documents", return_value=self.versions), \
				patch.object(competency.frappe.db, "get_value", return_value="Invalid"), \
				patch.object(competency, "get_valid_version", return_value={"name": "SOP 1.1.01.001-02", "title": "New title"}), \
				patch.object(competency, "_copy_competency_version", return_value=new_doc) as copy_version:
			self.assertIs(competency._create_qm_document_replacement(self.source), new_doc)

		copy_version.assert_called_once_with(self.source, "COMP-0001-1")
		self.assertEqual(new_doc.qm_documents[0].qm_document, "SOP 1.1.01.001-02")
		self.assertEqual(new_doc.qm_documents[0].title, "New title")
		self.assertEqual(self.source.qm_documents[0].qm_document, "SOP 1.1.01.001-01")
		new_doc.insert.assert_called_once_with(ignore_permissions=True)
		new_doc.submit.assert_called_once_with()
		self.assertTrue(new_doc.flags.ignore_permissions)

	def test_no_replacement_without_valid_qm_document(self):
		with patch.object(competency, "get_versioned_documents", return_value=self.versions), \
				patch.object(competency.frappe.db, "get_value", return_value="Invalid"), \
				patch.object(competency, "get_valid_version", return_value=None), \
				patch.object(competency, "_copy_competency_version") as copy_version:
			self.assertIsNone(competency._create_qm_document_replacement(self.source))
		copy_version.assert_not_called()

	def test_newer_submitted_version_prevents_duplicate_replacement(self):
		versions = ("COMP-0001", 0, self.versions[2] + [(1, "COMP-0001-1", "Valid", 1)])
		with patch.object(competency, "get_versioned_documents", return_value=versions), \
				patch.object(competency, "_copy_competency_version") as copy_version:
			self.assertIsNone(competency._create_qm_document_replacement(self.source))
		copy_version.assert_not_called()

	def test_previous_version_is_invalidated_without_revalidating_its_qm_links(self):
		versions = ("COMP-0001", 1, [(0, "COMP-0001", "Valid", 1), (1, "COMP-0001-1", "Valid", 1)])
		previous = Mock()
		with patch.object(competency, "get_versioned_documents", return_value=versions), \
				patch.object(competency.frappe, "get_doc", return_value=previous):
			competency.invalidate_previous_versions("COMP-0001-1")
		self.assertEqual(previous.status, "Invalid")
		previous.save.assert_called_once_with(ignore_permissions=True)
		previous.db_set.assert_not_called()

	def test_invalidating_document_creates_replacement_in_same_call(self):
		self.source.status = "Valid"
		self.source.save = Mock()
		self.source.add_comment = Mock()
		new_doc = Mock()
		new_doc.qm_documents = [SimpleNamespace(qm_document="SOP 1.1.01.001-01")]
		with patch.object(competency.frappe, "get_all", return_value=[{"parent": self.source.name}]), \
				patch.object(competency.frappe, "get_doc", return_value=self.source), \
				patch.object(competency, "get_versioned_documents", return_value=self.versions), \
				patch.object(competency.frappe.db, "get_value", return_value="Invalid"), \
				patch.object(competency, "get_valid_version", return_value={"name": "SOP 1.1.01.001-02", "title": "New title"}), \
				patch.object(competency, "_copy_competency_version", return_value=new_doc):
			competency.invalidate_competencies_for_qm_document("SOP 1.1.01.001-01")
		self.assertEqual(self.source.status, "Invalid")
		self.source.save.assert_called_once_with(ignore_permissions=True)
		new_doc.submit.assert_called_once_with()
		self.assertEqual(new_doc.qm_documents[0].qm_document, "SOP 1.1.01.001-02")

	def test_later_valid_document_retries_invalid_competency_without_duplicates(self):
		links = [
			{"parent": self.source.name, "qm_document": "SOP 1.1.01.001-01"},
			{"parent": self.source.name, "qm_document": "SOP 1.1.01.001-01"},
			{"parent": "UNRELATED", "qm_document": "SOP 1.1.01.001-extra-01"},
		]
		with patch.object(competency.frappe, "get_all", return_value=links), \
				patch.object(competency.frappe, "get_doc", return_value=self.source) as get_doc, \
				patch.object(competency, "_create_qm_document_replacement") as renew:
			competency.renew_competencies_for_qm_document("SOP 1.1.01.001-02")
		get_doc.assert_called_once_with("Competency", self.source.name)
		renew.assert_called_once_with(self.source)

	def test_all_invalid_qm_documents_need_valid_replacements(self):
		self.source.qm_documents.append(SimpleNamespace(qm_document="FORM 1.1.0001-01"))
		with patch.object(competency, "get_versioned_documents", return_value=self.versions), \
				patch.object(competency.frappe.db, "get_value", return_value="Invalid"), \
				patch.object(competency, "get_valid_version", side_effect=[{"name": "SOP 1.1.01.001-02"}, None]), \
				patch.object(competency, "_copy_competency_version") as copy_version:
			self.assertIsNone(competency._create_qm_document_replacement(self.source))
		copy_version.assert_not_called()

	def test_invalid_submitted_competency_keeps_historical_document_links(self):
		with patch.object(competency, "validate_prerequisite_types"), \
				patch.object(competency, "validate_linked_qm_documents") as validate_documents:
			competency.Competency.validate(self.source)
		validate_documents.assert_not_called()

	def test_draft_still_validates_qm_links_even_with_invalid_status(self):
		self.source.docstatus = 0
		with patch.object(competency, "validate_prerequisite_types"), \
				patch.object(competency, "validate_linked_qm_documents") as validate_documents:
			competency.Competency.validate(self.source)
		validate_documents.assert_called_once_with(self.source)

	def test_existing_draft_is_preserved_and_next_available_suffix_is_used(self):
		versions = ("COMP-0001", 0, self.versions[2] + [(1, "COMP-0001-1", "Draft", 0)])
		new_doc = Mock(qm_documents=[])
		with patch.object(competency, "get_versioned_documents", return_value=versions), \
				patch.object(competency.frappe.db, "get_value", return_value="Invalid"), \
				patch.object(competency, "get_valid_version", return_value={"name": "SOP 1.1.01.001-02"}), \
				patch.object(competency, "_copy_competency_version", return_value=new_doc) as copy_version:
			competency._create_qm_document_replacement(self.source)
		copy_version.assert_called_once_with(self.source, "COMP-0001-2")
		new_doc.submit.assert_called_once_with()

	def test_older_draft_cannot_be_submitted_after_automatic_replacement(self):
		versions = ("COMP-0001", 1, [(1, "COMP-0001-1", "Draft", 0), (2, "COMP-0001-2", "Valid", 1)])
		draft = SimpleNamespace(name="COMP-0001-1", status="Draft")
		with patch.object(competency, "get_versioned_documents", return_value=versions), \
				patch.object(competency.frappe, "throw", side_effect=ValueError):
			with self.assertRaises(ValueError):
				competency.Competency.before_submit(draft)
		self.assertEqual(draft.status, "Draft")

	def test_newest_draft_can_be_submitted_despite_cancelled_newer_version(self):
		versions = ("COMP-0001", 1, [(1, "COMP-0001-1", "Draft", 0), (2, "COMP-0001-2", "Invalid", 2)])
		draft = SimpleNamespace(name="COMP-0001-1", status="Draft")
		with patch.object(competency, "get_versioned_documents", return_value=versions):
			competency.Competency.before_submit(draft)
		self.assertEqual(draft.status, "Valid")
