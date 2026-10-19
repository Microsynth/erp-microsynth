# -*- coding: utf-8 -*-
# Copyright (c) 2026, Microsynth
# For license information, please see license.txt

from __future__ import unicode_literals

import csv
from datetime import datetime

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, nowdate

from microsynth.qms.doctype.competency_assignment.competency_assignment import update_competency_assignments_for_trainee
from microsynth.qms.doctype.staff_profile_template.staff_profile_template import (
    _get_validated_staff_profile_template,
    get_staff_profile_template_competency_values,
)
from microsynth.qms.signing import sign as signing_sign
from microsynth.qms.versioning import get_newer_active_versions, get_next_suffix, get_versioned_documents


class StaffProfile(Document):
    def validate(self):
        _throw_if_invalid_competency_versions(self.competencies)

    def before_submit(self):
        self.status = "To Sign"
        if self.employee:
            existing = has_valid_staff_profile(self.employee, self.name).get("name")
            if existing:
                if not getattr(self, "confirm_valid_staff_profile_replacement", None):
                    frappe.throw(
                        _(
                            "A valid Staff Profile already exists for this employee: {0}. "
                            "Please confirm that this profile should replace the existing valid version before submitting."
                        ).format(frappe.bold(existing)),
                        title=_("Existing valid Staff Profile"),
                    )

    def on_submit(self):
        self.status = "To Sign"
        self.save()
        _update_achieved_competencies_for_staff_profile(self)
        frappe.db.commit()

    def on_cancel(self):
        self.status = "Cancelled"
        self.db_set("status", "Cancelled", update_modified=False)
        frappe.db.commit()


def _is_draft_staff_profile(profile):
    return profile.docstatus == 0 and profile.status in (None, "", "Draft")


def _get_staff_profile_template_details_for_employee(employee):
    if not employee:
        return {}

    employee_doc = frappe.get_doc("Employee", employee)
    employee_doc.check_permission("read")

    job_applicant_name = employee_doc.get("job_applicant")
    if not job_applicant_name:
        return {}
    try:
        job_applicant = frappe.get_doc("Job Applicant", job_applicant_name)
        job_applicant.check_permission("read")

        job_opening_name = job_applicant.get("job_title")
        if not job_opening_name:
            return {}

        job_opening = frappe.get_doc("Job Opening", job_opening_name)
        job_opening.check_permission("read")

        template_name = job_opening.get("staff_profile_template")
        if not template_name:
            return {}

        template = frappe.get_doc("Staff Profile Template", template_name)
        template.check_permission("read")
    except (frappe.DoesNotExistError, frappe.PermissionError):
        return {}

    if getattr(template, "disabled", False):
        return {}

    return {
        "template_name": template.name,
        "template_title": template.get("template_title") or template.name,
    }


def _get_writable_draft_staff_profile(docname):
    profile = frappe.get_doc("Staff Profile", docname)
    profile.check_permission("write")
    if not _is_draft_staff_profile(profile):
        frappe.throw(_("Template competencies can only be added to a saved Staff Profile draft."))
    return profile


@frappe.whitelist()
def get_department_competencies(docname, employee=None):
    """Return readable, valid competencies for a saved draft's employee departments."""
    profile = _get_writable_draft_staff_profile(docname)

    # Use the current form value if the employee has been changed without saving.
    employee = employee or profile.employee
    if not employee:
        return []

    employee_doc = frappe.get_doc("Employee", employee)
    employee_doc.check_permission("read")
    departments = {row.department for row in employee_doc.get("additional_departments") or [] if row.department}
    if employee_doc.department:
        departments.add(employee_doc.department)
    if not departments:
        return []

    department_links = frappe.get_all(
        "Department Link",
        filters={
            "parenttype": "Competency",
            "parentfield": "departments",
            "department": ["in", sorted(departments)],
        },
        fields=["parent"],
    )
    competency_names = sorted({row.parent for row in department_links})
    if not competency_names:
        return []

    # get_list applies Competency permissions; get_all would bypass them.
    # The client excludes its current assignments, including unsaved changes.
    return frappe.get_list(
        "Competency",
        filters={"name": ["in", competency_names], "status": "Valid", "docstatus": 1},
        fields=["name", "title"],
        order_by="title asc, name asc",
        limit_page_length=0,
    )


