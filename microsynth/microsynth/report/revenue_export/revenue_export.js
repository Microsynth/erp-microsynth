// Copyright (c) 2023, Microsynth, libracore and contributors
// For license information, please see license.txt
/* eslint-disable */

frappe.query_reports["Revenue Export"] = {
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
            "label": __("Month Year"),
            "fieldtype": "Data",
            "options": [ 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12 ],
            "reqd": 1,
            "default": 7
        }
    ]
};
