// Copyright (c) 2025, Microsynth
// For license information, please see license.txt
/* eslint-disable */


frappe.query_reports["Purchasing Price History"] = {
    filters: [
        {
            fieldname: "item_code",
            label: __("Item"),
            fieldtype: "Link",
            options: "Item",
            get_query: function () {
                return {
                    filters: {
                        'is_purchase_item': 1
                    }
                };
            }
        },
        {
            fieldname: "supplier",
            label: __("Supplier"),
            fieldtype: "Link",
            options: "Supplier"
        },
        {
            fieldname: "from_date",
            label: __("From Date"),
            fieldtype: "Date"
        },
        {
            fieldname: "to_date",
            label: __("To Date"),
            fieldtype: "Date"
        }
    ],
    "onload": (report) => {
        hide_chart_buttons();
    }
};
