// Copyright (c) 2025, Microsynth
// For license information, please see license.txt
/* eslint-disable */

frappe.query_reports["Open Material Requests"] = {
    "filters": [
        {
            fieldname: "supplier",
            label: __("Supplier"),
            fieldtype: "Link",
            options: "Supplier"
        },
        {
            fieldname: "company",
            label: __("Company"),
            fieldtype: "Link",
            options: "Company",
            default: "Microsynth AG"
        }
    ],
    "onload": (report) => {
        hide_chart_buttons();

        report.page.add_inner_button( __("Create Purchase Order"), function() {
            create_purchase_order(report.get_values());
        }).addClass("btn-primary");
    }
};

function create_purchase_order(filters) {
    if (!filters.supplier) {
        frappe.msgprint( __("Please set the Supplier filter"), __("Validation") );
    } else {
        frappe.call({
            'method': "microsynth.microsynth.purchasing.create_po_from_open_mr",
            'args':{
                'filters': filters
            },
            'callback': function(r) {
                if (r.message) {
                    frappe.set_route("Form", "Purchase Order", r.message);
                } else {
                    frappe.show_alert("Internal Error");
                }
            }
        });
    }
}
