// Copyright (c) 2024, Microsynth, libracore and contributors
// For license information, please see license.txt


frappe.ui.form.on('QM Review', {
    refresh: function(frm) {
        // reset overview html
        cur_frm.set_df_property('overview', 'options', '<p><span class="text-muted">No data for overview available.</span></p>');

        // load document overview content
        frappe.call({
            'method': 'microsynth.qms.doctype.qm_review.qm_review.get_overview',
            'args': {
                'qm_review': frm.doc.name
            },
            'callback': function (r) {
                cur_frm.set_df_property('overview', 'options', r.message);
            }
        });

        // show sign button
        if (frm.doc.docstatus < 1) {
            // add sign button
            cur_frm.page.clear_primary_action();
            cur_frm.page.set_primary_action(
                __("Sign"),
                function() {
                    sign();
                }
            );

            // add reject button
            cur_frm.page.clear_secondary_action();
            cur_frm.page.set_secondary_action(
                __("Reject"), 
                function() { 
                    reject(); 
                }
            );
        } else {
            // disable cancelation
            cur_frm.page.clear_secondary_action();
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


function reject() {
    frappe.confirm(
        __("Are you sure to reject this review? This will invalidate the document and require a new version."),
        function() {
            // on yes
            frappe.call({
                'method': 'reject',
                'doc': cur_frm.doc,
                "callback": function(response) {
                    // Send notification to creator
                    if (cur_frm.doc.document_type == "QM Document") {
                        frappe.call({
                            'method': 'microsynth.qms.doctype.qm_document.qm_document.assign_after_review',
                            'args': {
                                'qm_document': cur_frm.doc.document_name,
                                'description': "Your document " + cur_frm.doc.document_name + " has been rejected."
                            },
                            "async": false
                        });
                    }
                    // positive response: signature correct, open document
                    window.open("/" 
                        + frappe.utils.get_form_link(cur_frm.doc.document_type, cur_frm.doc.document_name)
                        /* + "?dt=" + (new Date()).getTime()*/, "_self");
                }
            });
        },
        function() {
            // on no
        }
    )
}
