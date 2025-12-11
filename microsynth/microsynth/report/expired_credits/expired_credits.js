// Copyright (c) 2016, Microsynth, libracore and contributors and contributors
// For license information, please see license.txt
/* eslint-disable */

frappe.query_reports["Expired Credits"] = {
    filters: [
        {
            fieldname: "company",
            label: __("Company"),
            fieldtype: "Link",
            options: "Company"
        },
        {
            fieldname: "customer",
            label: __("Customer"),
            fieldtype: "Link",
            options: "Customer"
        },
        {
            fieldname: "contact_person",
            label: __("Contact"),
            fieldtype: "Link",
            options: "Contact"
        },
        {
            fieldname: "expiry_date_before",
            label: __("Expiry Date Before"),
            fieldtype: "Date",
            reqd: 1,
            default: frappe.datetime.get_today()
        }
    ],
    onload: function(report) {
        // Attach click handler after render
        report.page.wrapper.on('click', '.cancel-credit', function() {
            let credit_account = $(this).data("ca");
                let exp_raw = $(this).data("exp");
                // Convert YYYY-MM-DD into a JS Date object (ERPNext helper)
                let exp_date_obj = frappe.datetime.str_to_obj(exp_raw);
                // Format using user's preferred date format
                let exp_date = frappe.datetime.obj_to_user(exp_date_obj);

            frappe.confirm(
                __("Are you sure you want to cancel Credit Account {0} expiring on {1}?",
                    [credit_account, exp_date]),
                function() {
                    frappe.call({
                        'method': "microsynth.microsynth.report.expired_credits.expired_credits.cancel_credit_account",
                        'args': {
                            'credit_account_id': credit_account
                        },
                        'callback': function(r) {
                            if (!r.exc) {
                                report.refresh().then(
                                    function() {
                                        frappe.msgprint({
                                            'title': __("Success"),
                                            'message': __("Cancelled Credit Account {0}.", [credit_account]),
                                            'indicator': "green"
                                        });
                                    }
                                );
                            }
                        }
                    });
                }
            );
        });
    }
};
