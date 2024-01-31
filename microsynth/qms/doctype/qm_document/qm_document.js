// Copyright (c) 2024, Microsynth, libracore and contributors
// For license information, please see license.txt


frappe.ui.form.on('QM Document', {
    refresh: function(frm) {
        if (true) {
            frm.add_custom_button(__("Review request"), function() {
                request_review(frm);
            });
        }
        if (frm.doc.docstatus > 0) {
            frm.add_custom_button(__("New version"), function() {
                create_new_version(frm);
            });
        }
        if (!frm.doc.__islocal) {
            cur_frm.page.clear_primary_action();
        }
        if (frm.doc.docstatus < 1 && frm.doc.reviewed_on && frm.doc.reviewed_by) {
            // add release button
            cur_frm.page.set_primary_action(
                __("Release"),
                function() {
                    release();
                }
            );
        }
        
        // access protection: only owner and system manager can remove attachments
        if ((frappe.session.user !== frm.doc.owner) && (!frappe.user.has_role("System Manager"))) {
            access_protection();
        }
    }
});


function request_review() {
    frappe.prompt([
        {'fieldname': 'reviewer', 'fieldtype': 'Link', 'label': __('Reviewer'), 'options':'User', 'reqd': 1},
        {'fieldname': 'due_date', 'fieldtype': 'Date', 'label': __('Due date'), 'reqd': 1}
    ],
    function(values){
        console.log(values.reviewer);
        frappe.call({
            'method': 'microsynth.qms.doctype.qm_review.qm_review.create_review',
            'args': {
                'reviewer': values.reviewer,
                'dt': cur_frm.doc.doctype,
                'dn': cur_frm.doc.name,
                'due_date': values.due_date
            },
            "callback": function(response) {
                console.log("created review request...")
                cur_frm.reload_doc();
            }
        })
    },
    __('Please choose a reviewer'),
    __('Request review')
    )
}


function create_new_version(frm) {
    frappe.call({
        'method': 'microsynth.qms.doctype.qm_document.qm_document.create_new_version',
        'args': {
            'doc': frm.doc.name
        },
        'callback': function (r) {
            frappe.set_route("Form", "QM Document", r.message.name);
        }
    });
}


function release() {
    frappe.call({
        'method': 'microsynth.qms.doctype.qm_document.qm_document.set_released',
        'args': {
            'doc': cur_frm.doc.name,
            'user': frappe.session.user
        }
    });

    frappe.prompt([
            {'fieldname': 'password', 'fieldtype': 'Password', 'label': __('Approval Password'), 'reqd': 1}  
        ],
        function(values){
            // check password and if correct, submit
            frappe.call({
                'method': 'microsynth.qms.signing.sign',
                'args': {
                    'dt': "QM Document",
                    'dn': cur_frm.doc.name,
                    'user': frappe.session.user,
                    'password': values.password
                },
                "callback": function(response) {
                    cur_frm.reload_doc();
                }
            });
        },
        __('Please enter your approval password'),
        __('Sign')
    );
}
