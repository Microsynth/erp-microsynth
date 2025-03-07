// Copyright (c) 2025, Microsynth
// For license information, please see license.txt
/* eslint-disable */

frappe.query_reports["Quotation Tracker"] = {
	"filters": [
		{
            "fieldname": "sales_manager",
            "label": __("Sales Manager"),
            "fieldtype": "Link",
            "options": "User",
            "default": frappe.session.user,
        },
        {
            "fieldname": "minimum_age",
            "label": __("Minimum quotation age (days)"),
            "fieldtype": "Int",
            "default": 7
        },
        {
            "fieldname":"net_total_threshold",
            "label": __("Net Total threshold"),
            "fieldtype": "Currency"
        },
        {
            "fieldname": "followup_days",
            "label": __("Minimum follow up age (days)"),
            "fieldtype": "Int",
            "default": 30
        }
	],
    "onload": (report) => {
        hide_chart_buttons();
    }
};
