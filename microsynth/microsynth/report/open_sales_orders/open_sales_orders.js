// Copyright (c) 2024, Microsynth, libracore and contributors
// For license information, please see license.txt
/* eslint-disable */

frappe.query_reports["Open Sales Orders"] = {
	"filters": [
		{
            "fieldname": "from_date",
            "label": __("From date"),
            "fieldtype": "Date",
            "reqd": 1,
			"default": ((new Date().getMonth()) == 0) ? (((new Date().getFullYear()) - 1) + "-01-01") : ((new Date().getFullYear()) + "-01-01")
        },
        {
            "fieldname": "to_date",
            "label": __("To date"),
            "fieldtype": "Date",
            "reqd": 1,
			"default": frappe.datetime.add_days(frappe.datetime.get_today(), -21)
        },
        {
            "fieldname": "company",
            "label": __("Company"),
            "fieldtype": "Link",
            "options": "Company"
        },
        {
            "fieldname":"include_zero",
            "label": __("Include zero-sum orders"),
            "fieldtype": "Check"
        }
	]
};
