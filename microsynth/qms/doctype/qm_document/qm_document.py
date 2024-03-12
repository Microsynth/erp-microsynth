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

document_types_with_review = ['SOP', 'FLOW', 'QMH', 'APPX']

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
    "QMH": "Code1",
    "APPX": "Code1"
}


class QMDocument(Document):
    def autoname(self):
        if self.import_name:
            # in the case of an import, override naming generator by import name
            self.name = self.import_name
        else:
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


    def after_insert(self):
        # frappe will insert the default company on insert -> after insert remove this again
        self.company = None
        self.save()
        return
        
    def get_overview(self):
        files = get_attachments("QM Document", self.name)
        docs_linking_to_this = frappe.db.sql("""
            SELECT `parent` AS `document`
            FROM `tabQM Document Link`
            WHERE `qm_document` = "{doc}";
            """.format(doc=self.name), as_dict=True)
        
        trained = frappe.db.sql("""
            SELECT 
                `tabQM Training Record`.`trainee` AS `trainee`,
                `tabUser`.`full_name` AS `full_name`
            FROM `tabQM Training Record`
            LEFT JOIN `tabUser` ON `tabUser`.`name` = `tabQM Training Record`.`trainee`
            WHERE 
                `tabQM Training Record`.`document_type` = "QM Document"
                AND `tabQM Training Record`.`document_name` = "{doc}"
                AND `tabQM Training Record`.`signature` IS NOT NULL;
            """.format(doc=self.name), as_dict=True)
            
        html = frappe.render_template("microsynth/qms/doctype/qm_document/doc_overview.html", 
            {
                'files': files, 
                'doc': self, 
                'docs_linking_to_this': docs_linking_to_this,
                'trained': trained
            })
            
        return html


@frappe.whitelist()
def create_new_version(doc):
    new_doc = frappe.get_doc(frappe.get_doc("QM Document", doc).as_dict())
    new_doc.docstatus = 0                               # new doc is draft
    new_doc.version = cint(new_doc.version) + 1         # go to next version
    if new_doc.version > 99:
        frappe.throw( "Sorry, you have lost the lottery.", "Document version too high")
    new_doc.created_on = None
    new_doc.created_by = None
    new_doc.reviewed_on = None
    new_doc.reviewed_by = None
    new_doc.released_on = None
    new_doc.released_by = None
    new_doc.release_signature = None
    new_doc.signature = None
    new_doc.valid_from = None
    new_doc.valid_till = None
    new_doc.status = "Draft"
    new_doc.insert()
    frappe.db.commit()
    return {'name': new_doc.name, 'url': get_url_to_form("QM Document", new_doc.name)}


@frappe.whitelist()
def set_created(doc, user):
    # pull selected document
    qm_doc = frappe.get_doc(frappe.get_doc("QM Document", doc))

    if user != qm_doc.created_by:
        frappe.throw(f"Error signing the QM Document Status: Only {qm_doc.created_by} is allowed to sign the QM Document {qm_doc.name}. Current login user is {user}.")

    qm_doc.save()
    frappe.db.commit()

    update_status(qm_doc.name, "Created")
    return


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
def set_rejected(doc):
    invalidate_document(doc)
    return


@frappe.whitelist()
def update_status(qm_document, status):
    qm_doc = frappe.get_doc("QM Document", qm_document)
    if qm_doc.status == status:
        return
    
    # validate signatures
    if status == "Created" and not qm_doc.signature:
        frappe.throw(f"Cannot create QM Document {qm_doc.name} because the creation signature is missing.")
    
    if status == "Released" and not qm_doc.release_signature:
        frappe.throw(f"Cannot release QM Document {qm_doc.name} because the release signature is missing.")

    # validate status transitions
    if ((qm_doc.status == "Draft" and status == "Created") or 
        (qm_doc.status == "Created" and status == "In Review") or
        (qm_doc.status == "Created" and status == "Released" and qm_doc.document_type not in document_types_with_review) or
        (qm_doc.status == "In Review" and status == "Reviewed") or
        (qm_doc.status == "In Review" and status == "Invalid") or
        (qm_doc.status == "Reviewed" and status == "Released") or
        (qm_doc.status == "Reviewed" and status == "Invalid") or
        (qm_doc.status == "Released" and status == "Valid") or
        (qm_doc.status == "Valid" and status == "Invalid")
        ):

            qm_doc.status = status
            qm_doc.save()
            frappe.db.commit()
    else: 
        frappe.throw(f"Update QM Document Status: Status transition is not allowed {qm_doc.status} --> {status}")
    return


