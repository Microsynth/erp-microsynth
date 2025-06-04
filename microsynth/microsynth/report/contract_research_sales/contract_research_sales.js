// Copyright (c) 2025, Microsynth
// For license information, please see license.txt
/* eslint-disable */

frappe.query_reports["Contract Research Sales"] = {
    "filters": [
        {
            "fieldname": "from_date",
            "label": __("From Date"),
            "fieldtype": "Date"
        },
        {
            "fieldname": "to_date",
            "label": __("To Date"),
            "fieldtype": "Date"
        }
    ]
};

