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
        {"label": _("Sales Order"), "fieldname": "sales_order", "fieldtype": "Link", "options": "Sales Order", "width": 120},
        {"label": _("Customer"), "fieldname": "customer", "fieldtype": "Link", "options": "Customer", "width": 120},
        {"label": _("Customer name"), "fieldname": "customer_name", "fieldtype": "Data", "width": 200},
        {"label": _("Contact"), "fieldname": "contact", "fieldtype": "Link", "options": "Contact", "width": 120},
        {"label": _("Contact name"), "fieldname": "contact_name", "fieldtype": "Data", "width": 200},
        {"label": _("Date"), "fieldname": "date", "fieldtype": "Date", "width": 80}
    ]
    
def get_data(filters):
    open_label_orders = frappe.db.sql("""
        SELECT 
            `tabSales Order`.`name` AS `sales_order`,
            `tabSales Order`.`customer` AS `customer`,
            `tabSales Order`.`customer_name` AS `customer_name`,
            `tabSales Order`.`contact_person` AS `contact`,
            `tabSales Order`.`contact_display` AS `contact_name`,
            `tabSales Order`.`transaction_date` AS `date`
        FROM `tabSales Order`
        LEFT JOIN `tabSequencing Label` ON
            (`tabSequencing Label`.`sales_order` = `tabSales Order`.`name`)
        WHERE 
            `tabSales Order`.`product_type` = "Labels"
            AND `tabSales Order`.`docstatus` = 1
            AND `tabSales Order`.`transaction_date` >= DATE_SUB(NOW(), INTERVAL 1 YEAR)
            AND `tabSequencing Label`.`name` IS NULL;
    """, as_dict=True)
    
    return open_label_orders
            
