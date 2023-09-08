// Copyright (c) 2023, Microsynth, libracore and contributors and contributors
// For license information, please see license.txt
/* eslint-disable */

frappe.query_reports["Sales Overview Details"] = {
    "filters": [
        {
            "fieldname": "company",
            "label": __("Company"),
            "fieldtype": "Link",
            "options": "Company"
        },
        {
            "fieldname": "territory",
            "label": __("Territory"),
            "fieldtype": "Link",
            "options": "Territory"
        },
        {
            "fieldname": "fiscal_year",
            "label": __("Fiscal Year"),
            "fieldtype": "Link",
            "options": "Fiscal Year",
            "reqd": 1,
            "default": frappe.defaults.get_user_default("fiscal_year") || frappe.defaults.get_global_default("fiscal_year")
        },
        {
            "fieldname": "month",
            "label": __("Month"),
            "fieldtype": "Int",
            "reqd": 1
        },
        {
            "fieldname": "item_groups",
            "label": __("Item Group"),
            "fieldtype": "Data",
            "reqd": 1
        }
    ]
};
