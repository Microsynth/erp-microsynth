# -*- coding: utf-8 -*-
# Copyright (c) 2026, Microsynth
# For license information, please see license.txt

from __future__ import unicode_literals

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import nowdate

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
            existing = frappe.db.exists(
                "Staff Profile",
                {
                    "employee": self.employee,
                    "status": "Valid",
                    "docstatus": 1,
                    "name": ["!=", self.name],
                },
            )
            if existing:
                frappe.throw(
                    _("A valid Staff Profile already exists for this employee. Please confirm the replacement before submitting."),
                    title=_("Existing valid Staff Profile"),
                )

    def on_submit(self):
        self.status = "To Sign"
