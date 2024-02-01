# -*- coding: utf-8 -*-
# Copyright (c) 2024, Microsynth, libracore and contributors and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document
from datetime import datetime
from frappe.desk.form.assign_to import add, clear
from microsynth.qms.doctype.qm_document.qm_document import update_status


class QMReview(Document):
    def on_submit(self):
        # for QM document: update review section
        if self.document_type == "QM Document":
            ref_doc = frappe.get_doc(self.document_type, self.document_name)
            ref_doc.reviewed_by = frappe.session.user       # voted over self.modified_by
            ref_doc.reviewed_on = datetime.now()            # self.modified_on
            ref_doc.save(ignore_permissions=True)
            frappe.db.commit()

            update_status(ref_doc.name, "Reviewed")

        # clear any assignments
        clear("Qm Review", self.name)
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

    if dt == "QM Document":
        update_status(dn, "In Review")

    # create assignment to user
    add({
        'doctype': "QM Review",
        'name': review.name,
        'assign_to': reviewer
    })
    
    # submit qm document
    if dt == "QM Document":
        qm_doc = frappe.get_doc("QM Document", dn)
        if qm_doc.docstatus == 0:
            qm_doc.submit()
            frappe.db.commit()
            
    return review.name
