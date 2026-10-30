# -*- coding: utf-8 -*-
# Copyright (c) 2024, Microsynth, libracore and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.desk.form.assign_to import add
from frappe.utils.data import today
from frappe.model.document import Document


class QMImpactAssessment(Document):
    def validate(self):
        old_doc = self.get_doc_before_save()
        if not old_doc or old_doc.docstatus != 0 or old_doc.status != "Draft":
            return

        changed_fields = [
            field.fieldname
            for field in self.meta.fields
            if self.get(field.fieldname) != old_doc.get(field.fieldname)
        ]
        if self.docstatus != old_doc.docstatus:
            changed_fields.append("docstatus")

        user = frappe.session.user
        roles = set(frappe.get_roles(user))
        if changed_fields and not _can_edit_draft(user, old_doc.created_by, roles):
            frappe.throw(
                "Only the assigned Responsible Person or a user with the QAU role can edit a Draft QM Impact Assessment."
            )

    def on_submit(self):
        self.status = "Completed"
        self.completion_date = today()
        self.save()
        frappe.db.commit()

    def on_cancel(self):
        self.status = "Cancelled"
        self.save()
        frappe.db.commit()


def _can_edit_draft(user, responsible_person, roles):
    return user == responsible_person or "QAU" in roles


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
        'assign_to': [creator],
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
