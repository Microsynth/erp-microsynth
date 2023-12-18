// Copyright (c) 2023, Microsynth, libracore and contributors
// For license information, please see license.txt
/* eslint-disable */

frappe.query_reports["Label Accounting"] = {
	"filters": [
		{
            "fieldname": "company",
            "label": __("Company"),
            "fieldtype": "Link",
            "options": "Company",
            "reqd": 1
        }
	]
};
