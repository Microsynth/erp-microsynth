# -*- coding: utf-8 -*-
# Copyright (c) 2024, Microsynth, libracore and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document
from datetime import datetime
from frappe.desk.form.assign_to import add, clear
from microsynth.qms.doctype.qm_document.qm_document import update_status
from frappe.desk.form.load import get_attachments
from microsynth.qms.signing import sign
from frappe import _


class QMReview(Document):
    def on_submit(self):
        # for QM document: update review section
        if self.document_type == "QM Document":
            ref_doc = frappe.get_doc(self.document_type, self.document_name)
            ref_doc.reviewed_by = frappe.session.user       # voted over self.modified_by
            ref_doc.reviewed_on = datetime.now()            # self.modified_on
            ref_doc.save(ignore_permissions=True)
            frappe.db.commit()

            update_status(self.document_name, "Reviewed")

        # clear any assignments
        clear("QM Review", self.name)
        return


    def reject(self):
        # invalidate document
        update_status(self.document_name, "Invalid")
        # set review to cancelled (fast-track)
        frappe.db.set_value(self.doctype, self.name, "docstatus", 2)
        frappe.db.commit()
        # clear any assignments
        clear("QM Review", self.name)
        return 


@frappe.whitelist()
def get_overview(qm_review):
    doc = frappe.get_doc("QM Review", qm_review)
    if doc.document_type == "QM Document":
        files = get_attachments(doc.document_type, doc.document_name)
        html = frappe.render_template("microsynth/qms/doctype/qm_document/doc_overview.html", {'files': files, 'doc': doc})
    else:
        html = "<p>No data</p>"
    return html


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
    assign(review.name, reviewer)
    
    # submit qm document
    if dt == "QM Document":
        qm_doc = frappe.get_doc("QM Document", dn)
        if qm_doc.docstatus == 0:
            qm_doc.submit()
            frappe.db.commit()
            
    return review.name


@frappe.whitelist()
def assign(doc, reviewer):
    clear("QM Review", doc)
    add({
        'doctype': "QM Review",
        'name': doc,
        'assign_to': reviewer
    })
    return


@frappe.whitelist()
def sign_review(doc, user, password):
    # get document
    if type(doc) == str:
        doc = frappe.get_doc("QM Review", doc)
        
    # verify user is the creator of the QM document
    review_doc = frappe.get_doc(doc.get("document_type"), doc.get("document_name"))
    if (review_doc.created_by or review_doc.owner) == user:
        frappe.throw( _("Invalid reviewer. Please select a reviewer different from the document creator."), _("Review failed") )
        return False
    else:
        return sign("QM Review", doc.get("name"), user, password)


def get_qm_reviews(qm_document):
    """
    Return a list of all submitted QM Reviews for the given QM Document 
    """
    return frappe.get_all("QM Review",
            filters = [['document_name', '=', qm_document], ['docstatus', '=', 1]],
            fields = ['name', 'reviewer', 'signature'])