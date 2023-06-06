// Copyright (c) 2022, Microsynth, libracore and contributors and contributors
// For license information, please see license.txt
/* eslint-disable */

frappe.query_reports["Invoiceable Services"] = {
    "filters": [
        {
            "fieldname":"customer",
            "label": __("Customer"),
            "fieldtype": "Link",
            "options": "Customer"
        },
        {
            "fieldname": "company",
            "label": __("Company"),
            "fieldtype": "Link",
            "options": "Company",
            "reqd": 1,
            "default": frappe.defaults.get_user_default("company") || frappe.defaults.get_global_default("company")
        }
    ],
    "onload": (report) => {
        report.page.add_inner_button(__('Create Post Invoices'), function () {
            frappe.call({
                'method': "microsynth.microsynth.invoicing.create_invoices",
                'args': {
                    'mode': "Post",
                    'company': get_company(),
                    'customer': get_customer()
                },
                'callback': function(response) {
                    frappe.show_alert( __("Started") );
                }
            });
        });
        report.page.add_inner_button(__('Create Electronic Invoices'), function () {
           frappe.call({
                'method': "microsynth.microsynth.invoicing.create_invoices",
                'args': {
                    'mode': "Electronic",
                    'company': get_company(),
                    'customer': get_customer()
                },
                'callback': function(response) {
                    frappe.show_alert( __("Started") );
                }
            });
        });
        report.page.add_inner_button(__('Create Carlo Erba Invoices'), function () {
           frappe.call({
                'method': "microsynth.microsynth.invoicing.create_invoices",
                'args': {
                    'mode': "CarloErba",
                    'company': get_company(),
                    'customer': get_customer()
                },
                'callback': function(response) {
                    frappe.show_alert( __("Started") );
                }
            });
        });
        report.page.add_inner_button(__('Create Collective Invoices'), function () {
           frappe.call({
                'method': "microsynth.microsynth.invoicing.create_invoices",
                'args': {
                    'mode': "Collective",
                    'company': get_company(),
                    'customer': get_customer()
                },
                'callback': function(response) {
                    frappe.show_alert( __("Started") );
                }
            });
        });
    }
};

function get_customer() {
    var customer = null;
    for (var i = 0; i < frappe.query_report.filters.length; i++) {
        if (frappe.query_report.filters[i].fieldname == 'customer') {
            customer = frappe.query_report.filters[i].value;
            break;
        }
    }
    return customer;
}

function get_company() {
    var company = null;
    for (var i = 0; i < frappe.query_report.filters.length; i++) {
        if (frappe.query_report.filters[i].fieldname == 'company') {
            company = frappe.query_report.filters[i].value;
            break;
        }
    }
    return company;
}
