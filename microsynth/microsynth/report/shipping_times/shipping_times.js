// Copyright (c) 2025, Microsynth, libracore and contributors
// For license information, please see license.txt
/* eslint-disable */

frappe.query_reports["Shipping Times"] = {
    "filters": [
        {
            "fieldname": "item_code",
            "label": __("Shipping Item Code"),
            "fieldtype": "Link",
            "options": "Item"
        },
        {
            "fieldname": "country",
            "label": __("To Country"),
            "fieldtype": "Link",
            "options": "Country"
        },
        {
            "fieldname": "from_date",
            "label": __("From date"),
            "fieldtype": "Date",
            "reqd": 1
        },
        {
            "fieldname": "to_date",
            "label": __("To date"),
            "fieldtype": "Date",
            "reqd": 1
        },
        {
            "fieldname": "show_unknown_delivery",
            "label": "Include unknown delivery",
            "fieldtype": "Check",
            "default": 0
        }
    ],
    "onload": (report) => {
        hide_chart_buttons();

        report.page.add_inner_button(__('Upload UPS CSV'), function () {
            new frappe.ui.FileUploader({
                // folder: 'Home',
                upload_notes: 'Please upload a CSV file downloaded from UPS',
                restrictions: {
                    allowed_file_types: ['.csv']
                },
                allow_multiple: false,
                on_success: (file_doc) => {
                    console.log("upload ok, start parsing");
                    frappe.call({
                        'method': "microsynth.microsynth.doctype.tracking_code.tracking_code.parse_ups_file",
                        'args': {
                            "file_path": file_doc.file_url
                        },
                        'freeze': true,
                        'freeze_message': __("Parsing CSV, please be patient ..."),
                        'callback': function(response) {
                            if (response.message.success) {
                                frappe.msgprint({
                                    title: __('Success'),
                                    indicator: 'green',
                                    message: response.message.message + "<br><br><b>Please reload</b>"
                                });
                                frappe.click_button('Refresh');
                            } else {
                                frappe.msgprint({
                                    title: __('Failure'),
                                    indicator: 'red',
                                    message: response.message.message
                                });
                            }
                        }
                    });
                }
            });
        });
    }
};
