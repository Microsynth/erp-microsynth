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
            "fieldname": "qm_document",
            "label": __("QM Document"),
            "fieldtype": "Link",
            "options": "QM Document"
        }
	]
};
