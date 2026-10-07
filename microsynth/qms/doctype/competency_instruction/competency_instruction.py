# -*- coding: utf-8 -*-
# Copyright (c) 2026, Microsynth, libracore and contributors and contributors
# For license information, please see license.txt

from __future__ import unicode_literals

import frappe
from frappe.model.document import Document

class CompetencyInstruction(Document):

	def validate(self):
		if not self.competency_assignment:
			frappe.throw("Competency Assignment is required. Please only use the button <b>Confirm Instruction</b> to create a new Competency Instruction.")


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

	frappe.db.set_value("Competency Assignment", competency_assignment, "competency_instruction", doc.name)
	return doc.name
