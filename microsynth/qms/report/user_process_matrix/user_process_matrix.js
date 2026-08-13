// Copyright (c) 2016, Microsynth, libracore and contributors and contributors
// For license information, please see license.txt
/* eslint-disable */

frappe.query_reports["User Process Matrix"] = {
	"filters": [
		{
			"fieldname": "company",
			"label": __("Company"),
			"fieldtype": "Link",
			"options": "Company"
		},
		{
			"fieldname": "user",
			"label": __("User"),
			"fieldtype": "Link",
			"options": "User"
		},
		{
			"fieldname": "qm_process",
			"label": __("QM Process"),
			"fieldtype": "Link",
			"options": "QM Process"
		},
		{
			"fieldname": "is_process_owner",
			"label": __("Is Process Owner"),
			"fieldtype": "Select",
			"options": "\nYes\nNo"
		}
	],
	"onload": (report) => {
		hide_chart_buttons();
	}
};
