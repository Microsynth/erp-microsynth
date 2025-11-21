// Copyright (c) 2025, Microsynth
// For license information, please see license.txt
/* eslint-disable */

frappe.query_reports["Shipping Item Usage"] = {
    "filters": [
        {
            fieldname: "shipping_item",
            label: __("Shipping Item"),
            fieldtype: "Link",
            options: "Item",
            get_query: function() {
                return {
                    filters: {
                        "item_group": "Shipping",
                        "disabled": 0
                    }
                };
            }
        },
        {
            fieldname: "from_date",
            label: __("From Date"),
            fieldtype: "Date",
            reqd: 1,
            default: (function() {
                // today as string YYYY-MM-DD
                let today_str = frappe.datetime.get_today();

                // 12 months ago as string YYYY-MM-DD
                let year_ago_str = frappe.datetime.add_months(today_str, -12);

                // split string into parts
                let parts = year_ago_str.split('-'); // ["2024","11","21"]
                let year = parseInt(parts[0], 10);
                let month = parseInt(parts[1], 10) - 1; // JS months are 0-indexed

                // first day of that month
                let first_of_month = new Date(year, month, 1);

                // return ERPNext date string
                return frappe.datetime.obj_to_str(first_of_month);
            })()
        },
        {
            fieldname: "to_date",
            label: __("To Date"),
            fieldtype: "Date"
        }
    ],

    // Prevent invalid date ranges
    onload: function(report) {
        // Automatic validation on filter change
        report.get_filter("to_date").df.onchange = () => {
            const from_date = frappe.query_report.get_filter_value("from_date");
            const to_date = frappe.query_report.get_filter_value("to_date");

            if (to_date && to_date < from_date) {
                frappe.msgprint(__("To Date cannot be earlier than From Date."));
                frappe.query_report.set_filter_value("to_date", "");
            }
        };
    }
};
