# -*- coding: utf-8 -*-
# Copyright (c) 2026, Microsynth
# For license information, please see license.txt

from __future__ import unicode_literals
import os
import shutil
import traceback
from datetime import datetime
import socket
from frappe import _
import frappe
from frappe.utils import formatdate
from frappe.model.document import Document
from microsynth.qms.doctype.qm_instrument.qm_instrument import get_due_qualifications, is_gmp
from microsynth.qms.signing import sign


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
            if instrument_doc.instrument_class.startswith('A') or instrument_doc.instrument_class.startswith('B') \
                or (instrument_doc.instrument_class.startswith('F') and instrument_doc.regulatory_classification == 'GMP'):
                self.status = "To Review"
            else:
                self.status = "Closed"
            self.save()
            frappe.db.commit()
        elif self.document_type and self.document_name and self.document_type == "QM Computerised System":
            cs_doc = frappe.get_doc(self.document_type, self.document_name)
            if cs_doc.regulatory_classification == 'GMP':
                self.status = "To Review"
            else:
                self.status = "Closed"
            self.save()
            frappe.db.commit()

    def on_cancel(self):
        self.status = "Cancelled"
        self.save()
        frappe.db.commit()


def get_next_due_date(log_book_entry_id):
    log_book = frappe.get_doc("QM Log Book", log_book_entry_id)
    qm_instrument = frappe.get_doc(log_book.document_type, log_book.document_name)
    due_events = get_due_qualifications(qm_instrument.name, qm_instrument.instrument_class, qm_instrument.acquisition_date)
    for event in due_events:
        if event['qualification_type'] == log_book.entry_type:
            return event['due_date']
    return None


@frappe.whitelist()
def is_user_process_owner(log_book_id, user):
    log_book = frappe.get_doc("QM Log Book", log_book_id)
    linked_doc = frappe.get_doc(log_book.document_type, log_book.document_name)

    if linked_doc.doctype == "QM Instrument":
        company = SITE_COMPANY_MAP.get(linked_doc.site)
    elif linked_doc.doctype == "QM Computerised System":
        company = linked_doc.company
    else:
        company = None

    qm_process = getattr(linked_doc, "qm_process", None)

    if company and qm_process:
        process_owners = frappe.get_all("QM Process Owner", filters={"company": company, "qm_process": qm_process}, fields=["process_owner"])
        return any(owner.process_owner == user for owner in process_owners)
    return False


def print_raw(ip, port, content):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect((ip, port))
    s.sendall(content.encode())
    s.close()


@frappe.whitelist()
def print_instrument_certification_label(qm_log_book_entry_id):
    """
    bench execute "microsynth.qms.doctype.qm_log_book.qm_log_book.print_instrument_certification_label" --kwargs "{'qm_log_book_entry_id': 'QMLB-260003'}"
    """
    try:
        user = frappe.get_user().name

        # check if there is a user-specific printer
        if frappe.db.exists("User Printer", user):
            printer_name = frappe.get_value("User Printer", user, "instr_cert_label_printer")
            if printer_name:
                printer = frappe.get_doc("Brady Printer", printer_name)
            else:
                return {
                    "success": False,
                    "message": f"Found no instrument certification label printer for user '{user}'. Please let IT App know which printer to use."
                }
        else:
            return {
                "success": False,
                "message": f"No user-specific printer found for user '{user}'. Please let IT App know which printer to use."
            }
        qm_log_book_doc = frappe.get_doc("QM Log Book", qm_log_book_entry_id)
        qm_instrument_id = qm_log_book_doc.document_name
        raw_next_due_date = get_next_due_date(qm_log_book_entry_id)
        next_due_date = formatdate(raw_next_due_date, "dd.MM.yyyy")
        label_data = {
            'entry_type': qm_log_book_doc.entry_type,
            'qm_instrument_id': qm_instrument_id,
            'date': qm_log_book_doc.date.strftime("%d.%m.%Y") if qm_log_book_doc.date else "",
            'due_date': next_due_date,
            'datamatrix_content': qm_instrument_id
        }
        content = frappe.render_template("microsynth/templates/includes/instrument_certification_label_brady.html", label_data)
        if printer:
            #frappe.log_error(f"DEBUG: Printing label for QM Log Book Entry '{qm_log_book_entry_id}' on printer '{printer.name}' with IP {printer.ip} and port {printer.port}. Content:\n{content}\n\n{raw_next_due_date=}, {next_due_date=}", "labels.print_instrument_certification_label")
            print_raw(printer.ip, printer.port, content + "\n")  # Added newline to ensure the printer processes the content
            return {
                "success": True,
                "message": f"{qm_log_book_doc.entry_type} label for QM Instrument {qm_instrument_id} printed successfully on printer {printer.name}."
            }
        else:
            return {
                "success": False,
                "message": f"Found no Brady printer for user '{user}'. Please let IT App know which printer to use."
            }
    except Exception as err:
        msg = f"Error printing {qm_log_book_doc.entry_type} label for QM Instrument '{qm_instrument_id}': {err}"
        frappe.log_error(f"{msg}\n{traceback.format_exc()}", "labels.print_instrument_certification_label")
        return {
            "success": False,
            "message": f"Error printing {qm_log_book_doc.entry_type} label for QM Instrument '{qm_instrument_id}': {err}"
        }


