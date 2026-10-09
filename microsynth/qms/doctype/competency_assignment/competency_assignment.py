# -*- coding: utf-8 -*-
# Copyright (c) 2026, Microsynth
# For license information, please see license.txt

from __future__ import unicode_literals

import frappe
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


def _has_signed_qm_training_record(trainee, qm_document_name):
    if not trainee or not qm_document_name:
        return False
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
        fields=["name"],
    )
    return bool(records)


def _has_passed_training_template(trainee, training_template_name):
    if not trainee or not training_template_name:
        return False
    courses = frappe.get_all(
        "QM Training Course",
        filters={"training_template": training_template_name, "docstatus": 1},
        fields=["name"],
    )
    course_names = [course.get("name") for course in courses]
    if not course_names:
        return False
    participants = frappe.get_all(
        "QM Training Course Participant",
        filters=[
            ["parent", "in", course_names],
            ["parenttype", "=", "QM Training Course"],
            ["parentfield", "=", "participants"],
            ["user", "=", trainee],
            ["outcome", "=", "Passed"],
        ],
        fields=["name"],
    )
    return bool(participants)


def _competency_requirements_met(competency_name, trainee):
    if not competency_name or not trainee:
        return False

    competency = frappe.get_doc("Competency", competency_name)
    if not competency or competency.docstatus != 1 or competency.status != "Valid":
        return False

    prerequisite_types = {
        row.competency_prerequisite
        for row in (competency.prerequisite_types or [])
        if getattr(row, "competency_prerequisite", None)
    }

    if "QM Document" in prerequisite_types:
        linked_documents = [row.qm_document for row in (competency.qm_documents or []) if getattr(row, "qm_document", None)]
        if not linked_documents:
            return False
        if any(not _has_signed_qm_training_record(trainee, linked_document) for linked_document in linked_documents):
            return False

    if "Training" in prerequisite_types:
        linked_templates = [row.training_template for row in (competency.trainings or []) if getattr(row, "training_template", None)]
        if not linked_templates:
            return False
        if any(not _has_passed_training_template(trainee, template) for template in linked_templates):
            return False

    return True


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
