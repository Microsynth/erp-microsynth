// Copyright (c) 2023-2024, Microsynth, libracore and contributors
// For license information, please see license.txt
/* eslint-disable */

frappe.query_reports["Customer Credits"] = {
    "filters": [
        {
            "fieldname":"customer",
            "label": __("Customer"),
            "fieldtype": "Link",
            "options": "Customer"
        },
        {
            "fieldname": "credit_account",
            "label": __("Credit Account"),
            "fieldtype": "Link",
            "options": "Credit Account",
            "get_query": function() {
                let company = frappe.query_report.get_filter_value("company");
                let customer = frappe.query_report.get_filter_value("customer");
                let filters = {};
                if (company) {
                    filters["company"] = company;
                }
                if (customer) {
                    filters["customer"] = customer;
                }
                return {
                    'filters': filters
                };
            }
        },
        {
            "fieldname": "company",
            "label": __("Company"),
            "fieldtype": "Link",
            "options": "Company",
            "reqd": 1,
            "default": frappe.defaults.get_user_default("company") || frappe.defaults.get_global_default("company")
        },
        {
            "fieldname": "credit_type",
            "label": __("Credit Type"),
            "fieldtype": "Select",
            "options": "\nStandard\nProject"
        },
        {
            "fieldname": "to_date",
            "label": __("To Date"),
            "fieldtype": "Date"
        },
        {
            "fieldname": "currency",
            "label": __("Currency"),
            "fieldtype": "Select",
            "options": "\nCHF\n\EUR\nPLN\nSEK\nUSD"
        }
    ],
    "onload": (report) => {
        report.page.add_inner_button(__('Download PDF'), function () {
            create_pdf(
                frappe.query_report.get_filter_value("company"),
                frappe.query_report.get_filter_value("customer")
            );
        })
    }
};


function create_pdf(company, customer) {
    if (customer) {
        var w = window.open(
            frappe.urllib.get_full_url("/api/method/microsynth.microsynth.report.customer_credits.customer_credits.download_pdf"
                    + "?company=" + encodeURIComponent(company)
                    + "&customer=" + encodeURIComponent(customer))
        );
        if (!w) {
            frappe.msgprint(__("Please enable pop-ups")); return;
        }
    } else {
        frappe.msgprint(__("Please enter a Customer in the report filter, overview printing is not supported by this button.")); return;
    }
}
