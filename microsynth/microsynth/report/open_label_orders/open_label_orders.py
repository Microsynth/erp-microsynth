# Copyright (c) 2022, Microsynth, libracore and contributors and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
from erpnext.selling.doctype.sales_order.sales_order import make_delivery_note

def execute(filters=None):
    columns = get_columns()
    data = get_data(filters)
    return columns, data

def get_columns():
    return [
        {"label": _("Sales Order"), "fieldname": "sales_order", "fieldtype": "Link", "options": "Sales Order", "width": 120},
        {"label": _("Customer"), "fieldname": "customer", "fieldtype": "Link", "options": "Customer", "width": 120},
        {"label": _("Customer name"), "fieldname": "customer_name", "fieldtype": "Data", "width": 200},
        {"label": _("Contact"), "fieldname": "contact", "fieldtype": "Link", "options": "Contact", "width": 120},
        {"label": _("Contact name"), "fieldname": "contact_name", "fieldtype": "Data", "width": 200},
        {"label": _("Date"), "fieldname": "date", "fieldtype": "Date", "width": 80},
        {"label": _("Item"), "fieldname": "item_code", "fieldtype": "Link", "options": "Item", "width": 200},
        {"label": _("Qty"), "fieldname": "qty", "fieldtype": "Float", "width": 80},
        {"label": _("Range"), "fieldname": "range", "fieldtype": "Data", "width": 80}
    ]

@frappe.whitelist()
def get_data(filters=None):
    open_label_orders = frappe.db.sql("""
        SELECT 
            `tabSales Order`.`name` AS `sales_order`,
            `tabSales Order`.`customer` AS `customer`,
            `tabSales Order`.`customer_name` AS `customer_name`,
            `tabSales Order`.`contact_person` AS `contact`,
            `tabSales Order`.`contact_display` AS `contact_name`,
            `tabSales Order`.`transaction_date` AS `date`,
            `tabSales Order Item`.`item_code` AS `item_code`,
            `tabSales Order Item`.`item_name` AS `item_name`,
            `tabSales Order Item`.`qty` AS `qty`,
            `tabLabel Range`.`range` AS `range`
        FROM `tabSales Order`
        LEFT JOIN `tabSequencing Label` ON
            (`tabSequencing Label`.`sales_order` = `tabSales Order`.`name`)
        LEFT JOIN `tabSales Order Item` ON
            (`tabSales Order Item`.`parent` = `tabSales Order`.`name` AND `tabSales Order Item`.`idx` = 1)
        LEFT JOIN `tabLabel Range` ON
            (`tabLabel Range`.`item_code` = `tabSales Order Item`.`item_code`)
        WHERE 
            `tabSales Order`.`product_type` = "Labels"
            AND `tabSales Order`.`docstatus` = 1
            AND `tabSales Order`.`transaction_date` >= DATE_SUB(NOW(), INTERVAL 1 YEAR)
            AND `tabSequencing Label`.`name` IS NULL
        ORDER BY `tabSales Order`.`transaction_date` ASC;
    """, as_dict=True)
    
    return open_label_orders
    
@frappe.whitelist()
def pick_labels(sales_order, from_barcode, to_barcode):
    # create sequencing labels
    # TODO
    
    # create delivery note
    dn_content = make_delivery_note(sales_order)
    dn = frappe.get_doc(dn_content)
    dn.insert()
    frappe.db.commit()
    
    # return print format
    return dn.name
