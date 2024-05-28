# Copyright (c) 2013, Microsynth, libracore and contributors and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _

def execute(filters=None):
    columns = get_columns()
    data = get_data(filters)
    return columns, data

def get_columns():
    return [
        {"label": _("Sales Order"), "fieldname": "sales_order", "fieldtype": "Link", "options": "Sales Order", "width": 125},
        {"label": _("Web Order ID"), "fieldname": "web_order_id", "fieldtype": "Data", "width": 90},
        {"label": _("Punchout"), "fieldname": "is_punchout", "fieldtype": "Check", "width": 55},
        {"label": _("Customer"), "fieldname": "customer", "fieldtype": "Link", "options": "Customer", "width": 75},
        {"label": _("Customer name"), "fieldname": "customer_name", "fieldtype": "Data", "width": 180},
        {"label": _("Invoicing Method"), "fieldname": "invoicing_method", "fieldtype": "Data", "width": 120},
        {"label": _("Contact"), "fieldname": "contact", "fieldtype": "Link", "options": "Contact", "width": 70},
        {"label": _("Contact name"), "fieldname": "contact_name", "fieldtype": "Data", "width": 150},
        {"label": _("Date"), "fieldname": "date", "fieldtype": "Date", "width": 80},
        {"label": _("Comment"), "fieldname": "comment", "fieldtype": "Data", "width": 600}
    ]

@frappe.whitelist()
def get_data(filters=None):
    open_oligo_orders = frappe.db.sql("""
        SELECT
            `tabSales Order`.`name` AS `sales_order`,
            `tabSales Order`.`web_order_id` AS `web_order_id`,
            `tabSales Order`.`is_punchout` AS `is_punchout`,
            `tabSales Order`.`customer` AS `customer`,
            `tabSales Order`.`customer_name` AS `customer_name`,
            `tabCustomer`.`invoicing_method` AS `invoicing_method`,
            `tabSales Order`.`contact_person` AS `contact`,
            `tabSales Order`.`contact_display` AS `contact_name`,
            `tabSales Order`.`transaction_date` AS `date`,
            `tabCountry`.`export_code` AS `export_code`,
            `tabSales Order`.`comment` AS `comment`
        FROM `tabSales Order`
        LEFT JOIN `tabAddress` ON `tabAddress`.`name` = `tabSales Order`.`shipping_address_name`
        LEFT JOIN `tabCountry` ON `tabCountry`.`name` = `tabAddress`.`country`
        LEFT JOIN `tabCustomer` ON `tabCustomer`.`name` = `tabSales Order`.`customer`
        WHERE
            `tabSales Order`.`docstatus` = 1
            AND `tabSales Order`.`hold_order` = 1
            AND `tabSales Order`.`transaction_date` > '2022-12-22'
            AND ((NOT `tabCustomer`.`invoicing_method` = 'Stripe Prepayment')
                 OR (`tabSales Order`.`comment` IS NOT NULL))
        ORDER BY
            `tabSales Order`.`transaction_date` DESC;
    """, as_dict=True)
    
    return open_oligo_orders