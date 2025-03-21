# Copyright (c) 2025, Microsynth
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
#from microsynth.microsynth.shipping import get_shipping_items_with_tracking


def get_columns(filters):
    return [
        {"label": _("Sales Order"), "fieldname": "sales_order", "fieldtype": "Link", "options": "Sales Order", "width": 125 },
        {"label": _("Web Order ID"), "fieldname": "web_order_id", "fieldtype": "Data", "width": 90 },
        {"label": _("Date"), "fieldname": "transaction_date", "fieldtype": "Date", "width": 80 },
        {"label": _("Customer"), "fieldname": "customer", "fieldtype": "Link", "options": "Customer", "width": 80 },
        {"label": _("Customer Name"), "fieldname": "customer_name", "fieldtype": "Data", "width": 275 },
        {"label": _("Product Type"), "fieldname": "product_type", "fieldtype": "Data", "width": 100 },
        {"label": _("Net Total"), "fieldname": "net_total", "fieldtype": "Currency", "options": "currency", "width": 100},
        {"label": _("Shipping Item"), "fieldname": "item_code", "fieldtype": "Link", "options": "Item", "width": 375, "align": "left" },
        #{"label": _("Shipping Item Name"), "fieldname": "item_name", "fieldtype": "Data", "width": 170 },
        {"label": _("Shipping Label printed"), "fieldname": "label_printed_on", "fieldtype": "Date", "width": 145 },
        {"label": _("Delivery Note"), "fieldname": "delivery_note", "fieldtype": "Link", "options": "Delivery Note", "width": 125 }
    ]


def get_data(filters):
    conditions = ""
    if filters.get('item_code'):
        conditions += f" AND `tabSales Order Item`.`item_code` = '{filters.get('item_code')}' "

    #tracking_shipping_items = get_shipping_items_with_tracking()

    query = f"""
        SELECT DISTINCT
            `tabSales Order`.`name` AS `sales_order`,
            `tabSales Order`.`web_order_id`,
            `tabSales Order`.`transaction_date`,
            `tabSales Order`.`customer`,
            `tabSales Order`.`customer_name`,
            `tabSales Order`.`product_type`,
            `tabSales Order`.`net_total`,
            `tabSales Order`.`currency`,
            `tabSales Order Item`.`item_code`,
            `tabSales Order Item`.`item_name`,
            `tabSales Order`.`label_printed_on`,
            `tabDelivery Note`.`name` AS `delivery_note`
        FROM `tabSales Order`
        LEFT JOIN `tabSales Order Item` ON `tabSales Order Item`.`parent` = `tabSales Order`.`name`
        LEFT JOIN `tabTracking Code` ON `tabTracking Code`.`sales_order` = `tabSales Order`.`name`
        LEFT JOIN `tabDelivery Note Item` ON `tabDelivery Note Item`.`against_sales_order` = `tabSales Order`.`name`
        LEFT JOIN `tabDelivery Note` ON `tabDelivery Note`.`name` = `tabDelivery Note Item`.`parent`
        WHERE `tabSales Order`.`docstatus` = 1
            AND `tabSales Order`.`status` != 'Closed'
            AND `tabSales Order`.`transaction_date` >= DATE('{filters.get('from_date')}')
            AND `tabSales Order Item`.`item_name` LIKE '%Track%'
            AND `tabTracking Code`.`sales_order` IS NULL
            AND `tabDelivery Note`.`docstatus` != 2
            {conditions}
        ORDER BY `tabSales Order`.`transaction_date` DESC;
        """
    data = frappe.db.sql(query, as_dict=True)
    return data


def execute(filters=None):
    columns, data = get_columns(filters), get_data(filters)
    return columns, data
