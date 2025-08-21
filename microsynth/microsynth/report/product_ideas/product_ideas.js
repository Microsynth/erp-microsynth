// Copyright (c) 2024, Microsynth, libracore and contributors
// For license information, please see license.txt
/* eslint-disable */

frappe.query_reports["Product Ideas"] = {
    "filters": [
        {
            "fieldname":"from_date",
            "label": __("From Date"),
            "fieldtype": "Date"
        },
        {
            "fieldname":"to_date",
            "label": __("To Date"),
            "fieldtype": "Date"
        },
        {
            "fieldname": "item_group",
            "fieldtype": "Link",
            "label": "Item Group",
            "options": "Item Group"
        },
        {
            "fieldname": "territory",
            "label": __("Territory"),
            "fieldtype": "Link",
            "options": "Territory"
        },
        {
            "fieldname": "product",
            "fieldtype": "Data",
            "label": "Product"
        },
        {
            "fieldname": "item",
            "fieldtype": "Link",
            "label": "Item",
            "options": "Item"
        },
        {
            "fieldname": "rating",
            "fieldtype": "Select",
            "label": "Rating",
            "options": "\n0\n1\n2\n3\n4\n5"
        }
    ],
    "onload": (report) => {
        hide_chart_buttons();
        // Add "New" button
        report.page.add_inner_button(__('New'), () => {
            frappe.set_route('Form', 'Product Idea', 'New Product Idea');
        });
    }
};
