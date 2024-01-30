# -*- coding: utf-8 -*-
# Copyright (c) 2024, Microsynth, libracore and contributors and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document

class QMReview(Document):
    pass


@frappe.whitelist()
def create_review(reviewer, dt, dn, due_date):
    review = frappe.get_doc(
        {
            'doctype': 'QM Review',
            'reviewer': reviewer, 
            'document_type': dt,
            'document_name': dn,
            'due_date': due_date
        })

    review.save(ignore_permissions = True)
    frappe.db.commit()

    return