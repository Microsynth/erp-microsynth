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
        },
        {
            "fieldname": "company",
            "label": __("Company"),
            "fieldtype": "Link",
            "options": "Company"
        },
        {
            "fieldname": "product_type",
            "label": __("Product Type"),
            "fieldtype": "Select",
            "options": "\nOligos\nLabels\nSequencing\nGenetic Analysis\nNGS\nFLA\nProject\nMaterial\nService"
        }
	],
    "onload": (report) => {
        report.page.add_inner_button( __("Export Sales Invoices"), function() {
            pdf_export(report.get_values());
        });
    }
};


function pdf_export(filters) {
    frappe.call({
        'method': "microsynth.microsynth.report.commission_calculator.commission_calculator.async_pdf_export",
        'args': {
            'filters': filters
        },
        'callback': function(r) {
            frappe.show_alert( __("Export ongoing ...") );
        }
    });
}
