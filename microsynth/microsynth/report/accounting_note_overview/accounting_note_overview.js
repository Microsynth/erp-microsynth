// Copyright (c) 2024, Microsynth, libracore and contributors
// For license information, please see license.txt
/* eslint-disable */

frappe.query_reports["Accounting Note Overview"] = {
    "filters": [
        {
            "fieldname":"from_date",
            "label": __("From Date"),
            "fieldtype": "Date",
            "default": frappe.datetime.add_months(frappe.datetime.get_today(), -4),
            "reqd": 1
        },
        {
            "fieldname":"to_date",
            "label": __("To Date"),
            "fieldtype": "Date",
            "default": frappe.datetime.get_today(),
            "reqd": 1
        },
        {
            "fieldname":"account",
            "label": __("Account"),
            "fieldtype": "Link",
            "options": "Account"
        },
        {
            "fieldname":"status",
            "label": __("Status"),
            "fieldtype": "Select",
            "options": "\nOpen\nClosed",
            "default": "Open"
        }
    ],
    "onload": (report) => {
        report.page.add_inner_button( __("New"), function() {
            var d = new frappe.ui.Dialog({
                'fields': [
                    {'fieldname': 'text', 'fieldtype': 'HTML'}
                ],
                'primary_action': function() {
                    d.hide();
                    var target = __("New") + " " + __("Accounting Note");
                    frappe.set_route("Form", "Accounting Note", target);
                },
                'primary_action_label': __("I know what I am doing"),
                'title': __("Information")
            });
            d.fields_dict.text.$wrapper.html(__("Please use either <i>Sales Invoice > Create > Accounting Note</i>, <br><i>Payment Entry > Create Accounting Note</i> or <br><i>Journal Entry > Create Accounting Note</i> to create pre-filled records.")),
            d.show();
        });
    }
};
