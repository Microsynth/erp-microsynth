// Copyright (c) 2016, Microsynth, libracore and contributors and contributors
// For license information, please see license.txt
/* eslint-disable */

frappe.query_reports["Oligo Orders Ready To Package"] = {
    "filters": [

    ],
    "onload": (report) => {
        hide_chart_buttons();
        if (frappe.user.has_role("Accounts User")) {
            frappe.show_alert('Accounts User should not print Shipping Labels from this report.');
        } else {
            report.page.add_inner_button(__("Print Shipping Labels"), function () {
                frappe.call({
                    'method': "microsynth.microsynth.report.oligo_orders_ready_to_package.oligo_orders_ready_to_package.print_labels",
                    'callback': function(response){
                        frappe.show_alert( __("Started"))
                    }
                });
            });
        }
    }
};

function queue_builder() {
    frappe.call({
        'method': "microsynth.microsynth.report.oligo_orders_ready_to_package.oligo_orders_ready_to_package.get_data",
        'callback': function(r) {
            // reset queue
            locals.order_queue = r.message;
            // add status flags to each entry
            for (var i = 0; i < locals.order_queue.length; i++) {
                locals.order_queue[i].status = 0;
            }
            // start queue processing
            process_queue()
        }
    });
}

function process_queue() {
    if (locals.order_queue.length > 0) {
        order = locals.order_queue[0];
        // frappe.show_alert(locals.order_queue[0].sales_order);
        frappe.call({
            "method": "microsynth.microsynth.labels.print_address_template",
            "args": {
                "sales_order_id": locals.order_queue[0].sales_order,
                "printer_ip":"192.0.1.72"
            }
        })
    }
    // kick first order out and resume
    locals.order_queue.shift();
    process_queue();
}