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

        report.page.add_inner_button( __("New Request"), function() {
            // TODO: Open search dialog currently shown on Material Request (Button "Add Item")
        }).addClass("btn-primary");

        if (frappe.user.has_role('Purchase Manager') || frappe.user.has_role('Purchase User')) {
            report.page.add_inner_button( __("Create Purchase Order"), function() {
                create_purchase_order(frappe.query_report.get_filter_values(), frappe.query_report);
            }).addClass("btn-primary");
        }
    },
    'formatter': function(value, row, column, data, default_formatter) {
        // For Item Request rows, show item_name as plain text (no link)
        if (column.fieldname === "item_code" && data.request_type === "Item Request") {
            return data.item_name || value || "";
        }
        return default_formatter(value, row, column, data);
    }
};


function create_purchase_order(filters, report) {
    if (!filters.supplier) {
        frappe.msgprint( __("Please set the Supplier filter"), __("Validation") );
        return;
    }

    // Check for pending Item Requests in report data
    const pendingItemRequests = (report.data || []).filter(row =>
        row.request_type === "Item Request" &&
        row.supplier === filters.supplier
    );

    if (pendingItemRequests.length > 0) {
        frappe.msgprint(__("There are {0} pending Item Requests for this Supplier. Please treat them first.", [pendingItemRequests.length]), __("Warning"));
        return;
    }

    // No pending Item Requests, proceed with PO creation
    frappe.call({
        'method': "microsynth.microsynth.purchasing.create_po_from_open_mr",
        'args': {
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
