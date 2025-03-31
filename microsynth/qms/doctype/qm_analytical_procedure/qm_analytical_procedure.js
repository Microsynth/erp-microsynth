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
		}
	},
    regulatory_classification: function(frm) {
        if (frm.doc.regulatory_classification == 'GMP') {
			cur_frm.set_df_property('iso_17025_section', 'hidden', true);
			cur_frm.set_df_property('gmp_assays_section', 'hidden', false);
		} else if (frm.doc.regulatory_classification == 'ISO 17025') {
			cur_frm.set_df_property('gmp_assays_section', 'hidden', true);
			cur_frm.set_df_property('iso_17025_section', 'hidden', false);
		}
    }
});
