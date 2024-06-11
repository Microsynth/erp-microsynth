/* Custom script extension for Payment Entry */

frappe.ui.form.on('Payment Entry', {
    refresh(frm) {
        check_display_unallocated_warning(frm);

        if (!frm.doc.__islocal) {
            frm.add_custom_button(__("Create Accounting Note"), function() {
                create_accounting_note(frm);
            });
        }
    },
    unallocated_amount(frm) {
        check_display_unallocated_warning(frm);
    },
    difference_amount(frm) {
        check_display_unallocated_warning(frm);
    },
    validate: function(frm) {
        if (frm.doc.references) {
            for (var i= 0; i < frm.doc.references.length; i++) {
                if (frm.doc.references[i].outstanding_amount > frm.doc.references[i].allocated_amount) {
                    frappe.msgprint( __("Warning, Outstanding > Allocated in row " + (i+1) + ".", __("Validation") ));
                    break;
                }
            }
        }
    },
    before_save: function(frm) {
        // hotfix: check for < 0.01 allocations
        if ((frm.doc.references) && (frm.doc.references.length > 0)) {
            for (var i = 0; i < frm.doc.references.length; i++) {
                var delta = Math.abs(frm.doc.references[i].outstanding_amount - frm.doc.references[i].allocated_amount);
                console.log(i + ": delta=" + delta);
                if ((delta < 0.01) && (delta > 0)) {
                    frappe.model.set_value(frm.doc.references[i].doctype, frm.doc.references[i].name, 'allocated_amount', frm.doc.references[i].outstanding_amount);
                }
            }
        }
    }
});


function check_display_unallocated_warning(frm) {
    if (Math.round(100 * Math.abs(cur_frm.doc.unallocated_amount || cur_frm.doc.difference_amount || 0)) > 0) {
        cur_frm.dashboard.clear_comment();
        cur_frm.dashboard.add_comment(__('This document has an unallocated amount.'), 'red', true);
    } else {
        cur_frm.dashboard.clear_comment();
    }
}


function create_accounting_note(frm) {
    if (cur_frm.is_dirty()) {
        frappe.msgprint( __("Please save your unsaved changes first."), __(Information) );
    } else {
        if (frm.doc.payment_type == "Receive") {
            var account = frm.doc.paid_to;
            var currency = frm.doc.paid_to_account_currency;
        } else if (frm.doc.payment_type == "Pay") {
            var account = frm.doc.paid_from;
            var currency = frm.doc.paid_from_account_currency;
        } else if (frm.doc.payment_type == "Internal Transfer") {
            var account = frm.doc.paid_to;
            var currency = frm.doc.paid_to_account_currency;
        } else {
            console.log("Payment Type = '" + frm.doc.payment_type + "'");
            frappe.msgprint({
                title: __('Error'),
                indicator: 'red',
                message: __("Unknown Payment Type '" + frm.doc.payment_type + "'. Please contact 5.3.2 IT Applications.")
            });
            return;
        }
        frappe.call({
            'method': 'microsynth.microsynth.report.accounting_note_overview.accounting_note_overview.create_accounting_note',
            'args': {
                'date': frm.doc.posting_date,
                'note': frm.doc.party_name ? frm.doc.party_name : "",  // empty string as fallback if party_name does not exists
                'reference_doctype': frm.doc.doctype,
                'reference_name': frm.doc.name,
                'amount': frm.doc.paid_amount,
                'account': account,
                'currency': currency
            },
            'callback': function (r) {
                var doc = r.message;
                frappe.model.sync(doc);
                frappe.set_route("Form", doc.doctype, doc.name);
            }
        });
    }
}
