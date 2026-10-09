# -*- coding: utf-8 -*-
# Copyright (c) 2024, Microsynth, libracore and contributors and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.model.document import Document

from microsynth.qms.doctype.competency_assignment.competency_assignment import update_competency_assignments_for_trainee


class QMTrainingCourse(Document):
	def before_submit(self):
		missing = _get_missing_participant_outcomes(self.participants)
		if missing:
			frappe.throw(
				_("Please set an Outcome for all participants before submitting. Missing Outcome: {0}").format(", ".join(missing)),
				title=_("Missing participant outcomes"),
			)
		trainer_error = _is_missing_trainer(self)
		if trainer_error:
			frappe.throw(_(trainer_error), title=_("Missing trainer"))

	def on_submit(self):
		if not self.training_template:
			return

		passed_users = {
			participant.user
			for participant in (self.participants or [])
			if participant.user and participant.outcome == "Passed"
		}
		for user in sorted(passed_users):
			update_competency_assignments_for_trainee(user, self.doctype, self.name)


def _is_missing_trainer(course):
	if not getattr(course, "int_ext", None):
		return "Trainer type is required."
	if course.int_ext == "Internal":
		if not getattr(course, "internal_trainer", None):
			return "Please select an Internal Trainer before submitting."
		return None
	if course.int_ext == "External":
		if not getattr(course, "external_trainer", None):
			return "Please enter an External Trainer before submitting."
		return None
	return "Please select a valid Trainer type before submitting."


def _get_missing_participant_outcomes(participants):
	missing = []
	for participant in participants or []:
		if getattr(participant, "outcome", None) not in (None, ""):
			continue
		user = getattr(participant, "user", None)
		if user:
			missing.append(user)
			continue
		idx = getattr(participant, "idx", None)
		missing.append(f"Row {idx}" if idx else "Unnamed participant")
	return missing


@frappe.whitelist()
def get_proposed_participants(training_template, docname=None):
	"""Return readable employees with outstanding competencies for this template."""
	if docname:
		course = frappe.get_doc("QM Training Course", docname)
		course.check_permission("write")
		if course.docstatus != 0:
			frappe.throw(_("Participants can only be proposed for a draft QM Training Course."))
		if course.training_template != training_template:
			frappe.throw(_("The Training Template has changed. Please reload the QM Training Course."))
	elif not frappe.has_permission("QM Training Course", "create"):
		frappe.throw(_("Not permitted to create a QM Training Course."), frappe.PermissionError)

	if not training_template:
		return []
	frappe.get_doc("QM Training Template", training_template).check_permission("read")

	training_links = frappe.get_all(
		"QM Training Template Link",
		filters={
			"parenttype": "Competency",
			"parentfield": "trainings",
			"training_template": training_template,
		},
		fields=["parent"],
	)
	competency_names = sorted({row.parent for row in training_links})
	if not competency_names:
		return []

	assignments = frappe.get_all(
		"Competency Assignment",
		filters={
			"parenttype": "Staff Profile",
			"parentfield": "competencies",
			"competency": ["in", competency_names],
		},
		fields=["parent", "status"],
	)
	# Include empty statuses as well as Planned; only Achieved is excluded.
	profile_names = sorted({row.parent for row in assignments if row.status != "Achieved"})
	if not profile_names:
		return []

	profiles = frappe.get_list(
		"Staff Profile",
		filters={"name": ["in", profile_names], "docstatus": ["!=", 2]},
		fields=["employee", "status"],
		limit_page_length=0,
	)
	employee_names = sorted({row.employee for row in profiles if row.employee and row.status != "Cancelled"})
	if not employee_names:
		return []

	employees = frappe.get_list(
		"Employee",
		filters={"name": ["in", employee_names], "user_id": ["is", "set"]},
		fields=["name", "employee_name", "user_id"],
		order_by="employee_name asc, name asc",
		limit_page_length=0,
	)
	participants = []
	seen_users = set()
	for employee in employees:
		if not employee.user_id or employee.user_id in seen_users:
			continue
		seen_users.add(employee.user_id)
		participants.append({
			"employee": employee.name,
			"employee_name": employee.employee_name,
			"user": employee.user_id,
		})
	# The form excludes current participants, including unsaved additions/removals.
	return participants
