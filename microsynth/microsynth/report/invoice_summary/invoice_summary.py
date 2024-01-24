# Copyright (c) 2024, Microsynth, libracore and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _

def get_columns(filters):
    return [
        {"label": _("Sales Invoice"), "fieldname": "sales_invoice", "fieldtype": "Link", "options": "Sales Invoice", "width": 125 },
        {"label": _("Date"), "fieldname": "date", "fieldtype": "Date", "width": 75 },
        {"label": _("Customer Name"), "fieldname": "customer_name", "fieldtype": "Data", "options": "Customer", "width": 250 },
        {"label": _("Customer ID"), "fieldname": "customer", "fieldtype": "Link", "options": "Customer", "width": 90 },
        {"label": _("Rounded Grand Total"), "fieldname": "rounded_total", "fieldtype": "Currency", "width": 120 },
        {"label": _("Currency"), "fieldname": "currency", "fieldtype": "Data", "width": 75 },
        {"label": _("Customer's Purchase Order"), "fieldname": "po_no", "fieldtype": "Data", "width": 200 },
        {"label": _("Product Type"), "fieldname": "product_type", "fieldtype": "Data", "width": 100 },
        {"label": _("Contact"), "fieldname": "contact_person", "fieldtype": "Link", "options": "Contact", "width": 90 },
        {"label": _("Company"), "fieldname": "company", "fieldtype": "Data", "width": 160 },
        {"label": _("Web Order ID"), "fieldname": "web_order_id", "fieldtype": "Data", "width": 100 },
    ]


def get_data(filters):
    conditions = ''

    if filters.get('customer'):
        conditions += f"AND `customer` = '{filters.get('customer')}'"
    if filters.get('po_no'):
        conditions += f"AND `po_no` = '{filters.get('po_no')}'"
    if filters.get('company'):
        conditions += f"AND `company` = '{filters.get('company')}'"

    sql_query = f"""
        SELECT
			`tabSales Invoice`.`name` AS `sales_invoice`,
			`tabSales Invoice`.`posting_date` AS `date`,
            `tabSales Invoice`.`customer_name` AS `customer_name`,
			`tabSales Invoice`.`customer` AS `customer`,
            `tabSales Invoice`.`rounded_total` AS `rounded_total`,
            `tabSales Invoice`.`currency` AS `currency`,
            `tabSales Invoice`.`po_no` AS `po_no`,
            `tabSales Invoice`.`product_type` AS `product_type`,
            `tabSales Invoice`.`contact_person` AS `contact_person`,
            `tabSales Invoice`.`company` AS `company`,
            `tabSales Invoice`.`web_order_id` AS `web_order_id`
        FROM `tabSales Invoice`
        WHERE `tabSales Invoice`.`docstatus` = 1
        	AND `tabSales Invoice`.`posting_date` >= DATE('{filters.get('from_date')}') AND `tabSales Invoice`.`posting_date` <= DATE('{filters.get('to_date')}')
			{conditions}
        ORDER BY `tabSales Invoice`.`posting_date`;
        """
    data = frappe.db.sql(sql_query, as_dict=True)
    return data


def execute(filters=None):
    columns, data = get_columns(filters), get_data(filters)
    return columns, data
