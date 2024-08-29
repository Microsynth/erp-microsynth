// Copyright (c) 2024, Microsynth, libracore and contributors
// For license information, please see license.txt


frappe.ui.form.on('QM Nonconformity', {
    validate: function(frm) {
        if (frm.doc.nc_type == 'Event' && (frm.doc.criticality_classification != 'non-critical' || frm.doc.regulatory_classification == 'GMP')) {
            frappe.msgprint( __("An Event has to be classified as non-critical and non-GMP. Please change the Classification."), __("Validation") );
            frappe.validated=false;
        }
        if (frm.doc.nc_type == 'OOS' && frm.doc.regulatory_classification != 'GMP') {
            frappe.msgprint( __("An OOS has to be classified as GMP. Please change the Classification."), __("Validation") );
            frappe.validated=false;
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

        // access protection: only QAU in status unequals Closed can remove attachments
        if (frappe.user.has_role('QAU') && !["Closed", "Cancelled"].includes(frm.doc.status)) {
            remove_access_protection();
        } else {
            access_protection();
        }

        // remove Menu > Duplicate
        var target ="span[data-label='" + __("Duplicate") + "']";
        $(target).parent().parent().remove();

        if (frm.doc.__islocal) {
            cur_frm.set_value("created_by", frappe.session.user);
            cur_frm.set_value("created_on", frappe.datetime.get_today());
        }

        if (!frm.doc.__islocal) {
            cur_frm.page.clear_primary_action();
            cur_frm.page.clear_secondary_action();
        }

        // lock Criticality Classification for OOS and Track & Trend since it is an excluded step for these NC Types
        if (["OOS", "Track & Trend"].includes(frm.doc.nc_type)) {
            cur_frm.set_df_property('criticality_classification', 'read_only', true);
        }

        // load classification wizard or dashboard
        if (frm.doc.status == 'Draft') {
            if ((locals.classification_wizard && locals.classification_wizard=="closed") || frm.doc.nc_type){
                var visible = false;
                load_wizard(visible);
                setTimeout(function () {
                    add_restart_wizard_button();}, 300);
            } else {
                var visible = true;
                load_wizard(visible);
            }
            
        } else {
            // use the classification_wizard HTML field to display an advanced dashboard
            frappe.call({
                'method': 'get_advanced_dashboard',
                'doc': frm.doc,
                'callback': function (r) {
                    cur_frm.set_df_property('classification_wizard', 'options', r.message);
                }
            });
        }

        // Only QAU (in status Draft or Created) and creator (in status Draft) can change these fields: Process, Date of Occurrence, Company
        if ((["Draft"].includes(frm.doc.status) && frappe.session.user === frm.doc.created_by) || ["Draft", "Created"].includes(frm.doc.status) && frappe.user.has_role('QAU')) {
            cur_frm.set_df_property('qm_process', 'read_only', false);
            cur_frm.set_df_property('date', 'read_only', false);
            cur_frm.set_df_property('company', 'read_only', false);
            
        } else {
            cur_frm.set_df_property('qm_process', 'read_only', true);
            cur_frm.set_df_property('date', 'read_only', true);
            cur_frm.set_df_property('company', 'read_only', true);
        }

        // Only creator (in status Draft) or QAU (in status unequals Closed) can change these fields: Process, Date of Occurrence, Company
        if ((["Draft"].includes(frm.doc.status) && frappe.session.user === frm.doc.created_by) || !["Closed", "Cancelled"].includes(frm.doc.status) && frappe.user.has_role('QAU')) {
            cur_frm.set_df_property('title', 'read_only', false);
            cur_frm.set_df_property('hierarchy_1', 'read_only', false);
            cur_frm.set_df_property('hierarchy_2', 'read_only', false);
            cur_frm.set_df_property('description', 'read_only', false);            
        } else {
            cur_frm.set_df_property('title', 'read_only', true);
            cur_frm.set_df_property('hierarchy_1', 'read_only', true);
            cur_frm.set_df_property('hierarchy_2', 'read_only', true);
            cur_frm.set_df_property('description', 'read_only', true);
        }

        // lock all fields except References and Web Order ID if NC is Closed
        if (["Closed", "Cancelled"].includes(frm.doc.status)) {
            cur_frm.set_df_property('title', 'read_only', true);
            cur_frm.set_df_property('qm_process', 'read_only', true);
            cur_frm.set_df_property('date', 'read_only', true);
            cur_frm.set_df_property('company', 'read_only', true);
            cur_frm.set_df_property('description', 'read_only', true);
            cur_frm.set_df_property('criticality_classification', 'read_only', true);
            cur_frm.set_df_property('regulatory_classification', 'read_only', true);
            cur_frm.set_df_property('rational_for_classification', 'read_only', true);
            cur_frm.set_df_property('root_cause', 'read_only', true);
            cur_frm.set_df_property('occurrence_probability', 'read_only', true);
            cur_frm.set_df_property('impact', 'read_only', true);
            cur_frm.set_df_property('risk_analysis', 'read_only', true);
            cur_frm.set_df_property('action_plan_summary', 'read_only', true);
            cur_frm.set_df_property('occurrence_probability_after_actions', 'read_only', true);
            cur_frm.set_df_property('impact_after_actions', 'read_only', true);
            cur_frm.set_df_property('risk_analysis_after_actions', 'read_only', true);
        }

        // Only QAU can set field NC Type in status Draft directly
        if (["Draft", "Created"].includes(frm.doc.status) && frappe.user.has_role('QAU')) {
            cur_frm.set_df_property('nc_type', 'read_only', false);
        } else {
            cur_frm.set_df_property('nc_type', 'read_only', true);
        }

        // Only the creator or QAU can change the classification in status "Draft" or "Created"
        if ((["Draft", "Created"].includes(frm.doc.status) && frappe.session.user === frm.doc.created_by)
            || ["Draft", "Created", "Investigation"].includes(frm.doc.status) && frappe.user.has_role('QAU')) {
            cur_frm.set_df_property('criticality_classification', 'read_only', false);
            cur_frm.set_df_property('regulatory_classification', 'read_only', false);
            cur_frm.set_df_property('rational_for_classification', 'read_only', false);
        } else {
            cur_frm.set_df_property('criticality_classification', 'read_only', true);
            cur_frm.set_df_property('regulatory_classification', 'read_only', true);
            if (!frappe.user.has_role('QAU')){
                cur_frm.set_df_property('rational_for_classification', 'read_only', true);
            }
        }

        // Only QAU or the creator in Status Draft, Created or Investigation
        // can change the fields Root Cause and Risk Analysis Summary
        if ((['Draft', 'Created', 'Investigation'].includes(frm.doc.status) && frappe.session.user === frm.doc.created_by)
            || (frappe.user.has_role('QAU') && !["Closed", "Cancelled"].includes(frm.doc.status))) {
            cur_frm.set_df_property('root_cause', 'read_only', false);
            cur_frm.set_df_property('risk_analysis', 'read_only', false);
        } else {
            cur_frm.set_df_property('root_cause', 'read_only', true);
            cur_frm.set_df_property('risk_analysis', 'read_only', true);
        }

        // Access protection for fields Occurrence Probability and Impact
        if ((['Draft', 'Created', 'Investigation'].includes(frm.doc.status) && frappe.session.user === frm.doc.created_by)
            || ['Draft', 'Created', 'Investigation', 'Planning'].includes(frm.doc.status) && frappe.user.has_role('QAU')) {            
            cur_frm.set_df_property('occurrence_probability', 'read_only', false);
            cur_frm.set_df_property('impact', 'read_only', false);
        } else {
            cur_frm.set_df_property('occurrence_probability', 'read_only', true);
            cur_frm.set_df_property('impact', 'read_only', true);
        }

        // Only QAU and the creator can change these fields in the specified Status
        if ((['Draft', 'Created', 'Investigation', 'Planning', 'Plan Approval', 'Implementation', 'Completed'].includes(frm.doc.status)
            && frappe.session.user === frm.doc.created_by) || frappe.user.has_role('QAU')) {
            cur_frm.set_df_property('occurrence_probability_after_actions', 'read_only', false);
            cur_frm.set_df_property('impact_after_actions', 'read_only', false);
            cur_frm.set_df_property('risk_analysis_after_actions', 'read_only', false);
        } else {
            cur_frm.set_df_property('occurrence_probability_after_actions', 'read_only', true);
            cur_frm.set_df_property('impact_after_actions', 'read_only', true);
            cur_frm.set_df_property('risk_analysis_after_actions', 'read_only', true);
        }

        // Only QAU and the creator can change these fields in the specified Status
        if ((['Draft', 'Created', 'Investigation', 'Planning', 'Plan Approval', 'Implementation'].includes(frm.doc.status) && frappe.session.user === frm.doc.created_by)
            || (['Draft', 'Created', 'Investigation', 'Planning', 'Plan Approval', 'Implementation', 'Completed'].includes(frm.doc.status) && frappe.user.has_role('QAU'))) {
            cur_frm.set_df_property('action_plan_summary', 'read_only', false);
        } else {
            cur_frm.set_df_property('action_plan_summary', 'read_only', true);
        }

        if ((["Completed"].includes(frm.doc.status) && frappe.session.user === frm.doc.created_by)
            || (frappe.user.has_role('QAU') && !["Closed", "Cancelled"].includes(frm.doc.status))) {
            cur_frm.set_df_property('closure_comments', 'read_only', false);
        } else {
            cur_frm.set_df_property('closure_comments', 'read_only', true);
        }

        // allow the creator or QAU to change the creator (transfer document)
        if ((!frm.doc.__islocal)
            && (["Draft"].includes(frm.doc.status))
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

        // allow QAU to cancel
        if (!frm.doc.__islocal && frm.doc.docstatus < 2 && frappe.user.has_role('QAU') && !['Closed', 'Cancelled'].includes(frm.doc.status)) {
            frm.add_custom_button(__("Cancel"), function() {
                cancel(frm);
            }).addClass("btn-danger");
        }

        // Add buttons to request Correction or Corrective Action
        if (["Planning"].includes(frm.doc.status)
            && !["OOS", "Track & Trend"].includes(frm.doc.nc_type)
            && (frappe.user.has_role('QAU') || frappe.session.user === frm.doc.created_by)) {
            frm.add_custom_button(__("Request Correction"), function() {
                request_qm_action("Correction");
            }).addClass("btn-primary");
            frm.add_custom_button(__("Request Corrective Action"), function() {
                request_qm_action("Corrective Action");
            }).addClass("btn-primary");
        }

        // Add button to create a Change Request
        if (["Completed"].includes(frm.doc.status)
            && frm.doc.criticality_classification == "critical"
            && !["OOS", "Track & Trend", "Event"].includes(frm.doc.nc_type)
            && (frappe.user.has_role('QAU') || frappe.session.user === frm.doc.created_by)) {
            frm.add_custom_button(__("Create Change Request"), function() {
                create_change(frm);
            }).addClass("btn-primary");
        }

        // add a button to request an effectiveness check
        if (frm.doc.status == "Planning"
            && (frappe.session.user === frm.doc.created_by || frappe.user.has_role('QAU'))) {
            frm.add_custom_button(__("Request Effectiveness Check"), function() {
                request_qm_action("NC Effectiveness Check");
            });
        }

        if (!frm.doc.__islocal && frm.doc.status == 'Draft' && (frappe.session.user === frm.doc.created_by || frappe.user.has_role('QAU'))) {
            if (frm.doc.title
                && frm.doc.nc_type
                && frm.doc.description && frm.doc.description != "<div><br></div>"
                && frm.doc.qm_process
                && frm.doc.date) {
                if (frm.doc.regulatory_classification != 'GMP' && frm.doc.nc_type != 'Deviation') {
                    // add submit button
                    cur_frm.page.set_primary_action(
                        __("Submit"),
                        function() {
                            submit();
                        }
                    );
                } else {
                    // add submit button
                    cur_frm.page.set_primary_action(
                        __("Submit to QAU"),
                        function() {
                            submit();
                        }
                    );
                }
            } else {
                frm.dashboard.clear_comment();
                frm.dashboard.add_comment( __("Please set and <b>save</b> NC Type, Title, Process, Date and Description to submit this Nonconformity."), 'red', true);
            }
        }

        if (frm.doc.status == 'Created') {
            if (frm.doc.nc_type == "Track & Trend"
                && (frappe.session.user === frm.doc.created_by || frappe.user.has_role('QAU'))) {
                // add close button
                cur_frm.page.set_primary_action(
                    __("Close"),
                    function() {
                        sign_and_close(frm);
                    }
                );
            } else if (['Track & Trend'].includes(frm.doc.nc_type)) {
                frm.dashboard.add_comment( __("Track & Trend needs to be closed by the creator or QAU."), 'yellow', true);
            } else if (((frm.doc.regulatory_classification != 'GMP' && frm.doc.nc_type != 'Deviation')
                && frappe.session.user === frm.doc.created_by)
                || frappe.user.has_role('QAU')) {
                if (frm.doc.criticality_classification && frm.doc.regulatory_classification) {
                    // add confirm classification button
                    cur_frm.page.set_primary_action(
                        __("Confirm Classification"),
                        function() {
                            confirm_classification();  // -> status "Investigation"
                        }
                    );
                } else {
                    frm.dashboard.add_comment( __("Please complete the <b>Classification</b> section."), 'red', true);
                }
            } else {
                frm.dashboard.add_comment( __("The Classification needs to be confirmed by the creator or QAU (GMP or Deviation)."), 'yellow', true);
            }
        }

        if (frm.doc.status == 'Investigation' && (frappe.session.user === frm.doc.created_by || frappe.user.has_role('QAU'))) {
            if (frm.doc.nc_type == "OOS" && frappe.user.has_role('QAU')) {
                // add close button
                cur_frm.page.set_primary_action(
                    __("Close"),
                    function() {
                        sign_and_close(frm);
                    }
                );
            } else if (frm.doc.nc_type == "OOS") {
                frm.dashboard.add_comment( __("An OOS needs to be closed by QAU."), 'yellow', true);         
            // Check, that the required investigation is documented
            // if critical, risk analysis is required
            } else if ((frm.doc.criticality_classification != 'critical' || (frm.doc.occurrence_probability && frm.doc.impact && frm.doc.risk_classification))
                // root cause analysis is mandatory for Internal Audit, Deviation and Event
                && (!['Internal Audit', 'Deviation', 'Event'].includes(frm.doc.nc_type) || frm.doc.root_cause)
                // root cause analysis is mandatory for some ISO Authorities Audits
                && (!(frm.doc.nc_type == 'Authorities Audit' && ['ISO 9001', 'ISO 13485', 'ISO 17025'].includes(frm.doc.regulatory_classification)) || frm.doc.root_cause)
                ) {
                    // add button to finish investigation and start planning
                    cur_frm.page.set_primary_action(
                        __("Finish Investigation"),
                        function() {
                            set_status('Planning');
                        }
                    );
            } else {
                if (!frm.doc.root_cause && (['Internal Audit', 'Deviation', 'Event'].includes(frm.doc.nc_type)
                    || (frm.doc.nc_type == 'Authorities Audit' && ['ISO 9001', 'ISO 13485', 'ISO 17025'].includes(frm.doc.regulatory_classification)))) {
                    frm.dashboard.add_comment( __("Please do a root cause analysis."), 'red', true);
                }
                if (frm.doc.criticality_classification == 'critical') {
                    frm.dashboard.add_comment( __("Please do a risk analysis."), 'red', true);
                }
            }
        }

        if (frm.doc.status == 'Planning'
            && (frappe.session.user === frm.doc.created_by || frappe.user.has_role('QAU'))) {
                frappe.call({
                    'method': 'microsynth.qms.doctype.qm_nonconformity.qm_nonconformity.has_actions',
                    'args': {
                        'doc': frm.doc.name
                    },
                    'callback': function(response) {
                        // Check, that the required actions exist
                        if (['Internal Audit', 'Deviation', 'Event'].includes(frm.doc.nc_type)
                            && !response.message.has_correction)
                            {
                            frm.dashboard.add_comment( __("Please request a Correction for this Nonconformity."), 'red', true);
                        } else if (['Authorities Audit', 'Customer Audit', 'Internal Audit', 'Deviation'].includes(frm.doc.nc_type)
                            && frm.doc.criticality_classification == "critical"
                            && !response.message.has_corrective_action)
                            {
                            frm.dashboard.add_comment( __("Please request a Corrective Action for this Nonconformity."), 'red', true);
                        } else if (frm.doc.nc_type == "Event" && !response.message.has_corrective_action) {  // If Event and has no CAs -> Submit Action Plan to Creator else to QAU
                            cur_frm.page.set_primary_action(
                                __("Submit Action Plan to Creator"),
                                function() {
                                    set_status('Plan Approval');
                                }
                            );
                        } else {
                            cur_frm.page.set_primary_action(
                                __("Submit Action Plan to QAU"),
                                function() {
                                    set_status('Plan Approval');
                                    // Call function that sends an email to Q
                                    frappe.call({
                                        'method': 'microsynth.qms.doctype.qm_nonconformity.qm_nonconformity.notify_q_about_action_plan',
                                        'args': {
                                            'doc': cur_frm.doc.name
                                        },
                                        'callback': function(response) {
                                            // nothing to do?
                                        }
                                    });
                                }
                            );
                        }
                    }
                });
        }

        // Add button "Reject Action Plan" that goes back to status "Planning"
        // and button "Confirm Action Plan" that goes to status "Implementation"
        if (frm.doc.status == 'Plan Approval') {
            var allowed = false;
            if (frappe.user.has_role('QAU')) {
                allowed = true;
            } else if (frappe.session.user === frm.doc.created_by && frm.doc.regulatory_classification != 'GMP' && ['Event'].includes(frm.doc.nc_type)) {
                frappe.call({
                    'method': 'microsynth.qms.doctype.qm_nonconformity.qm_nonconformity.has_actions',
                    'args': {
                        'doc': frm.doc.name
                    },
                    'callback': function(response) {
                        if (!response.message.has_corrective_action) {
                            allowed = true;
                        }
                    }
                });
            }
            if (allowed) {
                cur_frm.set_df_property('plan_approval', 'read_only', false);
                cur_frm.page.set_primary_action(
                    __("Confirm Action Plan"),
                    function() {
                        set_status('Implementation');
                    }
                );
                cur_frm.add_custom_button(
                    __("Reject Action Plan"),
                    function() {
                        set_status('Planning');
                    }
                );
            } else {
                cur_frm.set_df_property('plan_approval', 'read_only', true);
            }
        } else {
            cur_frm.set_df_property('plan_approval', 'read_only', true);
        }

        if (frm.doc.status == 'Implementation'
            && (frappe.session.user === frm.doc.created_by || frappe.user.has_role('QAU'))) {
                frappe.call({
                    'method': 'microsynth.qms.doctype.qm_nonconformity.qm_nonconformity.has_non_completed_action',
                    'args': {
                        'doc': frm.doc.name
                    },
                    'callback': function(response) {
                        // Check, that all actions are finished
                        if (response.message) {
                            frm.dashboard.add_comment( __("Please complete all actions and reload this QM Nonconformity to finish the Implementation."), 'red', true);
                        } else {
                            // add button to finish implementation and complete
                            cur_frm.page.set_primary_action(
                                __("Finish Implementation"),
                                function() {
                                    set_status('Completed');
                                }
                            );
                        }
                    }
                });
        }

        if (frm.doc.status == 'Completed') {
            frappe.call({
                'method': 'microsynth.qms.doctype.qm_change.qm_change.has_non_completed_action',
                'args': {
                    'doc': frm.doc.name,
                    'type': 'NC Effectiveness Check'
                },
                'callback': function(response) {
                    // Check, that all actions are finished
                    if (response.message) {
                        frm.dashboard.add_comment( __("Please complete Effectiveness Check and reload this QM Change to close it."), 'red', true);
                    } else {
                        // Check presence of QM Change if required
                        frappe.call({
                            'method': 'microsynth.qms.doctype.qm_nonconformity.qm_nonconformity.has_change',
                            'args': {
                                'doc': frm.doc.name
                            },
                            'callback': function(response) {
                                var allowed = false;
                                if (frappe.user.has_role('QAU')
                                    || (frappe.session.user === frm.doc.created_by && frm.doc.nc_type == "Track & Trend")) {  // Track & Trend should never reach the status "Completed"
                                    allowed = true;
                                } else if (frm.doc.nc_type == "Event" && frm.doc.regulatory_classification != 'GMP') {
                                    frappe.call({
                                        'method': 'microsynth.qms.doctype.qm_nonconformity.qm_nonconformity.has_actions',
                                        'args': {
                                            'doc': frm.doc.name
                                        },
                                        'callback': function(response) {
                                            if (!response.message.has_corrective_action) {
                                                allowed = true;
                                            }
                                        }
                                    });
                                }
                                if (allowed) {
                                    if (frm.doc.criticality_classification != "critical" || response.message || frm.doc.closure_comments) {
                                        // add close button
                                        cur_frm.page.set_primary_action(
                                            __("Close"),
                                            function() {
                                                sign_and_close(frm);
                                            }
                                        );
                                    } else {
                                        frm.dashboard.add_comment( __("This is a critical Nonconformity. Please create a Change Request or explain in the Closure Comment why not."), 'red', true);
                                    }
                                } else {
                                    frm.dashboard.add_comment( __("This Nonconformity needs to be processed by its creator or QAU."), 'blue', true);
                                }                                
                            }
                        });
                    }
                }
            });
        }

        // Only show Valid QM Documents when linking
        frm.fields_dict.qm_documents.grid.get_field('qm_document').get_query = function() {
            return {
                    filters: [
                        ["status", "=", "Valid"]
                ]
            };
        };
        
        // filters for hierarchy fields
        frm.fields_dict.hierarchy_1.get_query = function(frm) {
            return {
                'query': 'microsynth.qms.doctype.qm_nonconformity.qm_nonconformity.get_allowed_classification_for_process',
                'filters': {
                    'process': cur_frm.doc.qm_process
                }
            };
        };
        frm.fields_dict.hierarchy_2.get_query = function(frm) {
            return {
                'query': 'microsynth.qms.doctype.qm_nonconformity.qm_nonconformity.get_allowed_classification_for_hierarchy',
                'filters': {
                    'hierarchy': cur_frm.doc.hierarchy_1
                }
            };
        };

        // remove dashboard doc (+) buttons
        var new_btns = document.getElementsByClassName("btn-new");
        for (var i = 0; i < new_btns.length; i++) {
            new_btns[i].style.visibility = "hidden";
        }
    },
    on_submit(frm) {
        cur_frm.set_value("status", "Created");
    },
    occurrence_probability: function(frm) {
        if (frm.doc.occurrence_probability && frm.doc.impact) {
            cur_frm.set_value("risk_classification", calculate_risk_classification(frm.doc.occurrence_probability, frm.doc.impact, false));
        } else {
            cur_frm.set_value("risk_classification", "");
        }
    },
    impact: function(frm) {
        if (frm.doc.occurrence_probability && frm.doc.impact) {
            cur_frm.set_value("risk_classification", calculate_risk_classification(frm.doc.occurrence_probability, frm.doc.impact, false));
        } else {
            cur_frm.set_value("risk_classification", "");
        }
    },
    occurrence_probability_after_actions: function(frm) {
        if (frm.doc.occurrence_probability_after_actions && frm.doc.impact_after_actions) {
            cur_frm.set_value("risk_classification_after_actions", calculate_risk_classification(frm.doc.occurrence_probability_after_actions, frm.doc.impact_after_actions, true));
        } else {
            cur_frm.set_value("risk_classification_after_actions", "");
        }
    },
    impact_after_actions: function(frm) {
        if (frm.doc.occurrence_probability_after_actions && frm.doc.impact_after_actions) {
            cur_frm.set_value("risk_classification_after_actions", calculate_risk_classification(frm.doc.occurrence_probability_after_actions, frm.doc.impact_after_actions, true));
        } else {
            cur_frm.set_value("risk_classification_after_actions", "");
        }
    },
    qm_process: function(frm) {
        // clear affected hierarchy 1 field when process has changed to prevent invalid values
        cur_frm.set_value("hierarchy_1", null);
    },
    hierarchy_1: function(frm) {
        // clear affected hierarchy 2 field
        cur_frm.set_value("hierarchy_2", null);
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
            cur_frm.set_df_property('classification_wizard', 'options', r.message);
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
            cur_frm.save();
        },
        __('Set new creator'),
        __('Set')
    );
}

function submit(frm) {
    frappe.call({
        'method': 'microsynth.qms.doctype.qm_nonconformity.qm_nonconformity.set_created',
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
    frappe.confirm("Are you sure you want to cancel QM Nonconformity '" + frm.doc.name + "'? This cannot be undone.",
    () => {
        frappe.call({
            'method': 'microsynth.qms.doctype.qm_nonconformity.qm_nonconformity.cancel',
            'args': {
                'nc': cur_frm.doc.name
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

function confirm_classification(frm) {
    frappe.call({
        'method': 'microsynth.qms.doctype.qm_nonconformity.qm_nonconformity.confirm_classification',
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

function set_status(status) {
    frappe.call({
        'method': 'microsynth.qms.doctype.qm_nonconformity.qm_nonconformity.set_status',
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

function sign_and_close(frm) {
    frappe.prompt([
            {'fieldname': 'password', 'fieldtype': 'Password', 'label': __('Approval Password'), 'reqd': 1}  
        ],
        function(values){
            // check password and if correct, sign
            frappe.call({
                'method': 'microsynth.qms.signing.sign',
                'args': {
                    'dt': "QM Nonconformity",
                    'dn': cur_frm.doc.name,
                    'user': frappe.session.user,
                    'password': values.password,
                    'submit': false
                },
                "callback": function(response) {
                    if (response.message) {
                        // signed, set signing date & close NC
                        frappe.call({
                            'method': 'microsynth.qms.doctype.qm_nonconformity.qm_nonconformity.close',
                            'args': {
                                'doc': cur_frm.doc.name,
                                'user': frappe.session.user
                            },
                            'async': false
                        });
                    }
                    cur_frm.reload_doc();
                }
            });
        },
        __('Please enter your approval password'),
        __('Sign & Close')
    );
}

function calculate_risk_classification(occ_prob, impact, after_actions) {
    const values = new Map([
        ["small", 1],
        ["medium", 2],
        ["high", 3],
        ["neglectable", 1],
        ["noticable", 2],
        ["severe", 3]
    ])
    var res = values.get(occ_prob) * values.get(impact);
    if (res < 3) {
        return after_actions ? "small" : "no actions";
    } else if (res < 6) {
        return after_actions ? "medium" : "check for risk mitigation";
    } else if (res >= 6) {
        return after_actions ? "high" : "actions required";
    } else {
        console.log(res);
        return "";
    }
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

function create_change(frm) {
    frappe.prompt([
        {'fieldname': 'title', 'fieldtype': 'Data', 'label': __('Title'), 'reqd': 1},
        {'fieldname': 'qm_process', 'fieldtype': 'Link', 'options': 'QM Process', 'default': cur_frm.doc.qm_process, 'label': __('Process'), 'reqd': 1},
        {'fieldname': 'creator', 'fieldtype': 'Link', 'label': __('Responsible Person'), 'options':'User', 'reqd': 1},
        {'fieldname': 'company', 'fieldtype': 'Link', 'options': 'Company', 'default': cur_frm.doc.company, 'label': __('Company'), 'reqd': 1},
        {'fieldname': 'description', 'fieldtype': 'Text', 'label': __('Description Change')}
    ],
    function(values){
        frappe.call({
            'method': 'microsynth.qms.doctype.qm_change.qm_change.create_change',
            'args': {
                'dt': cur_frm.doc.doctype,
                'dn': cur_frm.doc.name,
                'qm_process': values.qm_process,
                'creator': values.creator,
                'company': values.company,
                'title': values.title,
                'description': values.description || ''
            },
            "callback": function(response) {
                cur_frm.reload_doc();
                frappe.show_alert( __("QM Change created") +
                            ": <a href='/desk#Form/QM Change/" +
                            response.message + "'>" + response.message +
                            "</a>"
                        );
            }
        });
    },
    __('Please create a QM Change'),
    __('Create')
    )
}


