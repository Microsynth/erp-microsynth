# -*- coding: utf-8 -*-
# Copyright (c) 2026, Microsynth
# For license information, please see license.txt

from __future__ import unicode_literals

import frappe
from frappe import _
from frappe.model.document import Document


def _get_invalid_template_competency_rows(assignments):
    def _row_value(row, fieldname):
        if hasattr(row, fieldname):
            return getattr(row, fieldname)
        if isinstance(row, dict):
            return row.get(fieldname)
        return None

    competency_names = []
    for row in assignments or []:
        competency_name = _row_value(row, "competency")
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
        row_idx = _row_value(row, "idx")
        competency_name = _row_value(row, "competency")
        competency_doc = competencies_by_name.get(competency_name)

        if not competency_name:
            invalid_rows.append({
                "row": row_idx,
                "competency": _("not set"),
                "reason": _("No Competency is selected in this row."),
            })
            continue

        if not competency_doc:
            invalid_rows.append({
                "row": row_idx,
                "competency": competency_name,
                "reason": _("The linked Competency does not exist or is no longer accessible."),
            })
            continue

        competency_status = competency_doc.get("status") or _("not set")
        competency_docstatus = int(competency_doc.get("docstatus") or 0)
        if competency_docstatus != 1 or competency_doc.get("status") != "Valid":
            reason_parts = []
            if competency_docstatus != 1:
                reason_parts.append(
                    _("document status is {0} instead of Submitted (1)").format(
                        frappe.bold(str(competency_docstatus))
                    )
                )
            if competency_doc.get("status") != "Valid":
                reason_parts.append(
                    _("status is {0} instead of Valid").format(frappe.bold(competency_status))
                )
            invalid_rows.append({
                "row": row_idx,
                "competency": competency_name,
                "reason": "; ".join(reason_parts),
            })
    return invalid_rows


def _get_validated_staff_profile_template(template_name):
    if not template_name:
        frappe.throw(_("Missing Staff Profile Template name."))

    template = frappe.get_doc("Staff Profile Template", template_name)
    template.check_permission("read")

    if getattr(template, "disabled", False):
        frappe.throw(_("This Staff Profile Template is disabled and cannot be used to create a Staff Profile."))

    invalid_rows = _get_invalid_template_competency_rows(template.get("competencies") or [])
    if invalid_rows:
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
                "This Staff Profile Template contains at least one invalid Competency and therefore cannot be used to create a Staff Profile.<br><br>{0}"
            ).format(details),
            title=_("Invalid Competencies"),
        )

    return template


def get_staff_profile_template_competency_values(template):
    values = []
    for row in template.get("competencies") or []:
        row_values = {
            "competency": row.get("competency"),
            "responsibility_role": row.get("responsibility_role"),
            "level": row.get("level"),
            "remarks": row.get("remarks"),
            "status": "Planned",
        }
        if row.get("competency_title"):
            row_values["competency_title"] = row.get("competency_title")
        values.append(row_values)
    return values


def append_template_competencies(target_profile, template, skip_existing=False):
    existing_competencies = set()
    if skip_existing:
        existing_competencies = {
            row.get("competency")
            for row in (target_profile.get("competencies") or [])
            if row.get("competency")
        }

    added_rows = []
    for row_values in get_staff_profile_template_competency_values(template):
        competency_name = row_values.get("competency")
        if skip_existing and competency_name in existing_competencies:
            continue

        new_row = target_profile.append("competencies", row_values)
        if new_row and hasattr(new_row, "competency_title"):
            new_row.competency_title = row_values.get("competency_title")
        added_rows.append(row_values)

        if skip_existing and competency_name:
            existing_competencies.add(competency_name)

    return added_rows


@frappe.whitelist()
def validate_template_for_staff_profile(template_name):
    try:
        _get_validated_staff_profile_template(template_name)
    except frappe.ValidationError as exc:
        return {
            "valid": False,
            "message": frappe.safe_decode(exc),
        }

    return {"valid": True, "message": ""}


@frappe.whitelist()
def create_staff_profile_from_template(template_name, employee):
    if not employee:
        frappe.throw(_("An Employee is required to create a Staff Profile from a template."))

    template = _get_validated_staff_profile_template(template_name)

    employee_doc = frappe.get_doc("Employee", employee)
    employee_doc.check_permission("read")

    new_profile = frappe.new_doc("Staff Profile")
    new_profile.employee = employee
    new_profile.status = "Draft"

    append_template_competencies(new_profile, template)

    new_profile.insert(ignore_permissions=True)
    frappe.db.commit()
    return new_profile.name


class StaffProfileTemplate(Document):
    def validate(self):
        invalid_rows = _get_invalid_template_competency_rows(self.get("competencies") or [])
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
                "This Staff Profile Template contains at least one invalid Competency and therefore cannot be saved.<br><br>{0}"
            ).format(details),
            title=_("Invalid Competencies"),
        )
