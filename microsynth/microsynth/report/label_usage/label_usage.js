// Copyright (c) 2024, Microsynth
// For license information, please see license.txt
/* eslint-disable */

frappe.query_reports["Label Usage"] = {
	"filters": [
		{
            "fieldname": "from_barcode",
            "label": __("From Barcode"),
            "fieldtype": "Data",
			"reqd": 1,
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
			"reqd": 1,
            "on_change": function() {
                if ((frappe.query_report.get_filter_value("to_barcode")) && (!frappe.query_report.get_filter_value("from_barcode"))) {
                    frappe.query_report.set_filter_value("from_barcode", frappe.query_report.get_filter_value("to_barcode"));
                }
                frappe.query_report.refresh();
            }
        }
	],
    "onload": (report) => {
        hide_chart_buttons();
	}
};
