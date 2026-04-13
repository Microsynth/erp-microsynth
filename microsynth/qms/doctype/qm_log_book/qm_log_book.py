# -*- coding: utf-8 -*-
# Copyright (c) 2026, Microsynth
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document


SITE_COMPANY_MAP = {
    "Balgach": "Microsynth AG",
    "Göttingen": "Microsynth Seqlab GmbH",
    "Lyon": "Microsynth France SAS",
    "Wien": "Microsynth Austria GmbH"
}


class QMLogBook(Document):

    def on_submit(self):
        if self.document_type and self.document_name and self.document_type == "QM Instrument":
            instrument_doc = frappe.get_doc(self.document_type, self.document_name)
            if instrument_doc.regulatory_classification == "GMP":
                self.status = "To Review"
            else:
                self.status = "Closed"
            self.save()
            frappe.db.commit()

    def on_cancel(self):
        self.status = "Cancelled"
        self.save()
        frappe.db.commit()


@frappe.whitelist()
def is_user_process_owner(log_book_id, user):
    log_book = frappe.get_doc("QM Log Book", log_book_id)
    instrument_doc = frappe.get_doc(log_book.document_type, log_book.document_name, "qm_process")
    company = SITE_COMPANY_MAP.get(instrument_doc.site)
    qm_process = instrument_doc.qm_process
    if company and qm_process:
        process_owners = frappe.get_all("QM Process Owner", filters={"company": company, "qm_process": qm_process}, fields=["process_owner"])
        return any(owner.process_owner == user for owner in process_owners)
    return False
