// Copyright (c) 2026, Microsynth
// For license information, please see license.txt
/* eslint-disable */

frappe.query_reports["Procurement Prices"] = {
	"filters": [
		{
			"fieldname": "mode",
			"label": __("Mode"),
			"fieldtype": "Select",
			"options": "Order History\nBuying Prices",
			"default": "Order History",
			"reqd": 1
		},
		{
			"fieldname": "from_date",
			"label": __("From Date"),
			"fieldtype": "Date"
		},
		{
			"fieldname": "to_date",
			"label": __("To Date"),
			"fieldtype": "Date"
		},
		{
			"fieldname": "company",
			"label": __("Company"),
			"fieldtype": "Link",
			"options": "Company"
		},
		{
			"fieldname": "item_code",
			"label": __("Item"),
			"fieldtype": "Link",
			"options": "Item",
			"get_query": function() {
				return {
					"filters": {
						"is_purchase_item": 1,
						"item_group": ["=", "Purchasing"],
						"disabled": 0
					}
				};
			}
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
			"fieldname": "supplier_name",
			"label": __("Supplier Name"),
			"fieldtype": "Data"
		},
		{
			"fieldname": "supplier_part_no",
			"label": __("Supplier Item Code"),
			"fieldtype": "Data"
		}
	],
	"onload": function() {
		hide_chart_buttons();
	}
};
