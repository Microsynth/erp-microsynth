// Copyright (c) 2022-2024, Microsynth, libracore and contributors
// For license information, please see license.txt
/* eslint-disable */

frappe.query_reports["Open Label Orders"] = {
    "filters": [
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
        hide_chart_buttons();
        report.page.add_inner_button( __("Pick labels"), function() {
            queue_builder(report.get_values());
        });
        report.page.add_inner_button( __("PrioPick"), function() {
            prio_pick(report.get_values());
        });
    }
};

function queue_builder(filters) {
    frappe.call({
        'method': "microsynth.microsynth.report.open_label_orders.open_label_orders.picking_ready",
        'callback': function(r) {
            if (r.message) {
                frappe.call({
                    'method': "microsynth.microsynth.report.open_label_orders.open_label_orders.get_data",
                    'args': {
                        'filters': {
                            'company': filters.company
                        }
                    },
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
            } else {
                warn_process_running();
            }
        }
    });
}

function warn_process_running() {
    frappe.msgprint( __("Another picking process is still in progress, please wait."), __("Picking in progress") );
}

function process_queue() {
    if (locals.label_queue.length > 0) {
        // process first entry
        label_order = locals.label_queue[0];
        if (label_order.additional_items) {
            let allowed_additional_items = ['20050'];
            for (let i = 0; i < label_order.additional_item_codes.length; i++) {
                let item_code = label_order.additional_item_codes[i];
                if (!allowed_additional_items.includes(item_code)) {
                    frappe.msgprint({
                        title: __("Unallowed additional Item"),
                        indicator: 'red',
                        message: __("Label Order " + label_order.sales_order + " contains the unallowed additional Item ") + item_code + ".<br>Label picking for this order is <b>not</b> permitted.<br>Please contact its creator " + label_order.owner + "."
                    });
                    return;
                } else {
                    frappe.msgprint({
                        title: __("Additional Items to consider"),
                        indicator: 'blue',
                        message: __("Label Order " + label_order.sales_order + " contains the following additional Items:<br><br>") + label_order.additional_items
                    });
                }
            }
        }
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
                        'from_barcode': Number(locals.label_queue[0].from_barcode),
                        'to_barcode': locals.label_queue[0].to_barcode,
                        'number_length': locals.label_queue[0].from_barcode.length
                    },
                    'callback': function(r) {
                        // open print dialog & print
                        console.log(r.message);
                        //if (r.message.includes("DN-")){
                        window.open("/printview?doctype=Delivery%20Note&name=" + r.message + "&trigger_print=1&format=Delivery%20Note%20Sequencing%20Labels&no_letterhead=0&_lang=en", '_blank').focus();
                        //} else {
                        //    frappe.show_alert(r.message);
                        //}
                    }
                });
            // kick first order out and resume
            locals.label_queue.shift();
            process_queue();
        }
    } else {
        // queue is empty, all done ;-) refresh view to prevent duplicate pick
        frappe.query_report.refresh();
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
                    'fieldname': 'prefix',
                    'fieldtype': 'Data',
                    'label': 'Prefix',
                    'read_only': 1,
                    'default': locals.label_queue[0].prefix
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
                // delete spaces and numbers to get the prefix
                var prefix = values.from_barcode.replace(/\s+/g, '').replace(/[0-9]/g, '');
                // delete spaces and letters
                var from_barcode = values.from_barcode.replace(/\s+/g, '').replace(/[^0-9]/g, '');
                var to_barcode = Number(from_barcode) + Number(locals.label_queue[0].qty) - 1;

                validated = is_in_range(locals.label_queue[0].range, Number(from_barcode))
                            && (!locals.label_queue[0].prefix || prefix == locals.label_queue[0].prefix);

                if (validated) {
                    locals.label_queue[0].status = 1;
                }
                else {
                    frappe.msgprint("invalid barcode range or invalid prefix");
                }
                locals.label_queue[0].from_barcode = from_barcode;

                //process_queue(); // check availability, the proceed
                are_labels_available(locals.label_queue[0].item_code, Number(from_barcode), to_barcode);
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
                    'fieldname': 'print_shipping_label',
                    'fieldtype': 'Check',
                    'label': 'Print Shipping Label',
                    'default': (['3100', '3120', '3200', '3236', '3240', '3251'].includes(locals.label_queue[0].item_code) || locals.label_queue[0].additional_item_codes.includes('20050')) ? 1 : 0
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
                    'fieldname': 'prefix',
                    'fieldtype': 'Data',
                    'label': 'Prefix',
                    'read_only': 1,
                    'default': locals.label_queue[0].prefix
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
                    'default': (locals.label_queue[0].prefix ? locals.label_queue[0].prefix : '') + locals.label_queue[0].from_barcode
                }
            ],
            function (values) {
                // validation: if it fails, leave status on 0 and continue, on success move to 1
                var validated = false;
                // delete spaces and numbers to get prefix
                var prefix = values.to_barcode.replace(/\s+/g, '').replace(/[0-9]/g, '');
                // delete spaces and letters to get to_barcode as number
                var to_barcode = Number(values.to_barcode.replace(/\s+/g, '').replace(/[^0-9]/g, ''));

                validated =
                    is_in_range(locals.label_queue[0].range, to_barcode)
                    && to_barcode == Number(locals.label_queue[0].from_barcode) + Number(locals.label_queue[0].qty) - 1
                    && (!locals.label_queue[0].prefix || prefix == locals.label_queue[0].prefix);

                if (validated) {
                    frappe.show_alert("Barcodes OK");
                    locals.label_queue[0].status = 2;
                }
                else {
                    frappe.msgprint("invalid barcode range or invalid prefix");
                }
                locals.label_queue[0].to_barcode = to_barcode;

                if (values.print_shipping_label) {
                    // print shipping label
                    frappe.call({
                        "method": "microsynth.microsynth.labels.print_shipping_label",
                        "args": {
                            "sales_order_id": locals.label_queue[0].sales_order
                        }
                    });
                }

                process_queue();
            },
            __("Pick last label"),
            __("OK")
        )
    }
}

