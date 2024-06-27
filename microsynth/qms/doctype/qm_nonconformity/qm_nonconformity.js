// Copyright (c) 2024, Microsynth, libracore and contributors
// For license information, please see license.txt


frappe.ui.form.on('QM Nonconformity', {
    refresh: function(frm) {
        if (frm.doc.docstatus == 0 && !frm.doc.nc_type && !frappe.user.has_role('QAU')) {
            determine_nc_type(frm);
        }

        // Create Correction
        if (["Planning"].includes(frm.doc.status)
            && !["OOS", "Track & Trend"].includes(frm.doc.nc_type)
            && (frappe.user.has_role('QAU') || frappe.session.user === frm.doc.owner)) {  // TODO: change owner to created_by
            frm.add_custom_button(__("Request Correction"), function() {
                request_correction(frm);
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


function request_correction(frm) {
    frappe.prompt([
        {'fieldname': 'title', 'fieldtype': 'Data', 'label': __('Title')},
        {'fieldname': 'responsible_person', 'fieldtype': 'Link', 'label': __('Responsible Person'), 'options':'User', 'reqd': 1},
        {'fieldname': 'due_date', 'fieldtype': 'Date', 'label': __('Due date'), 'reqd': 1},
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
                'type': "Correction"
            },
            "callback": function(response) {
                console.log("created revision request...")
                frappe.show_alert( __("Correction created") + 
                            ": <a href='/desk#Form/QM Action/" + 
                            response.message + "'>" + response.message + 
                            "</a>"
                        );
            }
        });
    },
    __('Please choose a Responsible Person and a Due Date'),
    __('Request Correction')
    )
}


function determine_nc_type(frm) {
    // TODO: Discuss with Lars how to best implement the decision tree? (ideas: frappe.prompt, new frappe.ui.Dialog)
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