@frappe.whitelist()
def assign_after_review(qm_document, description=None):
    add({
        'doctype': "QM Document",
        'name': qm_document,
        'assign_to': frappe.get_value("QM Document", qm_document, "created_by"),
        'description': description or f"Your QM Document '{qm_document}' has been reviewed."
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

    # If no gap was found, use next number. Numbering starts with 1.
    if not gap:
        gap = last_number + 1

    return gap


def invalidate_document(qm_document):
    update_status(qm_document.name, "Invalid")
    # send a notification to the creator
    add({
        'doctype': "QM Document",
        'name': qm_document.name,
        'assign_to': frappe.get_value("QM Document", qm_document.name, "created_by"),
        'description': f"Your QM Document '{qm_document.name}' has been set to Invalid."
    })


@frappe.whitelist()
def set_valid_document(qm_docname):
    """
    Check valid_from and valid_till dates, invalidate all other valid version, set status to valid.
    """
    qm_doc = frappe.get_doc("QM Document", qm_docname)

    # check date, proceed if valid_from and valid_till conditions are met
    today = date.today()
    if not qm_doc.valid_from or today < qm_doc.valid_from:
        update_status(qm_doc.name, "Released")
        return False
    if qm_doc.valid_till and today > qm_doc.valid_till:
        invalidate_document(qm_doc)
        return False

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
        if cint(version['version']) > cint(qm_doc.version):
            frappe.log_error(f"Invalidated a later version of the document {qm_doc.name}", "qm_document.set_valid_document")
        qm_doc_other_version = frappe.get_doc("QM Document", version['name'])
        invalidate_document(qm_doc_other_version)

    # set document released
    update_status(qm_doc.name, "Released")
    # set document valid
    update_status(qm_doc.name, "Valid")
    return True


def invalidate_qm_docs():
    """
    Set Valid QM Documents to Invalid if valid_till < today.
    """
    valid_qm_docs = frappe.db.sql(f"""
        SELECT `name`
        FROM `tabQM Document`
        WHERE `valid_till` < DATE({date.today()})
            AND `status` = 'Valid'
            AND `docstatus` = 1
        ;""", as_dict=True)
    
    for valid_qm_doc in valid_qm_docs:
        qm_doc = frappe.get_doc("QM Document", valid_qm_doc['name'])
        invalidate_document(qm_doc)


def validate_released_qm_docs():
    """
    Call set_valid_document function for all Released QM Documents with valid_from <= today.
    """
    released_qm_docs = frappe.db.sql(f"""
        SELECT `name`
        FROM `tabQM Document`
        WHERE `valid_from` <= DATE({date.today()})
            AND `status` = 'Released'
            AND `docstatus` = 1
        ;""", as_dict=True)

    for doc in released_qm_docs:
        set_valid_document(doc['name'])


def check_update_validity():
    """
    Set Valid QM Documents to Invalid if valid_till < today.
    Call set_valid_document function for all Released QM Documents with valid_from <= today.

    Should be run by a cron job every day a few minutes after midnight:
    bench execute microsynth.qms.doctype.qm_document.qm_document.check_update_validity
    """
    invalidate_qm_docs()
    validate_released_qm_docs()


def parse_fm_export(file_path):
    """
    bench execute microsynth.qms.doctype.qm_document.qm_document.parse_fm_export --kwargs "{'file_path': '/mnt/erp_share/JPe/tabExportQ-documents_incl_steering.tab'}"
    """
    import csv
    expected_line_length = 3
    counter = 0

    with open(file_path) as tsv:
        print(f"Parsing Q Documents from '{file_path}' ...")
        csv_reader = csv.reader((l.replace('\0', '') for l in tsv), delimiter="\t")  # replace NULL bytes (throwing an error)
        #next(csv_reader)  # skip header
        for line in csv_reader:
            if len(line) != expected_line_length:
                print(f"Line '{line}' has length {len(line)}, but expected length {expected_line_length}. Going to continue.")
                continue
            title = line[0]
            doc_id = line[1]
            space_separated_parts = doc_id.split(' ')
            if len(space_separated_parts) != 2:
                print(f"'{doc_id}' contains more or less than one space, but according to QMH only one space is allowed between type of document and the rest of the document ID.")
                continue
            doc_type = space_separated_parts[0]
            numbers = space_separated_parts[1].split('.')
            chapter = None
            if doc_type in ['VERF', 'OFF', 'BER', 'VERS']:
                print(f"Q Document '{doc_id}' has a valid type of document according to QMH, but {doc_type} is not supported anymore.")
                continue
            if doc_type in ['AV', 'SOP', 'QMH', 'APPX']:  # Code 1
                if len(numbers) == 4:
                    process_number = numbers[0]
                    subprocess_number = numbers[1]
                    chapter = numbers[2]
                    document_number = numbers[3].replace('*','')
                else:
                    print(f"Expected {doc_type} to have four numbers separated by a dot, but second part is '{space_separated_parts[1]}' and whole Document ID is '{doc_id}'.")
                    continue
            elif doc_type in ['PROT']:  # Code 2
                if len(numbers) == 4:
                    process_number = numbers[0]
                    subprocess_number = numbers[1]
                    date = numbers[2]
                    document_number = numbers[3].replace('*','')
                else:
                    print(f"Expected {doc_type} to have four numbers separated by a dot, but second part is '{space_separated_parts[1]}' and whole Document ID is '{doc_id}'.")
                    continue
            elif doc_type in ['LIST', 'FORM', 'FLOW', 'CL', 'VERF', 'OFF']:  # Code 3
                if len(numbers) == 3:
                    process_number = numbers[0]
                    subprocess_number = numbers[1]
                    document_number = numbers[2].replace('*','')
                else:
                    print(f"Expected {doc_type} to have three numbers separated by a dot, but second part is '{space_separated_parts[1]}' and whole Document ID is '{doc_id}'.")
                    continue
            else:
                print(f"First part of Document ID '{doc_id}' is '{doc_type}' and not valid due to the QMH.")
                continue
            # Replace AV by SOP
            if doc_type == 'AV':
                doc_type = 'SOP'
            # TODO: Get fitting QM Process via SQL
            if chapter:
                pass
            # Create QM Document to check name
            # qm_doc = frappe.get_doc({
            #     'doctype': "QM Document",
            #     'document_type': doc_type,
            #     'qm_process': None,
            #     'document_number': document_number,
            #     'title': title
            # })
            # qm_doc.insert()
            # if '*' in doc_id:
            #     name_to_compare = qm_doc.name + '*'
            # else:
            #     name_to_compare = qm_doc.name
            # if name_to_compare != doc_id and doc_type != 'PROT':  # PROT gets current date into its name
            #     print(f"{name_to_compare=} unequals {doc_id=}")
            #     continue
            counter += 1
    print(f"Could successfully import {counter} Q Documents.")