function is_in_range(ranges, value) {
    var range_list = ranges.split(',');

    for (var i = 0; i < range_list.length; i++) {
        var e = range_list[i].split('-')
        var start = e[0].trim()
        var end = e[1].trim()

        if ( start <= value && value <= end ){
            return true;
        }
    }
    return false;
}

function are_labels_available(item_code, from_barcode, to_barcode) {
    frappe.call({
        'method': "microsynth.microsynth.report.open_label_orders.open_label_orders.are_labels_available",
        'args': {
            'item_code': item_code,
            'from_barcode': Number(from_barcode),
            'to_barcode': to_barcode
        },
        'asyc': false,
        'callback': function(r) {
            if (r.message == 1) {
                // labels available, proceed
                process_queue()
            } else {
                // labels have already been used -> stop
                frappe.msgprint("At least one of the labels from " + Number(from_barcode) + " to " + to_barcode + " is already used.");
            }
        }
    });
}

function prio_pick(report_data) {
    frappe.call({
        'method': "microsynth.microsynth.report.open_label_orders.open_label_orders.picking_ready",
        'callback': function(r) {
            if (r.message) {
                // collect all sales orders
                var orders = [];
                for (var i = 0; i < frappe.query_report.data.length; i++) {
                    orders.push(frappe.query_report.data[i].sales_order);
                }
                // show order selection dialog
                frappe.prompt([
                        {
                            'fieldname': 'sales_order',
                            'fieldtype': 'Select',
                            'label': 'Sales Order',
                            'reqd': 1,
                            'options': orders.join("\n"),
                            'default': orders[0]
                        }
                    ],
                    function(values){
                        // reset and prepare queue
                        locals.label_queue = [];
                        // find order details
                        order_details = null;
                        for (var i = 0; i < frappe.query_report.data.length; i++) {
                            if (frappe.query_report.data[i].sales_order === values.sales_order) {
                                locals.label_queue.push(frappe.query_report.data[i]);
                                locals.label_queue[0].status = 0;
                                break;
                            }
                        }
                        // start queue
                        process_queue();
                    },
                    'Select Sales Order',
                    'OK'
                );
            } else {
                warn_process_running();
            }
        }
    });
}
