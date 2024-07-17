# -*- coding: utf-8 -*-
# Copyright (c) 2024, Microsynth, libracore and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document
from frappe.utils.data import today

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