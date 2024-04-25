// Copyright (c) 2024, Microsynth, libracore and contributors
// For license information, please see license.txt
/* eslint-disable */

frappe.query_reports["Revision Required"] = {
	"filters": [
		{
            "fieldname": "document_type",
            "label": __("Document Type"),
            "fieldtype": "Select",
            "options": "\nSOP\nLIST\nFORM\nFLOW\nCL\nQMH\nAPPX"
        }
	]
};
