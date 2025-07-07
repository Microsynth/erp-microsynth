# -*- coding: utf-8 -*-
# Copyright (c) 2024, Microsynth, libracore and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document
from frappe.utils.data import today
from microsynth.microsynth.utils import user_has_role
from microsynth.qms.doctype.qm_action.qm_action import assign_and_notify


class QMChange(Document):
    def on_submit(self):
        self.status = "Created"
        self.save()

    def set_in_approval(self, in_approval):
        self.in_approval = in_approval
        self.save()

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

    def fill_impact_table(self):
        impacts = frappe.db.get_all("QM Change Impact", fields=['name'])
        if len(self.impact) < 1:
            for impact in impacts:
                self.append("impact", {
                    'qm_change_impact': impact['name'],
                    'impact_answer': ''
                    })
            self.save()
            frappe.db.commit()

    def are_all_impacts_answered(self):
        for potential_impact in self.impact:
            if not potential_impact.impact_answer:
                return False
        return True

    def has_impact(self):
        for potential_impact in self.impact:
            if potential_impact.impact_answer == 'yes':
                return True
        return False


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
            'status': 'Created',
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


def notify_actions(qm_change_id):
    qm_actions = frappe.get_all("QM Action", filters={
                                                'document_type': 'QM Change',
                                                'document_name': qm_change_id,
                                                'docstatus': 1
                                            }, fields=['name', 'responsible_person'])
    for action in qm_actions:
        assign_and_notify(action['name'], action['responsible_person'])


def update_status(nc, status):
    change = frappe.get_doc("QM Change", nc)
    if change.status == status:
        return

    # validate status transitions
    if ((change.status == 'Draft' and status == 'Created') or
        (change.status == 'Draft' and status == 'Assessment & Classification') or  # necessary for manually created QM Changes
        (change.status == 'Created' and status == 'Assessment & Classification') or
        (change.status == 'Assessment & Classification' and status == 'Trial') or
        (change.status == 'Assessment & Classification' and status == 'Planning') or  # if CC Type = Small Impact
        (change.status == 'Trial' and status == 'Planning') or
        (change.status == 'Planning' and status == 'Implementation') or
        (change.status == 'Implementation' and status == 'Completed') or
        (change.status == 'Completed' and status == 'Closed')
       ):
        if change.status == 'Created' and status == 'Assessment & Classification':
            change.date = today()
        if change.status == 'Planning' and status == 'Implementation':
            notify_actions(nc)
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
            frappe.throw(f"Unable to cancel QM Change {change}:\n{err}")
            #force_cancel("QM Change", change_doc.name)  # won't work for non-Draft documents


@frappe.whitelist()
def has_assessments(qm_change):
    assessments = frappe.db.sql(f"""
        SELECT
            `tabQM Impact Assessment`.`name`,
            `tabQM Impact Assessment`.`title`,
            `tabQM Impact Assessment`.`status`
        FROM `tabQM Impact Assessment`
        WHERE `tabQM Impact Assessment`.`docstatus` < 2
            AND `tabQM Impact Assessment`.`document_type` = "QM Change"
            AND `tabQM Impact Assessment`.`document_name` = "{qm_change}"
            AND `tabQM Impact Assessment`.`status` NOT IN ('Cancelled')
        ;""", as_dict=True)
    return len(assessments) > 0


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
def has_action(doc, action_type):
    """
    Returns whether there is a QM Action with status unequals 'Cancelled' and
    the given action_type linked against the given QM Change.
    """
    actions = frappe.db.sql(f"""
        SELECT `name`
        FROM `tabQM Action`
        WHERE `status` NOT IN ('Cancelled')
          AND `docstatus` < 2
          AND `document_name` = '{doc}'
          AND `type` IN ('{action_type}')
        ;""", as_dict=True)
    return len(actions) > 0


