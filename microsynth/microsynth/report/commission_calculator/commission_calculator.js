// Copyright (c) 2023, Microsynth, libracore and contributors
// For license information, please see license.txt
/* eslint-disable */

frappe.query_reports["Commission Calculator"] = {
	"filters": [
		{
            "fieldname": "country",
            "label": __("Country"),
            "fieldtype": "Link",
            "options": "Country",
            "reqd": 1
        },
		{
            "fieldname": "factor",
            "label": __("Commission Factor"),
            "fieldtype": "Float",
            "reqd": 1
        },
		{
            "fieldname": "from_date",
            "label": __("From date"),
            "fieldtype": "Date",
            "reqd": 1
        },
        {
            "fieldname": "to_date",
            "label": __("To date"),
            "fieldtype": "Date",
            "reqd": 1
        }
	]
};
