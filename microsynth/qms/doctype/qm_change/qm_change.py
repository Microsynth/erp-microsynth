# -*- coding: utf-8 -*-
# Copyright (c) 2024, Microsynth, libracore and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document

class QMChange(Document):
	pass


@frappe.whitelist()
def create_change(dt, dn, title, process, company, description):
    change = frappe.get_doc(
        {
            'doctype': 'QM Change',
            'document_type': dt,
            'document_name': dn,
            'title': title,
            'process': process,
            'company': company,
            'description': description
        })

    change.save(ignore_permissions = True)
    frappe.db.commit()

    return change.name