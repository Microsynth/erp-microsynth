// Copyright (c) 2024, Microsynth, libracore and contributors and contributors
// For license information, please see license.txt

frappe.ui.form.on('QM Document', {
    refresh: function(frm) {
        if (true) {
            frm.add_custom_button(__("Review request"), function() {
                request_review(frm);
            });
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