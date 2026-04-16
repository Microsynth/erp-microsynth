// Copyright (c) 2026, Microsynth
// For license information, please see license.txt
/* eslint-disable */

frappe.query_reports["Promo Credit Monitoring"] = {
    "filters": [
        {
            "fieldname": "promo_campaign",
            "label": "Promo Campaign",
            "fieldtype": "Select",
            "reqd": 1,
            "default": "Oligo Bonus Credit – Prepaid Labels",
            "options": "\nOligo Bonus Credit – Prepaid Labels"
        },
        {
            "fieldname": "person_id",
            "label": "Person ID",
            "fieldtype": "Link",
            "options": "Contact"
        },
        {
            "fieldname": "customer",
            "label": "Customer",
            "fieldtype": "Link",
            "options": "Customer"
        },
        {
            "fieldname": "from_date",
            "label": "From Date",
            "fieldtype": "Date",
			"reqd": 1,
			"default": frappe.datetime.add_months(frappe.datetime.get_today(), -1)
        },
        {
            "fieldname": "to_date",
            "label": "To Date",
            "fieldtype": "Date",
			"reqd": 1,
			"default": frappe.datetime.get_today()
        }
    ],
	"onload": function(report) {
		hide_chart_buttons();
	}
};
