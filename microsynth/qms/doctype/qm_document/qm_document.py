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

document_types_with_review = ['SOP', 'FLOW', 'QMH']

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
    new_doc.import_name = None
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


def parse_doc_id(doc_id, title, steering):
    """
    Takes a string and returns a dictionary of its parts
    if the string represents a valid Q Document number according to QMH or None otherwise.
    """
    space_separated_parts = doc_id.split(' ')
    if len(space_separated_parts) != 2:
        print(f"{doc_id};{title};{steering};contains more or less than one space, but expected exactly one space between type of document and the rest of the document ID according to the QMH.")
        return None
    doc_type = space_separated_parts[0]
    numbers = space_separated_parts[-1].split('.')
    chapter = date = None
    if doc_type in ['VERF', 'OFF', 'BER', 'VERS']:
        print(f"{doc_id};{title};{steering};has a valid type of document according to QMH, but {doc_type} is not supported anymore.")
        return None
    if doc_type in ['AV', 'SOP', 'QMH', 'APPX']:  # Code 1
        if len(numbers) == 4:
            chapter = numbers[2]
            document_number = numbers[3].replace('*','')
        else:
            print(f"{doc_id};{title};{steering};has {len(numbers)} part(s) separated by a dot after the rightmost space, but expected {doc_type} to have four numbers separated by a dot according to QMH.")
            return None
    elif doc_type in ['PROT']:  # Code 2
        if len(numbers) == 4:
            date = numbers[2]
            document_number = numbers[3].replace('*','')
        else:
            print(f"{doc_id};{title};{steering};has {len(numbers)} part(s) separated by a dot after the rightmost space, but expected {doc_type} to have four numbers separated by a dot according to QMH.")
            return None
    elif doc_type in ['LIST', 'FORM', 'FLOW', 'FLUDI', 'CL', 'VERF', 'OFF']:  # Code 3
        if len(numbers) == 3:
            document_number = numbers[2].replace('*','')
        else:
            print(f"{doc_id};{title};{steering};has {len(numbers)} part(s) separated by a dot after the rightmost space, but expected {doc_type} to have three numbers separated by a dot according to QMH.")
            return None
    else:
        print(f"{doc_id};{title};{steering};First part of Document ID is '{doc_type}' and not a valid type of document according to the QMH.")
        return None
    # try to convert process_number and subprocess_number to int
    try:
        process_number = int(numbers[0])
        subprocess_number = int(numbers[1])
    except Exception as err:
        print(f"{doc_id};{title};{steering};Unable to convert process number '{process_number}' or subprocess_number '{subprocess_number}' to an integer. Going to continue. Error = '{err}'")
        return None
    if chapter:
        # try to convert chapter to int
        try:
            chapter = int(chapter)
        except Exception as err:
            print(f"{doc_id};{title};{steering};Unable to convert chapter '{chapter}' to an integer. Going to continue. Error = '{err}'")
            return None
    # Replace AV by SOP
    if doc_type == 'AV':
        doc_type = 'SOP'
    # Replace FLUDI by FLOW
    if doc_type == 'FLUDI':
        doc_type = 'FLOW'
    return {'doc_type': doc_type,
            'process_number': process_number,
            'subprocess_number': subprocess_number,
            'chapter': chapter,
            'date': date,
            'document_number': document_number}


def import_qm_documents(file_path, expected_line_length=3):
    """
    Import Title and Document ID from a FileMaker export tsv.

    bench execute microsynth.qms.doctype.qm_document.qm_document.import_qm_documents --kwargs "{'file_path': '/mnt/erp_share/JPe/tabExportQ-documents_incl_steering.tab'}"
    """
    import csv
    imported_counter = line_counter = 0
    inserted_docs = []
    with open(file_path) as tsv:
        print(f"Parsing Q Documents from '{file_path}' ...")
        csv_reader = csv.reader((l.replace('\0', '') for l in tsv), delimiter="\t")  # replace NULL bytes (throwing an error)
        #next(csv_reader)  # skip header
        for line in csv_reader:
            line_counter += 1
            if len(line) != expected_line_length:
                print(f"Line '{line}' has length {len(line)}, but expected length {expected_line_length}. Going to continue.")
                continue
            title = line[0].strip()  # remove leading and trailing whitespaces
            # "All instruction numbers marked with * are confidential"
            doc_id = line[1].strip().replace('*', '')  # remove leading and trailing whitespaces and *
            doc_id = doc_id.replace('AV', 'SOP').replace('FLUDI', 'FLOW')  # rename AV and FLUDI
            steering = line[2]
            parts = parse_doc_id(doc_id, title, steering)
            if not parts:  # error occurred during parsing
                continue
            # Get fitting QM Process
            if parts['chapter'] and parts['chapter'] != '00':  #process_number == 5 and subprocess_number == 3:
                qm_processes = frappe.get_all("QM Process", filters=[
                    ['process_number', '=', parts['process_number']],
                    ['subprocess_number', '=', parts['subprocess_number']],
                    #['chapter', '=', parts['chapter']]  # Only Process 5.3 has a chapter (5.3.1 or 5.3.2)
                    ], fields=['name'])
            else:
                qm_processes = frappe.get_all("QM Process", filters=[
                    ['process_number', '=', parts['process_number']],
                    ['subprocess_number', '=', parts['subprocess_number']],
                    ['all_chapters', '=', 1]],
                    fields=['name'])

            if len(qm_processes) == 0:
                process_name = f"{parts['process_number']}.{parts['subprocess_number']}"
                qm_processes.append({'name': process_name})
                print(f"{doc_id};{title};{steering};Found no QM Process with process_number={parts['process_number']} and subprocess_number={parts['subprocess_number']}. "
                      f"Going to set Process of QM Document to '{process_name}'.")
            elif len(qm_processes) > 1:
                print(f"{doc_id};{title};{steering};Found the following {len(qm_processes)} QM Processes with process_number={parts['process_number']} and "
                      f"subprocess_number={parts['subprocess_number']}: {qm_processes}. Going to take the first QM Process.")
            # Create QM Document
            qm_doc = frappe.get_doc({
                'doctype': "QM Document",
                'document_type': parts['doc_type'],
                'qm_process': qm_processes[0]['name'],
                'chapter': parts['chapter'],  # Useless, chapter will always be fetched from QM Process. If QM Process has no chapter, chapter is set to 0.
                'date': parts['date'],  # only for PROT
                'document_number': parts['document_number'],
                'import_name': doc_id,
                'title': title
            })
            try:
                #qm_doc.chapter = parts['chapter']
                qm_doc.insert()
                #qm_doc.chapter = parts['chapter']
                #print(f"{qm_doc.chapter=}; {parts['chapter']=}")
                #qm_doc.save()  # TODO: How to avoid overwriting chapter?
                #print(f"{qm_doc.chapter=}; {parts['chapter']=}")
                inserted_docs.append(qm_doc.name)
            except Exception as err:
                print(f"{doc_id};{title};{steering};Unable to insert: {err}")
                continue
            if qm_doc.name != doc_id:  # currently useless
                print(f"{doc_id};{title};{steering};unequals {qm_doc.name=}.")
                continue
            imported_counter += 1
    print(f"Could successfully import {imported_counter}/{line_counter} Q Documents ({round((imported_counter/line_counter)*100, 2)} %).")

    # Delete inserted documents to be able to test again without deleting them manually or replace the whole database.
    # for doc_name in inserted_docs:
    #     frappe.db.delete("QM Document", {"name": doc_name})
