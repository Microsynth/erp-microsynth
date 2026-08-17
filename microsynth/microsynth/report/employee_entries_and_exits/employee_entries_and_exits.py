# Copyright (c) 2026, Microsynth
# For license information, please see license.txt

from __future__ import unicode_literals

import frappe
from frappe import _


def get_columns():
	return [
		{"label": _("Employee ID"), "fieldname": "employee", "fieldtype": "Link", "options": "Employee", "width": 220},
		{"label": _("Full Name"), "fieldname": "employee_name", "fieldtype": "Data", "width": 180},
		{"label": _("Visa"), "fieldname": "visa", "fieldtype": "Data", "width": 50},
		{"label": _("Department"), "fieldname": "department", "fieldtype": "Link", "options": "Department", "width": 200},
		{"label": _("QM Process"), "fieldname": "qm_process", "fieldtype": "Data", "width": 250, "align": "left"},
		{"label": _("Date of Joining"), "fieldname": "date_of_joining", "fieldtype": "Date", "width": 105, "align": "left"},
		{"label": _("Relieving Date"), "fieldname": "relieving_date", "fieldtype": "Date", "width": 100, "align": "left"},
		{"label": _("Picture Path"), "fieldname": "image", "fieldtype": "Data", "width": 300},
	]


def get_data(filters):
	if not filters.get("company"):
		frappe.throw(_("Filter Company is required."))
	if not filters.get("from_date"):
		frappe.throw(_("Filter From Date is required."))

	conditions = [
		"`tabEmployee`.`company` = %(company)s",
	]

	if filters.get("to_date"):
		conditions.append(
			"""
			(
				(`tabEmployee`.`date_of_joining` IS NOT NULL AND `tabEmployee`.`date_of_joining` >= %(from_date)s AND `tabEmployee`.`date_of_joining` <= %(to_date)s)
				OR
				(`tabEmployee`.`relieving_date` IS NOT NULL AND `tabEmployee`.`relieving_date` >= %(from_date)s AND `tabEmployee`.`relieving_date` <= %(to_date)s)
			)
			"""
		)
	else:
		conditions.append(
			"""
			(
				(`tabEmployee`.`date_of_joining` IS NOT NULL AND `tabEmployee`.`date_of_joining` >= %(from_date)s)
				OR
				(`tabEmployee`.`relieving_date` IS NOT NULL AND `tabEmployee`.`relieving_date` >= %(from_date)s)
			)
			"""
		)

	return frappe.db.sql(
		"""
			SELECT
				`tabEmployee`.`name` AS employee,
				`tabEmployee`.`employee_name`,
				`tabEmployee`.`visa`,
				`tabEmployee`.`department`,
				GROUP_CONCAT(DISTINCT `tabQM User Process Assignment`.`qm_process` ORDER BY `tabQM User Process Assignment`.`qm_process` SEPARATOR ', ') AS qm_process,
				`tabEmployee`.`date_of_joining`,
				`tabEmployee`.`relieving_date`,
				`tabEmployee`.`image`
			FROM `tabEmployee`
			LEFT JOIN `tabUser Settings`
				ON `tabUser Settings`.`user` = `tabEmployee`.`user_id`
				AND `tabUser Settings`.`disabled` = 0
			LEFT JOIN `tabQM User Process Assignment`
				ON `tabQM User Process Assignment`.`parent` = `tabUser Settings`.`name`
				AND `tabQM User Process Assignment`.`company` = `tabEmployee`.`company`
			WHERE {conditions}
			GROUP BY
				`tabEmployee`.`name`,
				`tabEmployee`.`employee_name`,
				`tabEmployee`.`department`,
				`tabEmployee`.`date_of_joining`,
				`tabEmployee`.`relieving_date`,
				`tabEmployee`.`image`
			ORDER BY `tabEmployee`.`company` ASC, COALESCE(`tabEmployee`.`date_of_joining`, `tabEmployee`.`relieving_date`) ASC, `tabEmployee`.`employee_name` ASC
		""".format(conditions=" AND ".join(["({0})".format(c) for c in conditions])),
		filters,
		as_dict=True,
	)

def execute(filters=None):
	filters = filters or {}
	columns = get_columns()
	data = get_data(filters)
	return columns, data
