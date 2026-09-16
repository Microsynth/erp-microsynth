// Copyright (c) 2026, Microsynth
// For license information, please see license.txt
/* eslint-disable */

frappe.query_reports["Computerised System QMF"] = {
    "filters": [
        {
            "fieldname": "cs_type",
            "label": "Type",
            "fieldtype": "Select",
            "options": "\nModule\nFORM / LIST\nApplication\nScript / Pipeline\nSponsor Tool"
        },
        {
            "fieldname": "regulatory_classification",
            "label": "Regulatory Classification",
            "fieldtype": "Select",
            "options": "\nGMP\nnon-GMP"
        },
        {
            "fieldname": "gamp5_class",
            "label": "GAMP5 Class",
            "fieldtype": "Select",
            "options": "\n1: Infrastructure\n3: Non-Configurable\n4: Configurable\n5: Custom"
        },
        {
            "fieldname": "primary_version_control_method",
            "label": "Primary Version Control Method",
            "fieldtype": "Select",
            "options": "\nVersion Control Tool\nQM Document\nLogbook\nBuilt-in Version History\nSupplier Release Records"
        },
        {
            "fieldname": "status",
            "label": "Status",
            "fieldtype": "Select",
            "options": "\nUnapproved\nValidated\nDecommissioned"
        },
        {
            "fieldname": "logbook_type",
            "label": "Log Book Type",
            "fieldtype": "Select",
            "options": "\nMaintanance\nService\nFunction Control\nCrash/Error\n(Re-)Qualification\nVerification\nCalibration\nSoftware\nBugfix\nUpdate\n(Re-)Validation\nAudit Trail Review\nOther"
        }
    ],
    "onload": function(report) {
        hide_chart_buttons();
    }
};