@frappe.whitelist()
def get_linked_staff_profile_template(docname, employee=None):
    profile = _get_writable_draft_staff_profile(docname)

    employee = employee or profile.employee
    if not employee:
        return {}

    return _get_staff_profile_template_details_for_employee(employee)


@frappe.whitelist()
def get_linked_template_competencies(docname, employee=None, template_name=None):
    profile = _get_writable_draft_staff_profile(docname)

    employee = employee or profile.employee
    if not employee:
        frappe.throw(_("Please select an Employee first."))

    template_details = _get_staff_profile_template_details_for_employee(employee)
    linked_template_name = template_details.get("template_name")
    if not linked_template_name:
        frappe.throw(_("No Staff Profile Template is linked to this employee via Job Applicant and Job Opening."))

    if template_name and template_name != linked_template_name:
        frappe.throw(_("The linked Staff Profile Template has changed. Please reopen the Staff Profile."))

    template = _get_validated_staff_profile_template(linked_template_name)
    return {
        "template_name": template.name,
        "template_title": template.get("template_title") or template.name,
        "competencies": get_staff_profile_template_competency_values(template),
    }


@frappe.whitelist()
def get_process_owner_for_employee(employee):
    """Return the process owner for an employee based on user process assignments."""
    if not employee:
        return None

    employee_user = frappe.db.get_value("Employee", employee, "user_id")
    if not employee_user:
        return None

    user_settings_name = frappe.db.get_value("User Settings", {"user": employee_user}, "name")
    if not user_settings_name:
        return None

    assignments = frappe.db.get_all(
        "QM User Process Assignment",
        filters={"parent": user_settings_name},
        fields=["company", "qm_process"],
    )
    owner_users = set()
    for assignment in assignments:
        owners = frappe.db.get_all(
            "QM Process Owner",
            filters={
                "qm_process": assignment.get("qm_process"),
                "company": assignment.get("company"),
            },
            fields=["process_owner"],
        )
        for owner in owners:
            owner_users.add(owner.get("process_owner"))

    if not owner_users:
        return None

    return sorted(owner_users)[0]


@frappe.whitelist()
def get_signing_users(employee):
    employee_user = None
    if employee:
        employee_user = frappe.db.get_value("Employee", employee, "user_id")

    return {
        "employee_user": employee_user,
        "process_owner": get_process_owner_for_employee(employee),
    }


@frappe.whitelist()
def has_valid_staff_profile(employee, current_name=None):
    if not employee:
        return {"has_valid": False}

    filters = {
        "employee": employee,
        "status": "Valid",
        "docstatus": 1,
    }
    if current_name:
        filters["name"] = ["!", current_name]

    valid_profile = frappe.db.exists("Staff Profile", filters)
    return {"has_valid": bool(valid_profile), "name": valid_profile}


