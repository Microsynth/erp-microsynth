// Copyright (c) 2025, Microsynth, libracore and contributors and contributors
// For license information, please see license.txt

frappe.ui.form.on('Credit Account', {
    refresh: function(frm) {
        frm.add_custom_button(__('Overview'), function() {
            frappe.set_route('query-report', 'Customer Credits', {
                customer: frm.doc.customer,
                company: frm.doc.company,
                credit_account: frm.doc.name
            });
        });
    }
});
