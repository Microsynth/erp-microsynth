# -*- coding: utf-8 -*-
# Copyright (c) 2024, Microsynth, libracore and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
from microsynth.microsynth.utils import user_has_role
from microsynth.qms.signing import sign
from frappe.model.document import Document
from datetime import date


class QMDecision(Document):
    pass


@frappe.whitelist()
def create_decision(approver, decision, dt, dn, from_status, to_status):
    decision = frappe.get_doc(
        {
            'doctype': 'QM Decision',
            'approver': approver,
            'decision': decision,
            'document_type': dt,
            'document_name': dn,
            'from_status': from_status,
            'to_status': to_status,
            'date': date.today()
        })

    decision.save(ignore_permissions = True)
    frappe.db.commit()
    return decision.name


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
