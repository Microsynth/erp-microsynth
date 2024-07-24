// Copyright (c) 2024, Microsynth, libracore and contributors and contributors
// For license information, please see license.txt

frappe.ui.form.on('QM Change', {
	refresh: function(frm) {

        // remove Menu > Duplicate
        var target ="span[data-label='" + __("Duplicate") + "']";
        $(target).parent().parent().remove();

        // add advanced dashboard
        if (!frm.doc.__islocal) {
            frappe.call({
                'method': 'get_advanced_dashboard',
                'doc': frm.doc,
                'callback': function (r) {
                    cur_frm.set_df_property('overview', 'options', r.message);
                }
            });
        }

        if (frm.doc.__islocal) {
            cur_frm.set_value("created_by", frappe.session.user);
            cur_frm.set_value("created_on", frappe.datetime.get_today());
        }

        // Only creator and QAU can change these fields in Draft status:
        if (((["Draft"].includes(frm.doc.status) || frm.doc.docstatus == 0) && frappe.session.user === frm.doc.created_by) || frappe.user.has_role('QAU')) {
            cur_frm.set_df_property('title', 'read_only', false);
            cur_frm.set_df_property('cc_type', 'read_only', false);
            cur_frm.set_df_property('qm_process', 'read_only', false);
            cur_frm.set_df_property('company', 'read_only', false);
            cur_frm.set_df_property('current_state', 'read_only', false);
            cur_frm.set_df_property('description', 'read_only', false);
        } else {
            cur_frm.set_df_property('title', 'read_only', true);
            cur_frm.set_df_property('cc_type', 'read_only', true);
            cur_frm.set_df_property('qm_process', 'read_only', true);
            cur_frm.set_df_property('company', 'read_only', true);
            cur_frm.set_df_property('current_state', 'read_only', true);
            cur_frm.set_df_property('description', 'read_only', true);
        }

		// allow the creator or QAU to change the creator (transfer document) in status "Requested"
        if ((!frm.doc.__islocal)
            && (["Requested"].includes(frm.doc.status))
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

        if (frm.doc.status == 'Requested' && (frappe.session.user === frm.doc.created_by || frappe.user.has_role('QAU'))) {
            if (frm.doc.cc_type
                && frm.doc.title
                && frm.doc.description
                && frm.doc.qm_process
                && frm.doc.current_state) {
                // add submit button
                cur_frm.page.set_primary_action(
                    __("Submit to QAU"),
                    function() {
                        set_status("Assessment & Classification");
                    }
                );
            } else {
                frm.dashboard.clear_comment();
                frm.dashboard.add_comment( __("Please set and save CC Type, Title, Process, Current State and Description Change to submit this QM Change to QAU."), 'red', true);
            }
        }

        if (frm.doc.status == 'Assessment & Classification' && frappe.user.has_role('QAU')) {
            frappe.call({
                'method': 'microsynth.qms.doctype.qm_change.qm_change.has_non_completed_assessments',
                'args': {
                    'qm_change': frm.doc.name
                },
                'callback': function(response) {
                    // Check, that the requested Impact Assessments are Completed or Cancelled
                    if (response.message) {
                        frm.dashboard.add_comment( __("There are QM Impact Assessments linked that are not in Status Completed or Cancelled."), 'red', true);
                    } else {
                        cur_frm.page.set_primary_action(
                            __("Confirm Classification"),
                            function() {
                                if (cur_frm.doc.cc_type == 'Large Impact') {
                                    set_status('Trial');
                                } else {
                                    set_status('Planning');
                                }                                
                            }
                        );
                    }
                }
            });
        }

        if (frm.doc.status == 'Assessment & Classification' && frappe.user.has_role('QAU')) {
            cur_frm.add_custom_button(
                __("Request Impact Assessment"),
                function() {
                    request_impact_assessment();
                }
            ).addClass("btn-primary");
        }

        // add buttons to request CC Action and Effectiveness Check
        if (frm.doc.status == 'Planning' && (frappe.session.user === frm.doc.created_by || frappe.user.has_role('QAU'))) {
            cur_frm.add_custom_button(__("Request Action"), function() {
                    request_qm_action('CC Action');
            }).addClass("btn-primary");

            frm.add_custom_button(__("Request Effectiveness Check"), function() {
                request_qm_action("CC Effectiveness Check");
            });
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


function set_status(status) {
    frappe.call({
        'method': 'microsynth.qms.doctype.qm_change.qm_change.set_status',
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


function request_impact_assessment() {
    frappe.prompt([
        {'fieldname': 'title', 'fieldtype': 'Data', 'label': __('Title'), 'reqd': 1},
        {'fieldname': 'qm_process', 'fieldtype': 'Link', 'options': 'QM Process', 'default': cur_frm.doc.qm_process, 'label': __('Process'), 'reqd': 1},
        {'fieldname': 'creator', 'fieldtype': 'Link', 'label': __('Responsible Person'), 'options':'User', 'reqd': 1}
    ],
    function(values){
        frappe.call({
            'method': 'microsynth.qms.doctype.qm_impact_assessment.qm_impact_assessment.create_impact_assessment',
            'args': {
                'dt': cur_frm.doc.doctype,
                'dn': cur_frm.doc.name,
                'qm_process': values.qm_process,
                'title': values.title,
                'creator': values.creator
            },
            "callback": function(response) {
                cur_frm.reload_doc();
                frappe.show_alert( __("QM Impact Assessment created") +
                            ": <a href='/desk#Form/QM Impact Assessment/" +
                            response.message + "'>" + response.message +
                            "</a>"
                        );
            }
        });
    },
    __('Please create a QM Impact Assessment'),
    __('Create')
    )
}

function request_qm_action(type) {
    frappe.prompt([
        {'fieldname': 'title', 'fieldtype': 'Data', 'label': __('Title'), 'reqd': 1},
        {'fieldname': 'qm_process', 'fieldtype': 'Link', 'options': 'QM Process', 'default': cur_frm.doc.qm_process, 'label': __('Process'), 'reqd': 1},
        {'fieldname': 'responsible_person', 'fieldtype': 'Link', 'label': __('Responsible Person'), 'options':'User', 'reqd': 1},
        {'fieldname': 'due_date', 'fieldtype': 'Date', 'label': __('Due date'), 'reqd': 1},
        {'fieldname': 'description', 'fieldtype': 'Text', 'label': __('Description')}
    ],
    function(values){
        frappe.call({
            'method': 'microsynth.qms.doctype.qm_action.qm_action.create_action',
            'args': {
                'title': values.title,
                'responsible_person': values.responsible_person,
                'dt': cur_frm.doc.doctype,
                'dn': cur_frm.doc.name,
                'qm_process': values.qm_process,
                'due_date': values.due_date,
                'type': type,
                'description': values.description || ''
            },
            "callback": function(response) {
                cur_frm.reload_doc();
                frappe.show_alert( __(type + " created") +
                            ": <a href='/desk#Form/QM Action/" +
                            response.message + "'>" + response.message +
                            "</a>"
                        );
            }
        });
    },
    __(type),
    __('Request ')
    )
}