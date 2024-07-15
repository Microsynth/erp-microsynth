# -*- coding: utf-8 -*-
# Copyright (c) 2024, Microsynth, libracore and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document
from frappe.utils.data import today
from microsynth.microsynth.utils import user_has_role


class QMNonconformity(Document):
    def get_classification_wizard(self):            
        html = frappe.render_template("microsynth/qms/doctype/qm_nonconformity/classification_wizard.html",
            {
                'doc': self
            })
        return html


    def get_advanced_dashboard(self):
        corrections = frappe.db.sql(f"""
            SELECT 
                `tabQM Action`.`name`,
                `tabQM Action`.`title`,
                `tabQM Action`.`status`
            FROM `tabQM Action`
            WHERE 
                `tabQM Action`.`document_type` = "QM Nonconformity"
                AND `tabQM Action`.`document_name` = "{self.name}"
                AND `tabQM Action`.`type` = "Correction"
            ;""", as_dict=True)

        corrective_actions = frappe.db.sql(f"""
            SELECT 
                `tabQM Action`.`name`,
                `tabQM Action`.`title`,
                `tabQM Action`.`status`
            FROM `tabQM Action`
            WHERE 
                `tabQM Action`.`document_type` = "QM Nonconformity"
                AND `tabQM Action`.`document_name` = "{self.name}"
                AND `tabQM Action`.`type` = "Corrective Action"
            ;""", as_dict=True)

        changes = frappe.db.sql(f"""
            SELECT 
                `tabQM Change`.`name`,
                `tabQM Change`.`title`,
                `tabQM Change`.`status`
            FROM `tabQM Change`
            WHERE 
                `tabQM Change`.`document_type` = "QM Nonconformity"
                AND `tabQM Change`.`document_name` = "{self.name}"
            ;""", as_dict=True)
        
        effectiveness_checks = frappe.db.sql(f"""
            SELECT 
                `tabQM Action`.`name`,
                `tabQM Action`.`title`,
                `tabQM Action`.`status`
            FROM `tabQM Action`
            WHERE 
                `tabQM Action`.`document_type` = "QM Nonconformity"
                AND `tabQM Action`.`document_name` = "{self.name}"
                AND `tabQM Action`.`type` = "NC Effectiveness Check"
            ;""", as_dict=True)

        html = frappe.render_template("microsynth/qms/doctype/qm_nonconformity/advanced_dashboard.html",
            {
                'doc': self, 
                'corrections': corrections,
                'corrective_actions': corrective_actions,
                'changes': changes,
                'effectiveness_checks': effectiveness_checks
            })
        return html


@frappe.whitelist()
def set_created(doc, user):
    # pull selected document
    nc = frappe.get_doc(frappe.get_doc("QM Nonconformity", doc))

    if user != nc.created_by:
        frappe.throw(f"Error creating the QM Nonconformity: Only {nc.created_by} is allowed to create the QM Nonconformity {nc.name}. Current login user is {user}.")

    nc.created_on = today()
    nc.created_by = user
    nc.save()
    nc.submit()
    frappe.db.commit()
    update_status(nc.name, "Created")


@frappe.whitelist()
def confirm_classification(doc, user):
    if not (user_has_role(user, "QAU") or user_has_role(user, "PV")):  # TODO: PV is not allowed to confirm classification if GMP
        frappe.throw(f"Only QAU or PV is allowed to classify a QM Nonconformity.")
    # TODO: function to check combinations of NC Type, Criticality Classification, Regulatory Classification 
    update_status(doc, "Investigation")


@frappe.whitelist()
def set_status(doc, user, status):
    created_by = frappe.get_doc(frappe.get_doc("QM Nonconformity", doc, "created_by"))
    if not (user == created_by or user_has_role(user, "QAU")):
        frappe.throw(f"Only Creator or QAU is allowed to set a QM Nonconformity to Status '{status}'.")
    update_status(doc, status)


def update_status(nc, status):
    nc = frappe.get_doc("QM Nonconformity", nc)
    if nc.status == status:
        return

    # validate status transitions
    if ((nc.status == 'Draft' and status == 'Created') or
        (nc.status == 'Created' and status == 'Investigation') or
        (nc.status == 'Investigation' and status == 'Planning') or
        (nc.status == 'Planning' and status == 'Plan Approval') or
        (nc.status == 'Plan Approval' and status == 'Planning') or
        (nc.status == 'Plan Approval' and status == 'Implementation') or
        (nc.status == 'Implementation' and status == 'Completed') or
        (nc.status == 'Created' and status == 'Closed') or
        (nc.status == 'Completed' and status == 'Closed')
       ):
        nc.status = status
        nc.save()
        frappe.db.commit()
    else: 
        frappe.throw(f"Update QM Nonconformity: Status transition is not allowed {nc.status} --> {status}")


@frappe.whitelist()
def cancel(nc):
    from microsynth.microsynth.utils import force_cancel
    nc = frappe.get_doc("QM Nonconformity", nc)
    if nc.status == "Draft":
        force_cancel("QM Nonconformity", nc.name)
    else:
        try:
            nc.cancel()
            frappe.db.commit()
        except Exception as err:
            force_cancel("QM Nonconformity", nc.name)


@frappe.whitelist()
def has_actions(doc):
    """
    Returns whether a given QM Nonconformity has Corrections and Corrective Actions.
    """
    corrective_actions = frappe.db.sql(f"""
        SELECT `name`
        FROM `tabQM Action`
        WHERE `type` = 'Corrective Action'
          AND `docstatus` < 2
          AND `document_name` = '{doc}';
        """, as_dict=True)
    
    corrections = frappe.db.sql(f"""
        SELECT `name`
        FROM `tabQM Action`
        WHERE `type` = 'Correction'
          AND `docstatus` < 2
          AND `document_name` = '{doc}';
        """, as_dict=True)
    
    actions = {
        'has_correction': len(corrections) > 0,
        'has_corrective_action': len(corrective_actions) > 0
    }    
    return actions


@frappe.whitelist()
def has_non_completed_action(doc):
    """
    Returns whether there is a QM Action with status unequals 'Completed' and
    Type 'Correction' or 'Corrective Action' linked against the given QM Nonconformity.
    """
    non_completed_actions = frappe.db.sql(f"""
        SELECT `name`
        FROM `tabQM Action`
        WHERE `status` != 'Completed'
          AND `docstatus` < 2
          AND `document_name` = '{doc}'
          AND `type` IN ('Correction', 'Corrective Action')
        ;""", as_dict=True)
    
    return len(non_completed_actions) > 0


@frappe.whitelist()
def has_change(doc):
    """
    Returns whether there is at least one QM Change linked against the given QM Nonconformity.
    """
    changes = frappe.db.sql(f"""
        SELECT `name`
        FROM `tabQM Change`
        WHERE `docstatus` < 2
          AND `document_name` = '{doc}';
        """, as_dict=True)
    
    return len(changes) > 0
