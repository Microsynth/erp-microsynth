# -*- coding: utf-8 -*-
# Copyright (c) 2025, Microsynth
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document
from frappe.utils import get_url_to_form


class QMStudy(Document):
	pass


@frappe.whitelist()
def create_qm_study(title, type, dt, dn, comments):
    study = frappe.get_doc({
                'doctype': 'QM Study',
                'title': title,
                'type': type,
                'document_type': dt,
                'document_name': dn,
                'comments': comments,
                'status': 'Draft'
            })
    study.save()
    frappe.db.commit()
    return get_url_to_form("QM Study", study.name)
