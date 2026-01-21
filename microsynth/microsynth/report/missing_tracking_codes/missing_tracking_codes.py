# Copyright (c) 2025, Microsynth
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
from microsynth.microsynth.shipping import get_shipping_items_with_tracking
from microsynth.microsynth.utils import get_sql_list


def get_columns(filters):
    return [
        {"label": _("Sales Order"), "fieldname": "sales_order", "fieldtype": "Link", "options": "Sales Order", "width": 125 },
        {"label": _("Order Status"), "fieldname": "so_status", "fieldtype": "Data", "width": 110 },
        {"label": _("Web Order ID"), "fieldname": "web_order_id_html", "fieldtype": "Data", "width": 90 },
        {"label": _("Date"), "fieldname": "transaction_date", "fieldtype": "Date", "width": 80 },
        {"label": _("Customer"), "fieldname": "customer", "fieldtype": "Link", "options": "Customer", "width": 80 },
        {"label": _("Customer Name"), "fieldname": "customer_name", "fieldtype": "Data", "width": 225 },
        {"label": _("Product Type"), "fieldname": "product_type", "fieldtype": "Data", "width": 95 },
        {"label": _("Net Total"), "fieldname": "net_total", "fieldtype": "Currency", "options": "currency", "width": 100},
        {"label": _("Shipping Item"), "fieldname": "item_code", "fieldtype": "Link", "options": "Item", "width": 370, "align": "left" },
        #{"label": _("Shipping Item Name"), "fieldname": "item_name", "fieldtype": "Data", "width": 170 },
        {"label": _("Shipping Label printed"), "fieldname": "label_printed_on", "fieldtype": "Date", "width": 145 },
        {"label": _("Delivery Note"), "fieldname": "delivery_note", "fieldtype": "Link", "options": "Delivery Note", "width": 125 },
        {"label": _("DN Status"), "fieldname": "dn_status", "fieldtype": "Data", "width": 80 }
    ]


def get_data(filters):
    params = {
        "from_date": filters.get("from_date") or "2000-01-01"
    }
    if filters.get("item_code"):
        item_condition = " AND `tabSales Order Item`.`item_code` = %(item_code)s"
        params["item_code"] = filters.get("item_code")
    else:
        item_condition = ""

    tracking_shipping_items = get_shipping_items_with_tracking()
    placeholders = ", ".join([f"%(item_{i})s" for i in range(len(tracking_shipping_items))])
    for i, code in enumerate(tracking_shipping_items):
        params[f"item_{i}"] = code

    query = f"""
        SELECT DISTINCT
            `tabSales Order`.`name` AS `sales_order`,
            `tabSales Order`.`status` AS `so_status`,
            `tabSales Order`.`web_order_id`,
            CASE
                WHEN `tabSales Order`.`web_order_id` IS NOT NULL
                    AND `tabSales Order`.`web_order_id` != ''
                THEN CONCAT(
                    '<a href="/desk#query-report/Sales Document Overview?web_order_id=',
                    `tabSales Order`.`web_order_id`,
                    '" target="_blank">',
                    `tabSales Order`.`web_order_id`,
                    '</a>'
                )
                ELSE ''
            END AS `web_order_id_html`,
            `tabSales Order`.`transaction_date`,
            `tabSales Order`.`customer`,
            `tabSales Order`.`customer_name`,
            `tabSales Order`.`product_type`,
            `tabSales Order`.`net_total`,
            `tabSales Order`.`currency`,
            `tabSales Order Item`.`item_code`,
            `tabSales Order Item`.`item_name`,
            `tabSales Order`.`label_printed_on`,
            `tabDelivery Note`.`name` AS `delivery_note`,
            `tabDelivery Note`.`status` AS `dn_status`
        FROM `tabSales Order`

        INNER JOIN (
            SELECT
                `tabSales Order Item`.`parent`,
                `tabSales Order Item`.`item_code`,
                `tabSales Order Item`.`item_name`
            FROM `tabSales Order Item`
            WHERE
                `tabSales Order Item`.`item_code` IN ({placeholders})
                AND `tabSales Order Item`.`item_code` NOT IN ('1105', '1140')
        ) AS `tabSales Order Item`
            ON `tabSales Order Item`.`parent` = `tabSales Order`.`name`
        LEFT JOIN `tabTracking Code`
            ON `tabTracking Code`.`sales_order` = `tabSales Order`.`name`
        LEFT JOIN `tabDelivery Note Item`
            ON `tabDelivery Note Item`.`against_sales_order` = `tabSales Order`.`name`
        LEFT JOIN `tabDelivery Note`
            ON `tabDelivery Note`.`name` = `tabDelivery Note Item`.`parent`
        WHERE
            `tabSales Order`.`docstatus` = 1
            AND `tabSales Order`.`status` != 'Closed'
            AND `tabSales Order`.`transaction_date` >= DATE(%(from_date)s)
            AND (
                `tabSales Order Item`.`item_code` NOT IN ('1106', '1115')
                OR `tabSales Order`.`transaction_date` > DATE('2025-08-27')
            )
            AND `tabTracking Code`.`sales_order` IS NULL
            AND `tabDelivery Note`.`docstatus` != 2
            {item_condition}
        ORDER BY `tabSales Order`.`transaction_date` DESC
    """
    return frappe.db.sql(query, values=params, as_dict=True)


def execute(filters=None):
    columns, data = get_columns(filters), get_data(filters)
    return columns, data
