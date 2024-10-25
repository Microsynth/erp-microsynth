// Copyright (c) 2024, Microsynth, libracore and contributors
// For license information, please see license.txt

frappe.ui.form.on('QM Impact Assessment', {
    refresh: function(frm) {

        cur_frm.set_df_property('status', 'read_only', true);
        cur_frm.set_df_property('qm_process', 'read_only', true);
        cur_frm.set_df_property('due_date', 'read_only', true);
        cur_frm.set_df_property('document_type', 'read_only', true);
        cur_frm.set_df_property('document_name', 'read_only', true);
        cur_frm.set_df_property('created_on', 'read_only', true);
        cur_frm.set_df_property('created_by', 'read_only', true);

        // remove Menu > Duplicate
        var target ="span[data-label='" + __("Duplicate") + "']";
        $(target).parent().parent().remove();

        // allow the creator or QAU to change the creator (transfer document) in status "Created"
            if ((!frm.doc.__islocal)
            && (frm.doc.docstatus == 0)
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
            cur_frm.save_or_update();
        },
        __('Set new creator'),
        __('Set')
    );
}
