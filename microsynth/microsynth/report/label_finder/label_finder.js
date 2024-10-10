// Copyright (c) 2024, Microsynth, libracore and contributors
// For license information, please see license.txt
/* eslint-disable */

frappe.query_reports["Label Finder"] = {
    "filters": [
        {
            "fieldname": "contact",
            "label": __("Contact"),
            "fieldtype": "Link",
            "options": "Contact"
        },
        {
            "fieldname": "registered_to",
            "label": __("Registered To"),
            "fieldtype": "Link",
            "options": "Contact"
        },
        {
            "fieldname": "customer",
            "label": __("Customer ID"),
            "fieldtype": "Link",
            "options": "Customer"
        },
        {
            "fieldname": "customer_name",
            "label": __("Customer Name"),
            "fieldtype": "Data"
        },
        {
            "fieldname": "from_barcode",
            "label": __("From Barcode"),
            "fieldtype": "Data"
        },
        {
            "fieldname": "to_barcode",
            "label": __("To Barcode"),
            "fieldtype": "Data"
        },
        {
            "fieldname": "sales_order",
            "label": __("Sales Order"),
            "fieldtype": "Link",
            "options": "Sales Order"
        },
        {
            "fieldname": "web_order_id",
            "label": __("Web Order ID"),
            "fieldtype": "Data"
        }
    ]
};
