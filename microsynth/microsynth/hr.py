import os
import shutil
import xml.etree.ElementTree as ET

import frappe
from frappe.utils import cint
from frappe.model.mapper import get_mapped_doc


naming_patterns = {
    'Job Opening': {
        'prefix': "JO-",
        'length': 5
    },
    'Job Applicant': {
        'prefix': "JA-",
        'length': 6
    }
}


def get_next_number(self):
    if self.doctype not in ["Job Opening", "Job Applicant"]:
        frappe.throw("Custom autoname is not implemented for this doctype.", "Not implemented")

    last_name = frappe.db.sql("""
        SELECT `name`
        FROM `tab{dt}`
        WHERE `name` LIKE "{prefix}%"
        ORDER BY `name` DESC
        LIMIT 1;""".format(
        dt=self.doctype,
        prefix=naming_patterns[self.doctype]['prefix']),
        as_dict=True)

    if len(last_name) == 0:
        next_number = 1
    else:
        prefix_length = len(naming_patterns[self.doctype]['prefix'])
        last_number = cint((last_name[0]['name'])[prefix_length:])
        next_number = last_number + 1

    next_number_string = get_fixed_length_string(next_number, naming_patterns[self.doctype]['length'])

    return "{prefix}{n}".format(prefix=naming_patterns[self.doctype]['prefix'], n=next_number_string)


def get_fixed_length_string(n, length):
    next_number_string = "{0}{1}".format(
        (length * "0"), n)[((-1)*length):]
    # prevent duplicates on naming series overload
    if n > cint(next_number_string):
        next_number_string = "{0}".format(n)
    return next_number_string


def hr_autoname(self, method):
    if self.doctype not in ["Job Opening", "Job Applicant"]:
        frappe.throw("Custom autoname is not implemented for this doctype.", "Not implemented")

    self.name = get_next_number(self)
    return


@frappe.whitelist()
def map_job_applicant_to_employee(source_name, target_doc=None):

    def set_missing_values(source, target):
        job_offer = frappe.get_doc("Job Offer", {"job_applicant": source.name})
        target.status = "Active"
        target.company = job_offer.company or source.company
        target.designation = job_offer.designation
        return target

    job_offer = frappe.get_doc("Job Offer", source_name)
    if not job_offer.job_applicant:
        frappe.throw("Job Offer must be linked to a Job Applicant.")

    job_applicant = frappe.get_doc("Job Applicant", job_offer.job_applicant)

    return get_mapped_doc(
        "Job Applicant",
        job_applicant.name,
        {
            "Job Applicant": {
                "doctype": "Employee",
                "field_map": {
                    "applicant_name": "employee_name",
                    "salutation": "salutation",
                    "first_name": "first_name",
                    "middle_name": "middle_name",
                    "last_name": "last_name",
                    "date_of_birth": "date_of_birth",
                    "gender": "gender"
                }
            }
        },
        target_doc,
        set_missing_values
    )


