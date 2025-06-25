// Copyright (c) 2024, Microsynth, libracore and contributors
// For license information, please see license.txt
/* eslint-disable */

frappe.query_reports["Invoice Summary"] = {
    "filters": [
        {
            "fieldname": "customer",
            "label": __("Customer ID"),
            "fieldtype": "Link",
            "options": "Customer"
        },
        {
            "fieldname": "po_no",
            "label": __("Customer's Purchase Order Number"),
            "fieldtype": "Data",
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
            "fieldname": "company",
            "label": __("Company"),
            "fieldtype": "Link",
            "options": "Company"
        },
        {
            "fieldname": "currency",
            "label": __("Currency"),
            "fieldtype": "Link",
            "options": "Currency"
        }
    ]
};