# Copyright (c) 2026, Microsynth
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _


def get_columns():
	return [
		{"label": _("Sales Invoice"), "fieldname": "sales_invoice", "fieldtype": "Link", "options": "Sales Invoice", "width": 110},
		{"label": _("Posting Date"), "fieldname": "posting_date", "fieldtype": "Date", "width": 90},
		{"label": _("Company"), "fieldname": "company", "fieldtype": "Link", "options": "Company", "width": 150},
		{"label": _("Customer"), "fieldname": "customer", "fieldtype": "Link", "options": "Customer", "width": 80},
		{"label": _("Customer Name"), "fieldname": "customer_name", "fieldtype": "Data", "width": 300},
		{"label": _("External Debitor Number"), "fieldname": "ext_debitor_number", "fieldtype": "Data", "width": 160},
		{"label": _("Net Total"), "fieldname": "net_total", "fieldtype": "Currency", "options": "currency", "width": 90},
		{"label": _("Taxes and Charges"), "fieldname": "total_taxes_and_charges", "fieldtype": "Currency", "options": "currency", "width": 125},
		{"label": _("Grand Total"), "fieldname": "grand_total", "fieldtype": "Currency", "options": "currency", "width": 90},
		{"label": _("Currency"), "fieldname": "currency", "fieldtype": "Data", "width": 75},
	]


def get_data(filters):
	if not filters:
		filters = {}

	query_filters = {
		"company": filters.get("company"),
		"from_date": filters.get("from_date"),
		"to_date": filters.get("to_date"),
	}

	conditions = [
		"`tabSales Invoice`.`docstatus` = 1",
		"`tabCredit Account`.`account_type` = 'Enforced Credit'",
	]

	if query_filters.get("company"):
		conditions.append("`tabSales Invoice`.`company` = %(company)s")
	if query_filters.get("from_date"):
		conditions.append("`tabSales Invoice`.`posting_date` >= %(from_date)s")
	if query_filters.get("to_date"):
		conditions.append("`tabSales Invoice`.`posting_date` <= %(to_date)s")

	where_clause = " AND ".join(conditions)

	return frappe.db.sql(
		"""
		SELECT
			`tabSales Invoice`.`name` AS `sales_invoice`,
			`tabSales Invoice`.`posting_date`,
			`tabSales Invoice`.`company`,
			`tabSales Invoice`.`customer`,
			`tabSales Invoice`.`customer_name`,
			`tabCustomer`.`ext_debitor_number`,
			`tabSales Invoice`.`net_total`,
			`tabSales Invoice`.`total_taxes_and_charges`,
			`tabSales Invoice`.`grand_total`,
			`tabSales Invoice`.`currency`
		FROM `tabSales Invoice`
		INNER JOIN `tabCredit Account`
			ON `tabCredit Account`.`name` = `tabSales Invoice`.`credit_account`
		LEFT JOIN `tabCustomer`
			ON `tabCustomer`.`name` = `tabSales Invoice`.`customer`
		WHERE {where_clause}
		ORDER BY `tabSales Invoice`.`posting_date` DESC, `tabSales Invoice`.`name` DESC
		""".format(where_clause=where_clause),
		query_filters,
		as_dict=True,
	)


def execute(filters=None):
	columns = get_columns()
	data = get_data(filters)
	return columns, data
