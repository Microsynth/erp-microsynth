/* Custom script extension for Journal Entry */

frappe.ui.form.on('Journal Entry', {
    refresh(frm) {
        if (!frm.doc.__islocal) {
            frm.add_custom_button(__("Create Accounting Note"), function() {
                create_accounting_note(frm);
            });
        }
    }
});


function create_accounting_note(frm) {
    if (cur_frm.is_dirty()) {
        frappe.msgprint( __("Please save your unsaved changes first."), __(Information) );
    } else {
        if (frm.doc.accounts.length) {
            var account = frm.doc.accounts[0].account;
        } else {
            var account = "";
        }
        frappe.call({
            'method': 'microsynth.microsynth.report.accounting_note_overview.accounting_note_overview.create_accounting_note',
            'args': {
                'date': frm.doc.posting_date,
                'note': "",
                'reference_doctype': frm.doc.doctype,
                'reference_name': frm.doc.name,
                'amount': frm.doc.total_amount ? frm.doc.total_amount : frm.doc.total_debit,  // alternative: frm.doc.total_credit
                'account': account,
                'currency': frm.doc.total_amount_currency ? frm.doc.total_amount_currency : ""
            },
            'callback': function (r) {
                var doc = r.message;
                frappe.model.sync(doc);
                frappe.set_route("Form", doc.doctype, doc.name);
            }
        });
    }
}
