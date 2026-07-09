// Copyright (c) 2026, Microsynth
// For license information, please see license.txt
/* eslint-disable */

frappe.query_reports["Sold Units Fast Lane Analysis"] = {
	"filters": [
		{
			"fieldname": "territory",
			"label": __("Territory"),
			"fieldtype": "Link",
			"options": "Territory"
		},
		{
			"fieldname": "fiscal_year",
			"label": __("Fiscal Year"),
			"fieldtype": "Link",
			"options": "Fiscal Year",
			"reqd": 1,
			"default": frappe.defaults.get_user_default("fiscal_year") || frappe.defaults.get_global_default("fiscal_year")
		}
	],
	"onload": function(report) {
		hide_chart_buttons(report);
	}
};
