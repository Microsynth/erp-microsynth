// Copyright (c) 2016, Microsynth, libracore and contributors and contributors
// For license information, please see license.txt
/* eslint-disable */

frappe.query_reports["Audit Trail Review Due"] = {
	"filters": [
		{
			"fieldname": "view",
			"label": "View",
			"fieldtype": "Select",
			"options": "Overdue\nATR due in next 6 weeks\nAll ATR-managed systems",
			"default": "ATR due in next 6 weeks"
		}
	],
	"onload": (report) => {
		hide_chart_buttons();
	}
};
