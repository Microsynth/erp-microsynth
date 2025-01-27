// Copyright (c) 2022-2024, Microsynth, libracore and contributors
// For license information, please see license.txt


frappe.ui.form.on('Signature', {
    refresh: function(frm) {
        if ((frappe.session.user === frm.doc.user) 
            || (frappe.user.has_role("System Manager")) 
            || (frappe.user.has_role("QAU"))) {
            
            if (!frm.doc.approval_password) {
                frm.add_custom_button(__("Initialize Approval Password"), function() {
                    initialize_approval_password(frm);
                });
            } else {
                frm.add_custom_button(__("Change Approval Password"), function() {
                    change_approval_password(frm);
                });
            }
        }

        // add button to reset Approval Password
        if (frappe.user.has_role("QAU") && frm.doc.approval_password) {
            frm.add_custom_button(__("Reset Approval Password"), function() {
                reset_approval_password(frm);
            });
        }

        if (!(frappe.user.has_role("System Manager") || frappe.session.user === frm.doc.user)) {
            cur_frm.set_df_property('full_name', 'read_only', true);
        }
    }
});


function initialize_approval_password(frm) {
    frappe.prompt(
        [
            {
                'fieldname': 'new_pw',
                'fieldtype': 'Password',
                'label': __('Approval Password'),
                'reqd': 1
            },
            {
                'fieldname': 'retype_new_pw',
                'fieldtype': 'Password',
                'label': __('Retype Approval Password'),
                'reqd': 1
            }
        ],
        function(values){
            frappe.call({
                'method': 'change_approval_password',
                'doc': frm.doc,
                'args': {
                    'new_pw': values.new_pw,
                    'retype_new_pw': values.retype_new_pw
                },
                'callback': function(response) {
                    if (!response.message.error) {
                        cur_frm.reload_doc();
                        frappe.show_alert( __("Initially set Approval Password.") );
                    } else {
                        frappe.msgprint( response.message.error, __("Error") );
                    }
                }
            });
        },
        __('Initialize Approval Password'),
        __('Set initially')
    )
}


function change_approval_password(frm) {
    frappe.prompt(
        [
            {
                'fieldname': 'old_pw', 
                'fieldtype': 'Password', 
                'label': __('Old Approval Password'), 
                'reqd': 1
            },
            {
                'fieldname': 'new_pw', 
                'fieldtype': 'Password', 
                'label': __('New Approval Password'), 
                'reqd': 1
            },
            {
                'fieldname': 'retype_new_pw', 
                'fieldtype': 'Password', 
                'label': __('Retype New Approval Password'), 
                'reqd': 1
            }
        ],
        function(values){
            frappe.call({
                'method': 'change_approval_password',
                'doc': frm.doc,
                'args': {
                    'old_pw': values.old_pw,
                    'new_pw': values.new_pw,
                    'retype_new_pw': values.retype_new_pw
                },
                'callback': function(response) {
                    if (!response.message.error) {
                        cur_frm.reload_doc();
                        frappe.show_alert( __("Approval password changed.") );
                    } else {
                        frappe.msgprint( response.message.error, __("Error") );
                    }
                }
            });
        },
        __('Change Approval Password'),
        __('Set')
    )
}


function reset_approval_password(frm) {
    frappe.confirm('Are you sure you want to <b>reset</b> the <b>Approval Password</b> of ' + frm.doc.name + '? This requires the user to set a new Approval Password.',
        () => {
            frappe.call({
                'method': "reset_approval_password",
                'doc': frm.doc,
                'args':{
                    'resetting_user': frappe.session.user
                },
                'freeze': true,
                'freeze_message': __("Resetting Approval Password ..."),
                'callback': function(r)
                {
                    cur_frm.reload_doc();
                    frappe.show_alert('Reset Approval Password');
                }
            });
        }, () => {
            frappe.show_alert('No changes made');
        });
}
