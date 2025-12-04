// Copyright (c) 2016, Microsynth, libracore and contributors and contributors
// For license information, please see license.txt
/* eslint-disable */

frappe.query_reports["Purchase Document Overview"] = {
    "filters": [
        {
            fieldname: "document_id",
            label: __("Document ID (IR/MR/PO/PR/PI)"),
            fieldtype: "Data",
            reqd: 1
        }
    ],
    "onload": function(report) {
		hide_chart_buttons();
    }
};
