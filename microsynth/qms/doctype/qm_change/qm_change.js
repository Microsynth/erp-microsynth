// Copyright (c) 2024, Microsynth, libracore and contributors and contributors
// For license information, please see license.txt

frappe.ui.form.on('QM Change', {
	refresh: function(frm) {

		// avoid manual changes to some fields
        cur_frm.set_df_property('document_type', 'read_only', true);
        cur_frm.set_df_property('document_name', 'read_only', true);
        cur_frm.set_df_property('created_by', 'read_only', true);
        cur_frm.set_df_property('created_on', 'read_only', true);

        if (frm.doc.__islocal) {
            cur_frm.set_value("created_by", frappe.session.user);
            cur_frm.set_value("created_on", frappe.datetime.get_today());
        }

        // Only creator and QAU can change these fields in Draft status:
        if (!((["Draft"].includes(frm.doc.status) || frm.doc.docstatus == 0) && (frappe.session.user === frm.doc.created_by || frappe.user.has_role('QAU')))) {
            cur_frm.set_df_property('title', 'read_only', true);
            cur_frm.set_df_property('cc_type', 'read_only', true);
            cur_frm.set_df_property('qm_process', 'read_only', true);
            cur_frm.set_df_property('company', 'read_only', true);
            cur_frm.set_df_property('current_state', 'read_only', true);
            cur_frm.set_df_property('description', 'read_only', true);
        } else {
            cur_frm.set_df_property('title', 'read_only', false);
            cur_frm.set_df_property('cc_type', 'read_only', false);
            cur_frm.set_df_property('qm_process', 'read_only', false);
            cur_frm.set_df_property('company', 'read_only', false);
            cur_frm.set_df_property('current_state', 'read_only', false);
            cur_frm.set_df_property('description', 'read_only', false);
        }

		// allow the creator or QAU to change the creator (transfer document)
        if ((!frm.doc.__islocal)
            && (["Draft"].includes(frm.doc.status) || frm.doc.docstatus == 0)
            && ((frappe.session.user === frm.doc.created_by) || (frappe.user.has_role('QAU')))
            ) {
            // add change creator button
            cur_frm.add_custom_button(
                __("Change Creator"),
                function() {
                    change_creator();
                }
            );
        }

	}
});


function change_creator() {
    frappe.prompt(
        [
            {'fieldname': 'new_creator', 
             'fieldtype': 'Link',
             'label': __('New Creator'),
             'reqd': 1,
             'options': 'User'
            }
        ],
        function(values){
            cur_frm.set_value("created_by", values.new_creator);
            cur_frm.save();
        },
        __('Set new creator'),
        __('Set')
    );
}
