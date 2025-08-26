// Copyright (c) 2025, Microsynth
// For license information, please see license.txt
/* eslint-disable */

frappe.query_reports["Sales Document Overview"] = {
    "filters": [
        {
            fieldname: "web_order_id",
            label: __("Web Order ID"),
            fieldtype: "Data",
            reqd: 0
        },
        {
            fieldname: "doctype",
            label: __("DocType"),
            fieldtype: "Select",
            options: ["", "Quotation", "Sales Order", "Delivery Note", "Sales Invoice"],
            reqd: 0
        },
        {
            fieldname: "document_id",
            label: __("Document ID"),
            fieldtype: "Data",
            reqd: 0
        }
    ],
    "onload": function(report) {
		hide_chart_buttons();
    }
};
