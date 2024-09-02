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

        if (!locals.double_click_handler) {
            locals.double_click_handler = true;
            // add event listener for double clicks to move up
            cur_page.container.addEventListener("dblclick", function(event) {
                let row = event.delegatedTarget.getAttribute("data-row-index");
                let column = event.delegatedTarget.getAttribute("data-col-index");
                if (parseInt(column) === 16) {
                    let note_id = frappe.query_report.data[row].note_id;
                    let date = frappe.query_report.data[row].date;
                    let contact = frappe.query_report.data[row].contact;
                    let contact_name = frappe.query_report.data[row].first_name + ' ' + frappe.query_report.data[row].last_name;
                    let notes = frappe.query_report.data[row].notes;
                    edit_cell(note_id, date, contact, contact_name, notes);
                }
            });
        }
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


function edit_cell(note_id, date, contact, contact_name, value) {
    var d = new frappe.ui.Dialog({
        'fields': [
            {'fieldname': 'note_id', 'fieldtype': 'Link', 'options': "Contact Note", 'label': __('Contact Note'), 'read_only': 1, 'default': note_id},
            {'fieldname': 'date', 'fieldtype': 'Date', 'label': __('Date'), 'read_only': 1, 'default': date},
            {'fieldname': 'contact', 'fieldtype': 'Link', 'options': "Contact", 'label': __('Contact'), 'read_only': 1, 'default': contact},
            {'fieldname': 'contact_name', 'fieldtype': 'Data', 'label': __('Contact Name'), 'read_only': 1, 'default': contact_name},
            {'fieldname': 'notes', 'fieldtype': 'Text Editor', 'label': __('Notes'), 'reqd': 1, 'default': value}
        ],
        'primary_action': function(){
            d.hide();
            var values = d.get_values();
            frappe.call({
                'method': "microsynth.microsynth.report.find_notes.find_notes.set_notes",
                'args':{
                    'note_id': values.note_id,
                    'notes': values.notes
                },
                'callback': function(r)
                {
                    frappe.query_report.refresh();
                }
            });
        },
        'primary_action_label': __('Save'),
        'title': __('Edit Notes')
    });
    d.show();
}
