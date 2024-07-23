# -*- coding: utf-8 -*-
# Copyright (c) 2024, Microsynth, libracore and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document
from frappe.utils.data import today
from microsynth.microsynth.utils import user_has_role


class QMChange(Document):
	pass


@frappe.whitelist()
def create_change(dt, dn, title, qm_process, creator, company, description):
    change = frappe.get_doc(
        {
            'doctype': 'QM Change',
            'document_type': dt,
            'document_name': dn,
            'title': title,
            'qm_process': qm_process,
            'date': today(),
            'created_on': today(),
            'created_by': creator,
            'status': 'Requested',
            'company': company,
            'description': description
        })
    change.save(ignore_permissions = True)
    change.submit()
    frappe.db.commit()
    return change.name


@frappe.whitelist()
def set_status(doc, user, status):
    created_by = frappe.get_value("QM Change", doc, "created_by")
    if not (user == created_by or user_has_role(user, "QAU")):
        frappe.throw(f"Only Creator or QAU is allowed to set a QM Change to Status '{status}'.")
    update_status(doc, status)


def update_status(nc, status):
    change = frappe.get_doc("QM Change", nc)
    if change.status == status:
        return

    # validate status transitions
    if ((change.status == 'Draft' and status == 'Requested') or
        (change.status == 'Requested' and status == 'Assessment & Classification') or
        (change.status == 'Assessment & Classification' and status == 'Trial') or
        (change.status == 'Trial' and status == 'Planning') or
        (change.status == 'Planning' and status == 'Implementation') or
        (change.status == 'Implementation' and status == 'Completed') or
        (change.status == 'Completed' and status == 'Closed')
       ):
        change.status = status
        change.save()
        frappe.db.commit()
    else: 
        frappe.throw(f"Update QM Change: Status transition is not allowed {change.status} --> {status}")