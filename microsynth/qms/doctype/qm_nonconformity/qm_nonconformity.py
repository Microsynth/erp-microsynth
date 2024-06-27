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
def set_classified(doc, user):
    if not user_has_role(user, "QAU"):
        frappe.throw(f"Only QAU is allowed to classify a QM Nonconformity.")
    update_status(doc, "Classified")


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


def user_has_role(user, role):
    """
    Check if a user has a role
    """
    role_matches = frappe.db.sql(f"""
        SELECT `parent`, `role`
        FROM `tabHas Role`
        WHERE `parent` = "{user}"
          AND `role` = "{role}"
          AND `parenttype` = "User";
        """, as_dict=True)
    
    if len(role_matches) > 0:
        return True
    else:
        return False
