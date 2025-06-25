// Copyright (c) 2025, Microsynth
// For license information, please see license.txt
/* eslint-disable */

frappe.query_reports["Missing Tracking Codes"] = {
    "filters": [
        {
            "fieldname": "item_code",
            "label": __("Shipping Item Code"),
            "fieldtype": "Link",
            "options": "Item"
        },
        {
            "fieldname":"from_date",
            "label": __("From Date"),
            "fieldtype": "Date",
            "default": "2025-01-01", // frappe.datetime.add_months(frappe.datetime.get_today(), -6),
            "reqd": 1
        },
    ],
    "onload": (report) => {
        hide_chart_buttons();
    }
};
