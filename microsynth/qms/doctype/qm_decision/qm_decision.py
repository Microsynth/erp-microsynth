# -*- coding: utf-8 -*-
# Copyright (c) 2024, Microsynth, libracore and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.desk.form.assign_to import add, clear
from microsynth.qms.signing import sign
from frappe.model.document import Document
from frappe.utils import get_url_to_form
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
        url = get_url_to_form(dt, dn)
        url_string = f"<a href={url}>{dn}</a>"
        description = f"Your {dt} {url_string} has been {'rejected' if decision == 'Reject' else 'approved'} by {approver} for status transition {from_status} -> {to_status}."
        if comments:
            description += f"<br><br>Rational: {comments}"
        # Delete existing assignments (otherwise leading to an error)
        clear(dt, dn)
        # Assign creator of linked document
        add({
            'doctype': dt,
            'name': dn,
            'assign_to': refdoc_creator,
            'description': description,
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
