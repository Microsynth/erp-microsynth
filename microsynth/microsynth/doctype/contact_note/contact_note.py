# -*- coding: utf-8 -*-
# Copyright (c) 2023, Microsynth, libracore and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
from datetime import datetime
import frappe
from frappe.model.document import Document
from frappe.utils import get_url_to_form
from frappe.model.mapper import get_mapped_doc


class ContactNote(Document):
    pass


@frappe.whitelist()
def create_new_follow_up(quotation):
    doc = get_mapped_doc("Quotation",
                         quotation,
                         {
                            "Quotation": {
			                    "doctype": "Contact Note",
				                "field_map": {
                                    "contact_person": "contact_person"
                                }
		                    }
                         },
                         None)
    doc.date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    doc.prevdoc_doctype = 'Quotation'
    doc.prevdoc_docname = quotation
    return doc


@frappe.whitelist()
def get_follow_ups(quotation):
    contact_notes = frappe.get_all("Contact Note", filters={'prevdoc_docname': quotation}, fields=['name', 'date'])
    for cn in contact_notes:
        cn['url'] = get_url_to_form("Contact Note", cn['name'])
    return contact_notes
