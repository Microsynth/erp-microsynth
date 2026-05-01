# -*- coding: utf-8 -*-
# Copyright (c) 2026, Microsynth
# For license information, please see license.txt

from __future__ import unicode_literals
import os
import shutil
from datetime import datetime

from frappe import _
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
            if instrument_doc.instrument_class.startswith('A') or instrument_doc.instrument_class.startswith('B') \
                or (instrument_doc.instrument_class.startswith('F') and instrument_doc.regulatory_classification == 'GMP'):
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

    def _safe_join(base, *paths):
        base = os.path.abspath(base)
        final = os.path.abspath(os.path.join(base, *paths))
        if os.path.commonpath([base, final]) != base:
            raise frappe.PermissionError("Invalid file path detected")
        return final

    def _move_to_error_folder(filename, msg):
        error_root = _safe_join(BASE_PATH, ERROR_FOLDER)
        os.makedirs(error_root, exist_ok=True)
        base = os.path.splitext(filename)[0]
        error_dir = _safe_join(error_root, base)
        os.makedirs(error_dir, exist_ok=True)

        src = _safe_join(BASE_PATH, filename)
        if os.path.exists(src):
            shutil.move(src, _safe_join(error_dir, filename))

        with open(_safe_join(error_dir, "error.txt"), "w", encoding="utf-8") as f:
            f.write(msg)

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

    if not os.path.isdir(BASE_PATH):
        frappe.throw(_("Base path does not exist: {0}").format(BASE_PATH))

    for fname in sorted(os.listdir(BASE_PATH)):
        if not fname.lower().endswith(".txt"):
            continue

        path = _safe_join(BASE_PATH, fname)
        if verbose:
            print(f"\nProcessing {fname}")

        try:
            with open(path, "r", encoding="utf-8") as f:
                lines = [l.strip() for l in f if l.strip()]

            if len(lines) < 2:
                raise Exception("No data rows")

            for line in lines[1:]:
                parts = line.split("\t")
                if len(parts) < 7:
                    raise Exception(f"Invalid row: {line}")

                instrument_id, date_str, entry_type, description, target_status_logbook_entry, target_status_instrument, pdf_name = parts

                if not frappe.db.exists("QM Instrument", instrument_id):
                    raise Exception(f"Instrument '{instrument_id}' not found")

                if target_status_logbook_entry not in ["Closed", "To Review", "Draft"]:
                    raise Exception(f"Invalid Target Status for Log Book Entry: '{target_status_logbook_entry}'")

                date = _parse_date(date_str)

                # Create log book entry
                doc = frappe.get_doc({
                    "doctype": "QM Log Book",
                    "status": target_status_logbook_entry,
                    "entry_type": entry_type,
                    "date": date,
                    "description": description,
                    "document_type": "QM Instrument",
                    "document_name": instrument_id
                }).insert()
                if target_status_logbook_entry in ["Closed", "To Review"]:
                    doc.submit()

                if verbose:
                    print(f"Created {doc.name}")

                # Attach PDF
                if pdf_name:
                    pdf_path = _safe_join(BASE_PATH, pdf_name)
                    if not os.path.isfile(pdf_path):
                        raise Exception(f"Missing PDF: {pdf_name}")
                    _attach_file(doc, pdf_path)

                # Update QM Instrument status
                if target_status_instrument and target_status_instrument.lower() != "na":
                    instrument_doc = frappe.get_doc("QM Instrument", instrument_id)
                    instrument_doc.status = target_status_instrument
                    instrument_doc.save()

            # Archive
            archive_root = _safe_join(BASE_PATH, ARCHIVE_FOLDER)
            os.makedirs(archive_root, exist_ok=True)
            archive_dir = _safe_join(archive_root, os.path.splitext(fname)[0])
            os.makedirs(archive_dir, exist_ok=True)

            shutil.move(path, _safe_join(archive_dir, fname))

            for line in lines[1:]:
                parts = line.split("\t")
                if len(parts) >= 7:
                    pdf_name = parts[6].strip()
                    pdf_path = _safe_join(BASE_PATH, pdf_name)
                    if os.path.isfile(pdf_path):
                        shutil.move(pdf_path, _safe_join(archive_dir, pdf_name))

            if verbose:
                print(f"Imported {fname}")

        except Exception as e:
            msg = f"{fname}: {str(e)}"
            frappe.log_error(msg, "QM Log Book Import")
            if verbose:
                print(msg)
            _move_to_error_folder(fname, msg)
            raise