@frappe.whitelist()
def create_new_version(docname):
    if not docname:
        frappe.throw(_("Missing Staff Profile name."))

    current_doc = frappe.get_doc("Staff Profile", docname)
    if current_doc.docstatus != 1 or current_doc.status != "Valid":
        frappe.throw(
            _("A new Staff Profile version can only be created from a submitted profile in status Valid.")
        )
    base_name, current_suffix, available_versions = get_versioned_documents("Staff Profile", docname)
    newer_versions = get_newer_active_versions(available_versions, current_suffix)

    if newer_versions:
        frappe.throw(
            _(
                "Cannot create a new version for Staff Profile {0}. A newer non-cancelled version already exists: {1}. "
                "Only the latest Staff Profile version may be used as the source for the next draft. "
                "Cancelled newer versions are ignored, but active newer versions still block creating another draft. "
                "Please continue from the newest active version instead."
            ).format(frappe.bold(docname), ", ".join(frappe.bold(name) for name in newer_versions)),
            title=_("Newer Version Exists"),
        )
    next_suffix = get_next_suffix(available_versions, current_suffix)
    if next_suffix > 99:
        frappe.throw(
            _("Cannot create a new version for Staff Profile {0} because the version suffix would exceed 99.").format(
                frappe.bold(docname)
            ),
            title=_("Version Limit Reached"),
        )
    new_name = "{0}-{1}".format(base_name, next_suffix)
    if frappe.db.exists("Staff Profile", new_name):
        frappe.throw(
            _("Cannot create a new version because the target Staff Profile name {0} already exists.").format(
                frappe.bold(new_name)
            ),
            title=_("Duplicate Version Name"),
        )
    new_doc = frappe.copy_doc(current_doc)
    _copy_assignments_without_instruction_links(getattr(new_doc, "competencies", None) or [])
    new_doc.name = new_name
    new_doc.docstatus = 0
    new_doc.status = "Draft"
    new_doc.amended_from = current_doc.name
    new_doc.employee_signed_on = None
    new_doc.employee_user = None
    new_doc.employee_signature = None
    new_doc.process_owner_signed_on = None
    new_doc.process_owner = None
    new_doc.process_owner_signature = None
    new_doc.owner = frappe.session.user
    new_doc.creation = None
    new_doc.modified = None
    new_doc.modified_by = None
    new_doc.flags.name_set = True
    new_doc.insert()
    frappe.db.commit()
    return {"name": new_doc.name}


@frappe.whitelist()
def sign_staff_profile(docname, user, password, role):
    if not docname or not user or not password or not role:
        frappe.throw(_("Missing required sign parameters."))

    doc = frappe.get_doc("Staff Profile", docname)
    if doc.status != "To Sign":
        frappe.throw(_("This Staff Profile is not awaiting signature."))

    employee_user = frappe.db.get_value("Employee", doc.employee, "user_id") if doc.employee else None
    process_owner = get_process_owner_for_employee(doc.employee)

    if role == "employee":
        if not employee_user:
            frappe.throw(_("No employee user is linked to this Employee."))
        if user != employee_user:
            frappe.throw(_("Only the employee can sign as employee."))
        target_field = "employee_signature"
    elif role == "process_owner":
        if not process_owner:
            frappe.throw(_("No process owner could be determined for this employee."))
        if user != process_owner:
            frappe.throw(_("Only the process owner may sign as process owner."))
        target_field = "process_owner_signature"
    else:
        frappe.throw(_("Invalid sign role."))

    signing_success = signing_sign(
        "Staff Profile",
        docname,
        user,
        password,
        target_field=target_field,
        submit=False,
    )
    if not signing_success:
        frappe.throw(_("Signing failed."))

    doc = frappe.get_doc("Staff Profile", docname)
    if role == "employee":
        doc.employee_user = user
        doc.employee_signed_on = nowdate()
    else:
        doc.process_owner = user
        doc.process_owner_signed_on = nowdate()

    if doc.employee_signed_on and doc.process_owner_signed_on:
        doc.status = "Valid"
        doc.valid_since = nowdate()
        archive_previous_valid_profiles(doc.employee, docname)

    doc.save(ignore_permissions=True)
    frappe.db.commit()
    return True


def archive_previous_valid_profiles(employee, current_name):
    if not employee:
        return

    valid_profiles = frappe.db.get_all(
        "Staff Profile",
        filters={
            "employee": employee,
            "status": "Valid",
            "docstatus": 1,
            "name": ["!=" , current_name],
        },
        fields=["name"],
    )
    for profile in valid_profiles:
        frappe.db.set_value("Staff Profile", profile.get("name"), "status", "Archived", update_modified=False)


