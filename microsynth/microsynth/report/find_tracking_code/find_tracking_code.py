# Copyright (c) 2023, Microsynth, libracore and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _


def get_columns(filters):
    return [
        {"label": _("Contact"), "fieldname": "contact", "fieldtype": "Link", "options": "Contact", "width": 75 },
        {"label": _("First Name"), "fieldname": "first_name", "fieldtype": "Data", "width": 100 },
        {"label": _("Last Name"), "fieldname": "last_name", "fieldtype": "Data", "width": 100 },
        {"label": _("Customer"), "fieldname": "customer", "fieldtype": "Link", "options": "Customer", "width": 75 },
        {"label": _("Customer Name"), "fieldname": "customer_name", "fieldtype": "Data", "width": 200 },
        {"label": _("Sales Order"), "fieldname": "sales_order", "fieldtype": "Link", "options": "Sales Order", "width": 120 },
        {"label": _("Web Order ID"), "fieldname": "web_order_id", "fieldtype": "Data", "width": 90 },
        {"label": _("Delivery Note"), "fieldname": "delivery_note", "fieldtype": "Link", "options": "Delivery Note", "width": 125 },
        {"label": _("Tracking Code"), "fieldname": "tracking_code", "fieldtype": "Data", "width": 175 },
        {"label": _("Tracking URL"), "fieldname": "tracking_url", "fieldtype": "HTML", "width": 500 },
    ]


def get_data(filters):
    """
    Get raw Sales Order records for find tracking code report.
    """
    contact_condition = customer_condition = sales_order_condition = web_order_id_condition = delivery_note_condition = ""
    hasFilters = False

    if filters and filters.get('contact'):
        contact_condition = f"AND `tabSales Order`.`contact_person` = '{filters.get('contact')}' "
        hasFilters = True
    if filters and filters.get('customer'):
        customer_condition = f"AND `tabSales Order`.`customer` = '{filters.get('customer')}' "
        hasFilters = True
    if filters and filters.get('sales_order'):
        sales_order_condition = f"AND `tabSales Order`.`name` = '{filters.get('sales_order')}' "
        hasFilters = True
    if filters and filters.get('web_order_id'):
        web_order_id_condition = f"AND `tabSales Order`.`web_order_id` = '{filters.get('web_order_id')}' "
        hasFilters = True
    if filters and filters.get('delivery_note'):
        delivery_note_condition = f"AND `tabDelivery Note Item`.`parent` = '{filters.get('delivery_note')}' "
        hasFilters = True

    data = dict()

    if hasFilters:
        query = """
                SELECT DISTINCT
                    `tabSales Order`.`contact_person` AS `contact`,
                    `tabContact`.`first_name` AS `first_name`,
                    `tabContact`.`last_name` AS `last_name`,
                    `tabSales Order`.`customer` AS `customer`,
                    `tabCustomer`.`customer_name` AS `customer_name`,
                    `tabSales Order`.`name` AS `sales_order`,
                    `tabSales Order`.`web_order_id` AS `web_order_id`,
                    `tabDelivery Note Item`.`parent` AS `delivery_note`,
                    `tabTracking Code`.`tracking_code` AS `tracking_code`,
                    CONCAT('<a href="', `tabTracking Code`.`tracking_url`, '">', `tabTracking Code`.`tracking_url`, '</a>') AS `tracking_url`
                FROM `tabSales Order`
                LEFT JOIN `tabContact` ON `tabContact`.`name` = `tabSales Order`.`contact_person`
                LEFT JOIN `tabCustomer` ON `tabCustomer`.`name` = `tabSales Order`.`customer`
                LEFT JOIN `tabTracking Code` ON `tabTracking Code`.`sales_order` = `tabSales Order`.`name`
                LEFT JOIN `tabDelivery Note Item` ON `tabDelivery Note Item`.`against_sales_order` = `tabSales Order`.`name`
                WHERE TRUE
                    {contact_condition}
                    {customer_condition}
                    {sales_order_condition}
                    {web_order_id_condition}
                    {delivery_note_condition}
            """.format(contact_condition=contact_condition, customer_condition=customer_condition,
                    sales_order_condition=sales_order_condition, web_order_id_condition=web_order_id_condition,
                    delivery_note_condition=delivery_note_condition)

        data = frappe.db.sql(query, as_dict=True)

    return data


def execute(filters=None):
    columns, data = get_columns(filters), get_data(filters)
    return columns, data
