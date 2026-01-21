# -*- coding: utf-8 -*-
# Copyright (c) 2024, Microsynth, libracore and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.desk.form.assign_to import add
from frappe.utils.data import today
from frappe.model.document import Document


class QMImpactAssessment(Document):
    def on_submit(self):
        self.status = "Completed"
        self.completion_date = today()
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
    add({
        'doctype': "QM Impact Assessment",
        'name': assessment.name,
        'assign_to': creator,
        'notify': True
    })
    return assessment.name


@frappe.whitelist()
def cancel(impact_assessment):
    from microsynth.microsynth.utils import force_cancel
    impact_assessment_doc = frappe.get_doc("QM Impact Assessment", impact_assessment)
    if impact_assessment_doc.status == "Draft":
        force_cancel("QM Impact Assessment", impact_assessment_doc.name)
    else:
        try:
            impact_assessment_doc.status = 'Cancelled'
            impact_assessment_doc.save()
            impact_assessment_doc.cancel()
            frappe.db.commit()
        except Exception as err:
            frappe.throw(f"Unable to cancel QM Impact Assessment {impact_assessment}:\n{err}")
