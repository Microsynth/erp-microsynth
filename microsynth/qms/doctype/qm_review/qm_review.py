# -*- coding: utf-8 -*-
# Copyright (c) 2024, Microsynth, libracore and contributors and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document
from datetime import datetime

class QMReview(Document):
    def on_submit(self):
        if self.document_type == "QM Document":
            ref_doc = frappe.get_doc(self.document_type, self.document_name)
            ref_doc.reviewed_by = frappe.session.user       # voted over self.modified_by
            ref_doc.reviewed_on = datetime.now()            # self.modified_on
            ref_doc.save(ignore_permissions=True)
            frappe.db.commit()
        return

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
