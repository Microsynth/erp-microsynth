// Copyright (c) 2024, Microsynth, libracore and contributors and contributors
// For license information, please see license.txt

frappe.ui.form.on('QM Training Record', {
    refresh: function(frm) {
        if (frm.doc.docstatus < 1) {
            // add sign button
            cur_frm.page.clear_primary_action();
            cur_frm.page.set_primary_action(
                __("Read & understood"),
                function() {
                    sign();
                }
            );
        }
    }
});


function sign() {
    frappe.prompt([
            {'fieldname': 'password', 'fieldtype': 'Password', 'label': __('Approval Password'), 'reqd': 1}  
        ],
        function(values){
            // check password and if correct, submit
            frappe.call({
                'method': 'microsynth.qms.signing.sign',
                'args': {
                    'dt': "QM Training Record",
                    'dn': cur_frm.doc.name,
                    'user': frappe.session.user,
                    'password': values.password
                },
                "callback": function(response) {
                    if (response.message) {
                        // signed, set signing date
                        frappe.call({
                            'method': 'microsynth.qms.doctype.qm_training_record.qm_training_record.set_signed_on',
                            'args': {
                                'doc': cur_frm.doc.name
                            },
                            'async': false
                        });
                    }
                    
                    // refresh UI
                    cur_frm.reload_doc();
                }
            });
        },
        __('Please enter your approval password'),
        __('Read & understood')
    );
}
