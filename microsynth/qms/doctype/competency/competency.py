# -*- coding: utf-8 -*-
# Copyright (c) 2026, Microsynth
# For license information, please see license.txt

from __future__ import unicode_literals

import csv
import re

import frappe
from frappe import _
from frappe.model.document import Document

from microsynth.qms.doctype.qm_document.qm_document import get_valid_version
from microsynth.qms.versioning import get_newer_active_versions, get_next_suffix, get_versioned_documents, split_versioned_name


class Competency(Document):
    def validate(self):
        validate_prerequisite_types(self)
        if self.docstatus == 0 or self.status != "Invalid":
            validate_linked_qm_documents(self)

    def before_cancel(self):
        validate_cancel_permission(self)

    def before_submit(self):
        base_name, current_suffix, available_versions = get_versioned_documents("Competency", self.name)
        newer_submitted_versions = [
            name for suffix, name, status, docstatus in available_versions
            if suffix > current_suffix and docstatus == 1
        ]
        if newer_submitted_versions:
            frappe.throw(
                _("Cannot submit Competency {0} because a newer submitted version already exists: {1}.").format(
                    frappe.bold(self.name), ", ".join(frappe.bold(name) for name in newer_submitted_versions)
                ),
                title=_("Newer Version Exists"),
            )
        self.status = "Valid"

    def on_submit(self):
        invalidate_previous_versions(self.name)

    def on_cancel(self):
        self.status = "Invalid"
        self.save()
        frappe.db.commit()


def invalidate_previous_versions(docname):
    base_name, current_suffix, available_versions = get_versioned_documents("Competency", docname)

    for suffix, version_name, status, docstatus in available_versions:
        if suffix >= current_suffix or version_name == docname or docstatus != 1 or status == "Invalid":
            continue
        previous_version = frappe.get_doc("Competency", version_name)
        previous_version.status = "Invalid"
        previous_version.save(ignore_permissions=True)


def invalidate_competencies_for_qm_document(qm_document_name):
    links = frappe.get_all(
        "QM Document Link",
        filters={"parenttype": "Competency", "parentfield": "qm_documents", "qm_document": qm_document_name},
        fields=["parent"],
    )
    for competency_name in sorted({row.get("parent") for row in links if row.get("parent")}):
        competency = frappe.get_doc("Competency", competency_name)
        if competency.docstatus != 1 or competency.status != "Valid":
            continue
        competency.status = "Invalid"
        competency.save(ignore_permissions=True)
        competency.add_comment(
            "Comment",
            _("Automatically invalidated because linked QM Document {0} was invalidated.").format(qm_document_name),
        )
        _create_qm_document_replacement(competency)


def renew_competencies_for_qm_document(qm_document_name):
    base_name, _ = split_versioned_name(qm_document_name)
    links = frappe.get_all(
        "QM Document Link",
        filters={
            "parenttype": "Competency",
            "parentfield": "qm_documents",
            "qm_document": ["like", "{0}-%".format(base_name)],
        },
        fields=["parent", "qm_document"],
    )
    competency_names = {
        row.get("parent") for row in links
        if row.get("parent") and split_versioned_name(row.get("qm_document") or "")[0] == base_name
    }
    for competency_name in sorted(competency_names):
        competency = frappe.get_doc("Competency", competency_name)
        _create_qm_document_replacement(competency)


