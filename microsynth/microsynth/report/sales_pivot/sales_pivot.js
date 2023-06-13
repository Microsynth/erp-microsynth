// Copyright (c) 2023, Microsynth, libracore and contributors and contributors
// For license information, please see license.txt
/* eslint-disable */

frappe.query_reports["Sales Pivot"] = {
    "filters": [
        {
            "fieldname": "company",
            "label": __("Company"),
            "fieldtype": "Link",
            "options": "Company",
            "reqd": 1,
            "default": frappe.defaults.get_user_default("company") || frappe.defaults.get_global_default("company")
        },
        {
            "fieldname": "territory",
            "label": __("Territory"),
            "fieldtype": "Link",
            "options": "Territory"
        },
        {
            "fieldname": "account_manager",
            "label": __("Account Manager"),
            "fieldtype": "Link",
            "options": "User"
        },
        {
            "fieldname": "product_type",
            "label": __("Product Type"),
            "fieldtype": "Select",
            "options": "\nOligos\nLabels\nSequencing\nNGS\nFLA\nMaterial\nService"
        },
        {
            "fieldname": "fiscal_year_1",
            "label": __("Fiscal Year 1"),
            "fieldtype": "Link",
            "options": "Fiscal Year",
            "reqd": 1,
            "default": (parseInt(frappe.defaults.get_user_default("fiscal_year") || frappe.defaults.get_global_default("fiscal_year")) - 1).toString()
        },
        {
            "fieldname": "fiscal_year_2",
            "label": __("Fiscal Year 2"),
            "fieldtype": "Link",
            "options": "Fiscal Year",
            "reqd": 1,
            "default": frappe.defaults.get_user_default("fiscal_year") || frappe.defaults.get_global_default("fiscal_year")
        }
    ]
};
