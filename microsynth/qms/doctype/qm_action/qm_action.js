// Copyright (c) 2024, Microsynth, libracore and contributors
// For license information, please see license.txt

frappe.ui.form.on('QM Action', {
	refresh: function(frm) {

		// Only creator and QAU can change these fields in Draft status: Title, NC Type, Process, Date, Company, Web Order ID
        if (!(["Draft"].includes(frm.doc.status) && (frappe.session.user === frm.doc.created_by || frappe.user.has_role('QAU')))) {
            cur_frm.set_df_property('title', 'read_only', true);
            cur_frm.set_df_property('type', 'read_only', true);
            cur_frm.set_df_property('qm_process', 'read_only', true);
            cur_frm.set_df_property('initiation_date', 'read_only', true);
            cur_frm.set_df_property('due_date', 'read_only', true);
            cur_frm.set_df_property('description', 'read_only', true);
        } else {
            cur_frm.set_df_property('title', 'read_only', false);
            cur_frm.set_df_property('type', 'read_only', false);
            cur_frm.set_df_property('qm_process', 'read_only', false);
            cur_frm.set_df_property('initiation_date', 'read_only', false);
            cur_frm.set_df_property('due_date', 'read_only', false);
            cur_frm.set_df_property('description', 'read_only', false);
        }

        // allow the responsible person or QAU to change the responsible person in Draft status (transfer document)
        if ((!frm.doc.__islocal)
            && (["Draft"].includes(frm.doc.status))
            && ((frappe.session.user === frm.doc.responsible_person) || (frappe.user.has_role('QAU')))
            ) {
            // add change responsible person button
            cur_frm.add_custom_button(
                __("Change Responsible Person"),
                function() {
                    change_responsible_person();
                }
            );
        }

	}
});


function change_responsible_person() {
    frappe.prompt(
        [
            {'fieldname': 'new_responsible_person', 
             'fieldtype': 'Link',
             'label': __('New Responsible Person'),
             'reqd': 1,
             'options': 'User'
            }
        ],
        function(values){
            cur_frm.set_value("responsible_person", values.new_responsible_person);
            cur_frm.save();
			frappe.call({
				'method': 'microsynth.qms.doctype.qm_action.qm_action.assign',
				'args': {
					'doc': cur_frm.doc.name,
					'responsible_person': values.new_responsible_person
				},
				'async': false,
				'callback': function(response) {
					cur_frm.reload_doc();
				}
			});
        },
        __('Set new responsible person'),
        __('Set')
    );
}
