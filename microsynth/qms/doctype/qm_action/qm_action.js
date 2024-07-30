// Copyright (c) 2024, Microsynth, libracore and contributors
// For license information, please see license.txt

frappe.ui.form.on('QM Action', {
    refresh: function(frm) {

        cur_frm.set_df_property('status', 'read_only', true);

        if (!frm.doc.__islocal) {
            cur_frm.page.clear_primary_action();
            cur_frm.page.clear_secondary_action();
        }

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

        if (frm.doc.status == "Work in Progress"
            && (frappe.session.user === frm.doc.responsible_person) || (frappe.user.has_role('QAU'))) {
            cur_frm.set_df_property('notes', 'read_only', false);
        } else {
            cur_frm.set_df_property('notes', 'read_only', true);
        }

        // allow QAU to cancel
        if (!frm.doc.__islocal && frm.doc.docstatus < 2 && frappe.user.has_role('QAU')) {
            frm.add_custom_button(__("Cancel"), function() {
                cancel(frm);
            }).addClass("btn-danger");
        }

        if (frm.doc.status == 'Draft' && (frappe.session.user === frm.doc.responsible_person || frappe.user.has_role('QAU'))) {
            if (frm.doc.title
                && frm.doc.type
                && frm.doc.description
                && frm.doc.qm_process
                && frm.doc.initiation_date
                && frm.doc.due_date
                && frm.doc.responsible_person) {
                // add submit button
                cur_frm.page.set_primary_action(
                    __("Submit"),
                    function() {
                        submit();
                    }
                );
            } else {
                frm.dashboard.clear_comment();
                frm.dashboard.add_comment( __("Please set and save Title, Type, Process, Initiation date, Due Date and Description to submit this QM Action."), 'red', true);
            }
        }        

        if (frm.doc.status == 'Created' && (frappe.session.user === frm.doc.responsible_person || frappe.user.has_role('QAU'))) {
            // add start working button
            cur_frm.page.set_primary_action(
                __("Start working"),
                function() {
                    set_status('Work in Progress');
                }
            );
        }

        if (frm.doc.status == 'Work in Progress' && (frappe.session.user === frm.doc.responsible_person || frappe.user.has_role('QAU'))) {
            // add complete button
            cur_frm.page.set_primary_action(
                __("Complete"),
                function() {
                    set_status('Completed');
                    cur_frm.set_value("completion_date", frappe.datetime.get_today());
                    cur_frm.reload_doc();
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

function submit(frm) {
    frappe.call({
        'method': 'microsynth.qms.doctype.qm_action.qm_action.set_created',
        'args': {
            'doc': cur_frm.doc.name,
            'user': frappe.session.user
        },
        'async': false,
        'callback': function(response) {
            cur_frm.reload_doc();
        }
    });
}

function cancel(frm) {
    frappe.confirm("Are you sure you want to cancel QM Action '" + frm.doc.name + "'? This cannot be undone.",
    () => {
        frappe.call({
            'method': 'microsynth.qms.doctype.qm_action.qm_action.cancel',
            'args': {
                'action': cur_frm.doc.name
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

function set_status(status) {
    frappe.call({
        'method': 'microsynth.qms.doctype.qm_action.qm_action.set_status',
        'args': {
            'doc': cur_frm.doc.name,
            'user': frappe.session.user,
            'status': status
        },
        'async': false,
        'callback': function(response) {
            cur_frm.reload_doc();
        }
    });
}