def _create_qm_document_replacement(competency):
    if competency.docstatus != 1 or competency.status != "Invalid":
        return
    base_name, current_suffix, available_versions = get_versioned_documents("Competency", competency.name)
    if any(suffix > current_suffix and docstatus == 1 for suffix, name, status, docstatus in available_versions):
        return

    replacements = {}
    for row in competency.qm_documents or []:
        if not row.qm_document or frappe.db.get_value("QM Document", row.qm_document, "status") == "Valid":
            continue
        valid_document = get_valid_version(split_versioned_name(row.qm_document)[0])
        if not valid_document:
            return
        replacements[row.qm_document] = valid_document
    if not replacements:
        return

    next_suffix = get_next_suffix(available_versions, current_suffix)
    if next_suffix > 99:
        frappe.throw(
            _("Cannot create a new version for Competency {0} because the version suffix would exceed 99.").format(
                frappe.bold(competency.name)
            ),
            title=_("Version Limit Reached"),
        )
    new_doc = _copy_competency_version(competency, "{0}-{1}".format(base_name, next_suffix))
    for row in new_doc.qm_documents or []:
        replacement = replacements.get(row.qm_document)
        if replacement:
            row.qm_document = replacement.get("name")
            row.title = replacement.get("title")
    new_doc.flags.ignore_permissions = True
    new_doc.insert(ignore_permissions=True)
    new_doc.submit()
    new_doc.add_comment(
        "Comment",
        _("Automatically created from Competency {0} with updated QM Document versions.").format(competency.name),
    )
    return new_doc


def validate_cancel_permission(doc):
    privileged_process_prefixes = ("1.1", "1.2", "1.3")
    globally_authorized_processes = frappe.get_all(
        "QM Process Owner",
        filters={"process_owner": frappe.session.user},
        fields=["qm_process"],
    )
    if any(
        (process.get("qm_process") or "").startswith(privileged_process_prefixes)
        for process in globally_authorized_processes
    ):
        return

    linked_departments = sorted(
        {row.department for row in (doc.departments or []) if getattr(row, "department", None)}
    )
    if not linked_departments:
        frappe.throw(
            _(
                "This Competency cannot be cancelled because it has no linked Department with a QM Process Owner who can authorize the cancellation."
            ),
            title=_("Cancellation Not Allowed"),
        )
    department_process_links = frappe.get_all(
        "QM Process Link",
        filters={
            "parent": ["in", linked_departments],
            "parenttype": "Department",
        },
        fields=["parent", "qm_process"],
    )
    linked_processes = sorted(
        {row.get("qm_process") for row in department_process_links if row.get("qm_process")}
    )
    if not linked_processes:
        frappe.throw(
            _(
                "This Competency cannot be cancelled because none of its linked Departments has a QM Process assigned."
            ),
            title=_("Cancellation Not Allowed"),
        )
    owned_processes = frappe.get_all(
        "QM Process Owner",
        filters={
            "qm_process": ["in", linked_processes],
            "process_owner": frappe.session.user,
        },
        fields=["qm_process"],
    )
    if owned_processes:
        return

    frappe.throw(
        _(
            "Only a QM Process Owner of a QM Process linked on a Department of this Competency may cancel it."
        ),
        title=_("Cancellation Not Allowed"),
    )


def validate_linked_qm_documents(doc):
    replacements = []
    invalid_rows = []

    for row in doc.qm_documents or []:
        qm_document_name = row.qm_document
        if not qm_document_name:
            continue

        qm_document_status = frappe.db.get_value("QM Document", qm_document_name, "status")
        if qm_document_status == "Valid":
            continue

        base_name = qm_document_name.split("-")[0]
        valid_doc = get_valid_version(base_name)
        if valid_doc:
            row.qm_document = valid_doc.get("name")
            row.title = valid_doc.get("title")
            replacements.append({
                "row": row.idx,
                "original": qm_document_name,
                "replacement": valid_doc.get("name"),
            })
            continue

        invalid_rows.append({
            "row": row.idx,
            "qm_document": qm_document_name,
            "status": qm_document_status or _("not found"),
        })
    if invalid_rows:
        details = "<br>".join(
            _("Row {0}: QM Document {1} is not valid (current status: {2}) and no valid version could be found.").format(
                frappe.bold(row.get("row")),
                frappe.bold(row.get("qm_document")),
                frappe.bold(row.get("status")),
            )
            for row in invalid_rows
        )
        frappe.throw(
            _(
                "This Competency cannot be saved because at least one linked QM Document is not valid and no valid replacement version could be proposed.<br><br>{0}<br><br>"
                "Please replace the affected QM Documents with a valid version and try again."
            ).format(details),
            title=_("Invalid QM Document Version"),
        )
    if replacements:
        details = "<br>".join(
            _("Row {0}: replaced QM Document {1} with valid version {2}.").format(
                frappe.bold(row.get("row")),
                frappe.bold(row.get("original")),
                frappe.bold(row.get("replacement")),
            )
            for row in replacements
        )
        frappe.msgprint(
            _(
                "One or more linked QM Documents were not valid. The corresponding valid version was proposed automatically before saving:<br><br>{0}"
            ).format(details),
            title=_("Linked QM Documents Updated"),
            indicator="orange",
        )


