// Copyright (c) 2024, Microsynth, libracore and contributors
// For license information, please see license.txt
/* eslint-disable */

frappe.query_reports["Users by Process"] = {
    "filters": [
        {
            "fieldname": "process_number",
            "label": __("Process Number"),
            "fieldtype": "Select",
            "options": "\n1\n2\n3\n4\n5",
            "reqd": 1
        },
        {
            "fieldname": "subprocess_number",
            "label": __("Subprocess Number"),
            "fieldtype": "Select",
            "options": "\n1\n2\n3\n4\n5\n6\n7\n37",
            "reqd": 1
        },
        {
            "fieldname": "chapter",
            "label": __("Chapter"),
            "fieldtype": "Int"
        },
        {
            "fieldname": "company",
            "label": __("Company"),
            "fieldtype": "Link",
            "options": "Company"
        }
    ]
};
