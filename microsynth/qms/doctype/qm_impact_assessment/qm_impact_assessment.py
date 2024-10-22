# -*- coding: utf-8 -*-
# Copyright (c) 2024, Microsynth, libracore and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.utils.data import today
from frappe.model.document import Document


class QMImpactAssessment(Document):
    def on_submit(self):
        self.status = "Completed"
        self.save()
        frappe.db.commit()

    def on_cancel(self):
        self.status = "Cancelled"
        self.save()
        frappe.db.commit()


@frappe.whitelist()
def create_impact_assessment(dt, dn, title, qm_process, creator, due_date):
    assessment = frappe.get_doc(
        {
            'doctype': 'QM Impact Assessment',
            'document_type': dt,
            'document_name': dn,
            'title': title,
            'qm_process': qm_process,
            'due_date': due_date,
            'created_on': today(),
            'created_by': creator,
            'status': 'Draft',
        })
    assessment.save(ignore_permissions = True)
    frappe.db.commit()
    return assessment.name