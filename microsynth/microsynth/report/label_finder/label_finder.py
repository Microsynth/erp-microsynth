# Copyright (c) 2024, Microsynth, libracore and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
import re


def get_columns(filters):
    return [
        {"label": _("Label Barcode"), "fieldname": "label_id", "fieldtype": "Data", "width": 100 },
        {"label": _("Status"), "fieldname": "status", "fieldtype": "Data", "width": 75 },
        {"label": _("Customer"), "fieldname": "customer", "fieldtype": "Link", "options": "Customer", "width": 75 },
        {"label": _("Customer Name"), "fieldname": "customer_name", "fieldtype": "Data", "width": 175 },
        {"label": _("Contact"), "fieldname": "contact", "fieldtype": "Link", "options": "Contact", "width": 75 },
        {"label": _("Sales Order"), "fieldname": "sales_order", "fieldtype": "Link", "options": "Sales Order", "width": 125 },
        {"label": _("Web Order ID"), "fieldname": "web_order_id", "fieldtype": "Data", "width": 95 },
        {"label": _("Item Code"), "fieldname": "item_code", "fieldtype": "Link", "options": "Item", "width": 75 },
        {"label": _("Registered"), "fieldname": "registered", "fieldtype": "Check", "width": 80 },
        {"label": _("Registered To"), "fieldname": "registered_to", "fieldtype": "Link", "options": "Contact", "width": 100 },
        {"label": _("Sequencing Label"), "fieldname": "name", "fieldtype": "Link", "options": "Sequencing Label", "width": 95 }
    ]


def get_data(filters):
    if not filters:
        return []
    conditions = ""
    
    if filters.get('contact'):
        conditions += f"AND `tabSequencing Label`.`contact` = '{filters.get('contact')}'"
    if filters.get('registered_to'):
        conditions += f"AND `tabSequencing Label`.`registered_to` = '{filters.get('registered_to')}'"
    if filters.get('customer'):
        conditions += f"AND `tabSequencing Label`.`customer` = '{filters.get('customer')}'"
    if filters.get('customer_name'):
        conditions += f"AND `tabSequencing Label`.`customer_name` LIKE '{filters.get('customer_name')}'"
    if filters.get('sales_order'):
        conditions += f"AND `tabSequencing Label`.`sales_order` = '{filters.get('sales_order')}'"
    if filters.get('web_order_id'):
        conditions += f"AND `tabSales Order`.`web_order_id` = '{filters.get('web_order_id')}'"
    if filters.get('from_barcode') and filters.get('to_barcode'):
        if filters.get('from_barcode').isnumeric() and filters.get('to_barcode').isnumeric():
            conditions += f"AND `tabSequencing Label`.`label_id` BETWEEN '{filters.get('from_barcode')}' AND '{filters.get('to_barcode')}'"
        else:
            from_prefix = ''.join([i for i in filters.get('from_barcode') if not i.isdigit()])
            to_prefix = ''.join([i for i in filters.get('to_barcode') if not i.isdigit()])
            if from_prefix != to_prefix:
                frappe.throw("From Barcode and To Barcode need to have the same Prefix.")
            from_barcode = re.sub("[^0-9]", "", filters.get('from_barcode'))
            to_barcode = re.sub("[^0-9]", "", filters.get('to_barcode'))
            if len(from_barcode) != len(to_barcode):
                frappe.throw("From Barcode and To Barcode need to have the same length.")
            barcode_list = ','.join(f'"{to_prefix}{i:0{len(to_barcode)}d}"' for i in range(int(from_barcode), int(to_barcode) + 1))
            conditions += f"AND `tabSequencing Label`.`label_id` IN ({barcode_list})"

    sql_query = f"""
        SELECT
            `tabSequencing Label`.`name`,
            `tabSequencing Label`.`status`,
            `tabSequencing Label`.`registered`,
            `tabSequencing Label`.`label_id`,
            `tabSequencing Label`.`item` AS `item_code`,
            `tabSequencing Label`.`customer`,
            `tabSequencing Label`.`customer_name`,
            `tabSequencing Label`.`sales_order`,
            `tabSales Order`.`web_order_id`,
            `tabSequencing Label`.`contact`,
            `tabSequencing Label`.`registered_to`
        FROM `tabSequencing Label`
        LEFT JOIN `tabSales Order` ON `tabSales Order`.`name` = `tabSequencing Label`.`sales_order`
        WHERE TRUE
            {conditions}
        ORDER BY `tabSequencing Label`.`label_id`;
        """
    data = frappe.db.sql(sql_query, as_dict=True)
    return data


def execute(filters):
    columns, data = get_columns(filters), get_data(filters)
    return columns, data
