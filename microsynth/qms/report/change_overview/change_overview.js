// Copyright (c) 2025, Microsynth
// For license information, please see license.txt
/* eslint-disable */

frappe.query_reports["Change Overview"] = {
	'filters': [
        {
            fieldname: "status_qm_change",
            label: __("Status QM Change"),
            fieldtype: "Select",
            options: "\nDraft\nCreated\nAssessment & Classification\nTrial\nPlanning\nImplementation\nCompleted\nClosed"
        },
        {
            fieldname: "status_qm_action",
            label: __("Status QM Action"),
            fieldtype: "Select",
            options: "\nDraft\nCreated\nWork in Progress\nCompleted\nCancelled"
        },
        {
            fieldname: "person",
            label: __("Responsible Person"),
            fieldtype: "Link",
            options: "User"
        },
        {
            fieldname: "qm_process",
            label: __("Process"),
            fieldtype: "Link",
            options: "QM Process"
        },
        {
            fieldname: "company",
            label: __("Company"),
            fieldtype: "Link",
            options: "Company"
        },
        {
            fieldname: "action_type",
            label: __("Action Type"),
            fieldtype: "Select",
            options: "\nCorrection\nCorrective Action\nNC Effectiveness Check\nChange Control Action\nCC Effectiveness Check"
        }
    ],
    'onload': function(report) {
        hide_chart_buttons();
    }
};
