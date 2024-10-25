// Copyright (c) 2024, Microsynth, libracore and contributors
// For license information, please see license.txt

frappe.ui.form.on('QM Change', {
    validate: function(frm) {
        if (frm.doc.cc_type == 'short' && frm.doc.regulatory_classification == 'GMP') {
            frappe.msgprint( __("Change Control Type 'short' cannot have Regulatory Classification 'GMP'."), __("Validation") );
            frappe.validated = false;
        }
    },
    refresh: function(frm) {
        // remove option to attach files depending on status
        if (["Closed", "Cancelled"].includes(frm.doc.status) || !(frappe.session.user === frm.doc.created_by || frappe.user.has_role('QAU'))) {
            var attach_btns = document.getElementsByClassName("add-attachment");
            for (var i = 0; i < attach_btns.length; i++) {
                attach_btns[i].style.visibility = "hidden";
            }
        }

        // access protection: avoid deletion of own attachments in status Closed and Cancelled (foreign attachments can only be deleted by System Manager)
        if (["Closed", "Cancelled"].includes(frm.doc.status)) {
            access_protection();
        } else {
            remove_access_protection();
        }

        // remove Menu > Duplicate
        var target ="span[data-label='" + __("Duplicate") + "']";
        $(target).parent().parent().remove();

        // set created_by and created_on
        if (frm.doc.__islocal) {
            cur_frm.set_value("created_by", frappe.session.user);
            cur_frm.set_value("created_on", frappe.datetime.get_today());
        }

        if ((!frm.doc.__islocal && frm.doc.status != "Draft")
            || (frm.doc.status == "Draft" && !(frappe.session.user === frm.doc.created_by || frappe.user.has_role('QAU')))) {
            cur_frm.page.clear_primary_action();
            cur_frm.page.clear_secondary_action();
        }

        // fetch classification wizard
        if (["Draft", "Created"].includes(frm.doc.status) && !frm.doc.in_approval) {
            if ((locals.classification_wizard && locals.classification_wizard=="closed") || frm.doc.cc_type) {
                if (!(frm.doc.cc_type
                    && frm.doc.qm_process
                    && frm.doc.title
                    && frm.doc.company
                    && frm.doc.description && frm.doc.description != "<div><br></div>"
                    && frm.doc.current_state && frm.doc.current_state != "<div><br></div>")) {
                        var visible = false;
                        load_wizard(visible);
                        setTimeout(function () {
                            add_restart_wizard_button();}, 300);
                    }
            } else {
                var visible = true;
                load_wizard(visible);
            }
        } else {
            // display an advanced dashboard
            frappe.call({
                'method': 'get_advanced_dashboard',
                'doc': frm.doc,
                'callback': function (r) {
                    cur_frm.set_df_property('overview', 'options', r.message);
                }
            });
        }


        // FIELDS LOCKING

        // TODO: Allow only QAU in status "Assessment & Classification" to edit the Impact table (Task #17756 KB ERP)

        if (((["Draft", "Created"].includes(frm.doc.status) || frm.doc.docstatus == 0) && frappe.user.has_role('QAU'))
            || (["Draft"].includes(frm.doc.status) && frappe.session.user === frm.doc.created_by)) {
            cur_frm.set_df_property('qm_process', 'read_only', false);
            cur_frm.set_df_property('title', 'read_only', false);
            cur_frm.set_df_property('company', 'read_only', false);
        } else {
            cur_frm.set_df_property('qm_process', 'read_only', true);
            cur_frm.set_df_property('title', 'read_only', true);
            cur_frm.set_df_property('company', 'read_only', true);
        }

        if (((["Draft", "Created"].includes(frm.doc.status) || frm.doc.docstatus == 0) && frappe.session.user === frm.doc.created_by)
            || (!["Closed", "Cancelled"].includes(frm.doc.status) && frappe.user.has_role('QAU'))) {
            cur_frm.set_df_property('current_state', 'read_only', false);
            cur_frm.set_df_property('description', 'read_only', false);
        } else {
            cur_frm.set_df_property('current_state', 'read_only', true);
            cur_frm.set_df_property('description', 'read_only', true);
        }

        // Only QAU can set fields CC Type, Regulatory Classification and Risk Classification in status Draft, Created or Assessment & Classification directly
        if (["Draft", "Created", "Assessment & Classification"].includes(frm.doc.status)
            && frappe.user.has_role('QAU')) {
            cur_frm.set_df_property('cc_type', 'read_only', false);
            cur_frm.set_df_property('regulatory_classification', 'read_only', false);
            cur_frm.set_df_property('risk_classification', 'read_only', false);
            if (frm.doc.regulatory_classification == 'GMP') {
                cur_frm.set_df_property('impact', 'read_only', false);
            } else {
                cur_frm.set_df_property('impact', 'read_only', true);
                cur_frm.set_df_property('impact', 'hidden', true);
            }
        } else {
            cur_frm.set_df_property('cc_type', 'read_only', true);
            cur_frm.set_df_property('regulatory_classification', 'read_only', true);
            cur_frm.set_df_property('risk_classification', 'read_only', true);
            cur_frm.set_df_property('impact', 'read_only', true);
            if (frm.doc.regulatory_classification != 'GMP') {
                cur_frm.set_df_property('impact', 'hidden', true);
            }
        }

        if (frm.doc.regulatory_classification && frm.doc.regulatory_classification == 'GMP') {
            cur_frm.set_df_property('impact', 'hidden', false);
            if (frm.doc.status == "Assessment & Classification" && frappe.user.has_role('QAU')) {
                fill_impact_table(frm);
            }
        }

        if (!["Closed", "Cancelled"].includes(frm.doc.status)
            && (frappe.user.has_role('QAU') || frappe.session.user === frm.doc.created_by && frm.doc.cc_type == 'short')) {
            cur_frm.set_df_property('impact_description', 'read_only', false);
        } else {
            cur_frm.set_df_property('impact_description', 'read_only', true);
        }

        if (["Draft", "Created", "Assessment & Classification", "Trial", "Planning"].includes(frm.doc.status)
            && (frappe.session.user === frm.doc.created_by || frappe.user.has_role('QAU'))) {
            cur_frm.set_df_property('summary_test_trial_results', 'read_only', false);
            cur_frm.set_df_property('action_plan_summary', 'read_only', false);
        } else {
            cur_frm.set_df_property('summary_test_trial_results', 'read_only', true);
            if (["Closed", "Cancelled"].includes(frm.doc.status) || !frappe.user.has_role('QAU')) {
                cur_frm.set_df_property('action_plan_summary', 'read_only', true);
            }
        }

        if (!["Closed", "Cancelled"].includes(frm.doc.status)
            && (frappe.session.user === frm.doc.created_by || frappe.user.has_role('QAU'))) {
            cur_frm.set_df_property('closure_comments', 'read_only', false);
        } else {
            cur_frm.set_df_property('closure_comments', 'read_only', true);
        }

        // Reference fields can be edited in all status unequals Cancelled
        if (frm.doc.docstatus < 2) {
            cur_frm.set_df_property('qm_documents', 'read_only', false);
            cur_frm.set_df_property('customers', 'read_only', false);
        } else {
            cur_frm.set_df_property('qm_documents', 'read_only', true);
            cur_frm.set_df_property('customers', 'read_only', true);
        }

        // lock all fields except References if CC is Closed
        if (["Closed", "Cancelled"].includes(frm.doc.status)
            || !(frappe.session.user === frm.doc.created_by || frappe.user.has_role('QAU'))) {
            cur_frm.set_df_property('cc_type', 'read_only', true);
            cur_frm.set_df_property('qm_documents', 'read_only', true);
            cur_frm.set_df_property('customers', 'read_only', true);
            cur_frm.set_df_property('qm_process', 'read_only', true);
            cur_frm.set_df_property('title', 'read_only', true);
            cur_frm.set_df_property('company', 'read_only', true);
            cur_frm.set_df_property('current_state', 'read_only', true);
            cur_frm.set_df_property('description', 'read_only', true);
            cur_frm.set_df_property('regulatory_classification', 'read_only', true);
            cur_frm.set_df_property('risk_classification', 'read_only', true);
            cur_frm.set_df_property('impact', 'read_only', true);
            cur_frm.set_df_property('impact_description', 'read_only', true);
            cur_frm.set_df_property('summary_test_trial_results', 'read_only', true);
            cur_frm.set_df_property('action_plan_summary', 'read_only', true);
            cur_frm.set_df_property('closure_comments', 'read_only', true);
        }


        // BUTTONS

        // allow QAU to cancel
        if (!frm.doc.__islocal && frm.doc.docstatus < 2 && frm.doc.status != 'Closed' && frappe.user.has_role('QAU')) {
            frm.add_custom_button(__("Cancel"), function() {
                cancel(frm);
            }).addClass("btn-danger");
        }

        // allow the creator or QAU to change the creator (transfer document) in status "Created"
        if ((!frm.doc.__islocal)
            && (["Draft", "Created"].includes(frm.doc.status))
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

        // add button to request an Impact Assessment
        if (frm.doc.status == 'Assessment & Classification'
            && ((frappe.session.user === frm.doc.created_by && frm.doc.cc_type == 'short')
                || frappe.user.has_role('QAU'))) {
            cur_frm.add_custom_button(
                __("Request Impact Assessment"),
                function() {
                    request_impact_assessment();
                }
            ).addClass("btn-primary");
        }

        // add buttons to request CC Action and Effectiveness Check
        if (frm.doc.status == 'Planning'
            && (frappe.user.has_role('QAU') || (frappe.session.user === frm.doc.created_by && !frm.doc.in_approval))) {
            cur_frm.add_custom_button(__("Request Action"), function() {
                request_qm_action('Change Control Action');
            }).addClass("btn-primary");

            frm.add_custom_button(__("Request Effectiveness Check"), function() {
                request_qm_action("CC Effectiveness Check");
            });
        }


        // STATUS TRANSITIONS

        if (frm.doc.status == 'Created'
            && (frappe.session.user === frm.doc.created_by || frappe.user.has_role('QAU'))) {
            if (frm.doc.cc_type
                && frm.doc.qm_process
                && frm.doc.title
                && frm.doc.company
                && frm.doc.description && frm.doc.description != "<div><br></div>"
                && frm.doc.current_state && frm.doc.current_state != "<div><br></div>") {
                if ((frappe.session.user === frm.doc.created_by && frm.doc.cc_type == 'short')
                    || frappe.user.has_role('QAU')) {
                    // add submit button
                    cur_frm.page.set_primary_action(
                        __("Proceed"),
                        function() {
                            set_status("Assessment & Classification");
                            frappe.call({
                                'method': 'set_in_approval',
                                'doc': cur_frm.doc,
                                'args': {
                                    'in_approval': 0
                                },
                                'async': false,
                                'callback': function (r) {
                                }
                            });
                            cur_frm.reload_doc();
                        }
                    );
                } else if (!frm.doc.in_approval) {
                    cur_frm.page.set_primary_action(
                        __("Send to Approval"),
                        function() {
                            frappe.call({
                                'method': 'set_in_approval',
                                'doc': cur_frm.doc,
                                'args': {
                                    'in_approval': 1
                                },
                                'async': false,
                                'callback': function (r) {
                                }
                            });
                            cur_frm.reload_doc();
                        }
                    );
                } else {
                    frm.dashboard.add_comment( __("Waiting for QAU to proceed."), 'yellow', true);
                }
            } else {
                frm.dashboard.clear_comment();
                if (frappe.session.user === frm.doc.created_by && frm.doc.cc_type == 'short') {
                    frm.dashboard.add_comment( __("Please set and save CC Type, Process, Title, Company, Current State and Description Change to proceed."), 'red', true);
                } else {
                    frm.dashboard.add_comment( __("Please set and save CC Type, Process, Title, Company, Current State and Description Change to submit this QM Change to QAU."), 'red', true);
                }
            }
        }

        if (frm.doc.status == 'Assessment & Classification'
            && ((frappe.session.user === frm.doc.created_by && frm.doc.cc_type == 'short')
                || frappe.user.has_role('QAU'))) {
            if (frm.doc.regulatory_classification
                && frm.doc.risk_classification) {
                var continue_checks = false;
                // Ensure that each Impact question is answered if Regulatory Classification is GMP
                if (frm.doc.regulatory_classification == 'GMP') {
                    frappe.call({
                        'method': 'are_all_impacts_answered',
                        'doc': cur_frm.doc,
                        'async': false,
                        'callback': function (response) {
                            if (response.message) {
                                // all questions answered
                                if (frm.doc.risk_classification == 'minor') {
                                    // check that no impact question is answered with yes
                                    frappe.call({
                                        'method': 'has_impact',
                                        'doc': cur_frm.doc,
                                        'async': false,
                                        'callback': function (response) {
                                            if (response.message) {
                                                frm.dashboard.add_comment( __("There is an impact. The risk classification has to be changed to major to continue."), 'red', true);
                                                continue_checks = false;
                                            } else {
                                                continue_checks = true;
                                            }
                                        }
                                    });
                                } else {
                                    continue_checks = true;
                                }
                            } else {
                                frm.dashboard.add_comment( __("Please answer all potential impacts."), 'red', true);
                                continue_checks = false;
                            }
                        }
                    });
                } else {
                    continue_checks = true;
                }
                if (continue_checks) {
                    // Check that there is at least one QM Impact Assessment
                    frappe.call({
                        'method': 'microsynth.qms.doctype.qm_change.qm_change.has_assessments',
                        'args': {
                            'qm_change': frm.doc.name
                        },
                        'callback': function(response) {
                            // Check, that the requested Impact Assessments are Completed or Cancelled
                            if (response.message) {
                                frappe.call({
                                    'method': 'microsynth.qms.doctype.qm_change.qm_change.has_non_completed_assessments',
                                    'args': {
                                        'qm_change': frm.doc.name
                                    },
                                    'callback': function(response) {
                                        // Check, that all requested Impact Assessments are Completed or Cancelled
                                        if (response.message) {
                                            frm.dashboard.add_comment( __("There are QM Impact Assessments linked that are not in Status Completed or Cancelled."), 'red', true);
                                        } else {
                                            cur_frm.page.set_primary_action(
                                                __("Confirm Classification"),
                                                function() {
                                                    if (cur_frm.doc.cc_type == 'full') {
                                                        set_status('Trial');
                                                    } else {
                                                        set_status('Planning');
                                                    }                                
                                                }
                                            );
                                        }
                                    }
                                });
                            } else {
                                frm.dashboard.add_comment( __("Please request at least one QM Impact Assessments."), 'red', true);
                            }
                        }
                    });
                }
            } else {
                frm.dashboard.clear_comment();
                frm.dashboard.add_comment( __("Please do the Classification"), 'red', true);
            }
        }

        if (frm.doc.status == 'Trial'
            && (frappe.session.user === frm.doc.created_by || frappe.user.has_role('QAU'))) {
            if (frm.doc.summary_test_trial_results) {
                if (frm.doc.cc_type == 'full' && frappe.user.has_role('QAU') && frm.doc.in_approval) {
                    // Add Approve and Reject buttons
                    cur_frm.page.set_primary_action(
                        __("Approve"),
                        function() {
                            create_qm_decision("Approve", frm.doc.status, "Planning");
                        }
                    );
                    frm.add_custom_button(__("Reject"), function() {
                        create_qm_decision("Reject", frm.doc.status, "Planning");
                    }).addClass("btn-danger");
                } else if (frm.doc.cc_type == 'short') {
                    cur_frm.page.set_primary_action(
                        __("Finish Tests & Trials"),
                        function() {
                            set_status("Planning");
                        }
                    );
                } else if (!frm.doc.in_approval) {
                    cur_frm.page.set_primary_action(
                        __("Send to Approval"),
                        function() {
                            frappe.call({
                                'method': 'set_in_approval',
                                'doc': cur_frm.doc,
                                'args': {
                                    'in_approval': 1
                                },
                                'async': false,
                                'callback': function (r) {
                                }
                            });
                            cur_frm.reload_doc();
                        }
                    );
                } else {
                    frm.dashboard.add_comment( __("In Approval"), 'yellow', true);
                }
            } else {
                frm.dashboard.add_comment( __("Please enter a Summary of Test & Trial Results."), 'red', true);
            }
        }

        if (frm.doc.status == 'Planning'
            && (frappe.session.user === frm.doc.created_by || frappe.user.has_role('QAU'))) {
            // Check that there is at least one Action
            frappe.call({
                'method': 'microsynth.qms.doctype.qm_change.qm_change.has_action',
                'args': {
                    'doc': frm.doc.name,
                    'type': 'Change Control Action'
                },
                'callback': function(response) {
                    if (response.message) {
                        if (frm.doc.action_plan_summary) {
                            if (frm.doc.cc_type == 'full' && frappe.user.has_role('QAU') && frm.doc.in_approval) {
                                // Add Approve and Reject buttons
                                cur_frm.page.set_primary_action(
                                    __("Approve"),
                                    function() {
                                        create_qm_decision("Approve", frm.doc.status, "Implementation");
                                    }
                                );
                                frm.add_custom_button(__("Reject"), function() {
                                    create_qm_decision("Reject", frm.doc.status, "Implementation");
                                }).addClass("btn-danger");
                            } else if (frm.doc.cc_type == 'short') {
                                cur_frm.page.set_primary_action(
                                    __("Finish Planning"),
                                    function() {
                                        set_status('Implementation');
                                    }
                                );
                            } else if (!frm.doc.in_approval) {
                                cur_frm.page.set_primary_action(
                                    __("Send to Approval"),
                                    function() {
                                        frappe.call({
                                            'method': 'set_in_approval',
                                            'doc': cur_frm.doc,
                                            'args': {
                                                'in_approval': 1
                                            },
                                            'async': false,
                                            'callback': function (r) {
                                            }
                                        });
                                        cur_frm.reload_doc();
                                    }
                                );
                            } else {
                                frm.dashboard.add_comment( __("In Approval"), 'yellow', true);
                            }
                        } else {
                            frm.dashboard.add_comment( __("Please enter an Action Plan Summary."), 'red', true);
                        }
                    } else {
                        frm.dashboard.add_comment( __("Please request at least one Action."), 'red', true);
                    }
                }
            });
        }

        if (frm.doc.status == 'Implementation'
            && (frappe.session.user === frm.doc.created_by || frappe.user.has_role('QAU'))) {
            frappe.call({
                'method': 'microsynth.qms.doctype.qm_change.qm_change.has_non_completed_action',
                'args': {
                    'doc': frm.doc.name,
                    'type': 'Change Control Action'
                },
                'callback': function(response) {
                    // Check, that all actions are finished
                    if (response.message) {
                        frm.dashboard.add_comment( __("Please complete all Change Control Actions and reload this QM Change to finish the Implementation."), 'red', true);
                    } else if (frappe.user.has_role('QAU') && frm.doc.in_approval) {
                        // Add Approve and Reject buttons
                        cur_frm.page.set_primary_action(
                            __("Approve"),
                            function() {
                                create_qm_decision("Approve", frm.doc.status, "Completed");
                            }
                        );
                        frm.add_custom_button(__("Reject"), function() {
                            create_qm_decision("Reject", frm.doc.status, "Completed");
                        }).addClass("btn-danger");
                    } else if (!frm.doc.in_approval) {  //  && frappe.session.user === frm.doc.created_by
                        cur_frm.page.set_primary_action(
                            __("Send to Approval"),
                            function() {
                                frappe.call({
                                    'method': 'set_in_approval',
                                    'doc': cur_frm.doc,
                                    'args': {
                                        'in_approval': 1
                                    },
                                    'async': false,
                                    'callback': function (r) {
                                    }
                                });
                                cur_frm.reload_doc();
                            }
                        );
                    } else if (frm.doc.in_approval) {
                        frm.dashboard.add_comment( __("In Approval"), 'yellow', true);
                    } else {
                        frm.dashboard.add_comment( __("Rejected. The Creator was notified, has to revise and resend it to Approval."), 'yellow', true);
                    }
                }
            });
        }

        if (frm.doc.status == 'Completed'
            && ((frappe.session.user === frm.doc.created_by && frm.doc.cc_type == 'short')
                || frappe.user.has_role('QAU'))) {
            if (frm.doc.closure_comments) {
                frappe.call({
                    'method': 'microsynth.qms.doctype.qm_change.qm_change.has_non_completed_action',
                    'args': {
                        'doc': frm.doc.name,
                        'type': 'CC Effectiveness Check'
                    },
                    'callback': function(response) {
                        // Check, that all actions are finished
                        if (response.message) {
                            frm.dashboard.add_comment( __("Please complete Effectiveness Check and reload this QM Change to close it."), 'red', true);
                        } else {
                            // add button to finish implementation and complete
                            cur_frm.page.set_primary_action(
                                __("Close"),
                                function() {
                                    set_status('Closed');
                                }
                            );
                        }
                    }
                });
            } else {
                frm.dashboard.clear_comment();
                frm.dashboard.add_comment( __("Please enter a Closure Comment."), 'red', true);
            }
        }

        // Only show Valid QM Documents when linking
        frm.fields_dict.qm_documents.grid.get_field('qm_document').get_query = function() {
            return {
                    filters: [
                        ["status", "=", "Valid"]
                ]
            };
        };
    }
});


function load_wizard(visible) {
    frappe.call({
        'method': 'get_classification_wizard',
        'doc': cur_frm.doc,
        'args': {
            'visible': visible
        },
        'callback': function (r) {
            cur_frm.set_df_property('overview', 'options', r.message);
        }
    });
}

function fill_impact_table(frm) {
    frappe.call({
        'method': 'fill_impact_table',
        'doc': cur_frm.doc,
        'callback': function (r) {
            // nothing to do?
        }
    });
}

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
    frappe.confirm("Are you sure you want to cancel QM Change '" + cur_frm.doc.name + "'? This cannot be undone.",
    () => {
        frappe.call({
            'method': 'microsynth.qms.doctype.qm_change.qm_change.cancel',
            'args': {
                'change': cur_frm.doc.name
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


function create_qm_decision(decision, from_status, to_status) {
    frappe.prompt([
        {'fieldname': 'decision', 'fieldtype': 'Data', 'label': __('Decision'), 'read_only': 1, 'default': decision},
        {'fieldname': 'from_status', 'fieldtype': 'Data', 'label': __('From Status'), 'read_only': 1, 'default': from_status},
        {'fieldname': 'to_status', 'fieldtype': 'Data', 'label': __('To Status'), 'read_only': 1, 'default': to_status},
        {'fieldname': 'password', 'fieldtype': 'Password', 'label': __('Approval Password'), 'reqd': 1},
        {'fieldname': 'comments', 'fieldtype': 'Text', 'label': __('Comments')}
    ],
    function(values){
        // Create QM Decision
        frappe.call({
            'method': 'microsynth.qms.doctype.qm_decision.qm_decision.create_decision',
            'args': {
                'approver': frappe.session.user,
                'decision': decision,
                'dt': 'QM Change',
                'dn': cur_frm.doc.name,
                'from_status': from_status,
                'to_status': to_status,
                'comments': values.comments || "",
                'refdoc_creator': cur_frm.doc.created_by
            },
            "async": false,
            'callback': function(response) {
                let qm_decision = response.message;
                // check password and if correct, submit
                frappe.call({
                    'method': 'microsynth.qms.doctype.qm_decision.qm_decision.sign_decision',
                    'args': {
                        'doc': qm_decision,
                        'user': frappe.session.user,
                        'password': values.password
                    },
                    "callback": function(response) {
                        if (response.message) {
                            // reset in_approval flag
                            frappe.call({
                                'method': 'set_in_approval',
                                'doc': cur_frm.doc,
                                'args': {
                                    'in_approval': 0
                                },
                                'async': false,
                                'callback': function (r) {
                                }
                            });
                            if (decision == "Reject") {
                                frappe.show_alert("Rejected with <a href='/desk#Form/QM Decision/" + qm_decision + "'>" + qm_decision + "</a> and notified creator");
                            } else {
                                set_status(to_status);
                            }
                        }
                    }
                });
            }
        });
    },
    __('Please enter your approval password to ' + decision),
    __('Sign')
);
}


function request_impact_assessment() {
    frappe.prompt([
        {'fieldname': 'title', 'fieldtype': 'Data', 'label': __('Title'), 'reqd': 1},
        {'fieldname': 'qm_process', 'fieldtype': 'Link', 'options': 'QM Process', 'default': cur_frm.doc.qm_process, 'label': __('Process'), 'reqd': 1},
        {'fieldname': 'creator', 'fieldtype': 'Link', 'label': __('Responsible Person'), 'options':'User', 'reqd': 1},
        {'fieldname': 'due_date', 'fieldtype': 'Date', 'label': __('Due date'), 'reqd': 1}
    ],
    function(values){
        frappe.call({
            'method': 'microsynth.qms.doctype.qm_impact_assessment.qm_impact_assessment.create_impact_assessment',
            'args': {
                'dt': cur_frm.doc.doctype,
                'dn': cur_frm.doc.name,
                'qm_process': values.qm_process,
                'title': values.title,
                'creator': values.creator,
                'due_date': values.due_date
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