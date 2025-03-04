// Copyright (c) 2025, Microsynth
// For license information, please see license.txt
/* eslint-disable */

frappe.query_reports["Quotation Tracker"] = {
	"filters": [
		{
            "fieldname": "sales_manager",
            "label": __("Sales Manager"),
            "fieldtype": "Link",
            "options": "User"
        }
	]
};
