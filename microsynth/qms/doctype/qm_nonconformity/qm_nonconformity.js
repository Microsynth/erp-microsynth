// Copyright (c) 2024, Microsynth, libracore and contributors
// For license information, please see license.txt


frappe.ui.form.on('QM Nonconformity', {
    refresh: function(frm) {

        // avoid manual changes to some fields
        cur_frm.set_df_property('created_by', 'read_only', true);
        cur_frm.set_df_property('created_on', 'read_only', true);

        if (frm.doc.__islocal) {
            cur_frm.set_value("created_by", frappe.session.user);
            cur_frm.set_value("created_on", frappe.datetime.get_today());
        }

        if (!frm.doc.__islocal) {
            cur_frm.page.clear_primary_action();
            cur_frm.page.clear_secondary_action();
        }

        if (frm.doc.docstatus == 0 && !frm.doc.nc_type && !frappe.user.has_role('QAU')) {
            determine_nc_type(frm);
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

        if (frm.doc.status == 'Draft'
            && frm.doc.title
            && frm.doc.nc_type
            && frm.doc.description
            && frm.doc.qm_process
            && (frappe.session.user === frm.doc.created_by || frappe.user.has_role('QAU'))) {
            // add create button
            cur_frm.page.set_primary_action(
                __("Create"),
                function() {
                    create();
                }
            );
        }

        if (frm.doc.status == 'Created'
            && frm.doc.criticality_classification
            && frm.doc.regulatory_classification
            && (frappe.user.has_role('PV') || frappe.user.has_role('QAU'))) {
            // add classify button
            cur_frm.page.set_primary_action(
                __("Classify"),
                function() {
                    classify();
                }
            );
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

        if (frm.doc.status == 'Investigation'
            // Check, that the required investigation is documented
            // if critical, risk analysis is required
            && (frm.doc.criticality_classification != 'critical' || (frm.doc.occurrence_probability && frm.doc.impact && frm.doc.risk_classification))
            // root cause analysis is mandatory for Internal Audit, Deviation and Event
            && (!['Internal Audit', 'Deviation', 'Event'].includes(frm.doc.nc_type) || frm.doc.root_cause)
            // root cause analysis is mandatory for some ISO Authorities Audits
            && (!(frm.doc.nc_type == 'Authorities Audit' && ['ISO 9001', 'ISO 13485', 'ISO 17025'].includes(frm.doc.regulatory_classification)) || frm.doc.root_cause)
            && (frappe.session.user === frm.doc.created_by || frappe.user.has_role('QAU'))) {
            // add button to finish investigation and start planning
            cur_frm.page.set_primary_action(
                __("Finish Investigation"),
                function() {
                    set_status('Planning');
                }
            );
        }

        if (frm.doc.status == 'Planning'
            // TODO: Check, that the required actions exist
            && (frappe.session.user === frm.doc.created_by || frappe.user.has_role('QAU'))) {
            // add button to finish planning and start implementation
            if ((frm.doc.nc_type == "Deviation" && (frm.doc.regulatory_classification == "GMP" || frm.doc.criticality_classification == "critical")
                || (frm.doc.nc_type == "Event" && true))) {  // TODO: Replace true by a a check whether a CA is present
                cur_frm.page.set_primary_action(
                    __("Submit Action Plan to QAU"),
                    function() {
                        set_status('Implementation');
                        // TODO: Function that sends an email to Q?
                    }
                );
            } else {
                cur_frm.page.set_primary_action(
                    __("Finish Planning"),
                    function() {
                        set_status('Implementation');
                    }
                );
            }
        }

        if (frm.doc.status == 'Implementation'
            // TODO: Check, that all actions are finished
            && (frappe.session.user === frm.doc.created_by || frappe.user.has_role('QAU'))) {
            // add button to finish implementation and complete
            cur_frm.page.set_primary_action(
                __("Finish Implementation"),
                function() {
                    set_status('Complete');
                }
            );
        }

        if (frm.doc.status == 'Completed'
            // TODO: Check that there exists at least one QM Change if Preventive Actions are required
            && (frappe.user.has_role('QAU') ||
                (['Event', "OOS", "Track & Trend"].includes(frm.doc.nc_type) && frappe.session.user === frm.doc.created_by))) {
            // add close button
            cur_frm.page.set_primary_action(
                __("Close"),
                function() {
                    set_status('Closed');
                }
            );
        }

        // set information bar for missing infos
        cur_frm.dashboard.clear_comment();
        if ((!frm.doc.__islocal)
            && (!frm.doc.title 
            || !frm.doc.nc_type
            || !frm.doc.description
            || !frm.doc.qm_process)) {
                cur_frm.dashboard.add_comment( __("Please set and save Title, NC Type, Process and Description to create this Nonconformity."), 'red', true);
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
                request_qm_action(frm, "Correction");
            });
            frm.add_custom_button(__("Request Corrective Action"), function() {
                request_qm_action(frm, "Corrective Action");
            });
        }

        // Add button to create a Change Request
        if (["Planning"].includes(frm.doc.status)
            && frm.doc.criticality_classification == "critical"
            && !["OOS", "Track & Trend", "Event"].includes(frm.doc.nc_type)
            && (frappe.user.has_role('QAU') || frappe.session.user === frm.doc.created_by)) {
            frm.add_custom_button(__("Create Preventive Action (Change Control)"), function() {
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


function determine_nc_type(frm) {
    // TODO: Discuss with Lars how to best implement the decision tree? (ideas: frappe.prompt, new frappe.ui.Dialog)
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


function create(frm) {
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


function request_qm_action(frm, type) {
    frappe.prompt([
        {'fieldname': 'title', 'fieldtype': 'Data', 'label': __('Title')},
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
                'due_date': values.due_date,
                'type': type,
                'description': values.description
            },
            "callback": function(response) {
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
