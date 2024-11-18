// Copyright (c) 2024, Microsynth, libracore and contributors
// For license information, please see license.txt
/* eslint-disable */

frappe.query_reports["Label Finder"] = {
    "filters": [
        {
            "fieldname": "contact",
            "label": __("Contact"),
            "fieldtype": "Link",
            "options": "Contact"
        },
        {
            "fieldname": "registered_to",
            "label": __("Registered To"),
            "fieldtype": "Link",
            "options": "Contact"
        },
        {
            "fieldname": "customer",
            "label": __("Customer ID"),
            "fieldtype": "Link",
            "options": "Customer"
        },
        {
            "fieldname": "customer_name",
            "label": __("Customer Name"),
            "fieldtype": "Data"
        },
        {
            "fieldname": "from_barcode",
            "label": __("From Barcode"),
            "fieldtype": "Data"
        },
        {
            "fieldname": "to_barcode",
            "label": __("To Barcode"),
            "fieldtype": "Data"
        },
        {
            "fieldname": "sales_order",
            "label": __("Sales Order"),
            "fieldtype": "Link",
            "options": "Sales Order"
        },
        {
            "fieldname": "web_order_id",
            "label": __("Web Order ID"),
            "fieldtype": "Data"
        }
    ],
    "onload": (report) => {
        hide_chart_buttons();
        report.page.add_inner_button( __("Lock Labels"), function() {
            // check that all labels are unused
            all_labels_unused = true;
            for (var i = 0; i < frappe.query_report.data.length; i++) {
                if (frappe.query_report.data[i].status != "unused") {
                    frappe.msgprint("The Sequencing Label " + frappe.query_report.data[i].name + " with Barcode " + frappe.query_report.data[i].label_id + " has Status " + frappe.query_report.data[i].status + ". Unable to set status to 'locked'. No Label status was changed. Please contact IT App if you have a valid use case.");
                    all_labels_unused = false;
                    break;
                }
            }
            if (all_labels_unused) {
                // TODO: ask for a reason
                frappe.msgprint("This functionality is not yet implemented.");
            }
            // TODO: trigger label locking
        });
        report.page.add_inner_button( __("Set Labels unused"), function() {
            // check that all labels are locked
            all_labels_locked = true;
            for (var i = 0; i < frappe.query_report.data.length; i++) {
                if (frappe.query_report.data[i].status != "locked") {
                    frappe.msgprint("The Sequencing Label " + frappe.query_report.data[i].name + " with Barcode " + frappe.query_report.data[i].label_id + " has Status " + frappe.query_report.data[i].status + ". Unable to set status to 'unused'. No Label status was changed. Please contact IT App if you have a valid use case.");
                    all_labels_locked = false;
                    break;
                }
            }
            if (all_labels_locked) {
                // TODO: ask for a reason
                frappe.msgprint("This functionality is not yet implemented.");
            }
            // TODO: set Labels to status unused
        });
    }
};
