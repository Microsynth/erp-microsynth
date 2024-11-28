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
            if ((frappe.session.user != frm.doc.created_by && !frappe.user.has_role('QAU')) || !frm.doc.assessment_summary) {
                cur_frm.page.clear_primary_action();
                cur_frm.page.clear_secondary_action();
            }
            if (!frm.doc.assessment_summary && frm.doc.docstatus < 2) {
                frm.dashboard.clear_comment();
                frm.dashboard.add_comment( __("Please enter and save an Assessment Summary to submit this QM Impact Assessment."), 'red', true);
            }
        }

        // allow QAU to cancel
        if (!frm.doc.__islocal && frm.doc.docstatus < 2 && frappe.user.has_role('QAU') && frm.doc.status != 'Completed') {
            frm.add_custom_button(__("Cancel"), function() {
                cancel(frm);
            }).addClass("btn-danger");
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

function cancel(frm) {
    frappe.confirm("Are you sure you want to <b>cancel</b> QM Impact Assessment '<b>" + frm.doc.name + "</b>'? This cannot be undone.",
    () => {
        frappe.call({
            'method': 'microsynth.qms.doctype.qm_impact_assessment.qm_impact_assessment.cancel',
            'args': {
                'impact_assessment': cur_frm.doc.name
            },
            'async': false,
            'callback': function(response) {
                cur_frm.reload_doc();
            }
        });
    }, () => {
        // nothing
    });
}
