# Copyright (c) 2013, Microsynth, libracore and contributors and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
from microsynth.microsynth.labels import print_oligo_order_labels


def execute(filters=None):
	columns = get_columns()
	data = get_data(filters)
	return columns, data

def get_columns():
	return [
        {"label": _("Sales Order"), "fieldname": "sales_order", "fieldtype": "Link", "options": "Sales Order", "width": 120},
		{"label": _("Deliver Note"), "fieldname": "delivery_note", "fieldtype": "Link", "options": "Delivery Note", "width": 120},
        {"label": _("Web ID"), "fieldname": "web_order_id", "fieldtype": "Data", "width": 70},
        {"label": _("Customer"), "fieldname": "customer", "fieldtype": "Link", "options": "Customer", "width": 70},        
        {"label": _("Customer name"), "fieldname": "customer_name", "fieldtype": "Data", "width": 180},
        {"label": _("Contact"), "fieldname": "contact", "fieldtype": "Link", "options": "Contact", "width": 60},
        {"label": _("Contact name"), "fieldname": "contact_name", "fieldtype": "Data", "width": 180},
        {"label": _("Order date"), "fieldname": "date", "fieldtype": "Date", "width": 80},
        {"label": _("Region"), "fieldname": "export_code", "fieldtype": "Data", "width": 60},
		{"label": _("Comment"), "fieldname": "comment", "fieldtype": "Data", "width": 100}
	]

@frappe.whitelist()
def get_data(filters=None):
	data = frappe.db.sql("""
		SELECT 
			`tabDelivery Note Item`.`parent` AS `delivery_note`, 
			`tabDelivery Note Item`.`against_sales_order` AS `sales_order`,
			`tabSales Order`.`web_order_id` AS `web_order_id`,
			`tabSales Order`.`customer` AS `customer`,
			`tabSales Order`.`customer_name` AS `customer_name`,
			`tabSales Order`.`contact_person` AS `contact`,
			`tabSales Order`.`contact_display` AS `contact_name`,
			`tabSales Order`.`transaction_date` AS `date`,
			`tabCountry`.`export_code` AS `export_code`,
			`tabSales Order`.`comment` AS `comment`
		FROM `tabDelivery Note Item`
		LEFT JOIN `tabSales Order` ON `tabSales Order`.`name` = `tabDelivery Note Item`.`against_sales_order`
		LEFT JOIN `tabAddress` ON `tabAddress`.`name` = `tabSales Order`.`shipping_address_name`
        LEFT JOIN `tabCountry` ON `tabCountry`.`name` = `tabAddress`.`country`
		WHERE 
			`tabSales Order`.`product_type` = "Oligos"
			AND `tabDelivery Note Item`.`docstatus` = 0
			AND `tabCountry`.`name` = 'Switzerland'
			AND `tabSales Order`.`label_printed_on` IS NULL
			AND `tabSales Order`.`hold_order` <> 1
			AND `tabDelivery Note Item`.`creation` > '2022-12-22'
		GROUP BY sales_order
		ORDER BY sales_order ASC;
	""", as_dict=True)
	
	return data

@frappe.whitelist()
def print_labels():    
    
    data = get_data(filters=None)
    orders = []

    for x in data:
        orders.append(x.sales_order)
    
    print_oligo_order_labels(orders)
    
    return