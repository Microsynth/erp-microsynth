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
            "fieldname": "limit_to_valid",
            "label": __("Limit to valid Documents"),
            "fieldtype": "Check"
        }
    ],
    "onload": (report) => {
        hide_chart_buttons();
    }
};
