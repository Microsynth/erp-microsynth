// Copyright (c) 2022, Microsynth, libracore and contributors and contributors
// For license information, please see license.txt
/* eslint-disable */

frappe.query_reports["Customer Finder"] = {
    "filters": [
        {
            "fieldname": "contact_name",
            "label": __("Person ID"),
            "fieldtype": "Link",
            "options": "Contact"
        },
        {
            "fieldname": "contact_full_name",
            "label": __("Contact Name"),
            "fieldtype": "Data",
            "options": ""
        },
        {
            "fieldname": "contact_email",
            "label": __("Contact Email"),
            "fieldtype": "Data",
            "options": ""
        },
        {
            "fieldname": "customer",
            "label": __("Customer (Company/Uni)"),
            "fieldtype": "Data",
            "options": ""
        },
        {
            "fieldname": "customer_id",
            "label": __("Customer ID"),
            "fieldtype": "Data",
            "options": "",
            "hidden": 1
        },
        {
            "fieldname": "contact_institute",
            "label": __("Institute"),
            "fieldtype": "Data",
            "options": ""
        },
        {
            "fieldname": "contact_institute_key",
            "label": __("Institute Key"),
            "fieldtype": "Data",
            "options": ""
        },
        {
            "fieldname": "contact_department",
            "label": __("Department"),
            "fieldtype": "Data",
            "options": ""
        },
        {
            "fieldname": "contact_group_leader",
            "label": __("Group Leader"),
            "fieldtype": "Data",
            "options": ""
        },
        {
            "fieldname": "address_country",
            "label": __("Country"),
            "fieldtype": "Link",
            "options": "Country"
        },
        {
            "fieldname": "address_city",
            "label": __("City"),
            "fieldtype": "Data",
            "options": ""
        },
        {
            "fieldname": "address_street",
            "label": __("Street"),
            "fieldtype": "Data",
            "options": ""
        },
        {
            "fieldname": "price_list",
            "label": __("Price List"),
            "fieldtype": "Link",
            "options": "Price List"
        },
        {
            "fieldname": "account_manager",
            "label": __("Sales Manager"),
            "fieldtype": "Link",
            "options": "User"
        },
        {
            "fieldname": "tax_id",
            "label": __("Tax ID"),
            "fieldtype": "Data",
            "options": ""
        },
        {
            "fieldname": "contact_status",
            "label": __("Contact Status"),
            "fieldtype": "Select",
            "options": [ '', 'Passive', 'Open', 'Lead', 'Replied', 'Disabled']
        },
        {
            "fieldname":"include_disabled",
            "label": __("Include disabled Customers (e.g. leads)"),
            "fieldtype": "Check"
        }
    ]
};
