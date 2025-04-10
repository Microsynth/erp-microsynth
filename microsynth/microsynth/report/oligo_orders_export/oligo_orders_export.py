# Copyright (c) 2013, Microsynth, libracore and contributors and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
from microsynth.microsynth.labels import print_oligo_order_labels, create_ups_batch_file


def execute(filters=None):
    columns = get_columns()
    data = get_data(filters)
    return columns, data

def get_columns():
    return [
        {"label": _("Sales Order"), "fieldname": "sales_order", "fieldtype": "Link", "options": "Sales Order", "width": 120},
        {"label": _("Web ID"), "fieldname": "web_order_id", "fieldtype": "Data", "width": 70},
        {"label": _("Punchout"), "fieldname": "is_punchout", "fieldtype": "Check", "width": 55},
        {"label": _("Customer"), "fieldname": "customer", "fieldtype": "Link", "options": "Customer", "width": 70},
        {"label": _("Customer name"), "fieldname": "customer_name", "fieldtype": "Data", "width": 180},
        {"label": _("Contact"), "fieldname": "contact", "fieldtype": "Link", "options": "Contact", "width": 60},
        {"label": _("Contact name"), "fieldname": "contact_name", "fieldtype": "Data", "width": 150},
        {"label": _("Date"), "fieldname": "date", "fieldtype": "Date", "width": 80},
        {"label": _("Region"), "fieldname": "export_code", "fieldtype": "Data", "width": 60},
        {"label": _("Tax ID"), "fieldname": "tax_id", "fieldtype": "Data", "width": 120},
        {"label": _("Item"), "fieldname": "shipping_item", "fieldtype": "Data", "width": 45},
        {"label": _("Description"), "fieldname": "shipping_description", "fieldtype": "Data", "width": 200},
        {"label": _("Comment"), "fieldname": "comment", "fieldtype": "Data", "width": 200}
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
            `tabSales Order`.`contact_person` AS `contact`,
            `tabSales Order`.`contact_display` AS `contact_name`,
            `tabSales Order`.`transaction_date` AS `date`,
            `tabCountry`.`export_code` AS `export_code`,
            `tabCustomer`.`tax_id` AS `tax_id`,
            `tabSales Order`.`comment` AS `comment`,
            `tabSales Order Item`.`item_code` AS `shipping_item`,
            `tabSales Order Item`.`description` AS `shipping_description`
        FROM `tabSales Order`
        LEFT JOIN `tabAddress` ON `tabAddress`.`name` = `tabSales Order`.`shipping_address_name`
        LEFT JOIN `tabCountry` ON `tabCountry`.`name` = `tabAddress`.`country`
        LEFT JOIN `tabSales Order Item` ON `tabSales Order Item`.`parent` = `tabSales Order`.`name`
        LEFT JOIN `tabCustomer` ON `tabCustomer`.`name` = `tabSales Order`.`customer`
        WHERE 
            `tabSales Order`.`product_type` = "Oligos"
            AND `tabSales Order`.`company` = "Microsynth AG"
            AND `tabSales Order`.`docstatus` = 1
            AND `tabSales Order`.`status` NOT IN ('Closed', 'Completed')
            AND `tabCountry`.`name` <> 'Switzerland'
            AND `tabSales Order`.`label_printed_on` IS NULL
            AND `tabSales Order`.`hold_order` <> 1
            AND `tabSales Order Item`.`item_group` = 'Shipping'
        ORDER BY 
            `tabSales Order Item`.`description`,
            `tabCountry`.`name`,
            `tabSales Order`.`transaction_date` ASC;
    """, as_dict=True)
    
    return open_oligo_orders


@frappe.whitelist()
def print_labels():    
    data = get_data(filters=None)
    orders = []

    for x in data:
        orders.append(x.sales_order)
    
    print_oligo_order_labels(orders)
    return


@frappe.whitelist()
def create_batch_file():    
    data = get_data(filters=None)
    orders = []

    for x in data:
        orders.append(x.sales_order)
    
    create_ups_batch_file(orders)
    return