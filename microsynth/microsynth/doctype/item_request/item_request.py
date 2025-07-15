# -*- coding: utf-8 -*-
# Copyright (c) 2025, Microsynth, libracore and contributors and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document
from frappe.desk.form.assign_to import add
from microsynth.microsynth.utils import user_has_role


class ItemRequest(Document):
	pass


@frappe.whitelist()
def reject_item_request(item_request, reject_reason=None):
    user = frappe.session.user
    if not (user_has_role(user, 'Purchase Manager') or user_has_role(user, 'Purchase User')):
        frappe.throw("You are not permitted to reject this request.")
    doc = frappe.get_doc("Item Request", item_request)
    doc.status = "Rejected"
    doc.reject_message = reject_reason or "No reason provided."
    doc.save()
    note = f"Your Item Request '{item_request}' was rejected by {user}: {reject_reason or 'No reason provided.'}"
    add({
        'doctype': "Item Request",
        'name': item_request,
        'assign_to': doc.owner,
        'description': note,
        'notify': True
    })
