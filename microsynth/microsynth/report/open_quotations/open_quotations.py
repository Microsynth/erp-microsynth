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
        {"label": _("Valid till"), "fieldname": "valid_till", "fieldtype": "Date", "width": 80},
        {"label": _("Customer"), "fieldname": "customer", "fieldtype": "Link", "options": "Customer", "width": 100},
        {"label": _("Contact Person"), "fieldname": "contact_person", "fieldtype": "Link", "options": "Contact", "width": 105},
        {"label": _("Quotation Type"), "fieldname": "quotation_type", "fieldtype": "Data", "width": 118},
        {"label": _("Net Total"), "fieldname": "net_total", "fieldtype": "Currency", "options": "currency", "width": 105},
        {"label": _("Sales Manager"), "fieldname": "sales_manager", "fieldtype": "Data", "options": "User", "width": 160 },
        {"label": _("Unlinked Sales Order(s)"), "fieldname": "unlinked_sales_order", "fieldtype": "Data", "options": "Sales Order", "width": 150 }
    ]


@frappe.whitelist()
def get_data(filters=None):
    filter_conditions = ''
    item_join = ""
    if filters.get('sales_manager'):
        filter_conditions += f"AND `tabQuotation`.`sales_manager` = '{filters.get('sales_manager')}'"
    if filters.get('company'):
        filter_conditions += f"AND `tabQuotation`.`company` = '{filters.get('company')}'"
    if filters.get('search_mode') != "Include Expired Quotations":
        filter_conditions += f"AND `tabQuotation`.`valid_till` >= '{date.today()}'"
    if filters.get('item_codes'):
        item_join = "LEFT JOIN `tabQuotation Item` ON `tabQuotation Item`.`parent` = `tabQuotation`.`name`"
        item_codes = filters.get('item_codes').split(',')
        item_code_list = ','.join(f'"{item_code.strip()}"' for item_code in item_codes)
        filter_conditions += f"AND `tabQuotation Item`.`item_code` IN ({item_code_list})"

    open_quotations = frappe.db.sql(f"""
        SELECT DISTINCT
            `tabQuotation`.`name`,
            `tabQuotation`.`title`,
            IF(`tabQuotation`.`valid_till` < '{date.today()}', 'Expired', `tabQuotation`.`status`) as `status`,
            `tabQuotation`.`transaction_date`,
            `tabQuotation`.`valid_till`,
            `tabQuotation`.`party_name` AS `customer`,
            `tabQuotation`.`contact_person`,
            `tabQuotation`.`quotation_type`,                  
            `tabQuotation`.`net_total`,
            `tabQuotation`.`currency`,
            `tabQuotation`.`sales_manager`
        FROM `tabQuotation`
        {item_join}
        WHERE `tabQuotation`.`docstatus` = 1
            AND `tabQuotation`.`status` NOT IN ('Ordered', 'Cancelled', 'Lost')
            AND `tabQuotation`.`transaction_date` BETWEEN DATE('{filters.get('from_date')}') AND DATE('{filters.get('to_date')}')
            {filter_conditions}
        ORDER BY
            `tabQuotation`.`transaction_date` DESC;
    """, as_dict=True)

    if filters.get('search_mode') == "Include unlinked orders (slow)":
        for open_quotation in open_quotations:
            comment_field_results = frappe.get_all("Sales Order", filters=[['comment', 'LIKE', f"%{open_quotation['name']}%"]], fields=['name'])
            open_quotation['unlinked_sales_order'] = ', '.join(uso['name'] for uso in comment_field_results)
    
    return open_quotations


def execute(filters=None):
    columns = get_columns()
    data = get_data(filters)
    return columns, data