def validate_prerequisite_types(doc):
    prerequisite_rows = list(doc.prerequisite_types or [])

    seen_prerequisites = set()
    duplicate_prerequisites = []
    for row in prerequisite_rows:
        prerequisite_type = getattr(row, "competency_prerequisite", None)
        if not prerequisite_type:
            continue

        if prerequisite_type in seen_prerequisites:
            duplicate_prerequisites.append(prerequisite_type)
            continue

        seen_prerequisites.add(prerequisite_type)

    if duplicate_prerequisites:
        duplicates = sorted(set(duplicate_prerequisites))
        frappe.throw(
            _(
                "Each Prerequisite Type may only be linked once. Duplicate entries were found for: {0}."
            ).format(", ".join(frappe.bold(prerequisite) for prerequisite in duplicates)),
            title=_("Duplicate Prerequisite Type"),
        )
    linked_qm_documents = [row.qm_document for row in (doc.qm_documents or []) if getattr(row, "qm_document", None)]
    linked_training_templates = [
        row.training_template for row in (doc.trainings or []) if getattr(row, "training_template", None)
    ]
    if linked_qm_documents and "QM Document" not in seen_prerequisites:
        doc.append("prerequisite_types", {"competency_prerequisite": "QM Document"})
        seen_prerequisites.add("QM Document")

    if linked_training_templates and "Training" not in seen_prerequisites:
        doc.append("prerequisite_types", {"competency_prerequisite": "Training"})
        seen_prerequisites.add("Training")

    if not doc.prerequisite_types:
        frappe.throw(
            _("This Competency cannot be saved without at least one Prerequisite Type."),
            title=_("Missing Prerequisite Type"),
        )
    if "QM Document" in seen_prerequisites and not linked_qm_documents:
        frappe.throw(
            _(
                "The Prerequisite Type <b>QM Document</b> is set, but no QM Document is linked. Please link at least one QM Document or remove the Prerequisite Type <b>QM Document</b>."
            ),
            title=_("Orphaned QM Document Prerequisite"),
        )
    if "Training" in seen_prerequisites and not linked_training_templates:
        frappe.throw(
            _(
                "The Prerequisite Type <b>Training</b> is set, but no QM Training Template is linked. Please link at least one QM Training Template or remove the Prerequisite Type <b>Training</b>."
            ),
            title=_("Orphaned Training Prerequisite"),
        )


@frappe.whitelist()
def get_linked_staff_profiles(docname):
    if not docname:
        return {"count": 0, "names": []}

    staff_profiles = frappe.db.sql(
        """
        SELECT DISTINCT parent
        FROM `tabCompetency Assignment`
        WHERE competency = %s AND parenttype = 'Staff Profile'
        ORDER BY parent
        """,
        (docname,),
        as_dict=True,
    )
    names = [row.get("parent") for row in staff_profiles if row.get("parent")]
    return {"count": len(names), "names": names}


@frappe.whitelist()
def get_on_the_job_instruction_requirements(competency_names=None):
    competency_names = frappe.parse_json(competency_names) if competency_names else []
    competency_names = [name for name in (competency_names or []) if name]
    if not competency_names:
        return {}

    linked_rows = frappe.get_all(
        "Competency Prerequisite Type Link",
        filters={
            "parent": ["in", competency_names],
            "parenttype": "Competency",
            "competency_prerequisite": "On-the-Job Instruction",
        },
        fields=["parent"],
    )
    linked_competencies = {row.get("parent") for row in linked_rows if row.get("parent")}
    return {name: name in linked_competencies for name in competency_names}


