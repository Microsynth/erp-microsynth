// Copyright (c) 2024, Microsynth
// For license information, please see license.txt
/* eslint-disable */

frappe.query_reports["Label Manager"] = {
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
            "fieldtype": "Data",
            "on_change": function() {
                if ((frappe.query_report.get_filter_value("from_barcode")) && (!frappe.query_report.get_filter_value("to_barcode"))) {
                    frappe.query_report.set_filter_value("to_barcode", frappe.query_report.get_filter_value("from_barcode"));
                }
                frappe.query_report.refresh();
            }
        },
        {
            "fieldname": "to_barcode",
            "label": __("To Barcode"),
            "fieldtype": "Data",
            "on_change": function() {
                if ((frappe.query_report.get_filter_value("to_barcode")) && (!frappe.query_report.get_filter_value("from_barcode"))) {
                    frappe.query_report.set_filter_value("from_barcode", frappe.query_report.get_filter_value("to_barcode"));
                }
                frappe.query_report.refresh();
            }
        },
        {
            "fieldname": "label_status",
            "label": __("Label Status"),
            "fieldtype": "Select",
            "options": "unknown\nunused\nsubmitted\nreceived\nprocessed\nlocked"
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
            "options": "Item",
            get_query: function () {
                return {
                    'filters': {
                        'is_sales_item': 1
                        // TODO: only show Items that have a Label Range associated
                    }
                };
            }
        },
        {
            "fieldname": "registered",
            "label": __("Registered"),
            "fieldtype": "Check"
        }
    ],
    "onload": (report) => {
        hide_chart_buttons();
        hide_column_filters();
        report.page.add_inner_button( __("Lock Labels"), function() {
            if (frappe.query_report.data.length == 0) {
                frappe.msgprint("No Labels to lock.");
            } else if (frappe.query_report.data.length > 1000) {
                frappe.msgprint("Unable to lock more than 1000 Labels at once.");
            } else {
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
                    // ask for a reason
                    frappe.prompt(
                        [
                            {
                                'fieldname': 'user',
                                'fieldtype': 'Link',
                                'label': __('User'),
                                'options': 'User',
                                'default': frappe.session.user,
                                'read_only': 1
                            },
                            {
                                'fieldname': 'reason',
                                'fieldtype': 'Select',
                                'label': __('Reason'),
                                'options': 'Payment of additional reactions\nLost',
                                'description': 'Please contact IT App if additional reasons are required.',
                                'reqd': 1
                            },
                            {
                                'fieldname': 'description',
                                'fieldtype': 'Text',
                                'label': __('Description')
                            }
                        ],
                        function(values) {
                            var my_filters = {};
                            for (var i = 0; i < frappe.query_report.filters.length; i++) {
                                my_filters[frappe.query_report.filters[i].fieldname] = frappe.query_report.filters[i].value;
                            }
                            // trigger label locking
                            frappe.call({
                                'method': "microsynth.microsynth.report.label_manager.label_manager.lock_labels",
                                'args': {
                                    'content_str': {'labels': labels_to_lock},
                                    'filters': my_filters,
                                    'reason': values.reason,
                                    'description': values.description || ''
                                },
                                'freeze': true,
                                'freeze_message': __('Locking ' + frappe.query_report.data.length + ' Labels ...'),
                                'callback': function(r) {
                                    if (r.message.success) {
                                        frappe.show_alert('Locked Labels');
                                        frappe.click_button('Refresh');
                                    } else {
                                        frappe.throw('Unable to lock Labels:<br>' + r.message.message + '<br><br>No Labels were locked.');
                                    }
                                }
                            });
                        },
                        __('Lock ' + frappe.query_report.data.length + ' Labels?'),
                        __('Lock')
                    )
                }
            }
        }).addClass("btn-primary");

        report.page.add_inner_button( __("Set Labels unused"), function() {
            if (frappe.query_report.data.length == 0) {
                frappe.msgprint("No Labels to set unused.");
            } else if (frappe.query_report.data.length > 100) {
                frappe.msgprint("Unable to set more than 100 Labels at once to unused.");
            } else {
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
                    // ask for a reason
                    frappe.prompt(
                        [
                            {
                                'fieldname': 'user',
                                'fieldtype': 'Link',
                                'label': __('User'),
                                'options': 'User',
                                'default': frappe.session.user,
                                'read_only': 1
                            },
                            {
                                'fieldname': 'reason',
                                'fieldtype': 'Select',
                                'label': __('Reason'),
                                'options': 'Arrived at Customer after considered lost',
                                'description': 'Please contact IT App if additional reasons are required.',
                                'reqd': 1
                            },
                            {
                                'fieldname': 'description',
                                'fieldtype': 'Text',
                                'label': __('Description')
                            }
                        ],
                        function(values) {
                            var my_filters = {};
                            for (var i = 0; i < frappe.query_report.filters.length; i++) {
                                my_filters[frappe.query_report.filters[i].fieldname] = frappe.query_report.filters[i].value;
                            }
                            // set Labels to status unused
                            frappe.call({
                                'method': "microsynth.microsynth.report.label_manager.label_manager.set_labels_unused",
                                'args':{
                                    'content_str': {'labels': labels_to_set_unused},
                                    'filters': my_filters,
                                    'reason': values.reason,
                                    'description': values.description || ''
                                },
                                'freeze': true,
                                'freeze_message': __('Setting ' + frappe.query_report.data.length + ' Labels to unused ...'),
                                'callback': function(r) {
                                    if (r.message.success) {
                                        frappe.show_alert('Set Labels to unused');
                                        frappe.click_button('Refresh');
                                    } else {
                                        frappe.throw('Unable to set Labels to unused:<br>' + r.message.message + '<br><br>No Labels were set to unused.');
                                    }

                                }
                            });
                        },
                        __('Set ' + frappe.query_report.data.length + ' Labels to unused?'),
                        __('Set unused')
                    )
                }
            }
        }).addClass("btn-primary");
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
