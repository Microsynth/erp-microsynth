import os
import sys
import csv
csv.field_size_limit(sys.maxsize)
from datetime import datetime
import frappe


def _employee_import_clean(value):
    if value is None:
        return None
    text = str(value).strip()
    return text if text else None


def _employee_import_parse_date(value, label, row_number):
    """
    Parse dates from TSV. Accepts:
    - DD.MM.YYYY
    - YYYY-MM-DD
    - datetime strings parseable by datetime.fromisoformat
    Returns YYYY-MM-DD or None.
    """
    value = _employee_import_clean(value)
    if not value:
        return None

    for fmt in ("%d.%m.%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, fmt).date().isoformat()
        except ValueError:
            pass
    try:
        return datetime.fromisoformat(value).date().isoformat()
    except ValueError:
        print(f"WARNING: Row {row_number}: could not parse '{label}' value '{value}'.")
        return None


def _employee_import_map_gender(raw_gender, row_number):
    raw = (_employee_import_clean(raw_gender) or "").lower()
    mapping = {
        "f": "Female",
        "m": "Male",
        "o": "Other",
    }
    if not raw:
        return None
    if raw in mapping:
        return mapping[raw]
    print(f"WARNING: Row {row_number}: unknown gender '{raw_gender}', leaving empty.")
    return None


def _employee_import_map_status(raw_status, row_number):
    raw = (_employee_import_clean(raw_status) or "").lower()
    mapping = {
        "active": "Active",
        "inactive": "Inactive",
        "left": "Left",
    }
    if not raw:
        return None
    if raw in mapping:
        return mapping[raw]
    print(f"WARNING: Row {row_number}: unknown status '{raw_status}', keeping current value.")
    return None


def _employee_import_find_user_by_email(company_email):
    """
    Find ERP user by Company Email.
    Prefer exact User.name match (common in ERPNext), fallback to User.email.
    """
    if not company_email:
        return None

    user_name = frappe.db.get_value("User", {"name": company_email}, "name")
    if user_name:
        return user_name

    user_name = frappe.db.get_value("User", {"email": company_email}, "name")
    return user_name


def _employee_import_set_first_existing_field(doc, meta, candidate_fieldnames, value):
    """
    Set the first field that exists in Employee meta.
    Returns the fieldname used, or None.
    """
    if value is None:
        return None

    for fieldname in candidate_fieldnames:
        if meta.has_field(fieldname):
            doc.set(fieldname, value)
            return fieldname
    return None


def _employee_import_attach_picture(employee_doc, picture_folder, picture_filename, row_number, counters):
    """
    Attach at most one picture to an Employee.
    Uses picture_folder + picture_filename from TSV column "Bild".
    """
    picture_folder = _employee_import_clean(picture_folder)
    picture_filename = _employee_import_clean(picture_filename)
    if not picture_folder or not picture_filename:
        return

    picture_path = os.path.join(picture_folder, picture_filename)
    if not os.path.isfile(picture_path):
        print(f"WARNING: Row {row_number}: picture file not found: '{picture_path}'.")
        counters["warnings"] += 1
        return

    existing_files = frappe.get_all(
        "File",
        filters={
            "attached_to_doctype": "Employee",
            "attached_to_name": employee_doc.name
        },
        fields=["name", "file_name", "file_url"]
    )

    image_extensions = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".tif", ".tiff"}
    existing_image_files = [
        f for f in existing_files
        if os.path.splitext((f.get("file_name") or "").lower())[1] in image_extensions
    ]

    if existing_image_files:
        # Keep first existing image and do not attach another one.
        existing_image = existing_image_files[0]
        if hasattr(employee_doc, "image") and (not employee_doc.image) and existing_image.get("file_url"):
            employee_doc.image = existing_image.get("file_url")
            employee_doc.save(ignore_permissions=True)
        return

    try:
        from frappe.utils.file_manager import save_file

        with open(picture_path, "rb") as picture_file:
            content = picture_file.read()

        attached_file = save_file(
            picture_filename,
            content,
            "Employee",
            employee_doc.name,
            is_private=1
        )

        if hasattr(employee_doc, "image") and attached_file and attached_file.file_url:
            employee_doc.image = attached_file.file_url
            employee_doc.save(ignore_permissions=True)
    except Exception as err:
        print(
            f"WARNING: Row {row_number}: failed to attach picture '{picture_filename}' to Employee '{employee_doc.name}': {str(err)}"
        )
        counters["warnings"] += 1


