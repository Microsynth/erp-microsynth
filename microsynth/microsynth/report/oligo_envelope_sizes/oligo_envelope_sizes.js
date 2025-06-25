// Copyright (c) 2024, Microsynth and contributors
// For license information, please see license.txt
/* eslint-disable */

frappe.query_reports["Oligo envelope sizes"] = {
    "filters": [
        {
            "fieldname": "date",
            "label": __("Date"),
            "fieldtype": "Date",
            "reqd": 1,
            "default": frappe.datetime.get_today()
        },
        {
            "fieldname": "tracking",
            "label": __("Tracking"),
            "fieldtype": "Select",
            "options": "no Tracking\nTracking",
            "reqd": 1,
            "default": 'no Tracking'
        }
    ]
};
