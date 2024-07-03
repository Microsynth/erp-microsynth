// Copyright (c) 2024, Microsynth, libracore and contributors
// For license information, please see license.txt


frappe.ui.form.on('QM Nonconformity', {
    refresh: function(frm) {

        if (frm.doc.__islocal) {
            cur_frm.set_value("created_by", frappe.session.user);
            cur_frm.set_value("created_on", frappe.datetime.get_today());
        }

        if (!frm.doc.__islocal) {
            cur_frm.page.clear_primary_action();
            cur_frm.page.clear_secondary_action();
        }

        // if (frm.doc.docstatus == 0 && !frm.doc.nc_type && !frappe.user.has_role('QAU')) {
        //     determine_nc_type(frm);
        // }

        // fetch classification wizard
        if (!frm.doc.nc_type) {
            frappe.call({
                'method': 'get_classification_wizard',
                'doc': frm.doc,
                'callback': function (r) {
                    cur_frm.set_df_property('classification_wizard', 'options', r.message);
                }
            });
        }

        // Only creator and QAU can change these fields in Draft status: Title, NC Type, Process, Date, Company, Web Order ID
        if (!(["Draft"].includes(frm.doc.status) && (frappe.session.user === frm.doc.created_by || frappe.user.has_role('QAU')))) {
            cur_frm.set_df_property('title', 'read_only', true);
            cur_frm.set_df_property('nc_type', 'read_only', true);
            cur_frm.set_df_property('qm_process', 'read_only', true);
            cur_frm.set_df_property('date', 'read_only', true);
            cur_frm.set_df_property('company', 'read_only', true);
            cur_frm.set_df_property('web_order_id', 'read_only', true);
            cur_frm.set_df_property('description', 'read_only', true);
        } else {
            cur_frm.set_df_property('title', 'read_only', false);
            cur_frm.set_df_property('nc_type', 'read_only', false);
            cur_frm.set_df_property('qm_process', 'read_only', false);
            cur_frm.set_df_property('date', 'read_only', false);
            cur_frm.set_df_property('company', 'read_only', false);
            cur_frm.set_df_property('web_order_id', 'read_only', false);
            cur_frm.set_df_property('description', 'read_only', false);
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

        // Only QAU can change the classification in status "Draft" or "Created"
        if (frappe.user.has_role('QAU') && ["Draft", "Created"].includes(frm.doc.status)) {
            cur_frm.set_df_property('criticality_classification', 'read_only', false);
            cur_frm.set_df_property('regulatory_classification', 'read_only', false);
        } else {
            cur_frm.set_df_property('criticality_classification', 'read_only', true);
            cur_frm.set_df_property('regulatory_classification', 'read_only', true);
        }

        if (["Closed"].includes(frm.doc.status)) {
            cur_frm.set_df_property('closure_comments', 'read_only', true);
        } else {
            cur_frm.set_df_property('closure_comments', 'read_only', false);
        }

        if (frm.doc.status == 'Draft' && (frappe.session.user === frm.doc.created_by || frappe.user.has_role('QAU'))) {
            if (frm.doc.title
                && frm.doc.nc_type
                && frm.doc.description
                && frm.doc.qm_process) {
                // add submit button
                cur_frm.page.set_primary_action(
                    __("Submit"),
                    function() {
                        submit();
                    }
                );
            } else {
                frm.dashboard.clear_comment();
                frm.dashboard.add_comment( __("Please set and save Title, NC Type, Process and Description to create this Nonconformity."), 'red', true);
            }
        }

        if (frm.doc.status == 'Created' && (frappe.user.has_role('PV') || frappe.user.has_role('QAU'))) {
            if (frm.doc.criticality_classification && frm.doc.regulatory_classification) {
                // add classify button
                cur_frm.page.set_primary_action(
                    __("Classify"),
                    function() {
                        classify();
                    }
                );
            } else {
                frm.dashboard.add_comment( __("Please do the classification."), 'red', true);
            }
        }

        if (frm.doc.status == 'Classified'
            && (frappe.session.user === frm.doc.created_by || frappe.user.has_role('QAU'))) {
            if (["OOS", "Track & Trend"].includes(frm.doc.nc_type)) {
                // add close button
                cur_frm.page.set_primary_action(
                    __("Close"),
                    function() {
                        set_status('Closed');
                    }
                );
            } else {
                // add investigate button
                cur_frm.page.set_primary_action(
                    __("Investigate"),
                    function() {
                        set_status('Investigation');
                    }
                );
            }
        }

        if (frm.doc.status == 'Investigation' && (frappe.session.user === frm.doc.created_by || frappe.user.has_role('QAU'))) {
            // Check, that the required investigation is documented
            // if critical, risk analysis is required
            if ((frm.doc.criticality_classification != 'critical' || (frm.doc.occurrence_probability && frm.doc.impact && frm.doc.risk_classification))
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
            && (frappe.session.user === frm.doc.created_by || frappe.user.has_role('QAU') || frappe.user.has_role('PV'))) {
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
                            frm.dashboard.add_comment( __("Please create a Correction for this Nonconformity."), 'red', true);
                        } else if (['Authorities Audit', 'Customer Audit', 'Internal Audit', 'Deviation'].includes(frm.doc.nc_type)
                            && frm.doc.criticality_classification == "critical"
                            && !response.message.has_corrective_action)
                            {
                            frm.dashboard.add_comment( __("Please create a Corrective Action for this Nonconformity."), 'red', true);
                        } else if ((frm.doc.nc_type == "Deviation" && (frm.doc.regulatory_classification == "GMP" || frm.doc.criticality_classification == "critical")
                            || (frm.doc.nc_type == "Event" && response.message.has_corrective_action))) {
                            cur_frm.page.set_primary_action(
                                __("Submit Action Plan to QAU"),
                                function() {
                                    set_status('Implementation');
                                    // TODO: Function that sends an email to Q?
                                }
                            );
                        } else {  // add button to finish planning and start implementation
                            cur_frm.page.set_primary_action(
                                __("Finish Planning"),
                                function() {
                                    set_status('Implementation');
                                }
                            );
                        }
                    }
                });
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
                'method': 'microsynth.qms.doctype.qm_nonconformity.qm_nonconformity.has_change',
                'args': {
                    'doc': frm.doc.name
                },
                'callback': function(response) {
                    if ((frm.doc.criticality_classification != "critical" || response.message || frm.doc.closure_comments)
                        && (frappe.user.has_role('QAU') ||
                            (['Event', "OOS", "Track & Trend"].includes(frm.doc.nc_type) && frappe.session.user === frm.doc.created_by))) {
                        // add close button
                        cur_frm.page.set_primary_action(
                            __("Close"),
                            function() {
                                set_status('Closed');
                            }
                        );
                    } else {
                        frm.dashboard.add_comment( __("Please create a Change Request or explain in the Closure Comment why not."), 'red', true);
                    }
                }
            });
        }

        // remove dashboard doc (+) buttons
        var new_btns = document.getElementsByClassName("btn-new");
        for (var i = 0; i < new_btns.length; i++) {
            new_btns[i].style.visibility = "hidden";
        }

        // Add buttons to request Correction or Corrective Action
        if (["Planning"].includes(frm.doc.status)
            && !["OOS", "Track & Trend"].includes(frm.doc.nc_type)
            && (frappe.user.has_role('QAU') || frappe.session.user === frm.doc.created_by)) {
            frm.add_custom_button(__("Request Correction"), function() {
                request_qm_action("Correction");
            });
            frm.add_custom_button(__("Request Corrective Action"), function() {
                request_qm_action("Corrective Action");
            });
        }

        // Add button to create a Change Request
        if (["Completed"].includes(frm.doc.status)
            && frm.doc.criticality_classification == "critical"
            && !["OOS", "Track & Trend", "Event"].includes(frm.doc.nc_type)
            && (frappe.user.has_role('QAU') || frappe.session.user === frm.doc.created_by)) {
            frm.add_custom_button(__("Create Change Request"), function() {
                create_change(frm);
            });
        }
    },
    on_submit(frm) {
        cur_frm.set_value("status", "Created");
    },
    occurrence_probability: function(frm) {
        if (frm.doc.occurrence_probability && frm.doc.impact) {
            cur_frm.set_value("risk_classification", calculate_risk_classification(frm.doc.occurrence_probability, frm.doc.impact));
        }
    },
    impact: function(frm) {
        if (frm.doc.occurrence_probability && frm.doc.impact) {
            cur_frm.set_value("risk_classification", calculate_risk_classification(frm.doc.occurrence_probability, frm.doc.impact));
        }
    },
    occurrence_probability_after_actions: function(frm) {
        if (frm.doc.occurrence_probability_after_actions && frm.doc.impact_after_actions) {
            cur_frm.set_value("risk_classification_after_actions", calculate_risk_classification(frm.doc.occurrence_probability_after_actions, frm.doc.impact_after_actions));
        }
    },
    impact_after_actions: function(frm) {
        if (frm.doc.occurrence_probability_after_actions && frm.doc.impact_after_actions) {
            cur_frm.set_value("risk_classification_after_actions", calculate_risk_classification(frm.doc.occurrence_probability_after_actions, frm.doc.impact_after_actions));
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

function classify(frm) {
    frappe.call({
        'method': 'microsynth.qms.doctype.qm_nonconformity.qm_nonconformity.set_classified',
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

function calculate_risk_classification(occ_prob, impact) {
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
        return "no actions";
    } else if (res < 6) {
        return "check for risk mitigation";
    } else if (res >= 6) {
        return "actions required";
    } else {
        console.log(res);
        return "";
    }
}

function request_qm_action(type) {
    frappe.prompt([
        {'fieldname': 'title', 'fieldtype': 'Data', 'label': __('Title')},
        {'fieldname': 'qm_process', 'fieldtype': 'Link', 'options': 'QM Process', 'default': cur_frm.doc.qm_process, 'label': __('Process')},
        {'fieldname': 'responsible_person', 'fieldtype': 'Link', 'label': __('Responsible Person'), 'options':'User', 'reqd': 1},
        {'fieldname': 'due_date', 'fieldtype': 'Date', 'label': __('Due date'), 'reqd': 1},
        {'fieldname': 'description', 'fieldtype': 'Text Editor', 'label': __('Description')}
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
                'description': values.description
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
    __('Please choose a Responsible Person and a Due Date'),
    __('Request ' + type)
    )
}

function create_change(frm) {
    frappe.prompt([
        {'fieldname': 'title', 'fieldtype': 'Data', 'label': __('Title')},
        {'fieldname': 'qm_process', 'fieldtype': 'Link', 'options': 'QM Process', 'default': cur_frm.doc.qm_process, 'label': __('Process')},
        {'fieldname': 'company', 'fieldtype': 'Link', 'options': 'Company', 'default': cur_frm.doc.company, 'label': __('Company')},
        {'fieldname': 'description', 'fieldtype': 'Text Editor', 'label': __('Description Change')}
    ],
    function(values){
        frappe.call({
            'method': 'microsynth.qms.doctype.qm_change.qm_change.create_change',
            'args': {
                'dt': cur_frm.doc.doctype,
                'dn': cur_frm.doc.name,
                'qm_process': values.qm_process,
                'company': values.company,
                'title': values.title,
                'description': values.description
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


// TODO: Implement functions for classification wizard here?
