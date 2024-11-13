// Copyright (c) 2024, Microsynth, libracore and contributors
// For license information, please see license.txt
/* eslint-disable */

frappe.query_reports["Open Quotations"] = {
    "filters": [
        {
            "fieldname": "sales_manager",
            "label": __("Sales Manager"),
            "fieldtype": "Link",
            "options": "User"
        },
        {
            "fieldname": "from_date",
            "label": __("From date"),
            "fieldtype": "Date",
            "reqd": 1,
            "default": new Date('2023-01-01')
        },
        {
            "fieldname": "to_date",
            "label": __("To date"),
            "fieldtype": "Date",
            "reqd": 1,
            "default": frappe.datetime.add_days(frappe.datetime.get_today(), -7)
        },
        {
            "fieldname": "company",
            "label": __("Company"),
            "fieldtype": "Link",
            "options": "Company"
        },
        {
            "fieldname": "item_codes",
            "label": __("Item Codes (comma separated)"),
            "fieldtype": "Data"
        },
        {
            "fieldname": "search_mode",
            "label": __("Search Mode"),
            "fieldtype": "Select",
            "options": "Open Quotations\nInclude unlinked orders (slow)\nInclude Expired Quotations",
            "default": "Open Quotations"
        }
    ]
};
