// Copyright (c) 2022-2024, Microsynth, libracore and contributors and contributors
// For license information, please see license.txt

frappe.ui.form.on('Signature', {
    refresh: function(frm) {
        frm.add_custom_button(__("Change Approval Password"), function() {
            change_approval_password(frm);
        });
    }
});

function change_approval_password(frm) {
    frappe.prompt(
        [
            {
                'fieldname': 'old_pw', 
                'fieldtype': 'Password', 
                'label': __('Old Approval Password'), 
                'reqd': 0
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
