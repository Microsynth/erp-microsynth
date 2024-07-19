# Copyright (c) 2024, Microsynth, libracore and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
from datetime import date


def get_columns():
    return [
        {"label": _("Quotation ID"), "fieldname": "name", "fieldtype": "Link", "options": "Quotation", "width": 100},
        {"label": _("Title"), "fieldname": "title", "fieldtype": "Data", "width": 250},
        {"label": _("Status"), "fieldname": "status", "fieldtype": "Data", "width": 55},
        {"label": _("Date"), "fieldname": "transaction_date", "fieldtype": "Date", "width": 80},
        {"label": _("Customer"), "fieldname": "customer", "fieldtype": "Link", "options": "Customer", "width": 100},
        {"label": _("Contact Person"), "fieldname": "contact_person", "fieldtype": "Link", "options": "Contact", "width": 105},
        {"label": _("Quotation Type"), "fieldname": "quotation_type", "fieldtype": "Data", "width": 118},
        {"label": _("Net Total"), "fieldname": "net_total", "fieldtype": "Currency", "options": "currency", "width": 105},
        {"label": _("Sales Manager"), "fieldname": "sales_manager", "fieldtype": "Data", "options": "User", "width": 160 }
    ]


@frappe.whitelist()
def get_data(filters=None):
    filter_conditions = ''

    if filters.get('sales_manager'):
        filter_conditions += f"AND `tabQuotation`.`sales_manager` = '{filters.get('sales_manager')}'"
    if filters.get('company'):
        filter_conditions += f"AND `tabQuotation`.`company` = '{filters.get('company')}'"
    if not filters.get('include_expired'):
        filter_conditions += f"AND `tabQuotation`.`valid_till` >= '{date.today()}'"

    open_quotations = frappe.db.sql(f"""
        SELECT
            `tabQuotation`.`name`,
            `tabQuotation`.`title`,
            IF(`tabQuotation`.`valid_till` < '{date.today()}', 'Expired', `tabQuotation`.`status`) as `status`,
            `tabQuotation`.`transaction_date`,
            `tabQuotation`.`party_name` AS `customer`,
            `tabQuotation`.`contact_person`,
            `tabQuotation`.`quotation_type`,                  
            `tabQuotation`.`net_total`,
            `tabQuotation`.`currency`,
            `tabQuotation`.`sales_manager`
        FROM `tabQuotation`
        WHERE `tabQuotation`.`docstatus` = 1
            AND `tabQuotation`.`status` NOT IN ('Ordered', 'Cancelled', 'Lost')
            AND `tabQuotation`.`transaction_date` BETWEEN DATE('{filters.get('from_date')}') AND DATE('{filters.get('to_date')}')
            {filter_conditions}
        ORDER BY
            `tabQuotation`.`transaction_date` DESC;
    """, as_dict=True)
    
    return open_quotations


# def has_sales_order(quotation):
#     return frappe.db.get_value("Sales Order Item", {"prevdoc_docname": quotation.name, "docstatus": 1})


def execute(filters=None):
    columns = get_columns()
    data = get_data(filters)
    return columns, data
