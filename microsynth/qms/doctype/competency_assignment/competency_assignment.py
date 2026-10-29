# -*- coding: utf-8 -*-
# Copyright (c) 2026, Microsynth
# For license information, please see license.txt

from __future__ import unicode_literals

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now_datetime

from microsynth.qms.versioning import split_versioned_name


class CompetencyAssignment(Document):
    def validate(self):
        _set_competency_achieved_on(self)


def _set_competency_achieved_on(assignment):
    if getattr(assignment, "status", None) != "Achieved":
        return

    previous_status = None
    if getattr(assignment, "name", None) and not getattr(assignment, "__islocal", False):
        previous_status = frappe.db.get_value("Competency Assignment", assignment.name, "status")

    if previous_status == "Achieved" or getattr(assignment, "competency_achieved_on", None):
        return

    assignment.competency_achieved_on = now_datetime()


def _mark_assignment_achieved(assignment_name):
    if not assignment_name:
        return

    assignment = frappe.get_doc("Competency Assignment", assignment_name)
    if assignment.status == "Achieved":
        return

    assignment.status = "Achieved"
    _set_competency_achieved_on(assignment)
    assignment.db_update()


def _matches_versioned_document_name(qm_document_name, candidate_name):
    if not qm_document_name or not candidate_name:
        return False
    base_name, _ = split_versioned_name(qm_document_name)
    candidate_base, _ = split_versioned_name(candidate_name)
    return base_name == candidate_base


def _get_signed_qm_training_records(trainee, qm_document_name):
    if not trainee or not qm_document_name:
        return []
    base_name, _ = split_versioned_name(qm_document_name)
    records = frappe.get_all(
        "QM Training Record",
        filters=[
            ["trainee", "=", trainee],
            ["document_type", "=", "QM Document"],
            ["document_name", "like", f"{base_name}-%"],
            ["signed_on", "is", "set"],
            ["docstatus", "=", 1],
        ],
        fields=["name", "document_name", "signed_on"],
    )
    # Reject similarly prefixed documents and SQL wildcard matches from other bases.
    return [record for record in records if _matches_versioned_document_name(
        qm_document_name, record.get("document_name")
    )]


def _get_passed_training_courses(trainee, training_template_name):
    if not trainee or not training_template_name:
        return []
    courses = frappe.get_all(
        "QM Training Course",
        filters={"training_template": training_template_name, "docstatus": 1},
        fields=["name", "training_template", "date", "int_ext", "internal_trainer", "external_trainer"],
    )
    course_names = [course.get("name") for course in courses]
    if not course_names:
        return []
    participants = frappe.get_all(
        "QM Training Course Participant",
        filters=[
            ["parent", "in", course_names],
            ["parenttype", "=", "QM Training Course"],
            ["parentfield", "=", "participants"],
            ["user", "=", trainee],
            ["outcome", "=", "Passed"],
        ],
        fields=["parent"],
    )
    passed_names = {row.get("parent") for row in participants}
    return [course for course in courses if course.get("name") in passed_names]


def _get_submitted_competency_instructions(competency_name, employee):
    if not competency_name or not employee:
        return []
    profiles = frappe.get_all("Staff Profile", filters={"employee": employee}, fields=["name"])
    profile_names = [row.get("name") for row in profiles]
    if not profile_names:
        return []
    assignments = frappe.get_all(
        "Competency Assignment",
        filters={"parenttype": "Staff Profile", "parent": ["in", profile_names], "competency": competency_name},
        fields=["name"],
    )
    assignment_names = [row.get("name") for row in assignments]
    if not assignment_names:
        return []
    # Reuse submitted instructions across profile versions, but never across
    # employees or Competency versions. Cancelled/draft instructions do not count.
    return frappe.get_all(
        "Competency Instruction",
        filters={"trainee": employee, "competency_assignment": ["in", assignment_names], "docstatus": 1},
        fields=["name", "instructor", "date"],
    )


def _competency_requirements_met(competency_name, trainee):
    if not competency_name or not trainee:
        return False
    return not get_competency_requirement_details(competency_name, trainee)["missing"]


