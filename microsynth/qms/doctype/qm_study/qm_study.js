// Copyright (c) 2025, Microsynth
// For license information, please see license.txt

frappe.ui.form.on('QM Study', {
    // refresh: function(frm) {

    // },
    before_submit(frm) {
        if (!frm.doc.completion_date) {
            frappe.msgprint("Please set the Completion Date.");
            frappe.validated = false;
        }
    }
});
