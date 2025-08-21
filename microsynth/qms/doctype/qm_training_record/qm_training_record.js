// Copyright (c) 2024, Microsynth, libracore and contributors and contributors
// For license information, please see license.txt


frappe.ui.form.on('QM Training Record', {
    refresh: function(frm) {
        // reset overview html
        cur_frm.set_df_property('overview', 'options', '<p><span class="text-muted">No data for overview available.</span></p>');

        // load document overview content
        frappe.call({
            'method': 'microsynth.qms.doctype.qm_training_record.qm_training_record.get_overview',
            'args': {
                'qm_training_record': frm.doc.name
            },
            'callback': function (r) {
                cur_frm.set_df_property('overview', 'options', r.message);
            }
        });

        if (frm.doc.docstatus < 1) {
            cur_frm.page.clear_primary_action();
            if (frappe.session.user === frm.doc.trainee) {
                // add sign button
                cur_frm.page.set_primary_action(
                    __("Read & understood"),
                    function() {
                        sign();
                    }
                );
            }
        }

        if (frm.doc.docstatus > 1) {
            frm.dashboard.add_comment( __("<b>Cancelled</b> Training Record, <b>nothing to do</b>."), 'red', true);
        }

        // allow QAU to force cancel Draft
        if ((!frm.doc.__islocal) && (frm.doc.docstatus === 0) && (frappe.user.has_role('QAU'))) {
            frm.add_custom_button(__("Force Cancel"), function() {
                force_cancel(cur_frm.doc.doctype, cur_frm.doc.name);
            }).addClass("btn-danger");
        }

        // remove Menu > Duplicate
        var target ="span[data-label='" + __("Duplicate") + "']";
        $(target).parent().parent().remove();
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