@frappe.whitelist()
def create_new_version(docname):
    if not docname:
        frappe.throw(_("Missing Competency name."))

    current_doc = frappe.get_doc("Competency", docname)
    if current_doc.docstatus != 1 or current_doc.status != "Valid":
        frappe.throw(
            _("A new Competency version can only be created from a submitted competency in status Valid.")
        )
    base_name, current_suffix, available_versions = get_versioned_documents("Competency", docname)
    newer_versions = get_newer_active_versions(available_versions, current_suffix)

    if newer_versions:
        frappe.throw(
            _(
                "Cannot create a new version for Competency {0}. A newer non-cancelled version already exists: {1}. "
                "Only the latest Competency version may be used as the source for the next draft. "
                "Cancelled newer versions are ignored, but active newer versions still block creating another draft. "
                "Please continue from the newest active version instead."
            ).format(frappe.bold(docname), ", ".join(frappe.bold(name) for name in newer_versions)),
            title=_("Newer Version Exists"),
        )
    next_suffix = get_next_suffix(available_versions, current_suffix)
    if next_suffix > 99:
        frappe.throw(
            _("Cannot create a new version for Competency {0} because the version suffix would exceed 99.").format(
                frappe.bold(docname)
            ),
            title=_("Version Limit Reached"),
        )
    new_name = "{0}-{1}".format(base_name, next_suffix)
    if frappe.db.exists("Competency", new_name):
        frappe.throw(
            _("Cannot create a new version because the target Competency name {0} already exists.").format(
                frappe.bold(new_name)
            ),
            title=_("Duplicate Version Name"),
        )
    new_doc = _copy_competency_version(current_doc, new_name)
    new_doc.insert()
    frappe.db.commit()
    return {"name": new_doc.name}


def _copy_competency_version(current_doc, new_name):
    new_doc = frappe.copy_doc(current_doc)
    new_doc.name = new_name
    new_doc.docstatus = 0
    new_doc.status = "Draft"
    new_doc.amended_from = current_doc.name
    new_doc.owner = frappe.session.user
    new_doc.creation = None
    new_doc.modified = None
    new_doc.modified_by = None
    new_doc.flags.name_set = True
    return new_doc


COMPETENCY_IMPORT_MAX_TITLE_LENGTH = 140
COMPETENCY_IMPORT_MANDATORY_COLUMNS = 5
COMPETENCY_IMPORT_FIRST_QM_DOCUMENT_COLUMN = 5


