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
        if (frm.doc.completion_date && frm.doc.completion_date > frappe.datetime.nowdate()) {
            frappe.msgprint("Completion Date cannot be in the future.");
            frappe.validated = false;
        }
    }
});
