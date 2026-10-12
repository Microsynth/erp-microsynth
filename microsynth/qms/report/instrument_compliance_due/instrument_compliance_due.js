// Copyright (c) 2026, Microsynth
// For license information, please see license.txt
/* eslint-disable */

frappe.query_reports["Instrument Compliance Due"] = {
    "filters": [
        {
            "fieldname": "requirement_type",
            "label": "Mode",
            "fieldtype": "Select",
            "options": "\nRequalification in next 6 weeks\nQMF (Class A, Active or Blocked)\nVerification due\nCalibration due\nOverdue"
        },
        {
            "fieldname": "status",
            "label": "Instrument Status",
            "fieldtype": "Select",
            "options": "\nUnapproved\nActive\nBlocked\nDecommissioned\nDisposed"
        },
        {
            "fieldname": "instrument_class",
            "label": "Instrument Class",
            "fieldtype": "Select",
            "options": "\nA – Complex or computerised instrument\nB – Standard device with straightforward measurement\nC – Instrument without measuring function\nF – Freezer or Fridge\nP – Pipette\nR – Measuring reference\nT – Thermometer\nW – Balance or Scale"
        },
        {
            "fieldname": "qm_process",
            "label": "Process",
            "fieldtype": "Link",
            "options": "QM Process"
        },
        {
            "fieldname": "site",
            "label": "Site",
            "fieldtype": "Select",
            "options": "\nBalgach\nGöttingen\nLyon\nWien"
        }
    ],
	"onload": (report) => {
		hide_chart_buttons();
        // Show "Import Certificates" button if User has role QAU calling a backend method to import QM Log Book Entries from ERP-Share
        if (report.page && !report.page.btn_import_certificates && frappe.user.has_role("QAU")) {
            report.page.btn_import_certificates = report.page.add_inner_button(__('Import Certificates'), function() {
                frappe.call({
                    'method': "microsynth.qms.doctype.qm_log_book.qm_log_book.import_log_book_entries",
                    'args': { 'verbose': true },
                    'freeze': true,
                    'freeze_message': __('Importing certificates...'),
                    'callback': function(r) {
                        frappe.msgprint(__('Import completed'));
                        report.refresh();
                    }
                });
            });
        }
	}
};
