# Copyright (c) 2024, Microsynth
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
import re


def get_columns():
    return [
        {"label": _("Sales Order"), "fieldname": "name", "fieldtype": "Link", "options": "Sales Order", "width": 125},
        {"label": _("Date"), "fieldname": "date", "fieldtype": "Date", "width": 75},
        {"label": _("Label Barcode"), "fieldname": "sequencing_label_id", "fieldtype": "Data", "width": 100},
        {"label": _("Contact"), "fieldname": "contact_person", "fieldtype": "Link", "options": "Contact", "width": 70},
        {"label": _("Customer"), "fieldname": "customer", "fieldtype": "Link", "options": "Customer", "width": 80},
        {"label": _("Customer name"), "fieldname": "customer_name", "fieldtype": "Data", "width": 250},
        {"label": _("Web Order ID"), "fieldname": "web_order_id", "fieldtype": "Data", "width": 95},
        {"label": _("Sample count"), "fieldname": "sample_count", "fieldtype": "Integer", "width": 100},
        # control fields:
        {"label": _("Total"), "fieldname": "total", "fieldtype": "Currency", "options": "currency", "width": 95},
        {"label": _("Status"), "fieldname": "status", "fieldtype": "Data", "width": 120},
        {"label": _("Product Type"), "fieldname": "product_type", "fieldtype": "Data", "width": 110},
        {"label": _("Company"), "fieldname": "company", "fieldtype": "Data", "width": 155},
        #{"label": _("Punchout"), "fieldname": "is_punchout", "fieldtype": "Check", "width": 75},
        #{"label": _("Hold Order"), "fieldname": "hold_order", "fieldtype": "Check", "width": 80},
        #{"label": _("Hold Inv."), "fieldname": "hold_invoice", "fieldtype": "Check", "width": 70},
        {"label": _("Creator"), "fieldname": "owner", "fieldtype": "Link", "options": "User", "width": 200},
        {"label": _("Item"), "fieldname": "item", "fieldtype": "Link", "options": "Item", "width": 50}
    ]


def get_data(filters):
    if not filters:
        return []
    conditions = ""

    if filters.get('from_barcode') and filters.get('to_barcode'):
        if filters.get('from_barcode').isnumeric() and filters.get('to_barcode').isnumeric():
            from_barcode = filters.get('from_barcode')
            to_barcode = filters.get('to_barcode')
            if len(from_barcode) != len(to_barcode):
                frappe.throw("From Barcode and To Barcode need to have the same length. Please use leading zeros if necessary.")
            barcode_list = ','.join(f'"{i:0{len(to_barcode)}d}"' for i in range(int(from_barcode), int(to_barcode) + 1))
            conditions += f"AND `tabSample`.`sequencing_label_id` IN ({barcode_list})"
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
            conditions += f"AND `tabSample`.`sequencing_label_id` IN ({barcode_list})"
    elif (filters.get('from_barcode') or filters.get('to_barcode')) and not conditions:
        return []
    elif filters.get('from_barcode') or filters.get('to_barcode'):
        return []

    sql_query = f"""
        SELECT `tabSales Order`.`name`,
            `tabSales Order`.`transaction_date` AS `date`,
            ROUND(`tabSales Order`.`total`, 2) AS `total`,
            `tabSales Order`.`currency`,
            `tabSample`.`sequencing_label_id`,
            `tabSales Order`.`contact_person`,
            `tabSales Order`.`customer`,
            `tabSales Order`.`customer_name`,
            `tabSales Order`.`web_order_id`,
            `tabSales Order`.`status`,
            `tabSales Order`.`product_type`,
            (SELECT COUNT(`tabSample Link`.`name`)
                FROM `tabSample Link`
                WHERE `tabSample Link`.`parent` = `tabSales Order`.`name`
            ) AS `sample_count`,
            `tabSales Order`.`company`,
            `tabSales Order`.`is_punchout`,
            `tabSales Order`.`hold_order`,
            `tabSales Order`.`hold_invoice`,
            `tabSales Order`.`owner`,
            (SELECT DISTINCT `tabSales Order Item`.`item_code`
                FROM `tabSales Order Item`
                WHERE `tabSales Order Item`.`parent` = `tabSales Order`.`name`
                LIMIT 1
            ) AS `item`
        FROM `tabSales Order`
        LEFT JOIN `tabSample Link` ON `tabSample Link`.`parent` = `tabSales Order`.`name`
        LEFT JOIN `tabSample` ON `tabSample Link`.`sample` = `tabSample`.`name`
        LEFT JOIN `tabSales Order Item` ON `tabSales Order Item`.`parent` = `tabSales Order`.`name`
        WHERE `tabSales Order`.`docstatus` = 1
            {conditions}
        -- GROUP BY `tabSales Order`.`name`
        ORDER BY `tabSales Order`.`transaction_date` DESC;
        """
    data = frappe.db.sql(sql_query, as_dict=True)
    return data


def execute(filters=None):
    columns = get_columns()
    data = get_data(filters)
    return columns, data
