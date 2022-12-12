// Copyright (c) 2022, Microsynth, libracore and contributors and contributors
// For license information, please see license.txt
/* eslint-disable */

frappe.query_reports["Open Label Orders"] = {
    "filters": [

    ],
    "onload": (report) => {
        report.page.add_inner_button( __("Pick labels"), function() {
            queue_builder();
        });
    }
};

function queue_builder() {
    frappe.call({
        'method': "microsynth.microsynth.report.open_label_orders.open_label_orders.get_data",
        'callback': function(r) {
            // reset queue
            locals.label_queue = r.message;
            // add status flags to each entry
            for (var i = 0; i < locals.label_queue.length; i++) {
                locals.label_queue[i].status = 0;
            }
            // start queue processing
            process_queue()
        }
    });
}

function process_queue() {
    if (locals.label_queue.length > 0) {
        // process first entry
        label_order = locals.label_queue[0];
        if (label_order.status === 0) {
            // nothing done - first barcode
            first_barcode_dialog();
        } else if (label_order.status === 1) {
            // first barcode done - get second barcode
            second_barcode_dialog();
        } else {
            // create delivery note / pdf
                frappe.call({
                    'method': "microsynth.microsynth.report.open_label_orders.open_label_orders.pick_labels",
                    'args': {
                        'sales_order': locals.label_queue[0].sales_order,
                        'from_barcode': locals.label_queue[0].from_barcode.replace(/\s+/g, ''),
                        'to_barcode': locals.label_queue[0].to_barcode.replace(/\s+/g, '')
                    },
                    'callback': function(r) {
                        // open print dialog & print
                        console.log(r.message);
                        window.open("/printview?doctype=Delivery%20Note&name=" + r.message + "&trigger_print=1&format=Standard&no_letterhead=0&_lang=en", '_blank').focus();
                    }
                });
            // kick first order out and resume
            locals.label_queue.shift();
            process_queue();
        }
    }
}


function first_barcode_dialog() {
    if (locals.label_queue.length > 0) {
        // show scan first dialog
        frappe.prompt(
            [
                {
                    'fieldname': 'from_barcode', 
                    'fieldtype': 'Data', 
                    'label': 'From barcode'
                },
                {
                    'fieldname': 'sales_order', 
                    'fieldtype': 'Link', 
                    'label': 'Sales Order', 
                    'read_only': 1, 
                    'options': 'Sales Order', 
                    'default': locals.label_queue[0].sales_order
                },
                {
                    'fieldname': 'item', 
                    'fieldtype': 'Data', 
                    'label': __('Item'), 
                    'read_only': 1, 
                    'default': locals.label_queue[0].qty + "x " + locals.label_queue[0].item_code + ": " + locals.label_queue[0].item_name
                },
                {
                    'fieldname': 'range', 
                    'fieldtype': 'Data', 
                    'label': 'Range', 
                    'read_only': 1, 
                    'default': locals.label_queue[0].range
                }
            ],
            function (values) {
                // validation: if it fails, leave status on 0 and continue, on success move to 1
                var validated = false;
                
                // TODO
                validated = true;
                
                if (validated) {
                    locals.label_queue[0].status = 1;
                }
                locals.label_queue[0].from_barcode = values.from_barcode;
                process_queue();
            },
            __("Pick first label"),
            __("OK")
        )
    }
}

function second_barcode_dialog() {
    if (locals.label_queue.length > 0) {
        // show scan second dialog
        frappe.prompt(
            [
                {
                    'fieldname': 'to_barcode', 
                    'fieldtype': 'Data', 
                    'label': 'To barcode'
                },
                {
                    'fieldname': 'sales_order', 
                    'fieldtype': 'Link', 
                    'label': 'Sales Order', 
                    'read_only': 1, 
                    'options': 'Sales Order', 
                    'default': locals.label_queue[0].sales_order
                },
                {
                    'fieldname': 'item', 
                    'fieldtype': 'Data', 
                    'label': __('Item'), 
                    'read_only': 1, 
                    'default': locals.label_queue[0].qty + "x " + locals.label_queue[0].item_code + ": " + locals.label_queue[0].item_name
                },
                {
                    'fieldname': 'range', 
                    'fieldtype': 'Data', 
                    'label': 'Range', 
                    'read_only': 1, 
                    'default': locals.label_queue[0].range
                },
                {
                    'fieldname': 'from_barcode', 
                    'fieldtype': 'Data', 
                    'label': 'From barcode', 
                    'read_only': 1, 
                    'default': locals.label_queue[0].from_barcode
                }
            ],
            function (values) {
                // validation: if it fails, leave status on 0 and continue, on success move to 1
                var validated = false;
                
                // TODO
                validated = true;
                
                if (validated) {
                    locals.label_queue[0].status = 2;
                }
                locals.label_queue[0].to_barcode = values.to_barcode;
                process_queue();
            },
            __("Pick last label"),
            __("OK")
        )
    }
}

