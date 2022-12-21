// Copyright (c) 2016, Microsynth, libracore and contributors and contributors
// For license information, please see license.txt
/* eslint-disable */

frappe.query_reports["Oligo Orders Export"] = {
	"filters": [

	],
	"onload": (report) => {
		report.page.add_inner_button(__("Print Shipping Labels"), function () {
			queue_builder();
		});
	}
};

function queue_builder() {
    frappe.call({
        'method': "microsynth.microsynth.report.oligo_orders_export.oligo_orders_export.get_data",
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
		});
		frappe.call({
			"method": "microsynth.microsynth.utils.set_order_label_printed",
			"args": {
				"sales_orders": [ locals.order_queue[0].sales_order ]
			},
			'callback': function(r)
			{
				frappe.query_report.refresh();
			}
		});
	}
	// kick first order out and resume
	locals.order_queue.shift();
	process_queue();
}