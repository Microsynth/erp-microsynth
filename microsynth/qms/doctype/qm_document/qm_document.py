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
from frappe.core.doctype.communication.email import make


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
        if self.prev_doc:
            parts = self.prev_doc.split("-")
            parts[-1] = f"{self.version:02d}"
            self.name = "-".join(parts)
        elif self.import_name:
            # in the case of an import, override naming generator by import name
            self.name = self.import_name
        else:
            chapter_formatted = '0' + str(self.chapter) if (self.chapter and self.chapter < 10) else (self.chapter or '00')
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
                    chapter = chapter_formatted,
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
                chapter = chapter_formatted,
                date = datetime.today().strftime("%Y%m%d"),
                doc = cint(self.document_number),
                version = cint(self.version)
            )
        return


    def after_insert(self):
        # frappe will insert the default company on insert -> after insert remove this again
        frappe.db.set_value("QM Document", self.name, "company", None, update_modified = False)
        return


    def get_overview(self):
        files = get_attachments("QM Document", self.name)
        docs_linking_to_this = frappe.db.sql("""
            SELECT `tabQM Document Link`.`parent` AS `document`,
                `tabQM Document`.`status`,
                `tabQM Document`.`version`
            FROM `tabQM Document Link`
            LEFT JOIN `tabQM Document` ON `tabQM Document`.`name` = `tabQM Document Link`.`parent`
            WHERE `tabQM Document Link`.`qm_document` = "{doc}"
                AND `tabQM Document`.`status` = 'Valid';
            """.format(doc=self.name), as_dict=True)

        relating_docs = []
        for doc in self.linked_documents:
            if frappe.get_value("QM Document", doc.qm_document, "status") == "Valid":
                relating_docs.append(doc.qm_document)
            else:
                # try to find the valid version
                without_version = doc.qm_document.split("-")[0]
                valid_docs = frappe.db.sql(f"""
                    SELECT `tabQM Document`.`name`
                    FROM `tabQM Document`
                    WHERE `tabQM Document`.`name` LIKE '{without_version}%'
                        AND `tabQM Document`.`status` = 'Valid';
                    """, as_dict=True)
                if len(valid_docs) == 1:
                    relating_docs.append(valid_docs[0]['name'])
                elif len(valid_docs) > 1:
                    frappe.log_error(f"There seem to be {len(valid_docs)} Valid versions of QM Document LIKE '{without_version}%'.", "qm_document.get_overview")
                else:
                    # no valid version -> take the highest version
                    all_versions = frappe.db.sql(f"""
                    SELECT `tabQM Document`.`name`
                    FROM `tabQM Document`
                    WHERE `tabQM Document`.`name` LIKE '{without_version}%'
                        AND `tabQM Document`.`docstatus` = 1
                    ORDER BY `tabQM Document`.`version` DESC;
                    """, as_dict=True)
                    if len(all_versions) > 0:
                        relating_docs.append(all_versions[0]['name'])
                    else:
                        #frappe.log_error(f"There seem to be no QM Documents LIKE '{without_version}%' with docstatus 1.", "qm_document.get_overview")
                        continue

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
                'relating_docs': relating_docs,
                'trained': trained
            })

        return html


@frappe.whitelist()
def create_new_version(doc, user):
    new_doc = frappe.get_doc(frappe.get_doc("QM Document", doc).as_dict())
    new_doc.docstatus = 0                               # new doc is draft
    new_doc.version = cint(new_doc.version) + 1         # go to next version
    if new_doc.version > 99:
        frappe.throw( "Sorry, you have lost the lottery.", "Document version too high")
    new_doc.import_name = None
    new_doc.creation = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    new_doc.created_on = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    new_doc.created_by = user
    new_doc.reviewed_on = None
    new_doc.reviewed_by = None
    new_doc.released_on = None
    new_doc.released_by = None
    new_doc.last_revision_on = None
    new_doc.last_revision_by = None
    new_doc.release_signature = None
    new_doc.signature = None
    new_doc.valid_from = None
    new_doc.valid_till = None
    new_doc.status = "Draft"
    new_doc.prev_doc = doc
    new_doc.insert()
    frappe.db.commit()
    return {'name': new_doc.name, 'url': get_url_to_form("QM Document", new_doc.name)}


