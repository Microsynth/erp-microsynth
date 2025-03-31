# -*- coding: utf-8 -*-
# Copyright (c) 2025, Microsynth
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document
from frappe.model.mapper import get_mapped_doc


class QMStudy(Document):
	pass


@frappe.whitelist()
def create_new_qm_study(dt, dn):
    doc = get_mapped_doc(dt,
                         dn,
                         {
                            dt: {
			                    "doctype": "QM Study",
				                "field_map": {
                                }
		                    }
                         },
                         None)
    doc.document_type = dt
    doc.document_name = dn
    return doc
