// Copyright (c) 2026, Microsynth
// For license information, please see license.txt
/* eslint-disable */

frappe.query_reports["Oligo Modifier Stock"] = {
	"filters": [
		{
			"fieldname": "mode",
			"label": __("Mode"),
			"fieldtype": "Select",
			"options": "Filled Locations\nEmpty Locations\nAll Locations",
			"default": "Filled Locations",
			"reqd": 1,
		}
	],
	"onload": (report) => {
		hide_chart_buttons();
	}
};