@frappe.whitelist()
def set_created(doc, user):
    # pull selected document
    qm_doc = frappe.get_doc("QM Document", doc)

    if user != qm_doc.created_by:
        frappe.throw(f"Error signing the QM Document Status: Only {qm_doc.created_by} is allowed to sign the QM Document {qm_doc.name}. Current login user is {user}.")

    qm_doc.save()
    frappe.db.commit()

    update_status(qm_doc.name, "Created")
    return


@frappe.whitelist()
def set_released(doc, user):
    # pull selected document
    qm_doc = frappe.get_doc("QM Document", doc)
    # if valid from is in the past, pull to today
    if qm_doc.valid_from and qm_doc.valid_from < date.today():
        qm_doc.valid_from = date.today()
    # set release user and (current) date
    qm_doc.released_by = user
    qm_doc.released_on = date.today()
    qm_doc.save()
    frappe.db.commit()
    # if valid_from date is today or in the past -> set directly to valid
    if qm_doc.valid_from and qm_doc.valid_from <= date.today():
        set_valid_document(qm_doc.name)
    else:
        update_status(qm_doc.name, "Released")
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
        (qm_doc.status == "Draft" and status == "Invalid") or
        (qm_doc.status == "Created" and status == "In Review") or
        (qm_doc.status == "Created" and status == "Released" and qm_doc.document_type not in document_types_with_review) or
        (qm_doc.status == "Created" and status == "Invalid") or
        (qm_doc.status == "In Review" and status == "Reviewed") or
        (qm_doc.status == "In Review" and status == "Invalid") or
        (qm_doc.status == "Reviewed" and status == "Released") or
        (qm_doc.status == "Reviewed" and status == "Invalid") or
        (qm_doc.status == "Released" and status == "Valid") or
        (qm_doc.status == "Released" and status == "Invalid") or
        (qm_doc.status == "Valid" and status == "Invalid")
        ):
            qm_doc.status = status
            qm_doc.save()
            frappe.db.commit()
    else:
        frappe.throw(f"Update QM Document Status: Status transition is not allowed {qm_doc.status} --> {status}")

    if status == "Reviewed" or (status == "Created" and qm_doc.document_type not in document_types_with_review):
        # notify Q about a new releasable document.
        notify_q_releasable(qm_doc)
    return


