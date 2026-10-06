# -*- coding: utf-8 -*-
# Copyright (c) 2026, Microsynth
# For license information, please see license.txt

from __future__ import unicode_literals
import re
import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, nowdate
from microsynth.qms.signing import sign as signing_sign


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


def _split_staff_profile_version(name):
    match = re.match(r"^(.*?)(?:-(\d{1,2}))?$", name)
    if not match:
        return name, 0
    base_name = match.group(1)
    suffix = int(match.group(2)) if match.group(2) else 0
    return base_name, suffix


def _get_staff_profile_versions(base_name):
    candidates = frappe.get_all(
        "Staff Profile",
        filters={"name": ["like", "{0}%".format(base_name)]},
        fields=["name", "status", "docstatus"],
    )
    versions = []
    for candidate in candidates:
        candidate_name = candidate.get("name")
        candidate_base, candidate_suffix = _split_staff_profile_version(candidate_name)
        if candidate_base == base_name:
            versions.append((
                candidate_suffix,
                candidate_name,
                candidate.get("status"),
                candidate.get("docstatus"),
            ))
    return sorted(versions, key=lambda item: item[0])


@frappe.whitelist()
def create_new_version(docname):

    def _is_cancelled_staff_profile_version(status, docstatus):
        return cint(docstatus) == 2 or status == "Cancelled"

    if not docname:
        frappe.throw(_("Missing Staff Profile name."))

    current_doc = frappe.get_doc("Staff Profile", docname)
    if current_doc.docstatus != 1 or current_doc.status != "Valid":
        frappe.throw(
            _("A new Staff Profile version can only be created from a submitted profile in status Valid.")
        )

    base_name, current_suffix = _split_staff_profile_version(docname)
    available_versions = _get_staff_profile_versions(base_name)
    newer_versions = [
        name
        for suffix, name, status, docstatus in available_versions
        if suffix > current_suffix and not _is_cancelled_staff_profile_version(status, docstatus)
    ]

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

    highest_suffix = max([suffix for suffix, name, status, docstatus in available_versions], default=current_suffix)
    next_suffix = highest_suffix + 1
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


class StaffProfile(Document):
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

    def on_cancel(self):
        self.status = "Cancelled"