def import_job_applicants(verbose=False):
    """
    Import job applicants from XML files in a specified directory.
    Each XML file should contain fields like job_id, email, name, etc.
    Associated PDF files (CV, cover letter, etc.) will be attached to the
    created Job Applicant document. After processing, files are moved to an Archive folder.
    1. Parse XML files in BASE_PATH
    2. For each file:
       - Extract relevant fields
       - Validate existence of Job Opening
       - Check for duplicate applications (same job + email)
       - Create Job Applicant document
       - Attach associated PDF files
       - Move processed files to Archive folder
    In case of any error with a single XML file that is currently written to the Error Log,
    all files starting with the same time stamp than the problematic XML are moved to a new subfolder in ERROR_FOLDER
    named after the XML file (without extension) and a txt file containing the error message is added to that folder.

    Should be run by an hourly cron job:
    32 4-18 * * * cd /home/frappe/frappe-bench && /usr/local/bin/bench --site erp.microsynth.local microsynth.microsynth.hr.import_job_applicants

    bench execute microsynth.microsynth.hr.import_job_applicants --kwargs '{"verbose": True}'
    """
    BASE_PATH = frappe.get_value("Microsynth Settings", "Microsynth Settings", "website_applications_path")
    ARCHIVE_FOLDER = "Archive"
    ERROR_FOLDER = "Errors"
    MANDATORY_FIELDS_MAP = {
        "job_id": "job_id",
        "email": "email",
        "Vorname": "first_name",
        "Name": "last_name",
        "Adresse": "address",
        "PLZ": "postal_code",
        "Ort": "city"
    }
    PDF_FIELDS = [
        "Dateiupload_CV",
        "Dateiupload_Motivationsschreiben",
        "Dateiupload_Andere",
    ]

    def _safe_join(base, *paths):
        """Prevent path traversal."""
        final_path = os.path.abspath(os.path.join(base, *paths))
        if not final_path.startswith(os.path.abspath(base)):
            raise frappe.PermissionError("Invalid file path detected")
        return final_path

    def _parse_xml_fields(xml_path):
        """Parse XML into a dict(name -> value)."""
        tree = ET.parse(xml_path)
        root = tree.getroot()
        data = {}
        for field in root.findall("field"):
            name_el = field.find("name")
            if name_el is None or not name_el.text:
                continue
            value_el = field.find("value")
            data[name_el.text.strip()] = (
                value_el.text.strip() if value_el is not None and value_el.text else ""
            )
        return data

    def _attach_file(doc, file_path):
        """Attach a file to a document."""
        if verbose:
            print(f"Attaching file: {file_path} to doc: {doc.doctype} / {doc.name}")
        with open(file_path, "rb") as f:
            frappe.get_doc({
                "doctype": "File",
                "file_name": os.path.basename(file_path),
                "attached_to_doctype": doc.doctype,
                "attached_to_name": doc.name,
                "content": f.read(),
                "is_private": 1,
            }).insert(ignore_permissions=True)
        if verbose:
            print(f"Successfully attached {file_path}")

    def _move_to_error_folder(xml_filename, error_message):
        base_name = os.path.splitext(xml_filename)[0]
        timestamp_prefix = base_name.split("-", 2)[:2]
        prefix = "-".join(timestamp_prefix)
        error_root = _safe_join(BASE_PATH, ERROR_FOLDER)
        os.makedirs(error_root, exist_ok=True)
        error_dir = _safe_join(error_root, base_name)
        os.makedirs(error_dir, exist_ok=True)
        # Move all matching files
        for f in os.listdir(BASE_PATH):
            if f.startswith(prefix):
                src = _safe_join(BASE_PATH, f)
                if os.path.isfile(src):
                    shutil.move(src, _safe_join(error_dir, f))
        # Write error log
        with open(_safe_join(error_dir, "error.txt"), "w", encoding="utf-8") as fh:
            fh.write(error_message)

    if not os.path.isdir(BASE_PATH):
        frappe.throw(f"Base path does not exist: {BASE_PATH}")

    for fname in os.listdir(BASE_PATH):
        if not fname.lower().endswith(".xml"):
            continue
        xml_path = _safe_join(BASE_PATH, fname)
        if verbose:
            print(f"\nProcessing XML: {fname}")
        try:
            raw_data = _parse_xml_fields(xml_path)
            if verbose:
                print(f"Parsed XML fields: {raw_data}")
            data = {}
            missing_field = False
            msg = ""
            for key, field in MANDATORY_FIELDS_MAP.items():
                if not raw_data.get(key):
                    msg += f"Missing required field '{key}' in {fname}\n"
                    missing_field = True
                data[field] = raw_data.get(key, "")

            if missing_field:
                if verbose:
                    print(f"Missing mandatory fields in {fname}: {msg}")
                _move_to_error_folder(fname, msg)
                frappe.log_error(msg, "Job Applicant Import")
                continue

            if not frappe.db.exists("Job Opening", data.get("job_id")):
                msg = f"Job Opening {data.get('job_id')} not found for {fname}"
                if verbose:
                    print(msg)
                frappe.log_error(msg, "Job Applicant Import")
                _move_to_error_folder(fname, msg)
                continue

            # Prevent duplicates (same job + email)
            if frappe.db.exists(
                "Job Applicant",
                {"email_id": data.get("email"), "job_opening": data.get("job_id")},
            ):
                msg = f"Duplicate application skipped: {data.get('email')} / {data.get('job_id')}"
                if verbose:
                    print(msg)
                frappe.log_error(msg, "Job Applicant Import")
                _move_to_error_folder(fname, msg)
                continue

            # Create Job Applicant
            if verbose:
                print(f"Creating Job Applicant for: {data.get('first_name')} {data.get('last_name')}, Job: {data.get('job_id')}")
            applicant = frappe.get_doc({
                "doctype": "Job Applicant",
                "applicant_name": f"{data.get('first_name').strip()} {data.get('last_name').strip()}",
                "job_title": data.get("job_id"),
                "company": frappe.db.get_value("Job Opening", data.get("job_id"), "company"),
                "first_name": data.get("first_name"),
                "last_name": data.get("last_name"),
                "email_id": data.get("email"),
                "phone_number": raw_data.get("Telefon"),
                "status": "Open",
                "cover_letter": raw_data.get("Mitteilungen"),
                "source": "Website Listing",
            })
            applicant.address = f"{data.get('address').strip()}\n{data.get('postal_code').strip()} {data.get('city').strip()}"
            applicant.insert()
            if verbose:
                print(f"Inserted Job Applicant: {applicant.name}")

            # Attach PDFs
            for fieldname in PDF_FIELDS:
                pdf_name = data.get(fieldname)
                if verbose:
                    print(f"Checking PDF field '{fieldname}': '{pdf_name}'")
                if not pdf_name:
                    if verbose:
                        print(f"No PDF specified for field '{fieldname}' in {fname}")
                    continue
                pdf_path = _safe_join(BASE_PATH, pdf_name)
                if not os.path.isfile(pdf_path):
                    msg = f"Missing PDF {pdf_name} for {fname}"
                    if verbose:
                        print(f"{msg} (expected at: {pdf_path})")
                    frappe.log_error(msg, "Job Applicant Import")
                    _move_to_error_folder(fname, msg)
                    continue
                if verbose:
                    print(f"Attaching PDF: {pdf_path}")
                _attach_file(applicant, pdf_path)

            # Archive processed files
            archive_root = _safe_join(BASE_PATH, ARCHIVE_FOLDER)
            os.makedirs(archive_root, exist_ok=True)

            archive_dir = _safe_join(
                archive_root, os.path.splitext(fname)[0]
            )
            os.makedirs(archive_dir, exist_ok=True)
            shutil.move(xml_path, _safe_join(archive_dir, fname))

            for fieldname in PDF_FIELDS:
                pdf_name = data.get(fieldname, "").strip()
                if not pdf_name:
                    continue
                pdf_path = _safe_join(BASE_PATH, pdf_name)
                if verbose:
                    print(f"PDF check: '{pdf_name}' → {os.path.exists(pdf_path)}")
                if os.path.isfile(pdf_path):
                    shutil.move(
                        pdf_path,
                        _safe_join(archive_dir, pdf_name),
                    )
            if verbose:
                print(f"Imported applicant from {fname}")

        except Exception:
            if verbose:
                print(f"Exception occurred while processing {fname}:")
                import traceback
                traceback.print_exc()
            frappe.log_error(
                frappe.get_traceback(),
                f"Failed to process {fname}",
            )
