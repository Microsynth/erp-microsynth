// Copyright (c) 2025, Microsynth, libracore and contributors
// For license information, please see license.txt
/* eslint-disable */

frappe.query_reports["Shipping Times"] = {
    "filters": [
        {
            "fieldname": "item_code",
            "label": __("Shipping Item Code"),
            "fieldtype": "Link",
            "options": "Item"
        },
        {
            "fieldname": "from_date",
            "label": __("From date"),
            "fieldtype": "Date",
            "reqd": 1
        },
        {
            "fieldname": "to_date",
            "label": __("To date"),
            "fieldtype": "Date",
            "reqd": 1
        },
        {
            "fieldname": "show_unknown_delivery",
            "label": "Show unknown delivery",
            "fieldtype": "Check",
            "default": 0
        }
    ],
    "onload": (report) => {
        hide_chart_buttons();
    }
};