def import_competencies(path, dry_run=True, verbose=False):
    """
    Import Competencies from a semicolon-separated CSV file. The first line is a header and is ignored,
    the column positions are fixed:

    0 Department(s), comma-separated (mandatory)
    1 Title, < 140 characters (mandatory)
    2 Prerequisite Type(s), comma-separated (mandatory)
    3 Scope, created if it does not exist (mandatory)
    4 Description (mandatory)
    5, 7, 9, ... QM Document (version suffix is removed, the Valid version is used)
    6, 8, 10, ... QM Document title (ignored)

    Competencies are inserted and submitted (status Valid). A Competency is not imported if a non-cancelled Competency with
    the same Title, Departments and Prerequisite Types already exists.

    Nothing is written to the database if dry_run is set (default).

    bench execute microsynth.qms.doctype.competency.competency.import_competencies --kwargs "{'path': '"/home/libracore/comp.csv"', 'dry_run': True, 'verbose': True}"
    """
    dry_run = _to_bool(dry_run)
    verbose = _to_bool(verbose)
    mode = "DRY RUN" if dry_run else "IMPORT"
    summary = {"created": 0, "skipped_existing": 0, "errors": 0, "warnings": 0, "scopes_created": 0}

    def log(message):
        if verbose:
            print(message)

    def warn(line_number, message):
        summary["warnings"] += 1
        print(f"WARNING (line {line_number}): {message}")

    def error(line_number, message):
        summary["errors"] += 1
        print(f"ERROR (line {line_number}): {message}")

    try:
        with open(path, "r", encoding="utf-8-sig", newline="") as csv_file:
            rows = list(csv.reader(csv_file, delimiter=";"))
    except (OSError, UnicodeDecodeError, csv.Error) as err:
        print(f"ERROR: Unable to read '{path}': {err}")
        summary["errors"] += 1
        return summary

    print(f"[{mode}] Reading {max(len(rows) - 1, 0)} data row(s) from {path}")

    prerequisite_types = [
        row.name for row in frappe.get_all("Competency Prerequisite Type", fields=["name"])
    ]
    scopes_to_create = set()
    seen_keys = set()

    for line_number, raw_row in enumerate(rows[1:], start=2):
        row = [(cell or "").strip() for cell in raw_row]
        if not any(row):
            continue
        row += [""] * (COMPETENCY_IMPORT_MANDATORY_COLUMNS - len(row))

        department_cell, title, prerequisite_cell, scope, description = row[:COMPETENCY_IMPORT_MANDATORY_COLUMNS]
        log(f"Line {line_number}: processing '{title}'")

        missing = [
            str(index + 1)
            for index, value in enumerate(row[:COMPETENCY_IMPORT_MANDATORY_COLUMNS])
            if not value
        ]
        if missing:
            error(line_number, f"Mandatory column(s) {', '.join(missing)} empty. Skipping row.")
            continue

        if len(title) >= COMPETENCY_IMPORT_MAX_TITLE_LENGTH:
            error(
                line_number,
                f"Title has {len(title)} characters but must be shorter than {COMPETENCY_IMPORT_MAX_TITLE_LENGTH}. Skipping row.",
            )
            continue

        # Departments
        departments = _split_unique(department_cell)
        unknown_departments = [d for d in departments if not frappe.db.exists("Department", d)]
        if unknown_departments:
            error(line_number, f"Unknown Department(s): {', '.join(unknown_departments)}. Skipping row.")
            continue

        # Prerequisite Types
        resolved_types = []
        unknown_types = []
        for requested in _split_unique(prerequisite_cell):
            resolved = _resolve_prerequisite_type(requested, prerequisite_types)
            if not resolved:
                unknown_types.append(requested)
            elif resolved not in resolved_types:
                if resolved != requested:
                    log(f"Line {line_number}: Prerequisite Type '{requested}' mapped to '{resolved}'")
                resolved_types.append(resolved)
        if unknown_types:
            error(line_number, f"Unknown Prerequisite Type(s): {', '.join(unknown_types)}. Skipping row.")
            continue

        # Existing Competency?
        key = (title, frozenset(departments), frozenset(resolved_types))
        if key in seen_keys:
            existing = "earlier row of this file"
        else:
            existing = _find_existing_competency(title, departments, resolved_types)
        if existing:
            summary["skipped_existing"] += 1
            print(f"Line {line_number}: Competency '{title}' already exists ({existing}). Skipping row.")
            continue
        seen_keys.add(key)

        # QM Documents
        qm_documents = []
        for column in range(COMPETENCY_IMPORT_FIRST_QM_DOCUMENT_COLUMN, len(row), 2):
            qm_document = row[column]
            if not qm_document:
                continue
            base_name = re.sub(r"-\d+$", "", qm_document)
            valid_documents = frappe.get_all(
                "QM Document",
                filters={"name": ["like", f"{base_name}-%"], "status": "Valid"},
                fields=["name", "title"],
                order_by="version desc",
                limit_page_length=1,
            )
            if not valid_documents:
                warn(line_number, f"No Valid version found for QM Document '{qm_document}'. Skipping this QM Document.")
                continue
            valid_document = valid_documents[0]
            if valid_document.name in [d["qm_document"] for d in qm_documents]:
                continue
            log(f"Line {line_number}: QM Document '{qm_document}' -> '{valid_document.name}'")
            qm_documents.append({"qm_document": valid_document.name, "title": valid_document.title})

        # Scope
        scope_exists = frappe.db.exists("Competency Scope", scope)
        scope_missing = not scope_exists and scope not in scopes_to_create

        competency = frappe.get_doc({
            "doctype": "Competency",
            "title": title,
            "status": "Draft",
            "scope": scope,
            "description": description,
            "departments": [{"department": department} for department in departments],
            "prerequisite_types": [{"competency_prerequisite": ptype} for ptype in resolved_types],
            "qm_documents": qm_documents,
            "trainings": [],
        })
        try:
            if dry_run:
                competency.validate()
                if scope_missing:
                    scopes_to_create.add(scope)
                    summary["scopes_created"] += 1
                    print(f"Line {line_number}: would create Competency Scope '{scope}'")
                summary["created"] += 1
                print(f"Line {line_number}: would create and submit Competency '{title}'")
            else:
                if scope_missing:
                    frappe.get_doc({"doctype": "Competency Scope", "scope": scope}).insert()
                    scopes_to_create.add(scope)
                    summary["scopes_created"] += 1
                    print(f"Line {line_number}: created Competency Scope '{scope}'")
                competency.insert()
                competency.submit()
                frappe.db.commit()
                summary["created"] += 1
                print(f"Line {line_number}: created and submitted Competency {competency.name} '{title}'")
        except Exception as err:
            frappe.db.rollback()
            error(line_number, f"Unable to {'validate' if dry_run else 'create'} Competency '{title}': {err}. Skipping row.")

    if dry_run:
        frappe.db.rollback()

    print(
        f"[{mode}] Done: {summary['created']} {'would be ' if dry_run else ''}created, "
        f"{summary['skipped_existing']} already existing, {summary['scopes_created']} "
        f"Scope(s) {'would be ' if dry_run else ''}created, {summary['warnings']} warning(s), {summary['errors']} error(s)."
    )
    return summary


