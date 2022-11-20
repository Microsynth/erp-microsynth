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
		{"label": _("Customer"), "fieldname": "customer", "fieldtype": "Data", "width": 75},
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

	entry = {
		"customer": "ETHZ",
		"first_name":"Peter",
		"last_name":"Musterkerl",
		"institute":"Biochemistry",
		"departement":"Chemistry & Biology",
		"group_leader":"Müller",
		"institute_key":"CH_01_01",
		"city":"Zürich",
		"street":"Langstrasse"
	}

	data.append(entry)

	return data
