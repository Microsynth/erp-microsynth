# -*- coding: utf-8 -*-
# Copyright (c) 2026, Microsynth
# See license.txt
from __future__ import unicode_literals

import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from frappe import _dict

from microsynth.qms.doctype.staff_profile import staff_profile


class TestStaffProfile(unittest.TestCase):
	def setUp(self):
		self.frappe = Mock()
		self.frappe.bold.side_effect = lambda text: text
		self.frappe.throw.side_effect = ValueError
		frappe_patch = patch.object(staff_profile, "frappe", self.frappe)
		frappe_patch.start()
		self.addCleanup(frappe_patch.stop)
		translation_patch = patch.object(staff_profile, "_", side_effect=lambda text: text)
		translation_patch.start()
		self.addCleanup(translation_patch.stop)
		self.assignment = _dict(
			idx=1, competency="COMP-0001", competency_title="Old title", status="Achieved",
			competency_achieved_on="2025-01-01", competency_instruction="INSTRUCTION-1",
			responsibility_role="Main", level="Expert",
		)
		self.profile = SimpleNamespace(employee="EMP-1", competencies=[self.assignment])
		self.frappe.db.get_value.side_effect = lambda doctype, name, fields, **kwargs: (
			"employee@example.com" if doctype == "Employee" else
			"Updated title" if fields == "title" else {"status": "Invalid", "docstatus": 1}
		)
		self.versions = ("COMP-0001", 0, [
			(0, "COMP-0001", "Invalid", 1),
			(1, "COMP-0001-1", "Valid", 1),
			(2, "COMP-0001-2", "Valid", 1),
			(3, "COMP-0001-3", "Draft", 0),
			(4, "COMP-0001-4", "Valid", 2),
		])

	def test_invalid_assignment_uses_latest_valid_submitted_version(self):
		with patch.object(staff_profile, "get_versioned_documents", return_value=self.versions), \
				patch.object(staff_profile, "get_competency_requirement_details", return_value={"missing": ["New signature required"]}) as requirements:
			staff_profile._replace_invalid_competency_versions(self.profile)

		self.assertEqual(self.assignment.competency, "COMP-0001-2")
		self.assertEqual(self.assignment.competency_title, "Updated title")
		self.assertEqual(self.assignment.status, "Planned")
		self.assertIsNone(self.assignment.competency_achieved_on)
		self.assertEqual(self.assignment.competency_instruction, "")
		self.assertEqual(self.assignment.responsibility_role, "Main")
		self.assertEqual(self.assignment.level, "Expert")
		requirements.assert_called_once_with("COMP-0001-2", "employee@example.com", employee="EMP-1")

	def test_replacement_is_achieved_when_all_new_requirements_are_met(self):
		with patch.object(staff_profile, "get_versioned_documents", return_value=self.versions), \
				patch.object(staff_profile, "get_competency_requirement_details", return_value={"missing": []}), \
				patch.object(staff_profile, "now_datetime", return_value="2026-10-30"):
			staff_profile._replace_invalid_competency_versions(self.profile)
		self.assertEqual(self.assignment.status, "Achieved")
		self.assertEqual(self.assignment.competency_achieved_on, "2026-10-30")

	def test_valid_assignment_is_not_replaced_or_reset(self):
		self.frappe.db.get_value.return_value = {"status": "Valid", "docstatus": 1}
		self.frappe.db.get_value.side_effect = None
		with patch.object(staff_profile, "get_versioned_documents") as get_versions:
			staff_profile._replace_invalid_competency_versions(self.profile)
		get_versions.assert_not_called()
		self.assertEqual(self.assignment.competency, "COMP-0001")
		self.assertEqual(self.assignment.status, "Achieved")
		self.assertEqual(self.assignment.competency_achieved_on, "2025-01-01")

	def test_no_valid_replacement_retains_invalid_link_and_save_error(self):
		versions = ("COMP-0001", 0, [(0, "COMP-0001", "Invalid", 1), (1, "COMP-0001-1", "Draft", 0)])
		with patch.object(staff_profile, "get_versioned_documents", return_value=versions):
			staff_profile._replace_invalid_competency_versions(self.profile)
		self.assertEqual(self.assignment.competency, "COMP-0001")
		self.frappe.get_all.return_value = [{"name": "COMP-0001", "status": "Invalid", "docstatus": 1}]
		with self.assertRaises(ValueError):
			staff_profile._throw_if_invalid_competency_versions(self.profile.competencies)

	def test_new_version_refreshes_assignments_before_insert(self):
		current = Mock(docstatus=1, status="Valid")
		current.name = "STAFF-0001"
		new_doc = Mock()
		new_doc.name = "STAFF-0001-1"
		new_doc.competencies = [self.assignment]
		self.frappe.get_doc.return_value = current
		self.frappe.copy_doc.return_value = new_doc
		self.frappe.db.exists.return_value = False
		self.frappe.session.user = "hr@example.com"
		with patch.object(staff_profile, "get_versioned_documents", return_value=("STAFF-0001", 0, [])), \
				patch.object(staff_profile, "_replace_invalid_competency_versions") as refresh:
			new_doc.insert.side_effect = lambda: refresh.assert_called_once_with(new_doc)
			result = staff_profile.create_new_version.__wrapped__(current.name)
		self.assertEqual(result, {"name": "STAFF-0001-1"})
		self.assertEqual(new_doc.status, "Draft")
		self.assertEqual(self.assignment.competency_instruction, "")
		new_doc.insert.assert_called_once_with()
