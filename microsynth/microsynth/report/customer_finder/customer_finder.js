// Copyright (c) 2022, Microsynth, libracore and contributors and contributors
// For license information, please see license.txt
/* eslint-disable */

frappe.query_reports["Customer Finder"] = {
	"filters": [
		{
			"fieldname": "customer",
			"label": __("Customer"),
			"fieldtype": "Data",
			"options": ""
		}, 
		{
			"fieldname": "contact_full_name",
			"label": __("Contact name"),
			"fieldtype": "Data",
			"options": ""
		},
		{
			"fieldname": "contact_email",
			"label": __("Contact Email"),
			"fieldtype": "Data",
			"options": ""
		},
		{
			"fieldname": "contact_institute",
			"label": __("Institute"),
			"fieldtype": "Data",
			"options": ""
		},  
		{
			"fieldname": "contact_department",
			"label": __("Department"),
			"fieldtype": "Data",
			"options": ""
		},  
		{
			"fieldname": "contact_group_leader",
			"label": __("Group Leader"),
			"fieldtype": "Data",
			"options": ""
		},
		{
			"fieldname": "contact_institute_key",
			"label": __("Institute Key"),
			"fieldtype": "Data",
			"options": ""
		},
		{
			"fieldname": "address_city",
			"label": __("City"),
			"fieldtype": "Data",
			"options": ""
		},
		{
			"fieldname": "address_street",
			"label": __("Street"),
			"fieldtype": "Data",
			"options": ""
		}
	]
};