def _to_bool(value):
    if isinstance(value, str):
        return value.strip().lower() in ("1", "true", "yes", "y")
    return bool(value)


def _split_unique(cell):
    values = []
    for value in (cell or "").split(","):
        value = value.strip()
        if value and value not in values:
            values.append(value)
    return values


def _resolve_prerequisite_type(requested, available_types):
    """
    Match a requested Prerequisite Type against the existing ones: exact, case-insensitive,
    then ignoring a trailing plural 's' (e.g. 'QM Documents' -> 'QM Document').
    """
    if requested in available_types:
        return requested
    normalized = {name.casefold(): name for name in available_types}
    candidate = requested.casefold()
    if candidate in normalized:
        return normalized[candidate]
    for variant in (candidate[:-1] if candidate.endswith("s") else None, f"{candidate}s"):
        if variant and variant in normalized:
            return normalized[variant]
    return None


def _find_existing_competency(title, departments, prerequisite_types):
    """
    Return the name of a non-cancelled Competency with the same title, departments and
    prerequisite types, otherwise None.
    """
    candidates = frappe.get_all(
        "Competency", filters={"title": title, "docstatus": ["!=", 2]}, fields=["name"]
    )
    for candidate in candidates:
        name = candidate.name
        existing_departments = {
            row.department
            for row in frappe.get_all(
                "Department Link",
                filters={"parent": name, "parenttype": "Competency"},
                fields=["department"],
            )
        }
        existing_types = {
            row.competency_prerequisite
            for row in frappe.get_all(
                "Competency Prerequisite Type Link",
                filters={"parent": name, "parenttype": "Competency"},
                fields=["competency_prerequisite"],
            )
        }
        if existing_departments == set(departments) and existing_types == set(prerequisite_types):
            return name
    return None
