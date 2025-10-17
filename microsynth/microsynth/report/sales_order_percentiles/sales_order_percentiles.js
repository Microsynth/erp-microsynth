// Copyright (c) 2016, Microsynth, libracore and contributors and contributors
// For license information, please see license.txt
/* eslint-disable */

frappe.query_reports["Sales Order Percentiles"] = {
    filters: [
        {
            fieldname: "from_date",
            label: __("From Date"),
            fieldtype: "Date",
            reqd: 0
        },
        {
            fieldname: "to_date",
            label: __("To Date"),
            fieldtype: "Date",
            reqd: 0
        },
        {
            fieldname: "product_type",
            label: __("Product Type"),
            fieldtype: "Select",
            options: "\nOligos\nLabels\nSequencing\nGenetic Analysis\nNGS\nFLA\nProject\nMaterial\nService",
            reqd: 0
        }
    ],
    onload: function() {
		hide_chart_buttons();
    }
};
