// Copyright (c) 2022, Microsynth, libracore and contributors and contributors
// For license information, please see license.txt
/* eslint-disable */

frappe.query_reports["Open Label Orders"] = {
    "filters": [

    ],
    "onload": (report) => {
        report.page.add_inner_button( __("Pick labels"), function() {
            pick_wizard();
        });
    }
};

function pick_wizard() {
    // get all orders to process
    frappe.call({
        'method': "microsynth.microsynth.report.open_label_orders.open_label_orders.get_data",
        'callback': function(r)
        {
            // show scan dialog
            for (var i = 0; i < r.message.length; i++) {
                frappe.prompt([
                    {
                        'fieldname': 'sales_order', 
                        'fieldtype': 'Link', 
                        'label': 'Sales Order', 
                        'readonly': 1, 
                        'options': 'Sales Order', 
                        'default': r.message[i].sales_order
                    },
                    {
                        'fieldname': 'from_barcode', 
                        'fieldtype': 'Data', 
                        'label': 'From barcode'
                    },
                    {
                        'fieldname': 'to_barcode', 
                        'fieldtype': 'Data', 
                        'label': 'To barcode'
                    }
                ],
                function (values) {
                    // create delivery note / pdf
                    frappe.call({
                        'method': "microsynth.microsynth.report.open_label_orders.open_label_orders.pick_labels",
                        'args': {
                            'sales_order': values.sales_order,
                            'from_barcode': values.from_barcode,
                            'to_barcode': values.to_barcode
                        },
                        'callback': function(r2) {
                            // open print dialog & print
                            console.log(r2.message);
                            window.open("/printview?doctype=Delivery%20Note&name=" + r2.message + "&trigger_print=1&format=Standard&no_letterhead=0&_lang=en", '_blank').focus();
                        }
                    });
                },
                __("Pick labels"),
                __("OK")
                )
            }
        }
    });
}
