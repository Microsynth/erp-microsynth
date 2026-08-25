# Copyright (c) 2026, Microsynth
# For license information, please see license.txt

from __future__ import unicode_literals
import re

import frappe
from frappe import _
from frappe.utils import now_datetime
from frappe.utils.pdf import get_pdf


def get_columns():
	return [
		{"label": _("Company"), "fieldname": "company", "fieldtype": "Link", "options": "Company", "width": 160},
		{"label": _("User Full Name"), "fieldname": "full_name", "fieldtype": "Data", "width": 180},
		{"label": _("QM Process"), "fieldname": "qm_process", "fieldtype": "Link", "options": "QM Process", "width": 220},
		{"label": _("Is Process Owner"), "fieldname": "is_process_owner", "fieldtype": "Check", "width": 120},
		{"label": _("Last Modified On"), "fieldname": "last_modified_on", "fieldtype": "Datetime", "width": 170},
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
			IFNULL(`tabSignature`.`full_name`, `tabUser Settings`.`user`) AS `full_name`,
			`tabQM User Process Assignment`.`qm_process` AS `qm_process`,
			CASE WHEN `tabQM Process Owner`.`name` IS NULL THEN 0 ELSE 1 END AS `is_process_owner`,
			CASE
				WHEN `tabQM Process Owner`.`modified` IS NOT NULL
					AND `tabQM Process Owner`.`modified` > `tabQM User Process Assignment`.`creation`
				THEN `tabQM Process Owner`.`modified`
				ELSE `tabQM User Process Assignment`.`creation`
			END AS `last_modified_on`
		FROM `tabUser Settings`
		INNER JOIN `tabQM User Process Assignment` ON `tabQM User Process Assignment`.`parent` = `tabUser Settings`.`name`
		LEFT JOIN `tabSignature` ON `tabSignature`.`user` = `tabUser Settings`.`user`
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


def _process_sort_key(process_name):
	name = (process_name or "").strip()
	match = re.match(r"^(\d+(?:\.\d+)*)", name)
	if not match:
		return ([9999], name.lower())

	parts = [int(part) for part in match.group(1).split(".") if part.isdigit()]
	return (parts, name.lower())


def _build_process_cards(rows):
	process_map = {}
	for row in rows:
		process_name = (row.get("qm_process") or "").strip()
		full_name = (row.get("full_name") or "").strip()
		if not process_name or not full_name:
			continue

		if process_name not in process_map:
			process_map[process_name] = {
				"qm_process": process_name,
				"owners": set(),
				"members": set(),
			}

		if int(row.get("is_process_owner") or 0) == 1:
			process_map[process_name]["owners"].add(full_name)
		else:
			process_map[process_name]["members"].add(full_name)

	process_cards = []
	for process_name, process_data in process_map.items():
		owners = sorted(process_data["owners"], key=lambda value: value.lower())
		members = sorted(process_data["members"] - set(owners), key=lambda value: value.lower())
		process_cards.append({
			"qm_process": process_name,
			"owners": owners,
			"members": members,
			"person_count": len(owners) + len(members),
		})

	process_cards.sort(key=lambda card: _process_sort_key(card.get("qm_process")))
	return process_cards


@frappe.whitelist()
def create_organigram_pdf(company, user=None, qm_process=None, is_process_owner=None):
	if not company:
		frappe.throw(_("Filter Company is required."))

	filters = {
		"company": company,
	}
	if user:
		filters["user"] = user
	if qm_process:
		filters["qm_process"] = qm_process
	if is_process_owner:
		filters["is_process_owner"] = is_process_owner

	rows = get_data(filters)
	process_cards = _build_process_cards(rows)
	if not process_cards:
		frappe.throw(_("No data found for the current filters."))

	owners = sorted({
		(row.get("full_name") or "").strip()
		for row in rows
		if int(row.get("is_process_owner") or 0) == 1 and (row.get("full_name") or "").strip()
	}, key=lambda value: value.lower())

	content = frappe.render_template(
		"microsynth/qms/report/user_process_matrix/user_process_matrix_organigram.html",
		{
			"company": company,
			"generated_on": now_datetime(),
			"owners": owners,
			"process_cards": process_cards,
			"filters": filters,
		}
	)

	pdf = get_pdf(content, {
		"orientation": "Landscape",
		"page-size": "A3",
		"disable-smart-shrinking": "",
	})

	filename = "organigram_{0}_{1}.pdf".format(
		frappe.scrub(company or "company"),
		now_datetime().strftime("%Y%m%d_%H%M%S")
	)

	file_doc = frappe.get_doc({
		"doctype": "File",
		"file_name": filename,
		"is_private": 1,
		"content": pdf,
	})
	file_doc.save(ignore_permissions=True)

	return file_doc.file_url