def _get_invalid_competency_assignments(assignments):
    competency_names = []
    for row in assignments or []:
        competency_name = row.get("competency")
        if competency_name and competency_name not in competency_names:
            competency_names.append(competency_name)

    competencies_by_name = {}
    if competency_names:
        competency_docs = frappe.get_all(
            "Competency",
            filters={"name": ["in", competency_names]},
            fields=["name", "title", "status", "docstatus"],
        )
        competencies_by_name = {doc.get("name"): doc for doc in competency_docs}

    invalid_rows = []
    for row in assignments or []:
        competency_name = row.get("competency")
        competency_doc = competencies_by_name.get(competency_name)

        if not competency_name:
            invalid_rows.append({
                "row": row.idx,
                "competency": _("not set"),
                "reason": _("No Competency is selected in this row."),
            })
            continue

        if not competency_doc:
            invalid_rows.append({
                "row": row.idx,
                "competency": competency_name,
                "reason": _("The linked Competency does not exist or is no longer accessible."),
            })
            continue

        competency_status = competency_doc.get("status") or _("not set")
        competency_docstatus = cint(competency_doc.get("docstatus"))
        if competency_docstatus != 1 or competency_doc.get("status") != "Valid":
            reason_parts = []
            if competency_docstatus != 1:
                reason_parts.append(
                    _("document status is {0} instead of Submitted (1)").format(frappe.bold(str(competency_docstatus)))
                )
            if competency_doc.get("status") != "Valid":
                reason_parts.append(
                    _("status is {0} instead of Valid").format(frappe.bold(competency_status))
                )
            invalid_rows.append({
                "row": row.idx,
                "competency": competency_name,
                "reason": "; ".join(reason_parts),
            })
    return invalid_rows


def _throw_if_invalid_competency_versions(assignments):
    invalid_rows = _get_invalid_competency_assignments(assignments)
    if not invalid_rows:
        return

    details = "<br>".join(
        _("Row {0}: Competency {1} is invalid because {2}.").format(
            frappe.bold(row.get("row")),
            frappe.bold(row.get("competency")),
            row.get("reason"),
        )
        for row in invalid_rows
    )
    frappe.throw(
        _(
            "This Staff Profile contains at least one invalid Competency version and therefore cannot be saved or submitted.<br><br>{0}<br><br>"
            "Please replace every invalid Competency with a submitted Competency in status Valid before continuing."
        ).format(details),
        title=_("Invalid Competency Version"),
    )


def _update_achieved_competencies_for_staff_profile(staff_profile):
    if not getattr(staff_profile, "employee", None):
        return

    trainee = frappe.db.get_value("Employee", staff_profile.employee, "user_id")
    if not trainee:
        return

    update_competency_assignments_for_trainee(trainee)


def _copy_assignments_without_instruction_links(assignments):
    if not assignments:
        return assignments

    for assignment in assignments:
        if getattr(assignment, "competency_instruction", None):
            assignment.competency_instruction = ""
    return assignments


def _clean_legacy_import_value(value):
    if value is None:
        return ""
    cleaned = str(value).replace("\x00", "").replace("\ufeff", "").replace("\r", "").replace("\n", " ")
    cleaned = cleaned.replace("\v", "").replace("\f", "")
    return cleaned.strip()


def build_legacy_competency_description(title, legacy_description):
    title = _clean_legacy_import_value(title)
    legacy_description = _clean_legacy_import_value(legacy_description)

    if len(title) <= 140:
        return legacy_description or title

    description = f"Aufgabe: {title}"
    if legacy_description:
        description = f"{description}\n\n{legacy_description}"
    return description


def merge_legacy_competency_descriptions(existing_description, new_description):
    existing_description = (existing_description or "").strip()
    new_description = (new_description or "").strip()

    if not existing_description:
        return new_description
    if not new_description:
        return existing_description
    if existing_description == new_description:
        return existing_description

    parts = []
    for description in (existing_description, new_description):
        if not description:
            continue
        if description not in parts:
            parts.append(description)
    return "\n\n".join(parts)


