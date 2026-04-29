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
            "fieldname": "qm_process",
            "label": "QM Process",
            "fieldtype": "Link",
            "options": "QM Process"
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
        hide_column_filters();

        // Add "Review all" button
        if (report.page && !report.page.btn_review_all) {
            report.page.btn_review_all = report.page.add_inner_button(__('Review all'), function() {
                const filters = report.get_filter_values(true);
                if (!filters.qm_process) {
                    frappe.msgprint(__('Please select a QM Process before clicking on Review all.'));
                    return;
                }
                if (!filters.regulatory_classification || filters.regulatory_classification === "GMP") {
                    frappe.msgprint(__('Please select "non-GMP" as Regulatory Classification before clicking on Review all, as only non-GMP entries can be reviewed in bulk.'));
                    return;
                }
                frappe.call({
                    'method': "microsynth.qms.report.log_book_review_required.log_book_review_required.review_all_log_book_entries",
                    'args': {
                        'filters_json': JSON.stringify(filters)
                    },
                    'freeze': true,
                    'freeze_message': __('Closing log book entries...'),
                    'callback': function(r) {
                        if (r.message && r.message.closed) {
                            frappe.msgprint(__("Closed {0} log book entries.".replace("{0}", r.message.count)));
                            report.refresh();
                        }
                    }
                });
            });
        }
    }
};


function hide_column_filters() {
    let container = document.getElementsByClassName("page-content");
    const hide_column_filter_style = document.createElement("style");
    hide_column_filter_style.innerHTML = `
        .dt-header .dt-row[data-is-filter] {
          display: none !important;
        }
    `
    for (let i = 0; i < container.length; i++) {
        container[i].appendChild(hide_column_filter_style);
    }
}
