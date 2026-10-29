# Copyright (c) 2026, Microsynth
# For license information, please see license.txt

from __future__ import unicode_literals

from html import escape

import frappe
from frappe import _
from frappe.utils import get_url_to_form

from microsynth.qms.doctype.competency_assignment.competency_assignment import (
	get_competency_requirement_details,
)
from microsynth.qms.versioning import get_versioned_documents


def execute(filters=None):
	filters = filters or {}
	employees = get_employees(filters)
	assignments = get_assignments(employees)
	competencies = get_competencies(filters)
	return get_columns(employees), get_data(employees, competencies, assignments)


@frappe.whitelist()
def get_cell_details(assignment_names=None):
	if not assignment_names:
		return {"title": _("Competency Details"), "html": "<p>{0}</p>".format(_("No assignment selected."))}

	if isinstance(assignment_names, str):
		# frappe.call serializes array arguments as JSON before sending them.
		if assignment_names.lstrip().startswith("["):
			assignment_names = frappe.parse_json(assignment_names)
		else:
			assignment_names = [name.strip() for name in assignment_names.split(",") if name.strip()]
	assignment_names = [name for name in (assignment_names or []) if name]
	if not assignment_names:
		return {"title": _("Competency Details"), "html": "<p>{0}</p>".format(_("No assignment selected."))}

	sections = []
	for assignment_name in assignment_names:
		if not frappe.db.exists("Competency Assignment", assignment_name):
			continue
		assignment = frappe.get_doc("Competency Assignment", assignment_name)
		competency = frappe.get_doc("Competency", assignment.competency) if assignment.competency else None
		employee_name = None
		if assignment.parenttype == "Staff Profile" and assignment.parent:
			employee_name = frappe.db.get_value("Staff Profile", assignment.parent, "employee")
		trainee = frappe.db.get_value("Employee", employee_name, "user_id") if employee_name else None
		details = get_competency_requirement_details(assignment.competency, trainee, employee_name)
		sections.append(_build_assignment_details_html(assignment, competency, details))

	if not sections:
		return {"title": _("Competency Details"), "html": "<p>{0}</p>".format(_("No competency details available."))}

	return {
		"title": _("Competency Details"),
		"html": "<div>{0}</div>".format("".join(sections)),
	}


def _detail_item(label, value, doctype=None, name=None):
	text = escape(str(value or _('Not set')))
	if doctype and (name or value):
		# Let the installed Frappe version choose desk#Form/... versus /app/....
		url = escape(get_url_to_form(doctype, name or value), quote=True)
		text = f'<a href="{url}" target="_blank" rel="noopener noreferrer">{text}</a>'
	return f"<li><strong>{escape(str(label))}:</strong> {text}</li>"


def _build_assignment_details_html(assignment, competency, details):
	title = escape(str(competency.title or assignment.competency))
	items = [
		_detail_item(_("Competency"), assignment.competency, "Competency"),
		_detail_item(_("Status"), _(assignment.status)),
		_detail_item(_("Staff Profile"), assignment.parent, "Staff Profile"),
	]
	# Include references even when their requirements have not been fulfilled yet.
	for row in competency.qm_documents or []:
		if row.qm_document:
			items.append(_detail_item(_("Required QM Document"), row.qm_document, "QM Document"))
	for row in competency.trainings or []:
		if row.training_template:
			items.append(_detail_item(_("QM Training Template"), row.training_template, "QM Training Template"))
	if assignment.status == "Achieved":
		items.append(_detail_item(_("Competency Achieved On"), assignment.competency_achieved_on))

	for instruction in details["instructions"]:
		instructor = frappe.db.get_value("User", instruction.get("instructor"), "full_name") or instruction.get("instructor")
		items.append(_detail_item(_("Competency Instruction"), instruction.get("name"), "Competency Instruction"))
		items.append(_detail_item(_("Instructor"), instructor))
		items.append(_detail_item(_("Date"), instruction.get("date")))
	for course in details["courses"]:
		trainer = course.get("external_trainer") if course.get("int_ext") == "External" else course.get("internal_trainer")
		if course.get("int_ext") != "External" and trainer:
			trainer = frappe.db.get_value("User", trainer, "full_name") or trainer
		items.append(_detail_item(_("QM Training Course"), course.get("name"), "QM Training Course"))
		items.append(_detail_item(_("Trainer"), trainer))
		items.append(_detail_item(_("Date"), course.get("date")))
	for record in details["records"]:
		document_name = record.get("document_name")
		items.append(_detail_item(_("QM Training Record"), record.get("name"), "QM Training Record"))
		items.append(_detail_item(_("Document Name"), document_name, "QM Document"))
		items.append(_detail_item(_("QM Document Title"), frappe.db.get_value("QM Document", document_name, "title") or document_name, "QM Document", document_name))
		items.append(_detail_item(_("Signed on"), record.get("signed_on")))

	warning = ""
	if details["missing"]:
		items.extend(_detail_item(_("Missing requirement"), reason) for reason in details["missing"])
		if competency.status == "Invalid":
			warning = _("This Competency is Invalid, but can be achieved.")
			base_name, current_suffix, versions = get_versioned_documents("Competency", assignment.competency)
			newer_valid_versions = [
				name for suffix, name, status, docstatus in versions
				if suffix > current_suffix and status == "Valid" and docstatus == 1
			]
			if newer_valid_versions:
				warning += " " + _("A newer submitted, Valid version of this Competency is available; see the link below.")
				items.append(_detail_item(_("Newer Valid Competency"), newer_valid_versions[-1], "Competency"))
			else:
				warning += " " + _("No newer submitted, Valid version of this Competency was found.")
		elif assignment.status == "Achieved":
			warning = _("Data inconsistency: this assignment is marked Achieved, but its current requirements are not supported by submitted evidence. Review the missing requirements below.")
	elif assignment.status != "Achieved":
		warning = _("Data inconsistency: all requirements are supported by the evidence below, but this assignment is still Planned.")
	if warning:
		warning = f'<div class="alert alert-warning">{escape(warning)}</div>'
	return f"<div><h4>{title}</h4>{warning}<ul>{''.join(items)}</ul></div>"


