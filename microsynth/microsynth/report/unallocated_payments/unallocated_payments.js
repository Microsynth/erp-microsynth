// Copyright (c) 2025, Microsynth
// For license information, please see license.txt
/* eslint-disable */


frappe.query_reports["Unallocated Payments"] = {
    "filters": [
        {
            "fieldname": "from_date",
            "label": __("From Date"),
            "fieldtype": "Date",
            "reqd": 0
        },
        {
            "fieldname": "to_date",
            "label": __("To Date"),
            "fieldtype": "Date",
            "default": frappe.datetime.get_today(),
            "reqd": 0
        },
        {
            "fieldname": "party_type",
            "label": __("Party Type"),
            "fieldtype": "Link",
            "options": "Party Type",
            "reqd": 0
        },
        {
            "fieldname": "party",
            "label": __("Party"),
            "fieldtype": "Dynamic Link",
            "options": "party_type",
            "reqd": 0
        },
        {
            "fieldname": "payment_type",
            "label": __("Payment Type"),
            "fieldtype": "Select",
            "options": "\nPay\nReceive\nInternal Transfer",
            "reqd": 0
        },
        {
            "fieldname": "company",
            "label": __("Company"),
            "fieldtype": "Link",
            "options": "Company",
            "reqd": 0
        }
    ]
};
