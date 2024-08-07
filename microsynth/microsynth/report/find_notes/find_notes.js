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
            "fieldname": "customer_name",
            "label": __("Customer Name"),
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
            "fieldname": "country",
            "label": __("Country"),
            "fieldtype": "Data"
        },
        {
            "fieldname": "city",
            "label": __("City"),
            "fieldtype": "Data"
        },
        {
            "fieldname": "pincode",
            "label": __("Postal Code"),
            "fieldtype": "Data"
        },
        {
            "fieldname": "street",
            "label": __("Street"),
            "fieldtype": "Data"
        },
        {
            "fieldname": "institute_key",
            "label": __("Institute Key"),
            "fieldtype": "Data"
        },
        {
            "fieldname": "group_leader",
            "label": __("Group Leader"),
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
	],
    "onload": (report) => {
        report.page.add_inner_button( __("Create PDF"), function() {
            create_pdf(report.get_values());
        });
    }
};


function create_pdf(filters) {
    frappe.call({
        'method': "microsynth.microsynth.report.find_notes.find_notes.create_pdf",
        'args': {
            'filters': filters
        },
        'freeze': true,
        'freeze_message': __("Creating PDF ..."),
        'callback': function (response) {
            // var doc = response.message;
            // frappe.model.sync(doc);
            // frappe.set_route("Form", doc.doctype, doc.name);
            window.location.href = response.message;
        }
    });
}