@frappe.whitelist()
def approve_and_close_log_book(dn, approval_password=None, expected_modified=None):
    """
    Robust wrapper for closing a QM Log Book entry.
    - Verifies the client did not start from a stale document.
    - If linked instrument is GMP, signs closure_signature via signing.sign().
    - Reloads the document after signing because signing.sign() saves and commits.
    - Sets closed_on, closed_by and status server-side.
    - Avoids any stale frm.save() from the browser.
    """
    doc = frappe.get_doc("QM Log Book", dn)

    if doc.status == "Closed":
        return {
            "ok": True,
            "already_closed": True
        }
    if expected_modified and frappe.utils.cstr(doc.modified) != frappe.utils.cstr(expected_modified):
        frappe.throw(
            _("This Log Book Entry was modified after you opened it. Please reload and try again.")
        )
    gmp = doc.document_type == "QM Instrument" and is_gmp(doc.document_name)

    if gmp:
        if not approval_password:
            frappe.throw(_("Approval password is required."))
        sign(
            dt="QM Log Book",
            dn=dn,
            user=frappe.session.user,
            password=approval_password,
            target_field="closure_signature",
            submit=False
        )
        # signing.sign() saved and committed the document, so reload before changing more fields.
        doc = frappe.get_doc("QM Log Book", dn)

        if not doc.closure_signature:
            frappe.throw(_("Signing failed. Closure signature was not set."))

    doc.status = "Closed"
    doc.closed_on = frappe.utils.now_datetime()
    doc.closed_by = frappe.session.user
    doc.save()
    frappe.db.commit()

    return {
        "ok": True,
        "already_closed": False,
        "gmp": gmp
    }


def safe_join_path(base, *paths):
    base = os.path.abspath(base)
    final = os.path.abspath(os.path.join(base, *paths))
    if os.path.commonpath([base, final]) != base:
        raise frappe.PermissionError("Invalid file path detected")
    return final


def import_log_book_entries_from_file(path, BASE_PATH=None, verbose=False, print_label=False):
    """
    bench execute microsynth.qms.doctype.qm_log_book.qm_log_book.import_log_book_entries_from_file --kwargs "{'path': '/mnt/erp_share/Migration/QM_Instruments/260612_Kühlgeräte_Log_Books_v05.txt', 'verbose': True, 'print_label': False}"
    """

    def _attach_file(doc, path):
        with open(path, "rb") as f:
            frappe.get_doc({
                "doctype": "File",
                "file_name": os.path.basename(path),
                "attached_to_doctype": doc.doctype,
                "attached_to_name": doc.name,
                "content": f.read(),
                "is_private": 1
            }).insert(ignore_permissions=True)

    def _parse_date(val):
        return datetime.strptime(val.strip(), "%d.%m.%Y").date()

    with open(path, "r", encoding="utf-8") as f:
        lines = [l.strip() for l in f if l.strip()]

    if len(lines) < 2:
        raise Exception("No data rows")

    for line in lines[1:]:
        # TODO: Deal with tabs in the description column. For now, we assume that the description does not contain tabs.
        parts = line.split("\t")
        if len(parts) != 7:
            raise Exception(f"Invalid row: {line}")

        instrument_id, date_str, entry_type, description, target_status_logbook_entry, target_status_instrument, pdf_name = parts

        if not frappe.db.exists("QM Instrument", instrument_id):
            raise Exception(f"Instrument '{instrument_id}' not found")

        if target_status_logbook_entry not in ["Closed", "To Review", "Draft"]:
            raise Exception(f"Invalid Target Status for Log Book Entry: '{target_status_logbook_entry}'")

        date = _parse_date(date_str)

        # Create log book entry
        log_book_doc = frappe.get_doc({
            "doctype": "QM Log Book",
            "status": target_status_logbook_entry,
            "entry_type": entry_type,
            "date": date,
            "description": description,
            "document_type": "QM Instrument",
            "document_name": instrument_id
        }).insert()
        if target_status_logbook_entry in ["Closed", "To Review"]:
            log_book_doc.submit()

        if verbose:
            print(f"Created {log_book_doc.name}")

        # Attach PDF
        if pdf_name and pdf_name.lower() != "na" and BASE_PATH:
            pdf_path = safe_join_path(BASE_PATH, pdf_name)
            if not os.path.isfile(pdf_path):
                raise Exception(f"Missing PDF: {pdf_name}")
            _attach_file(log_book_doc, pdf_path)

        # Update QM Instrument status
        if target_status_instrument and target_status_instrument.lower() != "na":
            instrument_doc = frappe.get_doc("QM Instrument", instrument_id)
            instrument_doc.status = target_status_instrument
            instrument_doc.save()

        # Print label
        if print_label:
            print_instrument_certification_label(log_book_doc.name)

    return lines


