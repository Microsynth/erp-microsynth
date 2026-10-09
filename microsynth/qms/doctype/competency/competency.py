# -*- coding: utf-8 -*-
# Copyright (c) 2026, Microsynth
# For license information, please see license.txt

from __future__ import unicode_literals

import frappe
from frappe import _
from frappe.model.document import Document

from microsynth.qms.doctype.qm_document.qm_document import get_valid_version
from microsynth.qms.versioning import get_newer_active_versions, get_next_suffix, get_versioned_documents


class Competency(Document):
    def validate(self):
        validate_prerequisite_types(self)
        validate_linked_qm_documents(self)

    def before_cancel(self):
        validate_cancel_permission(self)

    def on_submit(self):
        self.status = "Valid"
        invalidate_previous_versions(self.name)
        self.save()
        frappe.db.commit()

    def on_cancel(self):
        self.status = "Invalid"
        self.save()
        frappe.db.commit()


def invalidate_previous_versions(docname):
    base_name, current_suffix, available_versions = get_versioned_documents("Competency", docname)

    for suffix, version_name, status, docstatus in available_versions:
        if suffix >= current_suffix or version_name == docname or docstatus != 1:
            continue
        frappe.db.set_value("Competency", version_name, "status", "Invalid", update_modified=False)


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
    new_doc.insert()

    frappe.db.commit()
    return {"name": new_doc.name}