def aggregate_legacy_competency_rows(rows):
    aggregated = {}
    for row in rows or []:
        title = _clean_legacy_import_value(row.get("title"))
        if not title:
            continue

        existing = aggregated.setdefault(
            title,
            {
                "title": title,
                "description": "",
                "department_names": [],
                "scope_name": "",
                "entries": [],
            },
        )
        department_names = [department for department in (row.get("department_names") or []) if department]
        existing["department_names"] = [
            department
            for department in dict.fromkeys(existing["department_names"] + department_names)
            if department
        ]
        description = _clean_legacy_import_value(row.get("description"))
        existing["description"] = merge_legacy_competency_descriptions(existing["description"], description)

        if not existing["scope_name"] and row.get("scope_name"):
            existing["scope_name"] = _clean_legacy_import_value(row.get("scope_name"))

        existing["entries"].append(row)
    return aggregated


def normalize_legacy_visa(value):
    cleaned = _clean_legacy_import_value(value)
    if not cleaned:
        return ""
    if len(cleaned) == 3:
        return cleaned[:2].upper() + cleaned[2:]
    return cleaned


def normalize_legacy_date(value):
    cleaned = _clean_legacy_import_value(value)
    if not cleaned:
        return None
    for fmt in ("%d.%m.%Y", "%d.%m.%y", "%Y-%m-%d", "%d.%m.%Y %H:%M:%S"):
        try:
            return datetime.strptime(cleaned, fmt).strftime("%Y-%m-%d")
        except ValueError:
            pass
    return None


def split_competency_departments(value):
    cleaned = _clean_legacy_import_value(value)
    if not cleaned:
        return []
    return [part.strip() for part in cleaned.split("\\") if part and part.strip()]


def _make_qms_doc(doctype, name=None, values=None):
    if values is None and isinstance(name, dict):
        values = name
        name = None
    values = values or {}

    if doctype == "Competency":
        from microsynth.qms.doctype.competency.competency import Competency as Controller
        if name:
            return Controller(doctype, {"name": name})
        return Controller({"doctype": doctype, **values})
    if doctype == "Staff Profile":
        from microsynth.qms.doctype.staff_profile.staff_profile import StaffProfile as Controller
        if name:
            return Controller(doctype, {"name": name})
        return Controller({"doctype": doctype, **values})
    if doctype == "Competency Instruction":
        from microsynth.qms.doctype.competency_instruction.competency_instruction import CompetencyInstruction as Controller
        if name:
            return Controller(doctype, {"name": name})
        return Controller({"doctype": doctype, **values})
    if name:
        return frappe.get_doc(doctype, name)
    return frappe.get_doc({"doctype": doctype, **values})


