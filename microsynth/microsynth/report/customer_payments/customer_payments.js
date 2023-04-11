// Copyright (c) 2023, Microsynth, libracore and contributors and contributors
// For license information, please see license.txt
/* eslint-disable */

frappe.query_reports["Customer Payments"] = {
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
            "options": "Account",
            "reqd": 1,
            "get_query": function() {
                var company = frappe.query_report.get_filter_value('company');
                return {
                    "doctype": "Account",
                    "filters": {
                        "company": company,
                        "account_type": "Receivable"
                    }
                }
            }
        }
    ]
};
