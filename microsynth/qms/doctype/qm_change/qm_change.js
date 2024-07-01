// Copyright (c) 2024, Microsynth, libracore and contributors and contributors
// For license information, please see license.txt

frappe.ui.form.on('QM Change', {
	refresh: function(frm) {

		// avoid manual changes to some fields
        cur_frm.set_df_property('created_by', 'read_only', true);
        cur_frm.set_df_property('created_on', 'read_only', true);

        if (frm.doc.__islocal) {
            cur_frm.set_value("created_by", frappe.session.user);
            cur_frm.set_value("created_on", frappe.datetime.get_today());
        }

	}
});
