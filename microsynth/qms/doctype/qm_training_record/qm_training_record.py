# -*- coding: utf-8 -*-
# Copyright (c) 2024, Microsynth, libracore and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document
from frappe.desk.form.assign_to import add, clear


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

    # create assignment to user
    add({
        'doctype': "QM Training Record",
        'name': record.name,
        'assign_to': trainee
    })
