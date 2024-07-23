# -*- coding: utf-8 -*-
# Copyright (c) 2024, Microsynth, libracore and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.utils.data import today
from frappe.model.document import Document


class QMImpactAssessment(Document):
	pass


@frappe.whitelist()
def create_impact_assessment(dt, dn, title, qm_process, creator):
    assessment = frappe.get_doc(
        {
            'doctype': 'QM Impact Assessment',
            'document_type': dt,
            'document_name': dn,
            'title': title,
            'qm_process': qm_process,
            'date': today(),
            'created_on': today(),
            'created_by': creator,
            'status': 'Requested',
        })
    assessment.save(ignore_permissions = True)
    frappe.db.commit()
    return assessment.name