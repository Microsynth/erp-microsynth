# -*- coding: utf-8 -*-
# Copyright (c) 2024, Microsynth, libracore and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document
from frappe.desk.form.assign_to import add, clear
from frappe.utils.data import today

class QMAction(Document):
	pass


@frappe.whitelist()
def create_action(title, responsible_person, dt, dn, due_date, type, description):
    action = frappe.get_doc(
        {
            'doctype': 'QM Action',
            'title': title,
            'responsible_person': responsible_person, 
            'document_type': dt,
            'document_name': dn,
            'initiation_date': today(),
            'due_date': due_date,
            'type': type,
            'description': description,
            'status': 'Created'
        })

    action.save(ignore_permissions = True)
    frappe.db.commit()

    # create assignment to user
    assign(action.name, responsible_person)

    return action.name


@frappe.whitelist()
def assign(doc, responsible_person):
    clear("QM Action", doc)
    add({
        'doctype': "QM Action",
        'name': doc,
        'assign_to': responsible_person
    })