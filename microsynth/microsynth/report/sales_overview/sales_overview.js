// Copyright (c) 2023, Microsynth, libracore and contributors and contributors
// For license information, please see license.txt
/* eslint-disable */

frappe.query_reports["Sales Overview"] = {
    "filters": [
        {
            "fieldname": "company",
            "label": __("Company"),
            "fieldtype": "Link",
            "options": "Company"
        },
        {
            "fieldname": "territory",
            "label": __("Territory"),
            "fieldtype": "Link",
            "options": "Territory"
        },
        {
            "fieldname": "fiscal_year",
            "label": __("Fiscal Year"),
            "fieldtype": "Link",
            "options": "Fiscal Year",
            "reqd": 1,
            "default": frappe.defaults.get_user_default("fiscal_year") || frappe.defaults.get_global_default("fiscal_year")
        },
        {
            "fieldname": "reporting_type",
            "label": __("Reporting Type"),
            "fieldtype": "Select",
            "options": "CHF\nEUR",
            "reqd": 1,
            "default": "CHF"
        },
        // {
        //     "fieldname": "customer_credit_revenue",
        //     "label": __("Customer Credits Revenue"),
        //     "fieldtype": "Select",
        //     "options": "Credit deposit\nCredit allocation",
        //     "reqd": 1,
        //     "default": "Credit allocation"
        // },
        {
            "fieldname": "aggregate_genetic_analyis",
            "label": __("Aggregate Genetic Analysis"),
            "fieldtype": "Check"
        }
    ],
    "onload": (report) => {
        if ((window.location.toString().includes("/Sales%20Overview") ) && (!window.location.toString().includes("Details"))) {
            // add event listener for double clicks
            cur_page.container.addEventListener("dblclick", function(event) {
                if (event.delegatedTarget) {
                    var row = event.delegatedTarget.getAttribute("data-row-index");
                    var column = event.delegatedTarget.getAttribute("data-col-index");
                    
                    var filters = {
                        'company': frappe.query_report.get_filter_value('company'),
                        'territory': frappe.query_report.get_filter_value('territory'),
                        'year': frappe.query_report.get_filter_value('fiscal_year'),
                        'reporting_type': frappe.query_report.get_filter_value('reporting_type'),
                        // 'customer_credit_revenue': frappe.query_report.get_filter_value('customer_credit_revenue'),
                        'customer_credit_revenue': 'Credit allocation'
                    }
                    
                    // ignore columns that are not in the month-grid part
                    if ((1 < column) && (column < 14)) {
                        filters['month'] = column - 1;
                        filters['item_groups'] = frappe.query_report.data[row]['group']
                        
                        //console.log(filters);
                        frappe.set_route("query-report", "Sales Overview Details", filters);
                    }
                    
                }
            });
        }
    }
};