@frappe.whitelist()
def has_non_completed_action(doc, action_type):
    """
    Returns whether there is a QM Action with the given action_type,
    with status unequals 'Completed' or 'Cancelled'
    and linked against the given QM Change.
    """
    non_completed_actions = frappe.db.sql(f"""
        SELECT `name`
        FROM `tabQM Action`
        WHERE `status` NOT IN ('Completed', 'Cancelled')
          AND `docstatus` < 2
          AND `document_name` = '{doc}'
          AND `type` IN ('{action_type}')
        ;""", as_dict=True)
    return len(non_completed_actions) > 0


def get_cc_attachments(qm_change):
    from frappe.desk.form.load import get_attachments
    attachments = get_attachments("QM Change", qm_change)
    return attachments


def get_cc_actions(qm_change):
    actions = frappe.db.sql(f"""
        SELECT
            `tabQM Action`.`name`,
            `tabQM Action`.`title`,
            `tabQM Action`.`description`,
            `tabQM Action`.`responsible_person`,
            `tabQM Action`.`initiation_date`,
            `tabQM Action`.`description`,
            `tabQM Action`.`notes`,
            `tabQM Action`.`status`,
            `tabQM Action`.`completion_date`
        FROM `tabQM Action`
        WHERE
            `tabQM Action`.`document_type` = "QM Change"
            AND `tabQM Action`.`document_name` = "{qm_change}"
            AND `tabQM Action`.`type` = "Change Control Action"
            AND `tabQM Action`.`status` != "Cancelled"
        ;""", as_dict=True)
    return actions


def get_cc_effectiveness_checks(qm_change):
    effectiveness_checks = frappe.db.sql(f"""
        SELECT
            `tabQM Action`.`name`,
            `tabQM Action`.`title`,
            `tabQM Action`.`description`,
            `tabQM Action`.`responsible_person`,
            `tabQM Action`.`initiation_date`,
            `tabQM Action`.`description`,
            `tabQM Action`.`notes`,
            `tabQM Action`.`status`,
            `tabQM Action`.`completion_date`
        FROM `tabQM Action`
        WHERE
            `tabQM Action`.`document_type` = "QM Change"
            AND `tabQM Action`.`document_name` = "{qm_change}"
            AND `tabQM Action`.`type` = "CC Effectiveness Check"
            AND `tabQM Action`.`status` != "Cancelled"
        ;""", as_dict=True)
    return effectiveness_checks


def get_cc_impact_assessments(qm_change):
    """
    bench execute microsynth.qms.doctype.qm_change.qm_change.get_cc_impact_assessments --kwargs "{'qm_change': 'QMC-250003'}"
    """
    impact_assessments = frappe.db.sql(f"""
        SELECT
            `tabQM Impact Assessment`.`name`,
            `tabQM Impact Assessment`.`title`,
            `tabQM Impact Assessment`.`status`,
            `tabQM Impact Assessment`.`qm_process`,
            `tabQM Impact Assessment`.`due_date`,
            `tabQM Impact Assessment`.`assessment_summary`,
            `tabQM Impact Assessment`.`created_on`,
            `tabQM Impact Assessment`.`created_by`,
            `tabQM Impact Assessment`.`completion_date`
        FROM `tabQM Impact Assessment`
        WHERE
            `tabQM Impact Assessment`.`document_type` = "QM Change"
            AND `tabQM Impact Assessment`.`document_name` = "{qm_change}"
            AND `tabQM Impact Assessment`.`status` != "Cancelled"
        ;""", as_dict=True)
    #frappe.log_error(f"{qm_change=}\n{impact_assessments=}")
    #return []
    return impact_assessments


def get_qm_decisions(qm_change):
    decisions = frappe.db.sql(f"""
        SELECT
            `tabQM Decision`.`name`,
            `tabQM Decision`.`approver`,
            `tabQM Decision`.`decision`,
            `tabQM Decision`.`from_status`,
            `tabQM Decision`.`to_status`,
            `tabQM Decision`.`date`,
            `tabQM Decision`.`signature`,
            `tabQM Decision`.`comments`
        FROM `tabQM Decision`
        WHERE `tabQM Decision`.`docstatus` = 1
            AND `tabQM Decision`.`document_type` = "QM Change"
            AND `tabQM Decision`.`document_name` = "{qm_change}"
        ;""", as_dict=True)
    return decisions
