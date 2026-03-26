// Copyright (c) 2026, Microsynth
// For license information, please see license.txt

frappe.ui.form.on('QM Log Book', {
	refresh: function(frm) {
		if (frm.doc.__islocal && !frm.doc.document_name) {
			frm.dashboard.add_comment(__("Please create this Log Book Entry from the QM Instrument."), "red", true);
		}
		if (!frm.doc.__islocal && frm.doc.document_type && frm.doc.document_name) {
			// do not allow to relink the log book entry to another document after it has been created
			frm.set_df_property("document_name", "read_only", true);
		}
	}
});
