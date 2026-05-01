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
