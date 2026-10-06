# Copyright (c) 2026, Microsynth
# For license information, please see license.txt

from __future__ import unicode_literals

import frappe
from frappe import _


def execute(filters=None):
	filters = filters or {}
	employees = get_employees(filters)
	assignments = get_assignments(employees)
	competencies = get_competencies(filters)
	return get_columns(employees), get_data(employees, competencies, assignments)


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
	return frappe.db.sql("""
		SELECT employee.name, employee.employee_name, employee.visa
		FROM `tabEmployee` employee
		{conditions}
		ORDER BY COALESCE(NULLIF(employee.visa, ''), employee.employee_name, employee.name),
			employee.name
	""".format(conditions=conditions_sql), values=values, as_dict=True)


def get_assignments(employees):
	if not employees:
		return []

	return frappe.db.sql("""
		SELECT profile.employee, assignment.competency, assignment.status,
			assignment.responsibility_role, assignment.level
		FROM `tabStaff Profile` profile
		INNER JOIN `tabCompetency Assignment` assignment
			ON assignment.parent = profile.name
			AND assignment.parenttype = 'Staff Profile'
			AND assignment.parentfield = 'competencies'
		WHERE profile.status = 'Valid' AND profile.docstatus = 1
			AND profile.employee IN %(employees)s
		ORDER BY profile.employee, assignment.competency, profile.name, assignment.idx
	""", values={"employees": tuple(employee["name"] for employee in employees)}, as_dict=True)


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

	return frappe.db.sql("""
		SELECT competency.name, competency.title
		FROM `tabCompetency` competency
		WHERE {conditions}
		ORDER BY competency.title, competency.name
	""".format(conditions=" AND ".join(conditions)), values=values, as_dict=True)


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
			"width": 80,
			"employee": employee["name"],
			"employee_name": employee.get("employee_name") or employee["name"],
		})
	return columns


def get_data(employees, competencies, assignments):
	assignments_by_cell = {}
	for assignment in assignments:
		key = (assignment["competency"], assignment["employee"])
		label = {"Main": "M", "Substitute": "S"}.get(assignment.get("responsibility_role"), "")
		if assignment.get("level"):
			label = "{0} ({1})".format(label, assignment["level"]).strip()
		assignments_by_cell.setdefault(key, []).append({
			"label": label or assignment["status"],
			"status": assignment["status"],
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
