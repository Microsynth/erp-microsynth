# -*- coding: utf-8 -*-
# Copyright (c) 2024, Microsynth, libracore and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.desk.form.assign_to import add
from microsynth.qms.signing import sign
from frappe.model.document import Document
from datetime import date


class QMDecision(Document):
    pass


@frappe.whitelist()
def create_decision(approver, decision, dt, dn, from_status, to_status, comments, refdoc_creator):
    decision_doc = frappe.get_doc(
        {
            'doctype': 'QM Decision',
            'approver': approver,
            'decision': decision,
            'document_type': dt,
            'document_name': dn,
            'from_status': from_status,
            'to_status': to_status,
            'date': date.today(),
            'comments': comments
        })

    decision_doc.save(ignore_permissions = True)
    if refdoc_creator:
        # Assign creator of linked document
        add({
            'doctype': "QM Decision",
            'name': decision_doc.name,
            'assign_to': refdoc_creator,
            'description': f"Your {dt} {dn} has been {'rejected' if decision == 'Reject' else 'approved'} by {approver} for status transition {from_status} -> {to_status}.",
            'notify': True
        })
    frappe.db.commit()
    return decision_doc.name


@frappe.whitelist()
def sign_decision(doc, user, password):
    # get document
    if type(doc) == str:
        doc = frappe.get_doc("QM Decision", doc)
    return sign("QM Decision", doc.get("name"), user, password)
        

def get_qm_decisions(doc_name):
    """
    Return a list of all submitted QM Decisions for the given Document Name 
    """
    return frappe.get_all("QM Decision",
            filters = [['document_name', '=', doc_name], ['docstatus', '=', 1]],
            fields = ['name', 'approver', 'signature', 'comments'])
