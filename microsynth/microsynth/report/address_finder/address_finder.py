# Copyright (c) 2022, Microsynth, libracore and contributors and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _

def execute(filters=None):
	columns, data = get_columns(filters), get_data(filters)
	return columns, data

def get_columns(filters):
	return [		
		{"label": _("Customer ID"), "fieldname": "customer_id", "fieldtype": "Data", "width": 75},
		{"label": _("Customer"), "fieldname": "customer", "fieldtype": "Data", "width": 75},
		{"label": _("Contact ID"), "fieldname": "contact_id", "fieldtype": "Data", "width": 75},
		{"label": _("First Name"), "fieldname": "first_name", "fieldtype": "Data", "width": 60},
		{"label": _("Last Name"), "fieldname": "last_name", "fieldtype": "Data", "width": 60},
		{"label": _("Institute"), "fieldname": "institute", "fieldtype": "Data", "width": 75},
		{"label": _("Departement"), "fieldname": "departement", "fieldtype": "Data", "width": 75},
		{"label": _("Group Leader"), "fieldname": "group_leader", "fieldtype": "Data", "width": 50},
		{"label": _("Institute key"), "fieldname": "institute_key", "fieldtype": "Data", "width": 50},
		{"label": _("City"), "fieldname": "city", "fieldtype": "Data", "width": 50},
		{"label": _("Street"), "fieldname": "street", "fieldtype": "Data", "width": 50},
	]

def get_data(filters):
	data = []

	sql_query = """SELECT
		`tabCustomer`.`name` AS `customer_id`,
		`tabCustomer`.`customer_name` AS `customer`,
		`tabContact`.`name` AS `contact_id`,
		`tabContact`.`first_name` AS `first_name`,
		`tabContact`.`last_name` AS `last_name`,
		`tabContact`.`email_id` AS `email`,
		`tabContact`.`institute` AS `institute`,
		`tabContact`.`department` AS `department`,
		`tabContact`.`group_leader` AS `group_leader`,
		`tabContact`.`institute_key` AS `institute_key`,
		`tabAddress`.`address_line1` AS `address_line1`,		
		`tabAddress`.`city` AS `city`
		FROM `tabContact`
        LEFT JOIN `tabDynamic Link` AS `tDLA` ON `tDLA`.`parent` = `tabContact`.`name` 
                                              AND `tDLA`.`parenttype`  = "Contact" 
                                              AND `tDLA`.`link_doctype` = "Customer"
        LEFT JOIN `tabCustomer` ON `tabCustomer`.`name` = `tDLA`.`link_name` 
        LEFT JOIN `tabAddress` ON `tabContact`.`address` = `tabAddress`.`name`
        
		WHERE `tabCustomer`.`customer_name` LIKE '%Micros%'	
	"""

	fetched_data = frappe.db.sql(sql_query, as_dict = True)

	for d in fetched_data:
		entry = {
			"customer_id": d.customer_id,
			"customer": d.customer,
			"contact_id": d.contact_id,
			"first_name": d.first_name,
			"last_name": d.last_name,
			"institute": d.institute,
			"department": d.department,
			"group_leader": d.group_leader,
			"institute_key": d.institute_key,
			"city": d.city,
			"street": d.address_line1
		}
		data.append(entry)

	data.append(entry)

	return data
