# -*- coding: utf-8 -*-
# Copyright (c) 2024, Microsynth, libracore and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document
from frappe.desk.form.assign_to import add, clear
from frappe.desk.form.load import get_attachments
from datetime import datetime


class QMTrainingRecord(Document):
    pass


@frappe.whitelist()
def create_training_record(trainee, dt, dn, due_date):
    record = frappe.get_doc(
        {
            'doctype': 'QM Training Record',
            'trainee': trainee, 
            'document_type': dt,
            'document_name': dn,
            'due_date': due_date
        })
    record.save(ignore_permissions = True)
    frappe.db.commit()
    full_name = frappe.get_value("User", trainee, "full_name")
    # create assignment to user
    add({
        'doctype': "QM Training Record",
        'name': record.name,
        'assign_to': trainee,
        'description': f"Dear {full_name},<br>You are welcome to attend the document training.",
        'notify': True
    })


@frappe.whitelist()
def get_overview(qm_training_record):
    doc = frappe.get_doc("QM Training Record", qm_training_record)
    if doc.document_type == "QM Document":
        files = get_attachments(doc.document_type, doc.document_name)
        html = frappe.render_template("microsynth/qms/doctype/qm_document/doc_overview.html", {'files': files, 'doc': doc})
    else:
        html = "<p>No data</p>"
    return html


@frappe.whitelist()
def set_signed_on(doc):
    record = frappe.get_doc("QM Training Record", doc)
    record.signed_on = datetime.today()
    # clear assignment
    clear("QM Training Record", doc)
    record.save(ignore_permissions = True)
    frappe.db.commit()    


def get_training_records(qm_document):
    """
    Return a list of all submitted QM Training Records for the given QM Document 
    """
    return frappe.get_all("QM Training Record",
            filters = [['document_name', '=', qm_document], ['docstatus', '=', 1]],
            fields = ['name', 'trainee', 'signed_on', 'signature'])