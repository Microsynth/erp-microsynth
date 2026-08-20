# Copyright (c) 2026, Microsynth
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe


def get_columns():
	return [
		{"label": "System", "fieldname": "name", "fieldtype": "Link", "options": "QM Computerised System", "width": 100},
		{"label": "System Name", "fieldname": "cs_name", "fieldtype": "Data", "width": 220},
		{"label": "Status", "fieldname": "status", "fieldtype": "Data", "width": 110},
		{"label": "Type", "fieldname": "cs_type", "fieldtype": "Data", "width": 100},
		{"label": "GAMP5 Class", "fieldname": "gamp5_class", "fieldtype": "Data", "width": 130},
		{"label": "Regulatory Classification", "fieldname": "regulatory_classification", "fieldtype": "Data", "width": 160},
		{"label": "ATR Frequency (months)", "fieldname": "atr_frequency", "fieldtype": "Int", "width": 160},
		{"label": "Last ATR", "fieldname": "last_atr_date", "fieldtype": "Date", "width": 80, "align": "left"},
		{"label": "Due Date", "fieldname": "due_date", "fieldtype": "Date", "width": 80},
		{"label": "Process", "fieldname": "qm_process", "fieldtype": "Link", "options": "QM Process", "width": 160},
		{"label": "Company", "fieldname": "company", "fieldtype": "Link", "options": "Company", "width": 150},
		{"label": "Responsible Person", "fieldname": "responsible_user", "fieldtype": "Link", "options": "User", "width": 200, "align": "left"},
	]


def get_conditions(filters):
	view = (filters or {}).get("view")
	due_date_expression = """DATE_ADD(
				COALESCE(`last_atr`.`last_atr_date`, DATE(`tabQM Computerised System`.`creation`)),
				INTERVAL `tabQM Computerised System`.`atr_frequency` MONTH
			)"""

	if view == "All ATR-managed systems":
		return ""

	# default: systems due today or overdue
	return f"AND {due_date_expression} <= CURDATE()"


def get_data(filters):
	conditions = get_conditions(filters)

	return frappe.db.sql(f"""
		WITH `last_atr` AS (
			SELECT
				`tabQM Log Book`.`document_name`,
				MAX(`tabQM Log Book`.`date`) AS `last_atr_date`
			FROM `tabQM Log Book`
			WHERE `tabQM Log Book`.`docstatus` = 1
				AND `tabQM Log Book`.`document_type` = 'QM Computerised System'
				AND `tabQM Log Book`.`entry_type` = 'Audit Trail Review'
				AND `tabQM Log Book`.`status` IN ('To Review', 'Closed')
			GROUP BY `tabQM Log Book`.`document_name`
		)
		SELECT
			`tabQM Computerised System`.`name`,
			`tabQM Computerised System`.`cs_name`,
			`tabQM Computerised System`.`status`,
			`tabQM Computerised System`.`cs_type`,
			`tabQM Computerised System`.`gamp5_class`,
			`tabQM Computerised System`.`regulatory_classification`,
			`tabQM Computerised System`.`atr_frequency`,
			`last_atr`.`last_atr_date`,
			DATE_ADD(
				COALESCE(`last_atr`.`last_atr_date`, DATE(`tabQM Computerised System`.`creation`)),
				INTERVAL `tabQM Computerised System`.`atr_frequency` MONTH
			) AS `due_date`,
			`tabQM Computerised System`.`qm_process`,
			`tabQM Computerised System`.`company`,
			`tabQM Computerised System`.`responsible_user`
		FROM `tabQM Computerised System`
		LEFT JOIN `last_atr`
			ON `last_atr`.`document_name` = `tabQM Computerised System`.`name`
		WHERE `tabQM Computerised System`.`status` != 'Decommissioned'
			AND COALESCE(`tabQM Computerised System`.`atr_frequency`, 0) > 0
			{conditions}
		ORDER BY `due_date` ASC, `tabQM Computerised System`.`name` ASC
	""", filters, as_dict=True)

def execute(filters=None):
	if not filters:
		filters = {}
	columns = get_columns()
	data = get_data(filters)
	return columns, data