def get_employees(filters):
	conditions = []
	values = {}
	if filters.get("company"):
		conditions.append("employee.company = %(company)s")
		values["company"] = filters.get("company")
	if filters.get("department"):
		conditions.append("""
			(employee.department = %(department)s OR EXISTS (
				SELECT 1 FROM `tabDepartment Link` additional_department
				WHERE additional_department.parent = employee.name
					AND additional_department.parenttype = 'Employee'
					AND additional_department.parentfield = 'additional_departments'
					AND additional_department.department = %(department)s
			))
		""")
		values["department"] = filters.get("department")

	# Staff Profiles supply assignments, not the department's employee roster.
	conditions_sql = " WHERE " + " AND ".join(conditions) if conditions else ""
	employees = frappe.db.sql("""
		SELECT employee.name, employee.employee_name, employee.visa
		FROM `tabEmployee` employee
		{conditions}
		ORDER BY COALESCE(NULLIF(employee.visa, ''), employee.employee_name, employee.name),
			employee.name
	""".format(conditions=conditions_sql), values=values, as_dict=True)
	if not filters.get("department"):
		return employees

	competency_names = [row["name"] for row in frappe.db.sql("""
		SELECT competency.name
		FROM `tabCompetency` competency
		WHERE competency.status = 'Valid'
			AND competency.docstatus = 1
			AND EXISTS (
				SELECT 1 FROM `tabDepartment Link` department
				WHERE department.parent = competency.name
					AND department.parenttype = 'Competency'
					AND department.parentfield = 'departments'
					AND department.department = %(department)s
			)
	""", values={"department": filters.get("department")}, as_dict=True)]
	if not competency_names:
		return employees

	extra_employees = frappe.db.sql("""
		SELECT DISTINCT profile.employee AS name, employee.employee_name, employee.visa
		FROM `tabStaff Profile` profile
		INNER JOIN `tabCompetency Assignment` assignment
			ON assignment.parent = profile.name
			AND assignment.parenttype = 'Staff Profile'
			AND assignment.parentfield = 'competencies'
		INNER JOIN `tabEmployee` employee
			ON employee.name = profile.employee
		WHERE profile.status IN ('Valid', 'To Sign') AND profile.docstatus = 1
			AND assignment.competency IN %(competencies)s
	""", values={"competencies": tuple(competency_names)}, as_dict=True)
	employees_by_name = {employee["name"]: employee for employee in employees}
	for employee in extra_employees:
		employees_by_name.setdefault(employee["name"], employee)
	return sorted(employees_by_name.values(), key=lambda employee: (
		(employee.get("visa") or employee.get("employee_name") or employee["name"]).lower(),
		employee["name"].lower(),
	))


def get_assignments(employees):
	if not employees:
		return []

	return frappe.db.sql("""
		SELECT assignment.name, profile.employee, assignment.competency, assignment.status,
			assignment.responsibility_role, assignment.level, profile.status AS profile_status
		FROM `tabStaff Profile` profile
		INNER JOIN `tabCompetency Assignment` assignment
			ON assignment.parent = profile.name
			AND assignment.parenttype = 'Staff Profile'
			AND assignment.parentfield = 'competencies'
		WHERE profile.status IN ('Valid', 'To Sign') AND profile.docstatus = 1
			AND profile.employee IN %(employees)s
		ORDER BY profile.employee, assignment.competency, profile.name, assignment.idx
	""", values={"employees": tuple(employee["name"] for employee in employees)}, as_dict=True)


