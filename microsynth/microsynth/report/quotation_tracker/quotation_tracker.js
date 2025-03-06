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
            "fieldname": "date_threshold",
            "label": __("Date threshold"),
            "fieldtype": "Date",
            "reqd": 1,
            "default": frappe.datetime.add_days(frappe.datetime.get_today(), -7)
        },
        {
            "fieldname":"net_total_threshold",
            "label": __("Net Total threshold"),
            "fieldtype": "Currency"
        },
        {
            "fieldname": "last_follow_up_date_threshold",
            "label": __("Last followed up threshold"),
            "fieldtype": "Date",
            "reqd": 1,
            "default": frappe.datetime.add_months(frappe.datetime.get_today(), -1),
        }
	],
    "onload": (report) => {
        hide_chart_buttons();
    }
};
