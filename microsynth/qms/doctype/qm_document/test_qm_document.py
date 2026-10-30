# -*- coding: utf-8 -*-
# Copyright (c) 2024, Microsynth, libracore and contributors and Contributors
# See license.txt
from __future__ import unicode_literals

import unittest
from unittest.mock import Mock, call, patch

from microsynth.qms.doctype.competency import competency
from microsynth.qms.doctype.qm_document import qm_document


class TestQMDocument(unittest.TestCase):
	def setUp(self):
		self.frappe = Mock()
		frappe_patch = patch.object(qm_document, "frappe", self.frappe)
		frappe_patch.start()
		self.addCleanup(frappe_patch.stop)
		self.document = Mock(status="Valid")
		self.document.name = "SOP 1.1.01.001-01"
		self.frappe.get_doc.return_value = self.document

	def test_invalid_status_invalidates_competencies_before_commit(self):
		with patch.object(competency, "invalidate_competencies_for_qm_document") as invalidate:
			invalidate.side_effect = lambda name: self.frappe.db.commit.assert_not_called()
			qm_document.update_status.__wrapped__(self.document.name, "Invalid")
		invalidate.assert_called_once_with(self.document.name)
		self.assertEqual(self.document.status, "Invalid")
		self.document.save.assert_called_once_with()
		self.frappe.db.commit.assert_called_once_with()
		self.frappe.db.savepoint.assert_called_once_with("qm_document_competencies")
		self.frappe.db.rollback.assert_not_called()
		self.frappe.log_error.assert_not_called()

	def test_valid_status_renews_competencies_before_commit(self):
		self.document.status = "Released"
		with patch.object(competency, "renew_competencies_for_qm_document") as renew:
			renew.side_effect = lambda name: self.frappe.db.commit.assert_not_called()
			qm_document.update_status.__wrapped__(self.document.name, "Valid")
		renew.assert_called_once_with(self.document.name)
		self.assertEqual(self.document.status, "Valid")
		self.frappe.db.commit.assert_called_once_with()

	def test_failed_competency_update_still_commits_qm_status(self):
		for previous_status, status, handler in (
			("Valid", "Invalid", "invalidate_competencies_for_qm_document"),
			("Released", "Valid", "renew_competencies_for_qm_document"),
		):
			with self.subTest(status=status):
				self.frappe.reset_mock()
				self.document.reset_mock()
				self.document.status = previous_status
				self.frappe.get_traceback.return_value = "Competency update traceback"
				self.frappe.db.savepoint.side_effect = lambda name: self.document.save.assert_called_once_with()
				with patch.object(competency, handler, side_effect=ValueError("Competency update failed")):
					qm_document.update_status.__wrapped__(self.document.name, status)
				self.assertEqual(self.document.status, status)
				self.frappe.db.savepoint.assert_called_once_with("qm_document_competencies")
				self.frappe.db.rollback.assert_called_once_with(save_point="qm_document_competencies")
				self.frappe.log_error.assert_called_once()
				self.frappe.db.commit.assert_called_once_with()
				self.assertEqual(self.frappe.db.mock_calls, [
					call.savepoint("qm_document_competencies"),
					call.rollback(save_point="qm_document_competencies"),
					call.commit(),
				])
				message = self.frappe.log_error.call_args.kwargs["message"]
				for detail in (self.document.name, status, "Competency update traceback"):
					self.assertIn(detail, message)

	def test_qm_document_save_errors_are_not_suppressed(self):
		self.document.save.side_effect = ValueError("QM Document save failed")
		with patch.object(competency, "invalidate_competencies_for_qm_document") as invalidate:
			with self.assertRaisesRegex(ValueError, "QM Document save failed"):
				qm_document.update_status.__wrapped__(self.document.name, "Invalid")
		invalidate.assert_not_called()
		self.frappe.db.savepoint.assert_not_called()
		self.frappe.db.rollback.assert_not_called()
		self.frappe.db.commit.assert_not_called()

	def test_same_status_does_not_repeat_competency_renewal(self):
		with patch.object(competency, "renew_competencies_for_qm_document") as renew:
			qm_document.update_status.__wrapped__(self.document.name, "Valid")
		renew.assert_not_called()
		self.frappe.db.commit.assert_not_called()
