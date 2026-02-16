# Copyright (c) 2026, Microsynth
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe


def get_columns():
	return [
		{"label": "Analysis Report", "fieldname": "analysis_report", "fieldtype": "Link", "options": "Analysis Report", "width": 105},
		{"label": "Issue Date", "fieldname": "issue_date", "fieldtype": "Date", "width": 80},
		{"label": "Report Type", "fieldname": "report_type", "fieldtype": "Data", "width": 90},
		{"label": "Customer", "fieldname": "customer", "fieldtype": "Link", "options": "Customer", "width": 75},
		{"label": "Customer Name", "fieldname": "customer_name", "fieldtype": "Data", "width": 160},
		{"label": "Contact Person", "fieldname": "contact_person", "fieldtype": "Link", "options": "Contact", "width": 110},
		{"label": "Address", "fieldname": "address", "fieldtype": "Link", "options": "Address", "width": 80},
		{"label": "Company", "fieldname": "company", "fieldtype": "Link", "options": "Company", "width": 100},
		{"label": "Web Order ID", "fieldname": "web_order_id", "fieldtype": "Data", "width": 95},
		{"label": "Sales Order", "fieldname": "sales_order", "fieldtype": "Link", "options": "Sales Order", "width": 120},
		{"label": "Approved By", "fieldname": "approved_by", "fieldtype": "Link", "options": "User", "width": 140},
		{"label": "Comment", "fieldname": "ar_comment", "fieldtype": "Data", "width": 100},
		{"label": "Disclaimer", "fieldname": "disclaimer", "fieldtype": "Data", "width": 100},
		{"label": "Sample", "fieldname": "sample", "fieldtype": "Link", "options": "Sample", "width": 110},
		{"label": "Sample Name", "fieldname": "sample_name", "fieldtype": "Data", "width": 150},
		{"label": "Sample Customer", "fieldname": "sample_customer", "fieldtype": "Link", "options": "Customer", "width": 120},
		{"label": "Sample Customer Name", "fieldname": "sample_customer_name", "fieldtype": "Data", "width": 150},
		{"label": "Web ID", "fieldname": "web_id", "fieldtype": "Data", "width": 100},
		{"label": "Production ID", "fieldname": "prod_id", "fieldtype": "Data", "width": 100},
		{"label": "Barcode Label", "fieldname": "sequencing_label", "fieldtype": "Link", "options": "Sequencing Label", "width": 100},
		{"label": "Barcode Number", "fieldname": "sequencing_label_id", "fieldtype": "Data", "width": 110},
		{"label": "Analysis Method", "fieldname": "analysis_method", "fieldtype": "Data", "width": 150},
		{"label": "Analysis Result", "fieldname": "analysis_result", "fieldtype": "Data", "width": 150},
		{"label": "Reception Date", "fieldname": "reception_date", "fieldtype": "Datetime", "width": 155},
		{"label": "Analysis Date", "fieldname": "analysis_date", "fieldtype": "Datetime", "width": 160},
		{"label": "Deviations", "fieldname": "deviations", "fieldtype": "Data", "width": 160},
		{"label": "Sample Detail Comment", "fieldname": "detail_comment", "fieldtype": "Data", "width": 160},
	]


def get_data(filters):
	report_type = filters.get("type")
	from_date = filters.get("from_date")
	to_date = filters.get("to_date")
	type_filter_sub = ""
	type_filter_main = ""
	date_filter_sub = ""
	date_filter_main = ""

	if report_type:
		type_filter_sub = " AND `tabAnalysis Report`.`report_type` = %(report_type)s"
		type_filter_main = " AND `tabAnalysis Report`.`report_type` = %(report_type)s"
	if from_date and to_date:
		date_filter_sub = " AND `tabAnalysis Report`.`issue_date` BETWEEN %(from_date)s AND %(to_date)s"
		date_filter_main = " AND `tabAnalysis Report`.`issue_date` BETWEEN %(from_date)s AND %(to_date)s"
	elif from_date:
		date_filter_sub = " AND `tabAnalysis Report`.`issue_date` >= %(from_date)s"
		date_filter_main = " AND `tabAnalysis Report`.`issue_date` >= %(from_date)s"
	elif to_date:
		date_filter_sub = " AND `tabAnalysis Report`.`issue_date` <= %(to_date)s"
		date_filter_main = " AND `tabAnalysis Report`.`issue_date` <= %(to_date)s"

	query = f"""
		SELECT
			`tabAnalysis Report`.`name` AS `analysis_report`,
			`tabAnalysis Report`.`issue_date`,
			`tabAnalysis Report`.`report_type`,
			`tabAnalysis Report`.`customer`,
			`tabAnalysis Report`.`customer_name`,
			`tabAnalysis Report`.`contact_person`,
			`tabAnalysis Report`.`address`,
			`tabAnalysis Report`.`company`,
			`tabAnalysis Report`.`web_order_id`,
			`tabAnalysis Report`.`sales_order`,
			`tabAnalysis Report`.`approved_by`,
			`tabAnalysis Report`.`comment` AS `ar_comment`,
			`tabAnalysis Report`.`disclaimer`,
			`tabSample`.`name` AS `sample`,
			`tabSample`.`sample_name`,
			`tabSample`.`customer` AS `sample_customer`,
			`tabSample`.`customer_name` AS `sample_customer_name`,
			`tabSample`.`web_id`,
			`tabSample`.`prod_id`,
			`tabSample`.`sequencing_label`,
			`tabSample`.`sequencing_label_id`,
			`tabAnalysis Report Sample Detail`.`analysis_method`,
			`tabAnalysis Report Sample Detail`.`analysis_result`,
			`tabAnalysis Report Sample Detail`.`reception_date`,
			`tabAnalysis Report Sample Detail`.`analysis_date`,
			`tabAnalysis Report Sample Detail`.`deviations`,
			`tabAnalysis Report Sample Detail`.`comment` AS `detail_comment`
		FROM `tabAnalysis Report`
		INNER JOIN `tabAnalysis Report Sample Detail`
			ON `tabAnalysis Report Sample Detail`.`parent` = `tabAnalysis Report`.`name`
		INNER JOIN `tabSample`
			ON `tabAnalysis Report Sample Detail`.`sample` = `tabSample`.`name`
		INNER JOIN (
			SELECT
				`tabAnalysis Report Sample Detail`.`sample`,
				MAX(`tabAnalysis Report`.`issue_date`) AS `max_issue_date`
			FROM `tabAnalysis Report`
			INNER JOIN `tabAnalysis Report Sample Detail`
				ON `tabAnalysis Report Sample Detail`.`parent` = `tabAnalysis Report`.`name`
			WHERE `tabAnalysis Report`.`docstatus` < 2
			{type_filter_sub}
			{date_filter_sub}
			GROUP BY `tabAnalysis Report Sample Detail`.`sample`
		) AS `newest`
			ON `newest`.`sample` = `tabAnalysis Report Sample Detail`.`sample`
			AND `newest`.`max_issue_date` = `tabAnalysis Report`.`issue_date`
		WHERE `tabAnalysis Report`.`docstatus` < 2
		{type_filter_main}
		{date_filter_main}
		ORDER BY `tabSample`.`name`, `tabAnalysis Report`.`issue_date` DESC
	"""
	params = {}
	if report_type:
		params["report_type"] = report_type
	if from_date:
		params["from_date"] = from_date
	if to_date:
		params["to_date"] = to_date

	return frappe.db.sql(query, params, as_dict=True)


def execute(filters=None):
	if not filters:
		filters = {}
	columns = get_columns()
	data = get_data(filters)
	return columns, data
