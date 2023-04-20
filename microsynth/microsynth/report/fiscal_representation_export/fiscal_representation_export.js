// Copyright (c) 2023, Microsynth, libracore and contributors and contributors
// For license information, please see license.txt
/* eslint-disable */

frappe.query_reports["Fiscal Representation Export"] = {
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
            "label": __("From date"),
            "fieldtype": "Date",
            "default": new Date().getFullYear() + "-01-01",
            "reqd": 1,
        },
        {
            "fieldname":"to_date",
            "label": __("To date"),
            "fieldtype": "Date",
            "default" : frappe.datetime.get_today(),
            "reqd": 1,
        },
    ],
    "onload": (report) => {
        report.page.add_inner_button( __("Package Export"), function() {
            package_export(report.get_values());
        });
    }
};

function package_export(filters) {
    frappe.call({
        'method': "microsynth.microsynth.report.fiscal_representation_export.fiscal_representation_export.async_package_export",
        'args': {
            'filters': filters
        },
        'callback': function(r) {
            frappe.show_alert( __("Running...") );
        }
    });
}
