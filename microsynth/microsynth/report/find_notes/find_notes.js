// Copyright (c) 2023, Microsynth, libracore and contributors
// For license information, please see license.txt
/* eslint-disable */

frappe.query_reports["Find Notes"] = {
	"filters": [
		{
            "fieldname": "contact",
            "label": __("Contact"),
            "fieldtype": "Link",
            "options": "Contact"
        },
		{
            "fieldname": "first_name",
            "label": __("First Name"),
            "fieldtype": "Data"
        },
		{
            "fieldname": "last_name",
            "label": __("Last Name"),
            "fieldtype": "Data"
        },
		{
            "fieldname": "sales_manager",
            "label": __("Sales Manager"),
            "fieldtype": "Data"
        },
		{
            "fieldname": "territory",
            "label": __("Territory"),
            "fieldtype": "Link",
            "options": "Territory"
        },
        {
            "fieldname": "city",
            "label": __("City"),
            "fieldtype": "Data"
        },
        {
            "fieldname": "from_date",
            "label": __("From date"),
            "fieldtype": "Date"
        },
        {
            "fieldname": "to_date",
            "label": __("To date"),
            "fieldtype": "Date"
        }
	]
};