@frappe.whitelist()
def assign_after_review(qm_document, description=None):
    add({
        'doctype': "QM Document",
        'name': qm_document,
        'assign_to': frappe.get_value("QM Document", qm_document, "created_by"),
        'description': description or f"Your QM Document '{qm_document}' has been reviewed.",
        'notify': True
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


@frappe.whitelist()
def notify_new_creator(qm_document, new_creator):
    if type(qm_document) == str:
        qm_document = frappe.get_doc("QM Document", qm_document)
    # send a notification to the new creator
    add({
        'doctype': "QM Document",
        'name': qm_document.name,
        'assign_to': new_creator,
        'description': f"You are assigned as the new creator of QM Document '{qm_document.name}'.",
        'notify': True
    })


def notify_q_releasable(qm_document):
    url_string = f"<a href={get_url_to_form('QM Document', qm_document.name)}>{qm_document.name}</a>"
    # send a notification to qm
    make(
        recipients = 'qm@microsynth.ch',
        sender = 'erp@microsynth.ch',
        sender_full_name = 'Microsynth ERP',
        subject = f"Releasable: {qm_document.name}",
        content = f"Dear QAU,<br>the QM Document {url_string} ({qm_document.title}) is now releasable.",
        send_email = True
        )


def notify_pvs_about_valid_status(qm_document):
    if qm_document.company:
        companies = [qm_document.company]
    else:
        all_companies = frappe.get_all("Company", fields=['name'])
        companies = [company['name'] for company in all_companies]
    pvs = set()
    for company in companies:
        all_pvs = frappe.db.get_all("QM Process Owner", filters={'qm_process': qm_document.qm_process, 'company': company}, fields=['name', 'company', 'process_owner'])
        for pv in all_pvs:
            pvs.add(pv['process_owner'])
    if len(pvs) == 0:
        frappe.log_error(f"Found no PV for QM Document '{qm_document.name}' with QM Process '{qm_document.qm_process}' and Company '{qm_document.company}'.", "qm_document.notify_pvs_about_valid_status")

    url_string = f"<a href={get_url_to_form('QM Document', qm_document.name)}>{qm_document.name}</a>"
    make(
        recipients = ','.join(list(pvs)),
        sender = 'erp@microsynth.ch',
        sender_full_name = 'Microsynth ERP',
        subject = f"Validated {qm_document.name}",
        content = f"The QM Document {url_string} ({qm_document.title}) of your QM Process '{qm_document.qm_process}' {f'({qm_document.company})' if qm_document.company else ''} has been set to Valid.",
        send_email = True
    )


@frappe.whitelist()
def invalidate_document(qm_document):
    if type(qm_document) == str:
        qm_document = frappe.get_doc("QM Document", qm_document)
    update_status(qm_document.name, "Invalid")
    # clear any assignments
    clear("QM Document", qm_document.name)
    # send a notification to the creator
    url_string = f"<a href={get_url_to_form('QM Document', qm_document.name)}>{qm_document.name}</a>"
    if qm_document.created_by:  # do not try to send an email to a non-existing creator (can only happen for imported QM Documents)
        make(
            recipients = qm_document.created_by,
            sender = 'erp@microsynth.ch',
            sender_full_name = 'Microsynth ERP',
            subject = f"Invalidated {qm_document.name}",
            content = f"Your QM Document {url_string} ({qm_document.title}) has been set to Invalid.",
            send_email = True
            )
    # force cancel all QM Training Record Drafts
    qmtr_drafts = frappe.get_all("QM Training Record", filters={'docstatus': 0, 'document_name': qm_document.name, 'document_type': 'QM Document'}, fields=['name'])
    if len(qmtr_drafts) > 0:
        from microsynth.microsynth.utils import force_cancel
        for qmtr_draft in qmtr_drafts:
            force_cancel("QM Training Record", qmtr_draft['name'])


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

    # get all other valid versions and all smaller versions for this document
    other_versions = frappe.db.sql(f"""
        SELECT `name`, `version`
        FROM `tabQM Document`
        WHERE `version` != '{qm_doc.version}'
            AND `document_type` = '{qm_doc.document_type}'
            AND `process_number` = '{qm_doc.process_number}'
            AND `subprocess_number` = '{qm_doc.subprocess_number}'
            AND `chapter` = '{qm_doc.chapter}'
            AND `document_number` = '{qm_doc.document_number}'
            AND ((`status` = 'Valid' AND `docstatus` = 1)
                OR (`version` < '{qm_doc.version}' AND `status` != 'Invalid' AND `docstatus` < 2))
        ;""", as_dict=True)

    # set other versions to status Invalid
    for version in other_versions:
        if cint(version['version']) > cint(qm_doc.version):
            # should not happen anymore
            frappe.log_error(f"Invalidated the later version {qm_doc.version} of the document {qm_doc.name}", "qm_document.set_valid_document")
        qm_doc_other_version = frappe.get_doc("QM Document", version['name'])
        invalidate_document(qm_doc_other_version)

    # set document released
    update_status(qm_doc.name, "Released")
    # set document valid
    update_status(qm_doc.name, "Valid")
    notify_pvs_about_valid_status(qm_doc)
    return True


def invalidate_qm_docs():
    """
    Set Valid QM Documents to Invalid if valid_till < today.
    """
    valid_qm_docs = frappe.db.sql("""
        SELECT `name`
        FROM `tabQM Document`
        WHERE `valid_till` < CURDATE()
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
        WHERE `valid_from` <= DATE('{date.today()}')
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


def get_valid_appendices(qm_document):
    """
    Returns a dictionary of all valid QM Document with Document Type APPX that link to the given qm_document.
    """
    docs_linking_to_this = frappe.db.sql(f"""
        SELECT `tabQM Document`.`name`,
            `tabQM Document`.`title`,
            `tabQM Document`.`status`,
            `tabQM Document`.`version`
        FROM `tabQM Document Link`
        LEFT JOIN `tabQM Document` ON `tabQM Document`.`name` = `tabQM Document Link`.`parent`
        WHERE `tabQM Document Link`.`qm_document` = "{qm_document}"
            AND `tabQM Document`.`status` = 'Valid'
            AND `tabQM Document`.`document_type` = 'APPX'
        ORDER BY `tabQM Document`.`name`;
        """, as_dict=True)
    return docs_linking_to_this


def is_date_valid(date_str, format):
    """
    Checks if the given date matches the given format string.
    """
    try:
        if date_str:
            date_object = datetime.strptime(date_str, format).date()
            return date(2000, 1, 1) <= date_object <= date(2099, 12, 31)
    except Exception as err:
        return False
    else:
        return True


def validate_values(doc_id, chapter, title, version, status, company, created_on, created_by, reviewed_on, reviewed_by,
        released_on, released_by, last_revision_on, last_revision_by, valid_from, file_path, file_path_2):
    allowed_companies = ('', 'Microsynth AG', 'Microsynth Seqlab GmbH', 'Microsynth Austria GmbH', 'Microsynth France SAS', 'Ecogenics GmbH' )
    if chapter:
        try:
            chapter = int(chapter)
        except Exception as err:
            print(f"{doc_id};{title};Unable to convert chapter '{chapter}' to an integer. Going to continue. Error = '{err}'")
            return None, None
        if chapter > 99:
            print(f"{doc_id};{title};Chapter needs to be < 100, but is {chapter}. Going to continue.")
            return None, None
    try:
        version = int(version)
    except Exception as err:
        print(f"{doc_id};{title};Unable to convert version '{version}' to an integer. Going to continue. Error = '{err}'")
        return None, None
    if not 0 < version < 100:
        print(f"{doc_id};{title};Version needs to be > 0 and < 100, but is {version}. Going to continue.")
        return None, None
    if status not in ('Valid', 'Invalid'):
        print(f"{doc_id};{title};Status = '{status}', but only status 'Valid' and 'Invalid' are supported. Going to continue.")
        return None, None
    if company and company not in allowed_companies:
        print(f"{doc_id};{title};Company = '{company}', but only {allowed_companies} are supported. Going to continue.")
        return None, None
    format = "%d.%m.%Y"
    for date in [created_on, reviewed_on, released_on, last_revision_on, valid_from]:
        if not is_date_valid(date, format):
            print(f"{doc_id};{title};The date '{date}' has an incorrect format unequal dd.mm.yyyy or is not in the 21st century. Going to continue.")
            return None, None
    for user in [created_by, reviewed_by, released_by, last_revision_by]:
        if user and not frappe.db.exists("User", user):
            print(f"{doc_id};{title};The user '{user}' does not exist in the ERP. Going to continue.")
            return None, None

    if not (file_path and file_path.is_file()):
        print(f"{doc_id};{title};Cannot find file: \"{file_path}\"" )
        return None, None

    if file_path_2 and not file_path_2.is_file():
        print(f"{doc_id};{title};Cannot find file 2: \"{file_path_2}\"" )
        return None, None

    return chapter, version


def parse_doc_id(doc_id, title):
    """
    Takes a string and returns a dictionary of its parts
    if the string represents a valid Q Document number according to QMH or None otherwise.
    """
    space_separated_parts = doc_id.split(' ')
    if len(space_separated_parts) != 2:
        print(f"{doc_id};{title};contains more or less than one space but expected exactly one space "
              f"between type of document and the rest of the document ID according to the QMH.")
        return None
    doc_type = space_separated_parts[0]
    numbers = space_separated_parts[-1].split('.')
    chapter = date = None
    if doc_type in ['OFF', 'BER', 'VERS']:
        print(f"{doc_id};{title};has a valid type of document according to QMH, but {doc_type} is not supported anymore.")
        return None
    if doc_type in ['AV', 'SOP', 'QMH', 'APPX']:  # Code 1
        if len(numbers) == 4:
            chapter = numbers[2]
            document_number = numbers[3].replace('*','')
        else:
            print(f"{doc_id};{title};has {len(numbers)} part(s) separated by a dot after the rightmost space, "
                  f"but expected {doc_type} to have four numbers separated by a dot according to QMH.")
            return None
    elif doc_type in ['PROT']:  # Code 2
        if len(numbers) == 4:
            date = numbers[2]
            document_number = numbers[3].replace('*','')
        else:
            print(f"{doc_id};{title};has {len(numbers)} part(s) separated by a dot after the rightmost space, "
                  f"but expected {doc_type} to have four numbers separated by a dot according to QMH.")
            return None
    elif doc_type in ['LIST', 'FORM', 'FLOW', 'FLUDI', 'CL', 'VERF', 'OFF']:  # Code 3
        if len(numbers) == 3:
            document_number = numbers[2].replace('*','')
        else:
            print(f"{doc_id};{title};has {len(numbers)} part(s) separated by a dot after the rightmost space, "
                  f"but expected {doc_type} to have three numbers separated by a dot according to QMH.")
            return None
    else:
        print(f"{doc_id};{title};First part of Document ID is '{doc_type}' and not a valid type of document according to the QMH.")
        return None
    # try to convert process_number and subprocess_number to int
    try:
        process_number = int(numbers[0])
        subprocess_number = int(numbers[1])
    except Exception as err:
        print(f"{doc_id};{title};Unable to convert process number '{numbers[0]}' or subprocess_number "
              f"'{numbers[1]}' to an integer. Going to continue. Error = '{err}'")
        return None
    if chapter:
        # try to convert chapter to int
        try:
            chapter = int(chapter)
        except Exception as err:
            print(f"{doc_id};{title};Unable to convert chapter '{chapter}' to an integer. Going to continue. Error = '{err}'")
            return None
    # Replace AV by SOP
    if doc_type == 'AV':
        doc_type = 'SOP'
    # Replace FLUDI by FLOW
    if doc_type == 'FLUDI':
        doc_type = 'FLOW'
    # Replace VERF by FLOW
    if doc_type == 'VERF':
        doc_type = 'FLOW'
    return {'doc_type': doc_type,
            'process_number': process_number,
            'subprocess_number': subprocess_number,
            'chapter': chapter,
            'date': date,
            'document_number': document_number}


def create_file_attachment(qm_document, file_path):
    from erpnextswiss.erpnextswiss.attach_pdf import save_and_attach, create_folder

    # print(f"attach to {qm_document}: {file_path}")

    with open(file_path, mode='rb') as file:
        folder = create_folder("QM Document", "Home")

        save_and_attach(
            content = file.read(),
            to_doctype = "QM Document",
            to_name = qm_document,
            folder = folder,
            file_name = file_path.name,
            hashname = None,
            is_private = True )
    return


def rewrite_posix_path(windows_path):
    from pathlib import PureWindowsPath, PurePosixPath, Path

    path = PureWindowsPath(windows_path)       # see: https://stackoverflow.com/questions/60291545/converting-windows-path-to-linux
    posix_path = (PurePosixPath('/mnt/files', *path.parts[1:]))
    return Path(posix_path)


def import_qm_documents(file_path, expected_line_length=24, only_attach_docx=False):
    """
    Validate and import QM Documents from a FileMaker export tsv.

    bench execute microsynth.qms.doctype.qm_document.qm_document.import_qm_documents --kwargs "{'file_path': '/mnt/erp_share/JPe/250325_Upload_FORM 1.3.3101.csv', 'expected_line_length': 24, 'only_attach_docx': False}"
    """
    import csv

    imported_counter = line_counter = corrected_counter = 0
    inserted_docs = []
    with open(file_path) as file:
        print(f"Parsing Q Documents from '{file_path}' ...")
        csv_reader = csv.reader((l.replace('\0', '') for l in file), delimiter=";")  # replace NULL bytes (throwing an error)
        next(csv_reader)  # skip header
        for line in csv_reader:
            line_counter += 1
            if len(line) != expected_line_length:
                print(f"Line '{line}' has length {len(line)}, but expected length {expected_line_length}. Going to continue.")
                continue

            doc_id_old = line[5].strip()  # remove leading and trailing whitespaces
            doc_id_new = line[6]
            chapter = None if line[7] == 'NA' else line[7]
            title = line[8].strip()  # remove leading and trailing whitespaces
            version = line[9]
            status = line[10]
            company = None if line[11] == 'NA' else line[11]
            created_on = None if line[12] == 'NA' else line[12]
            created_by = None if line[13] == 'NA' else line[13].lower()
            reviewed_on = None if line[14] == 'NA' else line[14]
            reviewed_by = None if line[15] == 'NA' else line[15].lower()
            released_on = None if line[16] == 'NA' else line[16]  # was specified as mandatory
            if not released_on:
                print(f"{doc_id_new};{title};Released on is mandatory. Going to continue.")
                continue
            released_by = None if line[17] == 'NA' else line[17].lower()
            last_revision_on = None if line[18] == 'NA' else line[18]
            last_revision_by = None if line[19] == 'NA' else line[19].lower()
            valid_from = line[20]
            file_path = rewrite_posix_path(line[21])
            file_path_2 = rewrite_posix_path(line[22]) if line[22] != 'NA' else None

            doc_id_new = doc_id_new.replace('AV', 'SOP').replace('FLUDI', 'FLOW').replace('VERF', 'FLOW')  # rename AV, VERF and FLUDI
            parts = parse_doc_id(doc_id_new, title)
            if not parts:  # error occurred during parsing document ID
                continue

            chapter, version = validate_values(doc_id_new, chapter, title, version, status, company, created_on, created_by, reviewed_on, reviewed_by,
                                      released_on, released_by, last_revision_on, last_revision_by, valid_from, file_path, file_path_2)
            if not version:
                continue
            if parts['chapter'] and parts['chapter'] != chapter:
                print(f"{doc_id_new};{title};The chapter ({parts['chapter']}) parsed from the Document ID "
                      f"is unequal the chapter ({chapter}) given in the column 'Chapter'. Going to continue.")
                continue
            secret = doc_id_old[-1] == '*'
            # Get fitting QM Process
            if parts['process_number'] == 5 and parts['subprocess_number'] == 3 and chapter and chapter != 'NA':
                # Only Process 5.3 has a chapter (5.3.1 or 5.3.2)
                qm_processes = frappe.get_all("QM Process", filters=[
                    ['process_number', '=', parts['process_number']],
                    ['subprocess_number', '=', parts['subprocess_number']],
                    ['chapter', '=', chapter]
                    ], fields=['name'])
            elif parts['chapter'] and parts['chapter'] != '00':
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
                print(f"{doc_id_new};{title};Found no QM Process with process_number={parts['process_number']} and "
                      f"subprocess_number={parts['subprocess_number']}. Going to continue.")
                continue
            elif len(qm_processes) > 1:
                print(f"{doc_id_new};{title};Found the following {len(qm_processes)} QM Processes with process_number={parts['process_number']} and "
                      f"subprocess_number={parts['subprocess_number']}: {qm_processes}. Going to continue.")
                continue

            # reformat date from dd.mm.yyyy to yyyy-mm-dd
            given_date_format = "%d.%m.%Y"
            target_date_format = "%Y-%m-%d"
            released_on_formatted = datetime.strptime(released_on, given_date_format).strftime(target_date_format)

            # add version to import_name
            if len(str(version)) == 1:
                import_name = doc_id_new + "-0" + str(version)
            elif len(str(version)) == 2:
                import_name = doc_id_new + "-" + str(version)
            else:
                print(f"{doc_id_new};{title};Version '{version}' seems to be not between 1 and 99. Unable to process.")
                continue

            if '*' in import_name:
                print(f"{doc_id_new};{title};Column 'Document ID NEW' should not contain any '*', but import_name = '{import_name}'. Going to continue.")
                continue
            chapter = chapter if chapter is not None else 0

            # Check that there is not already a QM Document with the same type, qm_process, chapter and document_number
            duplicates = frappe.db.get_all("QM Document", filters=[['document_type', '=', parts['doc_type']],
                                                               ['qm_process', '=', qm_processes[0]['name']],
                                                               ['chapter', '=', chapter],
                                                               ['document_number', '=', parts['document_number']]])
            if len(duplicates) > 0 and not only_attach_docx:
                print(f"{doc_id_new};{title};There is already a QM Document with type {parts['doc_type']}, qm_process {qm_processes[0]['name']}, chapter {chapter} and document_number {parts['document_number']}. Going to continue.")
                continue
            if only_attach_docx and file_path_2:
                qm_doc = frappe.get_doc("QM Document", import_name)
            else:
                # Create QM Document
                qm_doc = frappe.get_doc({
                    'doctype': "QM Document",
                    'document_type': parts['doc_type'],
                    'qm_process': qm_processes[0]['name'],
                    'chapter': chapter,
                    'date': parts['date'],  # only for PROT
                    'document_number': parts['document_number'],
                    'import_name': import_name,
                    'title': title,
                    'version': version,
                    'status': status,
                    'classification_level': 'Secret' if secret else 'Confidential',
                    'company': company,
                    'created_on': datetime.strptime(created_on, given_date_format).strftime(target_date_format) if created_on else None,
                    'created_by': created_by or None,
                    'reviewed_on': datetime.strptime(reviewed_on, given_date_format).strftime(target_date_format) if reviewed_on else None,
                    'reviewed_by': reviewed_by or None,
                    'released_on': released_on_formatted,
                    'released_by': released_by or None,
                    'last_revision_on': datetime.strptime(last_revision_on, given_date_format).strftime(target_date_format) if last_revision_on else released_on_formatted,
                    'last_revision_by': last_revision_by or None,
                    'valid_from': datetime.strptime(valid_from, given_date_format).strftime(target_date_format)
                })
            try:
                if only_attach_docx and file_path_2:
                    create_file_attachment(qm_doc.name, file_path_2)
                    corrected_counter += 1
                else:
                    qm_doc.insert()
                    if not company:
                        qm_doc.company = None
                    qm_doc.submit()

                    create_file_attachment(qm_doc.name, file_path)

                    if file_path_2:
                        create_file_attachment(qm_doc.name, file_path_2)

                    inserted_docs.append(qm_doc.name)
                    if line[5].strip() != line[6].strip():  # compare old and new document ID from the import file
                        new_comment = frappe.get_doc({
                            'doctype': 'Comment',
                            'comment_type': "Comment",
                            'subject': qm_doc.name,
                            'content': f"The old ID of this document in FileMaker was '{doc_id_old}'",
                            'reference_doctype': "QM Document",
                            'status': "Linked",
                            'reference_name': qm_doc.name
                        })
                        new_comment.insert(ignore_permissions=True)

                    imported_counter += 1
            except Exception as err:
                print(f"{doc_id_new};{title};Unable to insert and submit: {err}")
                continue

            if qm_doc.name != import_name:  # currently useless
                print(f"{doc_id_new};{title};name/ID unequal {qm_doc.name=}.")
                continue
    if only_attach_docx:
        print(f"Could successfully attach DOCX to {corrected_counter}/{line_counter} Q Documents ({round((corrected_counter/line_counter)*100, 2)} %).")
    else:
        print(f"Could successfully import {imported_counter}/{line_counter} Q Documents ({round((imported_counter/line_counter)*100, 2)} %).")


def fix_chapters(file_path):
    """
    bench execute microsynth.qms.doctype.qm_document.qm_document.fix_chapters --kwargs "{'file_path': '/mnt/erp_share/JPe/240606_Chapters_to_fix_1.3_1.4.csv'}"
    """
    import csv
    counter = 0
    with open(file_path) as file:
        print(f"Parsing Chapter fixes from '{file_path}' ...")
        csv_reader = csv.reader(file, delimiter=";")
        next(csv_reader)  # skip header
        for line in csv_reader:
            if len(line) != 4:
                print(f"Line '{line}' has length {len(line)}, but expected length 4. Going to continue.")
                continue
            qm_doc_name = line[1]
            try:
                chapter = int(line[2])
                version = int(line[3])
            except Exception as err:
                print(f"{qm_doc_name}: Unable to convert chapter '{line[2]}' or '{line[3]}' to an integer. Going to continue. {err=}")
                continue

            if frappe.db.exists("QM Document", qm_doc_name):
                doc_version = frappe.db.get_value("QM Document", qm_doc_name, "version")
                if version != doc_version:
                    print(f"{qm_doc_name}: Version in the parsed table ('{version}') is unequal the version on the QM Document in the ERP ('{doc_version}'). Going to continue.")
                    continue
                frappe.db.set_value("QM Document", qm_doc_name, "chapter", chapter, update_modified = False)
                frappe.db.commit()
                print(f"Successfully updated {qm_doc_name} to chapter {chapter}.")
                counter += 1
            else:
                print(f"Unable to find '{qm_doc_name}' in the ERP. Going to continue.")
    print(f"Updated {counter} QM Documents.")


@frappe.whitelist()
def get_overview_wrapper(doc_name):
    self = frappe.get_doc("QM Document", doc_name)
    return self.get_overview()


@frappe.whitelist()
def get_valid_sops(qm_process_assignments):
    """
    """
    import json
    qm_process_assignments = json.loads(qm_process_assignments)
    conditions = ''
    for assignment in qm_process_assignments:
        #frappe.throw(f"{type(assignment)=}; {assignment=}")
        conditions += f"OR (`qm_process` = '{assignment.get('qm_process')}' AND ({assignment.get('all_chapters')} = 1 OR `chapter` = {assignment.get('chapter')}) AND (`company` IS NULL OR `company` = '{assignment.get('company')}'))"

    valid_docs = frappe.db.sql(f"""
        SELECT `name`, `title`
        FROM `tabQM Document`
        WHERE `document_type` = 'SOP'
            AND `status` = 'Valid'
            AND (FALSE {conditions});
        """, as_dict=True)
    return valid_docs


def find_duplicate_valid_documents():
    """
    Find duplicate valid QM Documents ignoring the version.

    bench execute microsynth.qms.doctype.qm_document.qm_document.find_duplicate_valid_documents
    """
    found_duplicates = set()
    qm_docs = frappe.db.get_all("QM Document", filters={'status': 'Valid'}, fields=['name', 'document_type', 'qm_process', 'process_number', 'subprocess_number', 'chapter', 'document_number'])

    for qm_doc in qm_docs:
        if qm_doc['name'] in found_duplicates:
            continue
        duplicates = frappe.db.get_all("QM Document", filters=[['name', '!=', qm_doc['name']],
                                                               ['status', '=', 'Valid'],
                                                               ['document_type', '=', qm_doc['document_type']],
                                                               ['process_number', '=', qm_doc['process_number']],
                                                               ['subprocess_number', '=', qm_doc['subprocess_number']],
                                                               ['chapter', '=', qm_doc['chapter']],
                                                               ['document_number', '=', qm_doc['document_number']]],
                                                      fields=['name'])
        if len(duplicates) > 0:
            print(f"Found a Valid duplicate for Valid {qm_doc['name']}: {duplicates}")
            found_duplicates.add(qm_doc['name'])
            for d in duplicates:
                found_duplicates.add(d['name'])
