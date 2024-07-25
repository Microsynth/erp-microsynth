// Copyright (c) 2024, Microsynth, libracore and contributors
// For license information, please see license.txt

frappe.ui.form.on('QM Impact Assessment', {
	refresh: function(frm) {

		//cur_frm.set_df_property('status', 'read_only', true);  TODO: comment in before releasing to ERP-Test

		// remove Menu > Duplicate
        var target ="span[data-label='" + __("Duplicate") + "']";
        $(target).parent().parent().remove();

		if (!frm.doc.__islocal) {
			if (!frm.doc.assessment_summary) {
				cur_frm.page.clear_primary_action();
            	cur_frm.page.clear_secondary_action();
				frm.dashboard.clear_comment();
                frm.dashboard.add_comment( __("Please enter and save an Assessment Summary to submit this QM Impact Assessment."), 'red', true);
			}
        }
	}
});
