// Copyright (c) 2016, Microsynth, libracore and contributors and contributors
// For license information, please see license.txt
/* eslint-disable */

frappe.query_reports["Oligo Modifier Stock"] = {
	"filters": [
		{
			"fieldname": "include_empty_locations",
			"label": __("Include empty locations"),
			"fieldtype": "Check",
			"default": 0,
		}
	],
	"onload": (report) => {
		hide_chart_buttons();
	}
};
