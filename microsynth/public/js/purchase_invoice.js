/* Custom script extension for Purchase Invoice */
// iframe interaction handler for invoice entry
window.onmessage = function(e) {
    if (e.data == "close_document") {
        if (cur_frm.is_dirty()) {
            cur_frm.save().then(function() {
                window.top.postMessage("iframe_saved", {});
            });
        } else {
            // all saved, signal can close
            window.top.postMessage("iframe_saved", {});
        }
    }
}

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

        if (!frm.doc.supplier_address) {
            frappe.throw("Please set a Supplier Address on this Purchase Invoice.");
            frappe.validated = false;
        }

        if (frm.doc.due_date < frappe.datetime.get_today()) {
            frm.dashboard.add_comment('Due date <b>exceeded</b>', 'red', true);
        }
        
        hide_in_words();
    },
    before_submit() {
        frappe.msgprint("Please use the Approval Manager to submit.");
        frappe.validated = false;
    },
    company(frm) {
        if (frm.doc.__islocal) {
            set_naming_series(frm);                 // common function
        }            
    }
});


function request_approval(frm) {
    frappe.prompt([
        {'fieldname': 'assign_to', 'fieldtype': 'Link', 'label': __('Approver'), 'options':'User', 'default': cur_frm.doc.approver, 'reqd': 1}
    ],
    function(values){
        if (values.assign_to != cur_frm.doc.approver) {
            frappe.confirm(
                __("Are you sure that you want to change the approver from " + cur_frm.doc.approver + " to " + values.assign_to + "?"),
                function () {
                    // yes
                    frappe.call({
                        'method': 'microsynth.microsynth.purchasing.create_approval_request',
                        'args': {
                            'assign_to': values.assign_to,
                            'dt': cur_frm.doc.doctype,
                            'dn': cur_frm.doc.name
                        },
                        "callback": function(response) {
                            if (response.message) {
                                frappe.show_alert( __("Approval request created") );
                                cur_frm.reload_doc();
                            } else {
                                frappe.show_alert( __("No approval request created. This Purchase Invoice seems to be already assigned to an approver.") );
                            }
                        }
                    });
                },
                function () {
                    // no
                    frappe.show_alert('No approval request created.');
                }
            );
        } else {
            frappe.call({
                'method': 'microsynth.microsynth.purchasing.create_approval_request',
                'args': {
                    'assign_to': values.assign_to,
                    'dt': cur_frm.doc.doctype,
                    'dn': cur_frm.doc.name
                },
                "callback": function(response) {
                    if (response.message) {
                        frappe.show_alert( __("Approval request created") );
                        cur_frm.reload_doc();
                    } else {
                        frappe.show_alert( __("This Purchase Invoice seems to be already assigned to an approver.") );
                    }
                }
            });
        }
    },
    __('Please choose an approver'),
    __('Request approval')
    )
}
