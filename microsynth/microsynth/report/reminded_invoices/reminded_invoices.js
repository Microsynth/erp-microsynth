// Copyright (c) 2025, Microsynth
// For license information, please see license.txt
/* eslint-disable */

frappe.query_reports["Reminded Invoices"] = {
	"filters": [
		// TODO
	],
    "onload": (report) => {
        if (!locals.double_click_handler) {
            locals.double_click_handler = true;
            // add event listener for double clicks to move up
            cur_page.container.addEventListener("dblclick", function(event) {
                let row = event.delegatedTarget.getAttribute("data-row-index");
                let column = event.delegatedTarget.getAttribute("data-col-index");
                if (parseInt(column) === 11) {
                    let accounting_note_id = frappe.query_report.data[row].accounting_note_id;
                    let note = frappe.query_report.data[row].note;
                    let remarks = frappe.query_report.data[row].remarks;
                    let sales_invoice = frappe.query_report.data[row].sales_invoice;
                    edit_cell(accounting_note_id, note, remarks, sales_invoice);
                }
            });
        }
        hide_chart_buttons();
    }
};


function edit_cell(accounting_note_id, note, remarks, sales_invoice_id) {
    var d = new frappe.ui.Dialog({
        'fields': [
            {'fieldname': 'sales_invoice_id', 'fieldtype': 'Link', 'options': "Sales Invoice", 'label': __('Sales Invoice'), 'read_only': 1, 'default': sales_invoice_id},
            {'fieldname': 'accounting_note_id', 'fieldtype': 'Link', 'options': "Accounting Note", 'label': __('Accounting Note'), 'read_only': 1, 'default': accounting_note_id},
            {'fieldname': 'note', 'fieldtype': 'Data', 'label': __('Note'), 'reqd': 1, 'default': note, 'description': 'Short summary'},
            {'fieldname': 'remarks', 'fieldtype': 'Small Text', 'label': __('Remarks'), 'default': remarks, 'description': 'Optional, detailed description or proceedings'}
        ],
        'primary_action': function(){
            d.hide();
            var values = d.get_values();
            frappe.call({
                'method': "microsynth.microsynth.report.reminded_invoices.reminded_invoices.set_accounting_note",
                'args':{
                    'accounting_note_id': accounting_note_id,
                    'note': values.note,
                    'remarks': values.remarks || null,
                    'sales_invoice_id': sales_invoice_id
                },
                'callback': function(r)
                {
                    frappe.query_report.refresh();
                }
            });
        },
        'primary_action_label': __('Save'),
        'title': accounting_note_id ? __('Edit Accounting Note') : __('Create a new Accounting Note')
    });
    d.show();
}
