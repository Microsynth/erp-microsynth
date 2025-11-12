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
        if (!frm.doc.__islocal && frm.doc.has_transactions) {
            cur_frm.set_df_property('customer', 'read_only', true);
            cur_frm.set_df_property('company', 'read_only', true);
            cur_frm.set_df_property('currency', 'read_only', true);
            cur_frm.set_df_property('account_type', 'read_only', true);
        }
    }
});
