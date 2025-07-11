// Copyright (c) 2025, Microsynth, libracore and contributors and contributors
// For license information, please see license.txt

frappe.ui.form.on('Item Request', {
    refresh: function(frm) {
        // Show Reject button only for Purchase Manager and Purchase User
        if (frappe.user.has_role('Purchase Manager') || frappe.user.has_role('Purchase User')) {
            if (frm.doc.docstatus === 1 && frm.doc.status !== "Rejected") {
                frm.add_custom_button(__('Reject'), function () {
                    frappe.prompt([
                        {
                            'label': 'Reject Reason',
                            'fieldname': 'reject_reason',
                            'fieldtype': 'Small Text',
                            'reqd': 1
                        }
                    ], function(values) {
                        frappe.call({
                            'method': "microsynth.microsynth.doctype.item_request.item_request.reject_item_request",
                            'args': {
                                'item_request': frm.doc.name,
                                'reject_reason': values.reject_reason || ''
                            },
                            'callback': function(r) {
                                if (!r.exc) {
                                    frappe.msgprint(__("Item Request rejected"));
                                    frm.reload_doc();
                                }
                            }
                        });
                    }, __('Reject Item Request'), __('Reject'));
                }).addClass('btn-danger');
            }
        }
    }
});
