// Copyright (c) 2024, Microsynth, libracore and contributors
// For license information, please see license.txt
/* eslint-disable */

frappe.query_reports["Benchmarking Information"] = {
	"filters": [
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
			"fieldname": "competitor",
			"fieldtype": "Data",
			"label": "Competitor"
		}
	]
};