def get_competency_requirement_details(competency_name, trainee, employee=None):
    """Use the same evidence and mandatory requirements for updates and reporting."""
    competency = frappe.get_doc("Competency", competency_name)
    details = {"instructions": [], "courses": [], "records": [], "missing": []}
    missing = details["missing"]
    if competency.docstatus != 1 or competency.status != "Valid":
        missing.append(_("The Competency must be submitted and Valid."))
    prerequisite_types = {
        row.competency_prerequisite
        for row in (competency.prerequisite_types or [])
        if getattr(row, "competency_prerequisite", None)
    }
    if not prerequisite_types:
        missing.append(_("The Competency has no prerequisite types configured."))
    supported_types = {"QM Document", "Training", "On-the-Job Instruction"}
    for prerequisite in sorted(prerequisite_types - supported_types):
        missing.append(_(f"Unsupported prerequisite type: {prerequisite}. Manual review is required."))

    employee = employee or (frappe.db.get_value("Employee", {"user_id": trainee}, "name") if trainee else None)
    details["instructions"] = _get_submitted_competency_instructions(competency_name, employee)
    if prerequisite_types & {"On-the-Job Instruction"} and not details["instructions"]:
        missing.append(_("Open the Staff Profile and confirm Instruction for this Competency."))

    if not trainee and prerequisite_types & {"QM Document", "Training"}:
        missing.append(_("The Employee has no linked User; document signatures and training participation cannot be verified; please contact HR."))

    if "QM Document" in prerequisite_types:
        linked_documents = [row.qm_document for row in (competency.qm_documents or []) if getattr(row, "qm_document", None)]
        if not linked_documents:
            missing.append(_("QM Document prerequisite: no QM Documents are linked."))
        for document_name in linked_documents:
            records = _get_signed_qm_training_records(trainee, document_name)
            details["records"].extend(records)
            if not records:
                title = frappe.db.get_value("QM Document", document_name, "title") or document_name
                missing.append(_(f"QM Document to sign: {document_name} ({title})."))

    if "Training" in prerequisite_types:
        linked_templates = [row.training_template for row in (competency.trainings or []) if getattr(row, "training_template", None)]
        if not linked_templates:
            missing.append(_("Training prerequisite: no QM Training Templates are linked."))
        for template in linked_templates:
            courses = _get_passed_training_courses(trainee, template)
            details["courses"].extend(courses)
            if not courses:
                missing.append(_(f"Create and submit a QM Training Course for QM Training Template {template} and ensure that the Employee completes it with outcome Passed."))
    # A document/course may satisfy more than one linked reference.
    for key in ("instructions", "courses", "records"):
        details[key] = list({row.get("name"): row for row in details[key]}.values())
    return details


def update_competency_assignments_for_trainee(trainee, document_type=None, document_name=None):
    if not trainee:
        return

    training_template = None
    if document_type == "QM Training Course" and document_name:
        training_template = frappe.db.get_value("QM Training Course", document_name, "training_template")
        if not training_template:
            return

    employee_name = frappe.db.get_value("Employee", {"user_id": trainee}, "name")
    if not employee_name:
        return

    staff_profiles = frappe.get_all(
        "Staff Profile",
        filters=[
            ["employee", "=", employee_name],
            ["status", "!=", "Archived"],
            ["docstatus", "!=", 2],
        ],
        fields=["name"],
    )
    if not staff_profiles:
        return

    profile_names = [row.get("name") for row in staff_profiles if row.get("name")]
    planned_assignments = frappe.get_all(
        "Competency Assignment",
        filters=[
            ["parenttype", "=", "Staff Profile"],
            ["parent", "in", profile_names],
            ["status", "=", "Planned"],
        ],
        fields=["name", "competency"],
    )
    for assignment in planned_assignments:
        competency = frappe.get_doc("Competency", assignment.get("competency"))
        if not competency:
            continue

        if document_type == "QM Document" and document_name:
            linked_documents = [row.qm_document for row in (competency.qm_documents or []) if getattr(row, "qm_document", None)]
            if not any(_matches_versioned_document_name(document_name, linked_document) for linked_document in linked_documents):
                continue
        elif document_type == "QM Training Course" and document_name:
            linked_templates = [row.training_template for row in (competency.trainings or []) if getattr(row, "training_template", None)]
            if training_template not in linked_templates:
                continue

        if _competency_requirements_met(assignment.get("competency"), trainee):
            _mark_assignment_achieved(assignment.get("name"))
