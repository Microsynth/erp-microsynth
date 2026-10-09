# -*- coding: utf-8 -*-
# Copyright (c) 2026, Microsynth
# For license information, please see license.txt

from __future__ import unicode_literals

import frappe
from frappe.model.document import Document

from microsynth.qms.doctype.competency_assignment.competency_assignment import update_competency_assignments_for_trainee


class CompetencyInstruction(Document):

	def validate(self):
		if not self.competency_assignment:
			frappe.throw("Competency Assignment is required. Please only use the button <b>Confirm Instruction</b> to create a new Competency Instruction.")

	def on_submit(self):
		if not self.trainee:
			return

		trainee_user = frappe.db.get_value("Employee", self.trainee, "user_id")
		if not trainee_user:
			return

		update_competency_assignments_for_trainee(trainee_user)

	def on_cancel(self):
		_clear_draft_assignment_links_for_instruction(self.name)


def _update_assignment_instruction_link(assignment_name, instruction_name):
	if not assignment_name:
		return

	assignment = frappe.get_doc("Competency Assignment", assignment_name)
	assignment.competency_instruction = instruction_name or ""
	assignment.db_update()


def _clear_draft_assignment_links_for_instruction(instruction_name):
	if not instruction_name:
		return

	draft_staff_profiles = frappe.get_all(
		"Staff Profile",
		filters={
			"docstatus": 0,
			"status": ["in", ["", "Draft"]],
		},
		fields=["name"],
	)
	if not draft_staff_profiles:
		return

	draft_profile_names = [row.get("name") for row in draft_staff_profiles if row.get("name")]
	if not draft_profile_names:
		return

	linked_assignments = frappe.get_all(
		"Competency Assignment",
		filters={
			"parenttype": "Staff Profile",
			"parent": ["in", draft_profile_names],
			"competency_instruction": instruction_name,
		},
		fields=["name"],
	)
	for assignment in linked_assignments:
		_update_assignment_instruction_link(assignment.get("name"), "")


@frappe.whitelist()
def has_submitted_instruction_for_assignment(competency_assignment):
	if not competency_assignment:
		return False
	return frappe.db.exists("Competency Instruction", {
		"competency_assignment": competency_assignment,
		"docstatus": 1
	})


@frappe.whitelist()
def get_linked_instruction_for_assignment(competency_assignment):
	if not competency_assignment:
		return None
	return frappe.db.get_value("Competency Instruction", {
		"competency_assignment": competency_assignment,
		"docstatus": 1
	}, "name")


@frappe.whitelist()
def get_staff_profile_parent_for_assignment(competency_assignment):
	if not competency_assignment:
		return None
	assignment = frappe.get_doc("Competency Assignment", competency_assignment)
	if not assignment:
		return None
	if assignment.parenttype == "Staff Profile":
		return assignment.parent
	return None


@frappe.whitelist()
def get_assignment_refresh_data(competency_assignment):
	if not competency_assignment:
		return {}
	assignment = frappe.get_doc("Competency Assignment", competency_assignment)
	if not assignment:
		return {}
	if assignment.parenttype and assignment.parent:
		parent = frappe.get_doc(assignment.parenttype, assignment.parent)
		parent.check_permission("read")
	return {
		"status": assignment.status,
		"competency_instruction": assignment.competency_instruction,
	}


@frappe.whitelist()
def create_and_submit_instruction(instructor, date, trainee, competency_assignment, remarks=None):
	if not instructor or not date or not trainee or not competency_assignment:
		frappe.throw("Instructor, date, trainee and competency assignment are required.")

	if has_submitted_instruction_for_assignment(competency_assignment):
		frappe.throw("A submitted Competency Instruction already exists for this Competency Assignment.")

	doc = frappe.get_doc({
		"doctype": "Competency Instruction",
		"instructor": instructor,
		"date": date,
		"trainee": trainee,
		"competency_assignment": competency_assignment,
		"remarks": remarks or ""
	})
	doc.insert(ignore_permissions=True)
	doc.submit()

	_update_assignment_instruction_link(competency_assignment, doc.name)
	return doc.name
