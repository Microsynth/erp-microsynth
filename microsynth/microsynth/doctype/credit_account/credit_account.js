// Copyright (c) 2025, Microsynth, libracore and contributors and contributors
// For license information, please see license.txt

frappe.ui.form.on('Credit Account', {
    refresh: function(frm) {
        // Add Overview button to get to Customer Credits report
        frm.add_custom_button(__('Overview'), function() {
            frappe.set_route('query-report', 'Customer Credits', {
                customer: frm.doc.customer,
                company: frm.doc.company,
                credit_account: frm.doc.name
            });
        });
        // Make fields read-only if there are transactions
        if (!frm.doc.__islocal && frm.doc.has_transactions) {
            cur_frm.set_df_property('customer', 'read_only', true);
            cur_frm.set_df_property('company', 'read_only', true);
            cur_frm.set_df_property('currency', 'read_only', true);
            cur_frm.set_df_property('account_type', 'read_only', true);

            // TODO: Replace this workaround once a better solution is found
            frm.add_custom_button(__('Sales Orders'), function() {
                frappe.call({
                    method: "frappe.client.get_list",
                    args: {
                        doctype: "Sales Order",
                        filters: [
                            ["Credit Account Link", "credit_account", "=", frm.doc.name]
                        ],
                        fields: ["name"]
                    },
                    callback: function(r) {
                        if (r.message && r.message.length) {
                            const names = r.message.map(d => d.name);
                            frappe.set_route("List", "Sales Order", { "name": ["in", names] });
                        } else {
                            frappe.msgprint(__("No Sales Orders linked to this Credit Account."));
                        }
                    }
                });
            });
        }
    }
});
