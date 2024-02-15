// Copyright (c) 2024, Microsynth, libracore and contributors
// For license information, please see license.txt


frappe.ui.form.on('QM Review', {
    refresh: function(frm) {
        if (frm.doc.docstatus < 1) {
            // add sign button
            cur_frm.page.clear_primary_action();
            cur_frm.page.set_primary_action(
                __("Sign"),
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
                    'dt': "QM Review",
                    'dn': cur_frm.doc.name,
                    'user': frappe.session.user,
                    'password': values.password
                },
                "callback": function(response) {
                    // cur_frm.reload_doc();
                    if (response.message) {
                        // Send notification to creator
                        if (cur_frm.doc.document_type == "QM Document") {
                            frappe.call({
                                'method': 'microsynth.qms.doctype.qm_document.qm_document.assign_after_review',
                                'args': {
                                    'qm_document': cur_frm.doc.document_name
                                },
                                "async": false
                            });
                        }
                        // positive response: signature correct, open document
                        window.open("/" 
                            + frappe.utils.get_form_link(cur_frm.doc.document_type, cur_frm.doc.document_name)
                            /* + "?dt=" + (new Date()).getTime()*/, "_self");
                    }
                }
            });
        },
        __('Please enter your approval password'),
        __('Sign')
    );
}
