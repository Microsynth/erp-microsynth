# -*- coding: utf-8 -*-
# Copyright (c) 2023, Microsynth, libracore and contributors and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document
from frappe.utils import cint, get_url_to_form
from datetime import date

class CustomsDeclaration(Document):
	pass

@frappe.whitelist()
def create_customs_declaration():
	cd = frappe.get_doc({
		'doctype':'Customs Declaration',
		'company': frappe.defaults.get_global_default('company'),
		'date': date.today()
		})	
	cd.insert()
	frappe.db.commit()
	return get_url_to_form("Customs Declaration", cd.name)
