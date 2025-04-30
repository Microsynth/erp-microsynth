// Copyright (c) 2025, Microsynth
// For license information, please see license.txt

frappe.ui.form.on('QM Analytical Procedure', {
    refresh: function(frm) {
        if (!frm.doc.__islocal && frm.doc.docstatus < 2) {
            cur_frm.add_custom_button(__("Add Study"), function() {
                create_qm_study();
            }).addClass("btn-primary");
        }
        if (!frm.doc.__islocal) {
            // display an advanced dashboard
            frappe.call({
                'method': 'get_advanced_dashboard',
                'doc': frm.doc,
                'callback': function (r) {
                    cur_frm.set_df_property('overview', 'options', r.message);
                }
            });
        }
    }
});


function create_qm_study() {
    frappe.prompt([
        {'fieldname': 'title', 'fieldtype': 'Data', 'label': __('Title'), 'reqd': 1},
        {'fieldname': 'type', 'fieldtype': 'Select', 'label': __('Type'), 'options': 'Early Development\nRobustness\nProtocol Transfer\nQualification\nValidation\nReference Material\nRound Robin Testing\nOther', 'reqd': 1},
        {'fieldname': 'comments', 'fieldtype': 'Text', 'label': __('Comments')}
    ],
    function(values){
        frappe.call({
            'method': 'microsynth.qms.doctype.qm_study.qm_study.create_qm_study',
            'args': {
                'title': values.title,
                'type': values.type,
                'dt': cur_frm.doc.doctype,
                'dn': cur_frm.doc.name,
                'comments': values.comments || ''
            },
            "callback": function(response) {
                window.open(
                    response.message,
                    '_blank' // open in a new tab
                );
            }
        });
    },
    __('Create a new QM Study'),
    __('Create ')
    )
}
