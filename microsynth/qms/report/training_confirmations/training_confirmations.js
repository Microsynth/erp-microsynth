// Copyright (c) 2024, Microsynth, libracore and contributors
// For license information, please see license.txt
/* eslint-disable */

frappe.query_reports["Training Confirmations"] = {
    "filters": [
        {
            "fieldname": "user",
            "label": __("User"),
            "fieldtype": "Link",
            "options": "User"
        },
        {
            "fieldname": "training_status",
            "label": __("Training Status"),
            "fieldtype": "Select",
            "options": "\nSigned\nUnsigned\nCancelled"
        },
        {
            "fieldname": "qm_process",
            "label": __("QM Process"),
            "fieldtype": "Link",
            "options": "QM Process"
        },
        {
            "fieldname": "qm_document",
            "label": __("QM Document"),
            "fieldtype": "Link",
            "options": "QM Document"
        },
        {
            "fieldname": "qm_document_list",
            "label": __("QM Document List"),
            "fieldtype": "Data",
            "length": 1000,
            "description": __("Comma separated QM Document prefixes")
        },
        {
            "fieldname": "limit_to_valid",
            "label": __("Limit to valid Documents"),
            "fieldtype": "Check"
        }
    ],
    "onload": (report) => {
        hide_chart_buttons();
    }
};
