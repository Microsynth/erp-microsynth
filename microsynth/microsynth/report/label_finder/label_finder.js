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
        },
        {
            "fieldname": "item_code",
            "label": __("Item Code"),
            "fieldtype": "Link",
            "options": "Item"
        },
        {
            "fieldname": "registered",
            "label": __("Registered"),
            "fieldtype": "Check"
        }
    ],
    "onload": (report) => {
        hide_chart_buttons();
        hide_column_filters()
        report.page.add_inner_button( __("Lock Labels"), function() {
            var labels_to_lock = [];
            // check that all labels are unused
            var all_labels_unused = true;
            for (var i = 0; i < frappe.query_report.data.length; i++) {
                if (frappe.query_report.data[i].status != "unused") {
                    frappe.msgprint("The Sequencing Label " + frappe.query_report.data[i].name + " with Barcode " + frappe.query_report.data[i].label_id + " has Status " + frappe.query_report.data[i].status + ". Unable to set status to 'locked'. No Label status was changed. Please contact IT App if you have a valid use case.");
                    all_labels_unused = false;
                    break;
                }
                labels_to_lock.push({
                    'label_id': frappe.query_report.data[i].label_id,
                    'item_code': frappe.query_report.data[i].item_code
                });
            }
            if (all_labels_unused) {
                // TODO: ask for a reason
                frappe.msgprint("This functionality is not yet implemented.");
                // trigger label locking
                // frappe.confirm('Are you sure you want to <b>lock</b> the ' + frappe.query_report.data.length + ' Sequencing Labels selected in the Label Finder?',
                //     () => {
                //         frappe.call({
                //             'method': "microsynth.microsynth.seqblatt.lock_labels",
                //             'args':{
                //                 'content': {'labels': labels_to_lock}
                //             },
                //             'freeze': true,
                //             'freeze_message': __("Locking Labels ..."),
                //             'callback': function(r)
                //             {
                //                 frappe.show_alert('Locked Labels');
                //                 frappe.click_button('Refresh');
                //             }
                //         });
                //     }, () => {
                //         frappe.show_alert('No changes made');
                // });
            }
        });
        report.page.add_inner_button( __("Set Labels unused"), function() {
            var labels_to_set_unused = [];
            // check that all labels are locked
            var all_labels_locked = true;
            for (var i = 0; i < frappe.query_report.data.length; i++) {
                if (frappe.query_report.data[i].status != "locked") {
                    frappe.msgprint("The Sequencing Label " + frappe.query_report.data[i].name + " with Barcode " + frappe.query_report.data[i].label_id + " has Status " + frappe.query_report.data[i].status + ". Unable to set status to 'unused'. No Label status was changed. Please contact IT App if you have a valid use case.");
                    all_labels_locked = false;
                    break;
                }
                labels_to_set_unused.push({
                    'label_id': frappe.query_report.data[i].label_id,
                    'item_code': frappe.query_report.data[i].item_code
                });
            }
            if (all_labels_locked) {
                // TODO: ask for a reason
                frappe.msgprint("This functionality is not yet implemented.");
                // set Labels to status unused
                // frappe.confirm('Are you sure you want to set the ' + frappe.query_report.data.length + ' Sequencing Labels selected in the Label Finder to status <b>unused</b>?',
                //     () => {
                //         frappe.call({
                //             'method': "microsynth.microsynth.seqblatt.set_unused",
                //             'args':{
                //                 'content': {'labels': labels_to_set_unused}
                //             },
                //             'freeze': true,
                //             'freeze_message': __("Setting Labels to unused ..."),
                //             'callback': function(r)
                //             {
                //                 frappe.show_alert('Set Labels to unused');
                //                 frappe.click_button('Refresh');
                //             }
                //         });
                //     }, () => {
                //         frappe.show_alert('No changes made');
                // });
            }
        });
    }
};

function hide_column_filters() {
    let container = document.getElementsByClassName("page-content");
    const hide_column_filter_style = document.createElement("style");
    hide_column_filter_style.innerHTML = `
        .dt-header .dt-row[data-is-filter] {
          display: none !important;
        }
    `
    for (let i = 0; i < container.length; i++) {
        container[i].appendChild(hide_column_filter_style);
    }
}
