# Copyright (c) 2013, Microsynth, libracore and contributors and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _


def get_columns():
	return [
		{"label": _("Company"), "fieldname": "company", "fieldtype": "Link", "options": "Company", "width": 220},
		{"label": _("User"), "fieldname": "user", "fieldtype": "Link", "options": "User", "width": 260},
		{"label": _("QM Process"), "fieldname": "qm_process", "fieldtype": "Link", "options": "QM Process", "width": 220},
		{"label": _("Is Process Owner"), "fieldname": "is_process_owner", "fieldtype": "Check", "width": 140},
	]


def get_data(filters=None):
	filters = filters or {}
	conditions = []
	params = {}

	if filters.get("company"):
		conditions.append("`tabQM User Process Assignment`.`company` = %(company)s")
		params["company"] = filters.get("company")

	if filters.get("user"):
		conditions.append("`tabUser Settings`.`user` = %(user)s")
		params["user"] = filters.get("user")

	if filters.get("qm_process"):
		conditions.append("`tabQM User Process Assignment`.`qm_process` = %(qm_process)s")
		params["qm_process"] = filters.get("qm_process")

	if filters.get("is_process_owner") == "Yes":
		conditions.append("`tabQM Process Owner`.`name` IS NOT NULL")
	elif filters.get("is_process_owner") == "No":
		conditions.append("`tabQM Process Owner`.`name` IS NULL")

	conditions_sql = ""
	if conditions:
		conditions_sql = " AND " + " AND ".join(conditions)

	query = f"""
		SELECT DISTINCT
			`tabQM User Process Assignment`.`company` AS `company`,
			`tabUser Settings`.`user` AS `user`,
			`tabQM User Process Assignment`.`qm_process` AS `qm_process`,
			CASE WHEN `tabQM Process Owner`.`name` IS NULL THEN 0 ELSE 1 END AS `is_process_owner`
		FROM `tabUser Settings`
		INNER JOIN `tabQM User Process Assignment` ON `tabQM User Process Assignment`.`parent` = `tabUser Settings`.`name`
		LEFT JOIN `tabQM Process Owner` ON `tabQM Process Owner`.`qm_process` = `tabQM User Process Assignment`.`qm_process`
			AND IFNULL(`tabQM Process Owner`.`company`, '') = IFNULL(`tabQM User Process Assignment`.`company`, '')
			AND `tabQM Process Owner`.`process_owner` = `tabUser Settings`.`user`
		WHERE `tabUser Settings`.`disabled` = 0
			{conditions_sql}
		ORDER BY `tabQM User Process Assignment`.`company`, `tabUser Settings`.`user`, `tabQM User Process Assignment`.`qm_process`
	"""

	return frappe.db.sql(query, values=params, as_dict=True)


def execute(filters=None):
	columns = get_columns()
	data = get_data(filters)
	return columns, data
