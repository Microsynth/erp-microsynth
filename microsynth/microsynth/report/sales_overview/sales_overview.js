// Copyright (c) 2023, Microsynth, libracore and contributors and contributors
// For license information, please see license.txt
/* eslint-disable */

frappe.query_reports["Sales Overview"] = {
    "filters": [
        {
            "fieldname": "company",
            "label": __("Company"),
            "fieldtype": "Link",
            "options": "Company"
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
            "fieldname": "reporting_type",
            "label": __("Reporting Type"),
            "fieldtype": "Select",
            "options": "CHF\nEUR",
            "reqd": 1,
            "default": "CHF"
        },
        {
            "fieldname": "territory",
            "label": __("Territory"),
            "fieldtype": "Link",
            "options": "Territory"
        }
    ]
};
