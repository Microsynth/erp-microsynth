# -*- coding: utf-8 -*-
# Copyright (c) 2024, Microsynth, libracore and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document
from frappe.utils import cint, get_url_to_form
from datetime import datetime
from frappe.desk.form.load import get_attachments


naming_patterns = {
    "Code1": {
        "base": "{document_type} {process_number}.{subprocess_number}.{chapter}.",
        "document_number": "{doc:03d}"
    },
    "Code2": {
        "base": "{document_type} {process_number}.{subprocess_number}.{date}.",
        "document_number": "{doc:02d}"
    },
    "Code3": {
        "base": "{document_type} {process_number}.{subprocess_number}.",
        "document_number": "{doc:04d}"
    }
}


naming_code = {
    "SOP": "Code1",
    "PROT": "Code2",
    "LIST": "Code3",
    "FORM": "Code3",
    "FLOW": "Code3",
    "CL": "Code3",
    "QMH": "Code1"
}


class QMDocument(Document):

    def autoname(self):       
        if cint(self.version) < 2:
            # new document number
            # auto name function
            pattern = "{p}".format(
                p=naming_patterns[naming_code[self.document_type]]['base']
            )
            base_name = pattern.format(
                document_type=self.document_type,
                process_number = self.process_number,
                subprocess_number = self.subprocess_number,
                chapter = self.chapter or "00",
                date = datetime.today().strftime("%Y%m%d")
            )
            # find document number
            docs = frappe.db.sql("""
                SELECT `name` 
                FROM `tabQM Document`
                WHERE `name` LIKE "{0}%"
                ORDER BY `name` DESC
                LIMIT 1;
                """.format(base_name), as_dict=True)
            
            if len(docs) == 0:
                self.document_number = 1
            else:
                self.document_number = cint((docs[0]['name'][len(base_name):]).split("-")[0]) + 1
            
            # check revision
            version = self.version or 1

        # generate name
        pattern = "{p}{d}-{v}".format(
            p=naming_patterns[naming_code[self.document_type]]['base'],
            d=naming_patterns[naming_code[self.document_type]]['document_number'],
            v="{version:02d}")
        self.name = pattern.format(
            document_type=self.document_type,
            process_number = self.process_number,
            subprocess_number = self.subprocess_number,
            chapter = self.chapter or "00",
            date = datetime.today().strftime("%Y%m%d"),
            doc = cint(self.document_number),
            version = cint(self.version)
        )
        return
    
    def get_overview(self):
        files = get_attachments("QM Document", self.name)
        html = frappe.render_template("microsynth/qms/doctype/qm_document/doc_overview.html", {'files': files, 'doc': self})
        return html


@frappe.whitelist()
def create_new_version(doc):
    new_doc = frappe.get_doc(frappe.get_doc("QM Document", doc).as_dict())
    new_doc.docstatus = 0                               # new doc is draft
    new_doc.version = cint(new_doc.version) + 1         # go to next version
    if new_doc.version > 99:
        frappe.throw( "Sorry, you have lost the lottery.", "Document version too high")
    new_doc.reviewed_on = None
    new_doc.reviewed_by = None
    new_doc.released_on = None
    new_doc.released_by = None
    new_doc.signature = None
    new_doc.insert()
    frappe.db.commit()
    return {'name': new_doc.name, 'url': get_url_to_form("QM Document", new_doc.name)}


@frappe.whitelist()
def set_released(doc, user):
    qm_doc = frappe.get_doc(frappe.get_doc("QM Document", doc))
    qm_doc.released_by = user
    qm_doc.released_on = datetime.now()
    qm_doc.save()
    frappe.db.commit()
    update_status(qm_doc.name, "Released")


@frappe.whitelist()
def update_status(qm_document, status):
    qm_doc = frappe.get_doc("QM Document", qm_document)
    qm_doc.status = status
    qm_doc.save()
    frappe.db.commit()
