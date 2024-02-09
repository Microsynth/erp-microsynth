# -*- coding: utf-8 -*-
# Copyright (c) 2024, Microsynth, libracore and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document
from frappe.utils import cint, get_url_to_form
from datetime import datetime, date
from frappe.desk.form.load import get_attachments
from frappe.desk.form.assign_to import add, clear


naming_patterns = {
    "Code1": {
        "base": "{document_type} {process_number}.{subprocess_number}.{chapter}.",
        "document_number": "{doc:03d}",
        "number_length": 3
    },
    "Code2": {
        "base": "{document_type} {process_number}.{subprocess_number}.{date}.",
        "document_number": "{doc:02d}",
        "number_length": 2
    },
    "Code3": {
        "base": "{document_type} {process_number}.{subprocess_number}.",
        "document_number": "{doc:04d}",
        "number_length": 4
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

            self.document_number = find_first_number_gap(
                base_name=base_name, 
                length=naming_patterns[naming_code[self.document_type]]['number_length'])

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


    def get_overview(self, files):
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
    # pull selected document
    qm_doc = frappe.get_doc(frappe.get_doc("QM Document", doc))
    # set release user and (current) date
    qm_doc.released_by = user
    qm_doc.released_on = datetime.now()
    qm_doc.save()
    frappe.db.commit()
    # if valid_from date is today or in the past -> set directly to valid
    if qm_doc.valid_from and qm_doc.valid_from <= datetime.today().date():
        set_valid_document(qm_doc.name)
    else:
        update_status(qm_doc.name, "Released")
    return


@frappe.whitelist()
def update_status(qm_document, status):
    qm_doc = frappe.get_doc("QM Document", qm_document)
    qm_doc.status = status
    qm_doc.save()
    frappe.db.commit()
    return


@frappe.whitelist()
def assign_after_review(qm_document):
    add({
        'doctype': "QM Document",
        'name': qm_document,
        'assign_to': frappe.get_value("QM Document", qm_document, "created_by")
    })
    return


def find_first_number_gap(base_name, length):
    numbers = frappe.db.sql("""
        SELECT SUBSTRING(`name`, {start}, {length})  AS `number`, `name`
        FROM `tabQM Document`
        WHERE `name` LIKE "{base_name}%"
        ORDER BY `name` ASC
        ;
        """.format(base_name=base_name, start=(len(base_name) + 1), length=length), as_dict=True)

    last_number = 0
    gap = None
    for n in numbers:
        if cint(n['number']) > (last_number + 1):
            gap = (last_number + 1)
            break
        else:
            last_number = cint(n['number'])

    # if no gap was found, use next number
    if not gap:
        # TODO: If there are no QM Documents with base_name, gap is None and last_number is 0.
        # last_number will be increased to 1 and 0 will never be used. Is this intended?
        gap = last_number + 1

    return gap
    

@frappe.whitelist()
def set_valid_document(qm_document):
    """
    Check valid_from and valid_till dates, invalidate all other valid version, set status to valid.
    """
    qm_doc = frappe.get_doc("QM Document", qm_document)

    # check date, proceed if valid_from and valid_till conditions are met
    today = date.today()
    if today < qm_doc.valid_from or today > qm_doc.valid_till:
        return

    # get all other valid versions for this document
    valid_versions = frappe.db.sql(f"""
        SELECT `name`, `version`
        FROM `tabQM Document`
        WHERE `version` != '{qm_doc.version}'
            AND `document_type` = '{qm_doc.document_type}'
            AND `process_number` = '{qm_doc.process_number}'
            AND `subprocess_number` = '{qm_doc.subprocess_number}'
            AND `chapter` = '{qm_doc.chapter}'
            AND `document_number` = '{qm_doc.document_number}'
            AND `status` = 'Valid'
            AND `docstatus` = 1
        ;""", as_dict=True)

    # set other versions to invalid
    for version in valid_versions:
        #if cint(version['version']) > cint(qm_doc.version):
            # TODO?
            #pass
        qm_doc_other_version = frappe.get_doc("QM Document", version['name'])
        qm_doc_other_version.status = 'Invalid'
        qm_doc_other_version.save()
        frappe.db.commit()

    # set document valid
    qm_doc.status = "Valid"
    return
