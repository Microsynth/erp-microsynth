// Copyright (c) 2024, Microsynth, libracore and contributors
// For license information, please see license.txt
/* eslint-disable */

frappe.query_reports["Same Day Oligos"] = {
	"filters": [
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
        },
		{
            "fieldname":"customer",
            "label": __("Customer ID"),
            "fieldtype": "Link",
            "options": "Customer"
        },
		{
            "fieldname":"customer_name",
            "label": __("Customer Name"),
            "fieldtype": "Data"
        },
		{
            "fieldname": "city",
            "label": __("City"),
            "fieldtype": "Data"
        }
	]
};
