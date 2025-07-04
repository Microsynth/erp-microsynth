// Copyright (c) 2025, Microsynth
// For license information, please see license.txt
/* eslint-disable */

frappe.query_reports["Item Accounting"] = {
    "filters": [
        {
            "fieldname": "account_type",
            "fieldtype": "Select",
            "label": "Account Type",
            "options": "Expense\nIncome",
            "default": "Expense",
            "reqd": 1
        },
        {
            "fieldname": "item_group",
            "fieldtype": "Link",
            "label": "Item Group",
            "options": "Item Group",
            "default": "Financial Accounting"
        }
    ],
    "onload": (report) => {
        hide_chart_buttons();
    }
};
