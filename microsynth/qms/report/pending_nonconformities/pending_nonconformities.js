// Copyright (c) 2024, Microsynth, libracore and contributors
// For license information, please see license.txt
/* eslint-disable */

frappe.query_reports["Pending Nonconformities"] = {
    "filters": [
        {
            "fieldname": "name",
            "label": __("ID"),
            "fieldtype": "Link",
            "options": "QM Nonconformity"
        },
        {
            "fieldname": "title",
            "label": __("Title"),
            "fieldtype": "Data"
        },
        {
            "fieldname": "nc_type",
            "label": __("NC Type"),
            "fieldtype": "Select",
            "options": "\nAuthorities Audit\nCustomer Audit\nInternal Audit\nDeviation\nEvent\nOOS\nTrack & Trend"
        },
        {
            "fieldname": "status",
            "label": __("Status"),
            "fieldtype": "Select",
            "options": "\nDraft\nCreated\nInvestigation\nPlanning\nPlan Approval\nImplementation\nCompleted\nClosed\nCancelled"
        },
        {
            "fieldname": "created_by",
            "label": __("Creator"),
            "fieldtype": "Link",
            "options": "User"
        },
        {
            "fieldname": "qm_process",
            "label": __("Process"),
            "fieldtype": "Link",
            "options": "QM Process"
        }
    ]
};
