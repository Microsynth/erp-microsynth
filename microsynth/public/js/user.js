frappe.ui.form.on('User', {
    before_save(frm) {
        if (!frm.doc.enabled) {
            frappe.call({
                "method":"microsynth.microsynth.doctype.user_settings.user_settings.disable_user_settings",
                "args":{
                    "email": frm.doc.name
                }
            })
        }        
    },
    validate(frm) {
        if (frm.doc.new_password) {
            // check that this password is different from approval password
            frappe.call({
                "method": "microsynth.microsynth.doctype.signature.signature.is_password_approval_password",
                "args": {
                    "user": frm.doc.name,
                    "password": frm.doc.new_password
                },
                "async": false,
                "callback": function(response) {
                    if (response.message) {
                        // the new password equals the approval password
                        frappe.validated = false;
                        frappe.msgprint( __("Please select a password that differs from your approval password."), __("Validation") );
                    } 
                }
            });
        }
    }
})
