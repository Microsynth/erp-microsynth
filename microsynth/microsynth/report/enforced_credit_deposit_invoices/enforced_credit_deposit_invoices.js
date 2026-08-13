// Copyright (c) 2026, Microsynth
// For license information, please see license.txt
/* eslint-disable */

function get_first_of_last_month() {
	const today = frappe.datetime.str_to_obj(frappe.datetime.get_today());
	const first_day_this_month = new Date(today.getFullYear(), today.getMonth(), 1);
	const last_day_prev_month = frappe.datetime.add_days(
		frappe.datetime.obj_to_str(first_day_this_month), -1
	);
	const d = frappe.datetime.str_to_obj(last_day_prev_month);
	return frappe.datetime.obj_to_str(new Date(d.getFullYear(), d.getMonth(), 1));
}

function get_last_of_last_month() {
	const today = frappe.datetime.str_to_obj(frappe.datetime.get_today());
	const first_day_this_month = new Date(today.getFullYear(), today.getMonth(), 1);
	return frappe.datetime.add_days(
		frappe.datetime.obj_to_str(first_day_this_month), -1
	);
}

frappe.query_reports["Enforced Credit Deposit Invoices"] = {
	"filters": [
		{
			"fieldname": "company",
			"label": __("Company"),
			"fieldtype": "Link",
			"options": "Company",
			"reqd": 1,
			"default": frappe.defaults.get_user_default("company") || frappe.defaults.get_global_default("company")
		},
		{
			"fieldname": "from_date",
			"label": __("From Date"),
			"fieldtype": "Date",
			"reqd": 1,
			"default": get_first_of_last_month()
		},
		{
			"fieldname": "to_date",
			"label": __("To Date"),
			"fieldtype": "Date",
			"reqd": 1,
			"default": get_last_of_last_month()
		}
	],
	"onload": (report) => {
		hide_chart_buttons();
	}
};
