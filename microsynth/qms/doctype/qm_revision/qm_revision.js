// Copyright (c) 2024, Microsynth, libracore and contributors
// For license information, please see license.txt

frappe.ui.form.on('QM Revision', {
    refresh: function(frm) {
        // reset buttons
        cur_frm.page.clear_primary_action();
        cur_frm.page.clear_secondary_action();
        
        // reset overview html
        cur_frm.set_df_property('overview', 'options', '<p><span class="text-muted">No data for overview available.</span></p>');

        // load document overview content
        frappe.call({
            'method': 'microsynth.qms.doctype.qm_revision.qm_revision.get_overview',
            'args': {
                'qm_revision': frm.doc.name
            },
            'callback': function (r) {
                cur_frm.set_df_property('overview', 'options', r.message);
            }
        });

        // show sign button (only for revisor!)
        if (frm.doc.docstatus < 1) {
            cur_frm.dashboard.clear_comment();
            if (frappe.session.user !== frm.doc.revisor) {
                cur_frm.dashboard.add_comment(__('Only the assigned revisor can sign this revision.'), 'yellow', true);
            } else if (!frappe.user.has_role('QAU')) {
                cur_frm.dashboard.add_comment(__('You need the QAU role to sign this revision.'), 'yellow', true);
            } else {
                // add sign button
                cur_frm.page.set_primary_action(
                    __("Sign"),
                    function() {
                        sign();
                    }
                );
            }
        }

        // allow the creator or QAU to change revisor (transfer document)
        if ((!frm.doc.__islocal)
            && (frm.doc.docstatus === 0)
            && ((frappe.session.user === frm.doc.revisor) || (frappe.user.has_role('QAU')))
            ) {
            // add change revisor button
            cur_frm.add_custom_button(
                __("Change Revisor"),
                function() {
                    change_revisor(frm);
                }
            );
        }
        
        // remove Menu > Duplicate
        var target ="span[data-label='" + __("Duplicate") + "']";
        $(target).parent().parent().remove();
    }
});


function sign() {
    cur_frm.set_value("revisor", frappe.session.user);
    cur_frm.save().then(function() {
        frappe.prompt([
                {'fieldname': 'password', 'fieldtype': 'Password', 'label': __('Approval Password'), 'reqd': 1}  
            ],
            function(values){
                // check password and if correct, submit
                frappe.call({
                    'method': 'microsynth.qms.doctype.qm_revision.qm_revision.sign_revision',
                    'args': {
                        'doc': cur_frm.doc.name,
                        'user': frappe.session.user,
                        'password': values.password
                    },
                    "callback": function(response) {
                        if (response.message) {
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
    });
}


function change_revisor(frm) {
    frappe.prompt(
        [
            {'fieldname': 'new_revisor', 
             'fieldtype': 'Link',
             'label': __('New Revisor'),
             'reqd': 1,
             'options': 'User'
            }
        ],
        function(values){
            cur_frm.set_value("revisor", values.new_revisor);
            cur_frm.save().then(function() {
                // assign QM Revision to new revisor
                frappe.call({
                    'method': 'microsynth.qms.doctype.qm_revision.qm_revision.assign',
                    'args': {
                        'doc': cur_frm.doc.name,
                        'revisor': values.new_revisor
                    },
                    'callback': function(response) {
                        cur_frm.reload_doc();
                    }
                });
            });
        },
        __('Set new revisor'),
        __('Set')
    );
}
