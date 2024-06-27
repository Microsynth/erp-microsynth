# -*- coding: utf-8 -*-
# Copyright (c) 2024, Microsynth, libracore and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document
from frappe.utils.data import today


class QMNonconformity(Document):
    pass


@frappe.whitelist()
def set_created(doc, user):
    # pull selected document
    nc = frappe.get_doc(frappe.get_doc("QM Nonconformity", doc))

    if user != nc.created_by:
        frappe.throw(f"Error creating the QM Nonconformity: Only {nc.created_by} is allowed to create the QM Nonconformity {nc.name}. Current login user is {user}.")

    nc.created_on = today()
    nc.created_by = user
    nc.save()
    frappe.db.commit()
    update_status(nc.name, "Created")


@frappe.whitelist()
def update_status(nc, status):
    nc = frappe.get_doc("QM Document", nc)
    if nc.status == status:
        return

    # validate status transitions
    if (1 == 1):
        nc.status = status
        nc.save()
        frappe.db.commit()
    else: 
        frappe.throw(f"Update QM Nonconformity: Status transition is not allowed {nc.status} --> {status}")