@frappe.whitelist()
def import_staff_profiles_from_legacy_competency_export(file_path, expected_line_length=10, dry_run=True, verbose=True):
    """
    Import a legacy FileMaker competency export into draft Staff Profiles and submitted Competency Instructions.

    The source file uses semicolon-separated columns in fixed positions, not names. The last data columns are:
    0: Prozess (ignored)
    1: Department ERP
    2: NameVorname (ignored)
    3: Kürzel - Visa
    4: Bereich - Scope
    5: Aufgabe - Title
    6: Anmerkungen - Description
    7: Kompetenz Datum
    8: Kompetenz Visum
    9: Competence - Role

    bench execute microsynth.qms.doctype.staff_profile.staff_profile.import_staff_profiles_from_legacy_competency_export --kwargs "{'file_path': '/mnt/erp_share/Migration/Kompetenzen_Schulungen/Mitarbeiter_für ERP_bearbeitet_CSc16.10.26.csv', 'dry_run': True, 'verbose': True}"
    """
    if not file_path:
        frappe.throw(_("Missing CSV/TSV file path."))

    imported_profiles = []
    imported_instructions = []
    imported_competencies = []

    def warn(message, row=None, row_number=None):
        details = []
        if row_number is not None:
            details.append(f"row_number={row_number}")
        if row is not None:
            details.append(f"row={row}")
        suffix = f" | {' | '.join(details)}" if details else ""
        print(f"WARNING: {message}{suffix}")

    def ensure_competency(title, description, department_names, scope_name=None):
        title = _clean_legacy_import_value(title)
        title_for_storage = title
        if len(title_for_storage) > 140:
            title_for_storage = f"{title_for_storage[:137]}..."
        legacy_description = _clean_legacy_import_value(description)
        if not title:
            return None
        description_text = build_legacy_competency_description(title, legacy_description)
        department_names = [department for department in (department_names or []) if department]

        existing_name = frappe.db.exists("Competency", {"title": title_for_storage})
        if existing_name:
            competency = _make_qms_doc("Competency", existing_name)
            linked_departments = {row.department for row in (competency.departments or []) if row.department}
            changed = False
            for department in department_names:
                if department not in linked_departments:
                    competency.append("departments", {"department": department})
                    linked_departments.add(department)
                    changed = True

            merged_description = merge_legacy_competency_descriptions(
                competency.description,
                description_text,
            )
            if merged_description != _clean_legacy_import_value(competency.description):
                competency.description = merged_description
                changed = True

            if not any(row.competency_prerequisite == "On-the-Job Instruction" for row in (competency.prerequisite_types or [])):
                competency.append("prerequisite_types", {"competency_prerequisite": "On-the-Job Instruction"})
                changed = True
            if changed and competency.docstatus == 0:
                competency.save(ignore_permissions=True)
                competency.submit()
            elif changed and competency.docstatus == 1:
                competency.save(ignore_permissions=True)
            return competency.name

        scope_value = None
        if scope_name:
            scope_name = _clean_legacy_import_value(scope_name)
            if scope_name:
                if not frappe.db.exists("Competency Scope", scope_name):
                    scope_doc = frappe.get_doc({"doctype": "Competency Scope", "scope": scope_name})
                    scope_doc.insert(ignore_permissions=True)
                scope_value = scope_name

        competency = _make_qms_doc("Competency", {
            "title": title_for_storage,
            "description": description_text,
            "scope": scope_value,
            "prerequisite_types": [{"competency_prerequisite": "On-the-Job Instruction"}],
        })
        for department in department_names:
            competency.append("departments", {"department": department})
        competency.insert(ignore_permissions=True)
        competency.submit()
        return competency.name

    def ensure_profile_draft(employee_name):
        existing_name = frappe.db.get_value(
            "Staff Profile",
            {
                "employee": employee_name,
                "docstatus": 0,
            },
            "name",
        )
        if existing_name:
            return _make_qms_doc("Staff Profile", existing_name)

        profile = _make_qms_doc("Staff Profile", {
            "employee": employee_name,
            "status": "Draft",
        })
        profile.insert(ignore_permissions=True)
        return profile

    parsed_rows = []
    with open(file_path, newline="") as source_file:
        csv_reader = csv.reader((line.replace("\0", "") for line in source_file), delimiter=";")
        first_row = True
        for row_number, row in enumerate(csv_reader, start=1):
            if not row:
                continue
            if first_row:
                first_row = False
                if any(_clean_legacy_import_value(value).lower().startswith("prozess") or _clean_legacy_import_value(value).lower().startswith("department") for value in row[:3]):
                    continue

            try:
                if len(row) < expected_line_length:
                    warn(f"Skipping row because it has {len(row)} cells and expected {expected_line_length}.", row=row, row_number=row_number)
                    continue

                department_text = row[1]
                visa_value = normalize_legacy_visa(row[3])
                scope_name = _clean_legacy_import_value(row[4])
                title = _clean_legacy_import_value(row[5])
                description = _clean_legacy_import_value(row[6])
                competency_date = normalize_legacy_date(row[7])
                instruction_visa = _clean_legacy_import_value(row[8])
                role_value = _clean_legacy_import_value(row[9]).title()
                department_names = split_competency_departments(department_text)

                if not department_names:
                    warn("Skipping row due to missing Department ERP value.", row=row, row_number=row_number)
                    continue
                if not visa_value:
                    warn("Skipping row due to missing employee visa.", row=row, row_number=row_number)
                    continue
                if not title:
                    warn("Skipping row due to missing competency title.", row=row, row_number=row_number)
                    continue
                if role_value not in ("Main", "Substitute"):
                    warn(f"Skipping row due to invalid Competence - Role '{role_value}'.", row=row, row_number=row_number)
                    continue

                if not competency_date or not instruction_visa:
                    warn(
                        "Row imported without creating a Competency Instruction because the competency date or visa is missing.",
                        row=row,
                        row_number=row_number,
                    )

                missing_departments = [department for department in department_names if not frappe.db.exists("Department", department)]
                if missing_departments:
                    warn(f"Skipping row because the Department(s) do not exist: {', '.join(missing_departments)}.", row=row, row_number=row_number)
                    continue

                employee_name = frappe.db.get_value("Employee", {"visa": visa_value})
                if not employee_name:
                    employee_matches = frappe.get_all("Employee", filters={"visa": ["like", f"%{visa_value}%"]}, fields=["name", "visa"])
                    if len(employee_matches) != 1:
                        warn(f"Skipping row because no unique Employee matches the visa '{visa_value}'.", row=row, row_number=row_number)
                        continue
                    employee_name = employee_matches[0].get("name")

                parsed_rows.append({
                    "title": title,
                    "description": description,
                    "department_names": department_names,
                    "scope_name": scope_name,
                    "employee_name": employee_name,
                    "role_value": role_value,
                    "competency_date": competency_date,
                    "instruction_visa": instruction_visa,
                    "row_number": row_number,
                    "row": row,
                })
            except Exception as exc:
                warn(f"Error importing row: {exc}", row=row, row_number=row_number)
                continue

    aggregated_rows = aggregate_legacy_competency_rows(parsed_rows)
    for title, aggregated in aggregated_rows.items():
        competency_name = ensure_competency(
            aggregated["title"],
            aggregated["description"],
            aggregated["department_names"],
            aggregated["scope_name"],
        )
        if not competency_name:
            warn("Skipping competency because it could not be created.", row=aggregated["entries"][0].get("row"), row_number=aggregated["entries"][0].get("row_number"))
            continue

        for entry in aggregated["entries"]:
            employee_name = entry["employee_name"]
            role_value = entry["role_value"]
            competency_date = entry["competency_date"]
            instruction_visa = entry["instruction_visa"]

            profile = ensure_profile_draft(employee_name)
            assignment_exists = False
            assignment_name = None
            for assignment in profile.competencies or []:
                if assignment.competency == competency_name and assignment.responsibility_role == role_value:
                    assignment_exists = True
                    assignment_name = assignment.name
                    break

            if not assignment_exists:
                profile.append("competencies", {
                    "competency": competency_name,
                    "responsibility_role": role_value,
                    "status": "Planned",
                })
                profile.save(ignore_permissions=True)
                assignment_name = profile.competencies[-1].name

            if not assignment_name:
                warn("Skipping row because the Staff Profile assignment could not be created.", row=entry["row"], row_number=entry["row_number"])
                continue

            if competency_date and instruction_visa:
                instruction_doc = _make_qms_doc("Competency Instruction", {
                    "instructor": frappe.session.user or "Administrator",
                    "date": competency_date,
                    "trainee": employee_name,
                    "competency_assignment": assignment_name,
                    "remarks": instruction_visa,
                })
                instruction_doc.insert(ignore_permissions=True)
                instruction_doc.submit()
                imported_instructions.append(instruction_doc.name)

            imported_profiles.append(profile.name)
            imported_competencies.append(competency_name)
            if verbose:
                print(f"INFO: imported row {entry['row_number']}: {entry['row']}")

    if verbose:
        print(f"INFO: imported {len(imported_profiles)} Staff Profiles, {len(imported_instructions)} Competency Instructions and {len(imported_competencies)} Competencies.")

    return {
        "profiles": imported_profiles,
        "instructions": imported_instructions,
        "competencies": imported_competencies,
    }
