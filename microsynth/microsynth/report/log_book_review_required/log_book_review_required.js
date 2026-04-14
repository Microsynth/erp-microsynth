// Copyright (c) 2026, Microsynth
// For license information, please see license.txt
/* eslint-disable */

frappe.query_reports["Log Book Review Required"] = {
    "filters": [
        {
            "fieldname": "qm_instrument",
            "label": "QM Instrument",
            "fieldtype": "Link",
            "options": "QM Instrument"
        },
        {
            "fieldname": "entry_type",
            "label": "Log Book Entry Type",
            "fieldtype": "Select",
            "options": "\nMaintanance/Service\n(Re-)Qualification\nVerification\nCalibration\nSoftware update\nOther"
        },
        {
            "fieldname": "instrument_class",
            "label": "Instrument Class",
            "fieldtype": "Select",
            "options": "\nA – Complex or computerised instrument\nB – Standard device with straightforward measurement\nC – Instrument without measuring function\nF – Freezer or Fridge\nP – Pipette\nR – Measuring reference\nT – Thermometer\nW – Balance or Scale"
        },
        {
            "fieldname": "regulatory_classification",
            "label": "Regulatory Classification",
            "fieldtype": "Select",
            "options": "\nGMP\nnon-GMP"
        },
        {
            "fieldname": "to_date",
            "label": "To Date",
            "fieldtype": "Date",
            "reqd": 1,
            "default": frappe.datetime.add_days(frappe.datetime.get_today(), -180)
        }
    ],
    "onload": (report) => {
        hide_chart_buttons();
    }
};
