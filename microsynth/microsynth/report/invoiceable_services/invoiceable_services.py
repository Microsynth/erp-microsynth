# Copyright (c) 2022, Microsynth, libracore and contributors and contributors
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
        {"label": _("Date"), "fieldname": "date", "fieldtype": "Date", "width": 120},
        {"label": _("Delivery Note"), "fieldname": "delivery_note", "fieldtype": "Link", "options": "Delivery Note", "width": 120},
        {"label": _("Customer"), "fieldname": "customer", "fieldtype": "Link", "options": "Customer", "width": 120},
        {"label": _("Customer name"), "fieldname": "customer_name", "fieldtype": "Data", "width": 200},
        {"label": _("Invoice type"), "fieldname": "invoice_type", "fieldtype": "Data", "width": 120},
        {"label": _("Collective invoice"), "fieldname": "collective_invoice", "fieldtype": "Check", "width": 200},
        {"label": _("PO number"), "fieldname": "po_no", "fieldtype": "Data", "width": 80},
        {"label": _("Region"), "fieldname": "region", "fieldtype": "Data", "width": 80},
        {"label": _("Shipment type"), "fieldname": "shipment_type", "fieldtype": "Data", "width": 80}
    ]

def get_data(filters=None):
    invoiceable_services = frappe.db.sql("""
        SELECT 
            `tabDelivery Note`.`posting_datre` AS `date`,
            `tabDelivery Note`.`name` AS `delivery_note`,
            `tabDelivery Note`.`customer` AS `customer`,
            `tabDelivery Note`.`customer_name` AS `customer_name`,
            `tabCustomer`.`invoice_type` AS `invoice_type`,
            `tabCustomer`.`collective_invoice` AS `collective_invoice`,
            `tabDelivery Note`.`po_no` AS `po_no`,
            
        FROM `tabDelivery Note`
        LEFT JOIN `tabCustomer` ON
            (`tabDelivery Note`.`customer` = `tabCustomer`.`name`)
        LEFT JOIN `tabAddress` ON
            (`tabDelivery Note`.`shipping_address` = `tabAddress`.`name`)
        WHERE 
            tabDelivery Note.`docstatus` = 1
        ORDER BY `tabDelivery Note`.`customer` ASC;
    """, as_dict=True)
    
    return invoiceable_services
