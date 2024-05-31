// Copyright (c) 2024, Microsynth, libracore and contributors and contributors
// For license information, please see license.txt
/* eslint-disable */

frappe.query_reports["Accounting Note Overview"] = {
    "filters": [
        {
            "fieldname":"from_date",
            "label": __("From Date"),
            "fieldtype": "Date",
            "default": frappe.datetime.add_months(frappe.datetime.get_today(), -1),
            "reqd": 1
        },
        {
            "fieldname":"to_date",
            "label": __("To Date"),
            "fieldtype": "Date",
            "default": frappe.datetime.get_today(),
            "reqd": 1
        },
        {
            "fieldname":"account",
            "label": __("Account"),
            "fieldtype": "Link",
            "options": "Account"
        },
        {
            "fieldname":"status",
            "label": __("Status"),
            "fieldtype": "Select",
            "options": "\nOpen\nClosed"
        }
    ]
};
