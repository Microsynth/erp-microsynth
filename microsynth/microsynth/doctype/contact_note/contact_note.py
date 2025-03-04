# -*- coding: utf-8 -*-
# Copyright (c) 2023, Microsynth, libracore and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
from datetime import datetime
import frappe
from frappe.model.document import Document
from frappe.utils import get_url_to_form


class ContactNote(Document):
    pass


@frappe.whitelist()
def create_new_follow_up(quotation, contact_person):
    new_doc = frappe.get_doc({
        'doctype': 'Contact Note',
        'contact_person': contact_person,
        'prevdoc_docname': quotation,
        'date': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })
    new_doc.flags.ignore_mandatory = True
    new_doc.insert()
    frappe.db.commit()
    return {'name': new_doc.name, 'url': get_url_to_form("Contact Note", new_doc.name)}


@frappe.whitelist()
def get_follow_ups(quotation):
    contact_notes = frappe.get_all("Contact Note", filters={'prevdoc_docname': quotation}, fields=['name', 'date'])
    for cn in contact_notes:
        cn['url'] = get_url_to_form("Contact Note", cn['name'])
    return contact_notes