def import_employees(filename, dry_run=False, update_existing=True, picture_folder=None):
    """
    Import or update Employee records from a tab separated values file.

    Required headers:
    Company, Vorname, Nachname, Company Email

    Supported optional headers:
    Gender, Date of Birth, Date of Joining, Emergency Phone, Emergency Contact,
    User ID, Abacus Nr. (External Employee ID), Department, Visa, Status, Bild

    bench execute microsynth.microsynth.migration.import_employees --kwargs "{'filename': '/mnt/erp_share/Migration/2026-07-29_Employee_List.txt', 'dry_run': True, 'update_existing': True, 'picture_folder': '/mnt/erp_share/Migration/employee_pictures'}"
    """
    required_headers = {"Company", "Vorname", "Nachname", "Company Email"}
    meta = frappe.get_meta("Employee")

    counters = {
        "processed": 0,
        "created": 0,
        "updated": 0,
        "skipped": 0,
        "warnings": 0,
        "errors": 0,
        "linked_users": 0,
        "missing_users": 0
    }
    print(f"Starting Employee import from {filename} (dry_run={dry_run}, update_existing={update_existing})")

    with open(filename, "r", encoding="utf-8-sig", newline="") as tsv_file:
        reader = csv.DictReader(tsv_file, delimiter="\t")

        if not reader.fieldnames:
            raise Exception("TSV has no header row.")

        headers = {h.strip() for h in reader.fieldnames if h}
        missing_headers = required_headers - headers
        if missing_headers:
            raise Exception(f"Missing required TSV headers: {sorted(missing_headers)}")

        for row_number, raw_row in enumerate(reader, start=2):
            row = {k.strip(): _employee_import_clean(v) for k, v in raw_row.items() if k}

            if not any(row.values()):
                continue

            company = row.get("Company")
            first_name = row.get("Vorname")
            last_name = row.get("Nachname")
            company_email = row.get("Company Email")
            external_employee_id = row.get("Abacus Nr. (External Employee ID)")
            user_id_from_file = row.get("User ID")
            department = row.get("Department")
            picture_filename = row.get("Bild")

            if not company or not first_name or not last_name:
                print(f"WARNING: Row {row_number}: missing Company/Vorname/Nachname, skipping.")
                counters["warnings"] += 1
                counters["skipped"] += 1
                continue

            if not frappe.db.exists("Company", company):
                print(f"WARNING: Row {row_number}: Company '{company}' does not exist, skipping.")
                counters["warnings"] += 1
                counters["skipped"] += 1
                continue

            employee_doc = None

            if external_employee_id and meta.has_field("external_employee_id"):
                employee_name = frappe.db.get_value("Employee", {"external_employee_id": external_employee_id}, "name")
                if employee_name:
                    employee_doc = frappe.get_doc("Employee", employee_name)

            if not employee_doc and company_email and meta.has_field("company_email"):
                employee_name = frappe.db.get_value("Employee", {"company_email": company_email}, "name")
                if employee_name:
                    employee_doc = frappe.get_doc("Employee", employee_name)

            if not employee_doc and user_id_from_file and meta.has_field("user_id"):
                employee_name = frappe.db.get_value("Employee", {"user_id": user_id_from_file}, "name")
                if employee_name:
                    employee_doc = frappe.get_doc("Employee", employee_name)

            is_new = False
            if not employee_doc:
                employee_doc = frappe.new_doc("Employee")
                is_new = True
            elif not update_existing:
                counters["skipped"] += 1
                continue

            # Core fields
            if meta.has_field("company"):
                employee_doc.company = company
            if meta.has_field("first_name"):
                employee_doc.first_name = first_name
            if meta.has_field("last_name"):
                employee_doc.last_name = last_name

            gender = _employee_import_map_gender(row.get("Gender"), row_number)
            if gender and meta.has_field("gender"):
                employee_doc.gender = gender

            date_of_birth = _employee_import_parse_date(row.get("Date of Birth"), "Date of Birth", row_number)
            if date_of_birth and meta.has_field("date_of_birth"):
                employee_doc.date_of_birth = date_of_birth

            date_of_joining = _employee_import_parse_date(row.get("Date of Joining"), "Date of Joining", row_number)
            if date_of_joining and meta.has_field("date_of_joining"):
                employee_doc.date_of_joining = date_of_joining

            if department:
                if frappe.db.exists("Department", department):
                    if meta.has_field("department"):
                        employee_doc.department = department
                else:
                    print(f"WARNING: Row {row_number}: Department '{department}' does not exist, leaving empty.")
                    counters["warnings"] += 1

            # Optional fields with resilient mapping
            _employee_import_set_first_existing_field(
                employee_doc, meta, ["emergency_phone_number", "emergency_phone"], row.get("Emergency Phone")
            )
            _employee_import_set_first_existing_field(
                employee_doc, meta, ["emergency_contact", "emergency_contact_name"], row.get("Emergency Contact")
            )
            if company_email and meta.has_field("company_email"):
                employee_doc.company_email = company_email

            if external_employee_id and meta.has_field("external_employee_id"):
                employee_doc.external_employee_id = external_employee_id

            mapped_status = _employee_import_map_status(row.get("Status"), row_number)
            if mapped_status and meta.has_field("status"):
                employee_doc.status = mapped_status

            # User link by Company Email (requested behavior)
            if company_email and meta.has_field("user_id"):
                user_name = _employee_import_find_user_by_email(company_email)
                if user_name:
                    employee_doc.user_id = user_name
                    counters["linked_users"] += 1
                    visa_value = _employee_import_clean(row.get("Visa"))
                    if visa_value:
                        user_username = _employee_import_clean(frappe.db.get_value("User", user_name, "username"))
                        if user_username and visa_value.lower() != user_username.lower():
                            print(
                                f"WARNING: Row {row_number}: Visa '{visa_value}' differs from User.username '{user_username}' for User '{user_name}'."
                            )
                            counters["warnings"] += 1
                else:
                    print(f"WARNING: Row {row_number}: no ERP User found for Company Email '{company_email}'.")
                    counters["warnings"] += 1
                    counters["missing_users"] += 1
            try:
                if dry_run:
                    action = "CREATE" if is_new else "UPDATE"
                    print(f"DRY RUN: {action} Employee ({first_name} {last_name}, company_email={company_email})")
                    if picture_folder and picture_filename:
                        picture_path = os.path.join(picture_folder, picture_filename)
                        if not os.path.isfile(picture_path):
                            print(f"WARNING: Row {row_number}: picture file not found: '{picture_path}'.")
                            counters["warnings"] += 1
                else:
                    if is_new:
                        employee_doc.insert(ignore_permissions=True)
                        counters["created"] += 1
                    else:
                        employee_doc.save(ignore_permissions=True)
                        counters["updated"] += 1

                    _employee_import_attach_picture(
                        employee_doc=employee_doc,
                        picture_folder=picture_folder,
                        picture_filename=picture_filename,
                        row_number=row_number,
                        counters=counters,
                    )

                    counters["processed"] += 1

            except Exception as err:
                counters["errors"] += 1
                print(f"ERROR: Row {row_number}: failed to save employee ({first_name} {last_name}): {str(err)}")
                #print(traceback.format_exc())

    if not dry_run:
        frappe.db.commit()

    print("Employee import finished.")
    print(
        f"processed={counters['processed']}, created={counters['created']}, updated={counters['updated']}, "
        f"skipped={counters['skipped']}, warnings={counters['warnings']}, errors={counters['errors']}, "
        f"linked_users={counters['linked_users']}, missing_users={counters['missing_users']}"
    )
    return counters
