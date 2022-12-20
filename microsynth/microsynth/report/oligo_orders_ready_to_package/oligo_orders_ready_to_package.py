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
        {"label": _("Delivery Note"), "fieldname": "delivery_note", "fieldtype": "Link", "options": "Delivery Note", "width": 120},
        {"label": _("Web ID"), "fieldname": "web_order_id", "fieldtype": "Data", "width": 80},
		{"label": _("Customer"), "fieldname": "customer", "fieldtype": "Link", "options": "Customer", "width": 80},
        {"label": _("Customer name"), "fieldname": "customer_name", "fieldtype": "Data", "width": 180},
        {"label": _("Contact"), "fieldname": "contact", "fieldtype": "Link", "options": "Contact", "width": 60},
        {"label": _("Contact name"), "fieldname": "contact_name", "fieldtype": "Data", "width": 180},
        {"label": _("Date"), "fieldname": "date", "fieldtype": "Date", "width": 80},
        {"label": _("Region"), "fieldname": "export_code", "fieldtype": "Data", "width": 60},
		{"label": _("Comment"), "fieldname": "comment", "fieldtype": "Data", "width": 100}
	]

def get_data(filters=None):
	data = frappe.db.sql("""
		SELECT
			`tabDelivery Note`.`name` as `delivery_note`,
			`tabDelivery Note`.`web_order_id` as `web_order_id`,
			`tabCountry`.`export_code` AS `export_code`,
			`tabDelivery Note`.`posting_date` as `date`,
			`tabDelivery Note`.`customer` AS `customer`,
			`tabDelivery Note`.`customer_name` as `customer_name`,
			`tabDelivery Note`.`contact_person` AS `contact`,
            `tabDelivery Note`.`contact_display` AS `contact_name`

		FROM `tabDelivery Note`
		LEFT JOIN `tabAddress` ON `tabAddress`.`name` = `tabDelivery Note`.`shipping_address_name`
        LEFT JOIN `tabCountry` ON `tabCountry`.`name` = `tabAddress`.`country`
		WHERE 
			`tabDelivery Note`.`product_type` = "Oligos"
			AND `tabDelivery Note`.`docstatus` = 1
			AND `tabCountry`.`name` = 'Switzerland'	
		ORDER BY `tabDelivery Note`.`web_order_id` ASC;
	""", as_dict=True)
	
	
	
	return data