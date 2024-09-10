# -*- coding: utf-8 -*-
# Copyright (c) 2024, Microsynth, libracore and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document
from frappe.utils.data import today
from microsynth.microsynth.utils import user_has_role


class QMChange(Document):
    def on_submit(self):
        self.status = "Requested"

    def get_classification_wizard(self, visible):            
        html = frappe.render_template("microsynth/qms/doctype/qm_change/classification_wizard.html",
            {
                'doc': self,
                'visible': visible
            })
        return html

    def get_advanced_dashboard(self):
        assessments = frappe.db.sql(f"""
            SELECT 
                `tabQM Impact Assessment`.`name`,
                `tabQM Impact Assessment`.`title`,
                `tabQM Impact Assessment`.`status`
            FROM `tabQM Impact Assessment`
            WHERE 
                `tabQM Impact Assessment`.`document_type` = "QM Change"
                AND `tabQM Impact Assessment`.`document_name` = "{self.name}"
            ;""", as_dict=True)

        actions = frappe.db.sql(f"""
            SELECT 
                `tabQM Action`.`name`,
                `tabQM Action`.`title`,
                `tabQM Action`.`status`
            FROM `tabQM Action`
            WHERE 
                `tabQM Action`.`document_type` = "QM Change"
                AND `tabQM Action`.`document_name` = "{self.name}"
                AND `tabQM Action`.`type` = "Change Control Action"
            ;""", as_dict=True)

        effectiveness_checks = frappe.db.sql(f"""
            SELECT 
                `tabQM Action`.`name`,
                `tabQM Action`.`title`,
                `tabQM Action`.`status`
            FROM `tabQM Action`
            WHERE 
                `tabQM Action`.`document_type` = "QM Change"
                AND `tabQM Action`.`document_name` = "{self.name}"
                AND `tabQM Action`.`type` = "CC Effectiveness Check"
            ;""", as_dict=True)

        html = frappe.render_template("microsynth/qms/doctype/qm_change/advanced_dashboard.html",
            {
                'doc': self,
                'assessments': assessments,
                'actions': actions,
                'effectiveness_checks': effectiveness_checks
            })
        return html


@frappe.whitelist()
def create_change(dt, dn, title, qm_process, creator, company, description):
    change = frappe.get_doc(
        {
            'doctype': 'QM Change',
            'document_type': dt,
            'document_name': dn,
            'title': title,
            'qm_process': qm_process,
            'date': today(),
            'created_on': today(),
            'created_by': creator,
            'status': 'Requested',
            'company': company,
            'description': description
        })
    change.save(ignore_permissions = True)
    change.submit()
    frappe.db.commit()
    return change.name


@frappe.whitelist()
def set_status(doc, user, status):
    created_by = frappe.get_value("QM Change", doc, "created_by")
    if not (user == created_by or user_has_role(user, "QAU")):
        frappe.throw(f"Only Creator or QAU is allowed to set a QM Change to Status '{status}'.")
    update_status(doc, status)


def update_status(nc, status):
    change = frappe.get_doc("QM Change", nc)
    if change.status == status:
        return

    # validate status transitions
    if ((change.status == 'Draft' and status == 'Requested') or
        (change.status == 'Draft' and status == 'Assessment & Classification') or  # necessary for manually created QM Changes
        (change.status == 'Requested' and status == 'Assessment & Classification') or
        (change.status == 'Assessment & Classification' and status == 'Trial') or
        (change.status == 'Assessment & Classification' and status == 'Planning') or  # if CC Type = Small Impact
        (change.status == 'Trial' and status == 'Planning') or
        (change.status == 'Planning' and status == 'Implementation') or
        (change.status == 'Implementation' and status == 'Completed') or
        (change.status == 'Completed' and status == 'Closed')
       ):
        change.status = status
        change.save()
        frappe.db.commit()
    else: 
        frappe.throw(f"Update QM Change: Status transition is not allowed {change.status} --> {status}")


@frappe.whitelist()
def cancel(change):
    from microsynth.microsynth.utils import force_cancel
    change_doc = frappe.get_doc("QM Change", change)
    if change_doc.status == "Draft":
        force_cancel("QM Change", change_doc.name)
    else:
        try:
            change_doc.status = 'Cancelled'
            change_doc.save()
            change_doc.cancel()
            frappe.db.commit()
        except Exception as err:
            force_cancel("QM Change", change_doc.name)


@frappe.whitelist()
def has_non_completed_assessments(qm_change):
    assessments = frappe.db.sql(f"""
        SELECT 
            `tabQM Impact Assessment`.`name`,
            `tabQM Impact Assessment`.`title`,
            `tabQM Impact Assessment`.`status`
        FROM `tabQM Impact Assessment`
        WHERE `tabQM Impact Assessment`.`docstatus` < 2
            AND `tabQM Impact Assessment`.`document_type` = "QM Change"
            AND `tabQM Impact Assessment`.`document_name` = "{qm_change}"
            AND `tabQM Impact Assessment`.`status` NOT IN ('Completed', 'Cancelled')
        ;""", as_dict=True)
    return len(assessments) > 0


@frappe.whitelist()
def has_non_completed_action(doc, type):
    """
    Returns whether there is a QM Action with status unequals 'Completed' and
    the given type linked against the given QM Change.
    """
    non_completed_actions = frappe.db.sql(f"""
        SELECT `name`
        FROM `tabQM Action`
        WHERE `status` != 'Completed'
          AND `docstatus` < 2
          AND `document_name` = '{doc}'
          AND `type` IN ('{type}')
        ;""", as_dict=True)
    return len(non_completed_actions) > 0
