# -*- coding: utf-8 -*-
# Copyright (c) 2026, Microsynth
# For license information, please see license.txt

from __future__ import unicode_literals

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, nowdate

from microsynth.qms.doctype.competency_assignment.competency_assignment import update_competency_assignments_for_trainee
from microsynth.qms.signing import sign as signing_sign
from microsynth.qms.versioning import get_newer_active_versions, get_next_suffix, get_versioned_documents


@frappe.whitelist()
def get_department_competencies(docname, employee=None):
    """Return readable, valid competencies for a saved draft's employee departments."""
    profile = frappe.get_doc("Staff Profile", docname)
    profile.check_permission("write")
    if profile.docstatus != 0 or profile.status not in (None, "", "Draft"):
        frappe.throw(_("Department competencies can only be added to a saved Staff Profile draft."))

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
        self.save()
        frappe.db.commit()
