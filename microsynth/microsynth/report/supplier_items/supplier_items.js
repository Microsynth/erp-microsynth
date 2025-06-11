// Copyright (c) 2025, Microsynth
// For license information, please see license.txt
/* eslint-disable */


frappe.query_reports["Supplier Items"] = {
    "filters": [
        {
            "fieldname": "item_id",
            "label": __("Item ID"),
            "fieldtype": "Link",
            "options": "Item"
        },
        {
            "fieldname": "item_name",
            "label": __("Item Name"),
            "fieldtype": "Data"
        },
        {
            "fieldname": "supplier",
            "label": __("Supplier"),
            "fieldtype": "Link",
            "options": "Supplier"
        },
        {
            "fieldname": "supplier_part_no",
            "label": __("Supplier Part Number"),
            "fieldtype": "Data"
        }
    ],
    "onload": (report) => {
        hide_chart_buttons();
    }
};

