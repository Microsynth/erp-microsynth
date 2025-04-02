// Copyright (c) 2025, Microsynth
// For license information, please see license.txt

frappe.ui.form.on('QM Analytical Procedure', {
    refresh: function(frm) {
        if (frm.doc.regulatory_classification == 'GMP') {
            cur_frm.set_df_property('iso_17025_section', 'hidden', true);
            cur_frm.set_df_property('gmp_assays_section', 'hidden', false);
        } else if (frm.doc.regulatory_classification == 'ISO 17025') {
            cur_frm.set_df_property('gmp_assays_section', 'hidden', true);
            cur_frm.set_df_property('iso_17025_section', 'hidden', false);
        } else {
            cur_frm.set_df_property('gmp_assays_section', 'hidden', true);
            cur_frm.set_df_property('iso_17025_section', 'hidden', true);
        }
        if (!frm.doc.__islocal && frm.doc.docstatus < 2) {
            cur_frm.add_custom_button(__("Add Study"), function() {
                create_qm_study();
            }).addClass("btn-primary");
        }
    },
    regulatory_classification: function(frm) {
        if (frm.doc.regulatory_classification == 'GMP') {
            cur_frm.set_df_property('iso_17025_section', 'hidden', true);
            cur_frm.set_df_property('gmp_assays_section', 'hidden', false);
        } else if (frm.doc.regulatory_classification == 'ISO 17025') {
            cur_frm.set_df_property('gmp_assays_section', 'hidden', true);
            cur_frm.set_df_property('iso_17025_section', 'hidden', false);
        } else {
            cur_frm.set_df_property('gmp_assays_section', 'hidden', true);
            cur_frm.set_df_property('iso_17025_section', 'hidden', true);
        }
    }
});


function create_qm_study() {
    frappe.prompt([
        {'fieldname': 'type', 'fieldtype': 'Select', 'label': __('Type'), 'options': 'Early Development\nRobustness\nProtocol Transfer\nQualification\nValidation\nRound robin testing\nOther', 'reqd': 1},
        {'fieldname': 'comments', 'fieldtype': 'Text', 'label': __('Comments')}
    ],
    function(values){
        frappe.call({
            'method': 'microsynth.qms.doctype.qm_study.qm_study.create_qm_study',
            'args': {
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
