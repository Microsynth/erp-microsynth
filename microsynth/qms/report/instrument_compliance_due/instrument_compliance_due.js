// Copyright (c) 2026, Microsynth
// For license information, please see license.txt
/* eslint-disable */

frappe.query_reports["Instrument Compliance Due"] = {
    "filters": [
        {
            "fieldname": "requirement_type",
            "label": "Requirement Type",
            "fieldtype": "Select",
            "options": "\nRequalification in next 6 weeks\nVerification in next 24 weeks\nCalibration in next 24 weeks\nOverdue"
        }
    ],
	"onload": (report) => {
		hide_chart_buttons();
	}
};
