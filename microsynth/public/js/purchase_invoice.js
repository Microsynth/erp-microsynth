/* Custom script extension for Purchase Invoice */
frappe.ui.form.on('Purchase Invoice', {
    refresh(frm) {
        if (frm.doc.__islocal) {
            prepare_naming_series(frm);             // common function
        }

        if (!frm.doc.__islocal && frm.doc.docstatus == 0 && !frm.doc.in_approval) {
            frm.add_custom_button(__("Request Approval"), function() {
                request_approval(frm);
            });
        }

        if (frm.doc.in_approval) {
            cur_frm.set_df_property('approver', 'read_only', true);
        } else {
            cur_frm.set_df_property('approver', 'read_only', false);
        }
        
        hide_in_words();
    },
    company(frm) {
        if (frm.doc.__islocal) {
            set_naming_series(frm);                 // common function
        }            
    }
});


function request_approval(frm) {
    frappe.prompt([
        {'fieldname': 'approver', 'fieldtype': 'Link', 'label': __('Approver'), 'options':'User', 'default': cur_frm.doc.approver, 'reqd': 1}
    ],
    function(values){
        frappe.call({
            'method': 'microsynth.microsynth.purchasing.create_approval_request',
            'args': {
                'approver': values.approver,
                'dt': cur_frm.doc.doctype,
                'dn': cur_frm.doc.name
            },
            "callback": function(response) {
                if (response.message) {
                    cur_frm.set_value("in_approval", 1);
                    frappe.show_alert( __("Approval request created") );
                    cur_frm.reload_doc();
                } else {
                    frappe.show_alert( __("This Purchase Invoice seems to be already assigned to an approver.") );
                }
            }
        });
    },
    __('Please choose an approver'),
    __('Request approval')
    )
}
