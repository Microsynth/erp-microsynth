# -*- coding: utf-8 -*-
# Copyright (c) 2024, Microsynth, libracore and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document
from frappe.desk.form.load import get_attachments
from frappe.desk.form.assign_to import add, clear
from microsynth.qms.signing import sign

class QMRevision(Document):
	pass


@frappe.whitelist()
def get_overview(qm_revision):
    doc = frappe.get_doc("QM Revision", qm_revision)
    if doc.document_type == "QM Document":
        files = get_attachments(doc.document_type, doc.document_name)
        html = frappe.render_template("microsynth/qms/doctype/qm_document/doc_overview.html", {'files': files, 'doc': doc})
    else:
        html = "<p>No data</p>"
    return html


@frappe.whitelist()
def create_revision(revisor, dt, dn, due_date):
    revision = frappe.get_doc(
        {
            'doctype': 'QM Revision',
            'revisor': revisor, 
            'document_type': dt,
            'document_name': dn,
            'due_date': due_date
        })

    revision.save(ignore_permissions = True)
    frappe.db.commit()

    # create assignment to user
    assign(revision.name, revisor)
    
    # submit qm document
    if dt == "QM Document":
        qm_doc = frappe.get_doc("QM Document", dn)
        if qm_doc.docstatus == 0:
            qm_doc.submit()
            frappe.db.commit()
            
    return revision.name


@frappe.whitelist()
def assign(doc, revisor):
    clear("QM Revision", doc)
    add({
        'doctype': "QM Revision",
        'name': doc,
        'assign_to': revisor
    })


@frappe.whitelist()
def sign_revision(doc, user, password):
    # get document
    if type(doc) == str:
        doc = frappe.get_doc("QM Revision", doc)
    return sign("QM Revision", doc.get("name"), user, password)
