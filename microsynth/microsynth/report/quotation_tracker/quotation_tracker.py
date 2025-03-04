# Copyright (c) 2025, Microsynth
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
from datetime import date, timedelta


def get_columns():
    return [
        {"label": _("Quotation ID"), "fieldname": "name", "fieldtype": "Link", "options": "Quotation", "width": 100},
        {"label": _("Title"), "fieldname": "title", "fieldtype": "Data", "width": 250},
        {"label": _("Status"), "fieldname": "status", "fieldtype": "Data", "width": 80},
        {"label": _("Date"), "fieldname": "transaction_date", "fieldtype": "Date", "width": 80},
        {"label": _("Valid till"), "fieldname": "valid_till", "fieldtype": "Date", "width": 80},
        {"label": _("Quotation Type"), "fieldname": "quotation_type", "fieldtype": "Data", "width": 118},
        {"label": _("Net Total"), "fieldname": "net_total", "fieldtype": "Currency", "options": "currency", "width": 100},
        {"label": _("Last Follow Up"), "fieldname": "last_follow_up", "fieldtype": "Link", "options": "Contact Note", "width": 100},
        {"label": _("Last Followed Up"), "fieldname": "last_follow_up_date", "fieldtype": "Date", "width": 115},
        {"label": _("Customer"), "fieldname": "customer", "fieldtype": "Link", "options": "Customer", "width": 100},
        {"label": _("Contact Person"), "fieldname": "contact_person", "fieldtype": "Link", "options": "Contact", "width": 105},
        {"label": _("Contact Person Name"), "fieldname": "contact_display", "fieldtype": "Data", "width": 160 },        
        {"label": _("Sales Manager"), "fieldname": "sales_manager", "fieldtype": "Data", "width": 245 }
    ]


@frappe.whitelist()
def get_data(filters=None):
    filter_conditions = ''
    if filters.get('sales_manager'):
        filter_conditions += f"AND `tabQuotation`.`sales_manager` = '{filters.get('sales_manager')}'"

    quotations = frappe.db.sql(f"""
        SELECT DISTINCT
            `tabQuotation`.`name`,
            `tabQuotation`.`title`,
            IF(`tabQuotation`.`valid_till` < '{date.today()}', 'Expired', `tabQuotation`.`status`) as `status`,
            `tabQuotation`.`transaction_date`,
            `tabQuotation`.`valid_till`,
            `tabQuotation`.`party_name` AS `customer`,
            `tabQuotation`.`contact_person`,
            `tabQuotation`.`contact_display`,
            `tabQuotation`.`quotation_type`,                  
            `tabQuotation`.`net_total`,
            `tabQuotation`.`currency`,
            `tabQuotation`.`sales_manager`,

            (SELECT DISTINCT `tabContact Note`.`name`
                FROM `tabContact Note`
                WHERE `tabContact Note`.`prevdoc_docname` = `tabQuotation`.`name`
                ORDER BY `tabContact Note`.`date` DESC
                    LIMIT 1
            ) AS `last_follow_up`,
            
            (SELECT DISTINCT `tabContact Note`.`date`
                FROM `tabContact Note`
                WHERE `tabContact Note`.`prevdoc_docname` = `tabQuotation`.`name`
                ORDER BY `tabContact Note`.`date` DESC
                    LIMIT 1
            ) AS `last_follow_up_date`
            
        FROM `tabQuotation`
        LEFT JOIN `tabContact Note` ON `tabContact Note`.`prevdoc_docname` = `tabQuotation`.`name`
        WHERE `tabQuotation`.`docstatus` = 1
            AND `tabQuotation`.`status` NOT IN ('Ordered', 'Cancelled', 'Lost')
            AND `tabQuotation`.`valid_till` >= '{date.today()}'
            {filter_conditions}
        ORDER BY
            `tabQuotation`.`transaction_date` DESC;
    """, as_dict=True)

    quotations_to_follow_up = []
    threshold_day = date.today() - timedelta(days=30)

    for quote in quotations:
        if quote['last_follow_up_date']:
            if quote['last_follow_up_date'] < threshold_day:
                quote['status'] = 'Followed Up'
                quotations_to_follow_up.append(quote)
        else:
            quotations_to_follow_up.append(quote)
    
    return quotations_to_follow_up


def execute(filters=None):
    columns = get_columns()
    data = get_data(filters)
    return columns, data
