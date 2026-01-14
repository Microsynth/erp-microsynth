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
            "default": frappe.datetime.add_months(frappe.datetime.get_today(), -1),
            "reqd": 1
        },
    ],
    "onload": (report) => {
        hide_chart_buttons();
    }
};
