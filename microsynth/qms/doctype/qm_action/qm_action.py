# -*- coding: utf-8 -*-
# Copyright (c) 2024, Microsynth, libracore and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document
from frappe.desk.form.assign_to import add, clear
from frappe.utils.data import today
from microsynth.microsynth.utils import user_has_role


class QMAction(Document):
	pass


@frappe.whitelist()
def create_action(title, responsible_person, dt, dn, qm_process, due_date, type, description):
    action = frappe.get_doc(
        {
            'doctype': 'QM Action',
            'title': title,
            'responsible_person': responsible_person, 
            'document_type': dt,
            'document_name': dn,
            'qm_process': qm_process,
            'initiation_date': today(),
            'due_date': due_date,
            'type': type,
            'description': description,
            'status': 'Created'
        })
    action.save(ignore_permissions = True)
    action.submit()
    frappe.db.commit()

    # create assignment to user
    assign(action.name, responsible_person)

    return action.name


@frappe.whitelist()
def set_created(doc, user):
    # pull selected document
    action = frappe.get_doc("QM Action", doc)
    action.submit()
    frappe.db.commit()
    update_status(action.name, "Created")


@frappe.whitelist()
def set_status(doc, user, status):
    responsible_person = frappe.get_value("QM Action", doc, "responsible_person")
    if not (user == responsible_person or user_has_role(user, "QAU")):
        frappe.throw(f"Only the Responsible Person '{responsible_person}' or QAU is allowed to set a QM Action to Status '{status}', but user = '{user}'.")
    update_status(doc, status)


def update_status(action, status):
    action = frappe.get_doc("QM Action", action)
    if action.status == status:
        return

    # validate status transitions
    if ((action.status == 'Draft' and status == 'Created') or
        (action.status == 'Created' and status == 'Work in Progress') or
        (action.status == 'Work in Progress' and status == 'Completed')
       ):
        action.status = status
        action.save()
        frappe.db.commit()
    else: 
        frappe.throw(f"Update QM Action: Status transition is not allowed {action.status} --> {status}")


@frappe.whitelist()
def cancel(action):
    from microsynth.microsynth.utils import force_cancel
    action_doc = frappe.get_doc("QM Action", action)
    if action_doc.status == "Draft":
        force_cancel("QM Action", action_doc.name)
    else:
        try:
            action_doc.status = 'Cancelled'
            action_doc.save()
            action_doc.cancel()
            frappe.db.commit()
        except Exception as err:
            force_cancel("QM Action", action_doc.name)


@frappe.whitelist()
def assign(doc, responsible_person):
    clear("QM Action", doc)
    add({
        'doctype': "QM Action",
        'name': doc,
        'assign_to': responsible_person,
        'notify': True
    })


@frappe.whitelist()
def change_responsible_person(user, action, responsible_person):
    action_doc = frappe.get_doc("QM Action", action)
    # check that the user has the right to change the responsible person
    if not (user == action_doc.responsible_person or user_has_role(user, "QAU")):
        frappe.throw(f"Only the Responsible Person '{responsible_person}' or QAU is allowed to change the responsible person, but user = '{user}'.")
    # change the responsible person
    action_doc.responsible_person = responsible_person
    action_doc.save()
    # create assignment to user
    assign(action, responsible_person)