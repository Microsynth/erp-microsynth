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
            //console.log(values.password);
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
                        // positive response: signature correct, open document
                        frappe.set_route("Form", cur_frm.doc.document_type, cur_frm.doc.document_name); 
                    }
                }
            });
        },
        __('Please enter your approval password'),
        __('Sign')
    );
}
