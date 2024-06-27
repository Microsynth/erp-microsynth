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

        if (frm.doc.docstatus == 0 && !frm.doc.nc_type && !frappe.user.has_role('QAU')) {
            determine_nc_type(frm);
        }

        // Only creator and QAU can change these fields in Draft status: Title, NC Type, Process, Date, Company
        if (!(["Draft"].includes(frm.doc.status) && (frappe.session.user === frm.doc.created_by || frappe.user.has_role('QAU')))) {
            cur_frm.set_df_property('title', 'read_only', true);
            cur_frm.set_df_property('nc_type', 'read_only', true);
            cur_frm.set_df_property('qm_process', 'read_only', true);
            cur_frm.set_df_property('date', 'read_only', true);
            cur_frm.set_df_property('company', 'read_only', true);
        } else {
            cur_frm.set_df_property('title', 'read_only', false);
            cur_frm.set_df_property('nc_type', 'read_only', false);
            cur_frm.set_df_property('qm_process', 'read_only', false);
            cur_frm.set_df_property('date', 'read_only', false);
            cur_frm.set_df_property('company', 'read_only', false);
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

        // Only QAU can change the classification
        if (frappe.user.has_role('QAU')) {
            cur_frm.set_df_property('criticality_classification', 'read_only', false);
            cur_frm.set_df_property('regulatory_classification', 'read_only', false);
        } else {
            cur_frm.set_df_property('criticality_classification', 'read_only', true);
            cur_frm.set_df_property('regulatory_classification', 'read_only', true);
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

        // set information bar for missing infos
        cur_frm.dashboard.clear_comment();
        if ((!frm.doc.__islocal)
            && (!frm.doc.title 
            || !frm.doc.nc_type
            || !frm.doc.description
            || !frm.doc.qm_process)) {
                cur_frm.dashboard.add_comment( __("Please set and save Title, NC Type, Process and Description to create this Nonconformity."), 'red', true);
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
        {'fieldname': 'description', 'fieldtype': 'Text Editor', 'label': __('Description')}
    ],
    function(values){
        frappe.call({
            'method': 'microsynth.qms.doctype.qm_change.qm_change.create_change',
            'args': {
                'dt': cur_frm.doc.doctype,
                'dn': cur_frm.doc.name,
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
    __('Please enter a title'),
    __('Create')
    )
}