@frappe.whitelist()
def import_log_book_entries(verbose=False):
    """
    Import QM Log Book entries from ERP-Share. This is a whitelist method that can be called from the frontend.
    At the BASE_PATH, the system expects to find one .txt file and folders "Archive" and "Errors". The method will move processed files to "Archive" and files with errors to "Errors".
    The .txt file is expected to have the following format:

    ID	Date of Occurrence	Type	Description	Target Status Logbook Entry	Target Status Instrument	Filename
    QMI-01500	19.08.2025	Calibration	Calibration of the pipette was performed by external ISO/IEC accredited service provider	Closed	NA	19G98658.pdf

    The .pdf file is expected to be in the same folder and will be attached to the QM Log Book entry to be created.
    The method will create a QM Log Book entry for each row in the .txt file (except the header) and link it to the corresponding QM Instrument.
    If a Target Status is provided, it will update the status of the QM Instrument accordingly.

    bench execute microsynth.qms.doctype.qm_log_book.qm_log_book.import_log_book_entries --kwargs "{'verbose': True}"
    """
    BASE_PATH = frappe.get_value("Microsynth Settings", "Microsynth Settings", "certificate_import_path")  # or '/mnt/erp_share/Quality_Management/certificates_to_import'
    if not BASE_PATH:
        frappe.throw("Microsynth Settings: Certificate import path is not set")
    ARCHIVE_FOLDER = "Archive"
    ERROR_FOLDER = "Errors"

    def _move_to_error_folder(filename, msg):
        error_root = safe_join_path(BASE_PATH, ERROR_FOLDER)
        os.makedirs(error_root, exist_ok=True)
        base = os.path.splitext(filename)[0]
        error_dir = safe_join_path(error_root, base)
        os.makedirs(error_dir, exist_ok=True)

        src = safe_join_path(BASE_PATH, filename)
        if os.path.exists(src):
            shutil.move(src, safe_join_path(error_dir, filename))

        with open(safe_join_path(error_dir, "error.txt"), "w", encoding="utf-8") as f:
            f.write(msg)

    if not os.path.isdir(BASE_PATH):
        frappe.throw(_("Base path does not exist: {0}").format(BASE_PATH))

    for fname in sorted(os.listdir(BASE_PATH)):
        if not fname.lower().endswith(".txt"):
            continue

        path = "/mnt/erp_share/JPe/260505_QM_Log_Book_Testimport.csv"
        if verbose:
            print(f"\nProcessing {fname}")

        try:
            lines = import_log_book_entries_from_file(path, verbose=verbose, print_label=True)

            # Archive
            archive_root = safe_join_path(BASE_PATH, ARCHIVE_FOLDER)
            os.makedirs(archive_root, exist_ok=True)
            archive_dir = safe_join_path(archive_root, os.path.splitext(fname)[0])
            os.makedirs(archive_dir, exist_ok=True)

            shutil.move(path, safe_join_path(archive_dir, fname))

            for line in lines[1:]:
                parts = line.split("\t")
                if len(parts) >= 7:
                    pdf_name = parts[6].strip()
                    pdf_path = safe_join_path(BASE_PATH, pdf_name)
                    if os.path.isfile(pdf_path):
                        shutil.move(pdf_path, safe_join_path(archive_dir, pdf_name))

            if verbose:
                print(f"Imported {fname}")

        except Exception as e:
            msg = f"{fname}: {str(e)}"
            frappe.log_error(msg, "QM Log Book Import")
            if verbose:
                print(msg)
            _move_to_error_folder(fname, msg)
            raise