def get_linked_department_employees(filters):
	conditions = []
	values = {}
	if filters.get("company"):
		conditions.append("employee.company = %(company)s")
		values["company"] = filters.get("company")
	if filters.get("department"):
		conditions.append("""
			employee.department = %(department)s OR EXISTS (
				SELECT 1 FROM `tabDepartment Link` additional_department
				WHERE additional_department.parent = employee.name
					AND additional_department.parenttype = 'Employee'
					AND additional_department.parentfield = 'additional_departments'
					AND additional_department.department = %(department)s
			)
		""")
		values["department"] = filters.get("department")
	conditions_sql = " WHERE " + " AND ".join(conditions) if conditions else ""
	return frappe.db.sql("""
		SELECT employee.name
		FROM `tabEmployee` employee
		{conditions}
	""".format(conditions=conditions_sql), values=values, as_dict=True)


def get_competencies(filters):
	# Select the department's catalogue independently of Staff Profiles. Unassigned
	# competencies remain visible; assignments cannot bypass the department filter.
	conditions = ["competency.status = 'Valid'", "competency.docstatus = 1"]
	values = {}
	if filters.get("department"):
		conditions.append("""
			EXISTS (
				SELECT 1 FROM `tabDepartment Link` department
				WHERE department.parent = competency.name
					AND department.parenttype = 'Competency'
					AND department.parentfield = 'departments'
					AND department.department = %(department)s
			)
		""")
		values["department"] = filters.get("department")
	if filters.get("competency_scope"):
		conditions.append("competency.scope = %(competency_scope)s")
		values["competency_scope"] = filters.get("competency_scope")

	competencies = frappe.db.sql("""
		SELECT competency.name, competency.title
		FROM `tabCompetency` competency
		WHERE {conditions}
		ORDER BY competency.title, competency.name
	""".format(conditions=" AND ".join(conditions)), values=values, as_dict=True)
	if not filters.get("department"):
		return competencies

	employees = get_employees(filters)
	if not employees:
		return competencies

	department_employees = tuple(employee["name"] for employee in get_linked_department_employees(filters))
	if not department_employees:
		return competencies

	extra_competencies = frappe.db.sql("""
		SELECT DISTINCT assignment.competency AS name, competency.title
		FROM `tabStaff Profile` profile
		INNER JOIN `tabCompetency Assignment` assignment
			ON assignment.parent = profile.name
			AND assignment.parenttype = 'Staff Profile'
			AND assignment.parentfield = 'competencies'
		INNER JOIN `tabCompetency` competency
			ON competency.name = assignment.competency
		WHERE profile.status IN ('Valid', 'To Sign') AND profile.docstatus = 1
			AND profile.employee IN %(department_employees)s
	""", values={"department_employees": department_employees}, as_dict=True)
	competencies_by_name = {competency["name"]: competency for competency in competencies}
	for competency in extra_competencies:
		competencies_by_name.setdefault(competency["name"], competency)
	return sorted(competencies_by_name.values(), key=lambda competency: (
		(competency.get("title") or competency.get("name") or "").lower(),
		(competency.get("name") or "").lower(),
	))


def get_columns(employees):
	columns = [
		{"label": _("Competency"), "fieldname": "competency", "fieldtype": "Link", "options": "Competency", "width": 90},
		{"label": _("Title"), "fieldname": "competency_title", "fieldtype": "Data", "width": 200},
	]
	for index, employee in enumerate(employees):
		# Visa is a label, not a key: missing or duplicate visas must not merge staff.
		columns.append({
			"label": employee.get("visa") or employee.get("employee_name") or employee["name"],
			"fieldname": "employee_{0}".format(index),
			"fieldtype": "Data",
			"width": 90,
			"employee": employee["name"],
			"employee_name": employee.get("employee_name") or employee["name"],
		})
	return columns


def get_data(employees, competencies, assignments):
	assignments_by_cell = {}
	for assignment in assignments:
		key = (assignment["competency"], assignment["employee"])
		profile_status = assignment.get("profile_status")
		current = assignments_by_cell.get(key)
		if current is not None and current and any(item.get("profile_status") == "Valid" for item in current):
			if profile_status == "To Sign":
				continue
		if current is not None and current and profile_status == "Valid" and any(item.get("profile_status") == "To Sign" for item in current):
			assignments_by_cell[key] = []
		label = {"Main": "M", "Substitute": "S"}.get(assignment.get("responsibility_role"), "")
		if assignment.get("level"):
			label = "{0} ({1})".format(label, assignment["level"]).strip()
		assignments_by_cell.setdefault(key, []).append({
			"label": label or assignment["status"],
			"status": assignment["status"],
			"profile_status": profile_status,
			"assignment_name": assignment.get("name"),
		})

	data = []
	for competency in competencies:
		row = {"competency": competency["name"], "competency_title": competency["title"], "_assignments": {}}
		for index, employee in enumerate(employees):
			fieldname = "employee_{0}".format(index)
			cell_assignments = assignments_by_cell.get((competency["name"], employee["name"]), [])
			# Keep plain text for sorting/export, and separate status metadata for
			# formatting. Multiple assignments retain their individual statuses.
			row[fieldname] = ", ".join(assignment["label"] for assignment in cell_assignments) or "-"
			row["_assignments"][fieldname] = cell_assignments
		data.append(row)
	return data
