# -*- coding: utf-8 -*-
# Copyright (c) 2024, Microsynth, libracore and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
from datetime import date

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils.data import today
from frappe.utils import get_url_to_form
from frappe.desk.form.assign_to import add
from frappe.core.doctype.communication.email import make

from microsynth.microsynth.utils import user_has_role


class QMNonconformity(Document):
    def get_classification_wizard(self, visible):
        user_language = frappe.get_value("User", frappe.session.user, "language")
        html = frappe.render_template("microsynth/qms/doctype/qm_nonconformity/classification_wizard.html",
            {
                'doc': self,
                'visible': visible,
                'language': user_language
            })
        return html


    def get_advanced_dashboard(self):
        html = frappe.render_template("microsynth/qms/doctype/qm_nonconformity/advanced_dashboard.html",
            {
                'doc': self,
                'corrections': get_corrections(self.name),
                'corrective_actions': get_corrective_actions(self.name),
                'changes': get_qm_changes(self.name),
                'effectiveness_checks': get_effectiveness_checks(self.name)
            })
        return html
    

    def set_in_approval(self, in_approval):
        self.in_approval = in_approval
        self.save()
        frappe.db.commit()


    def validate(self):
        self.validate_hierarchy()


    def validate_hierarchy(self):
        if self.hierarchy_1:
            allowed_hierarchy_1s = get_allowed_classification_for_process(
                doctype="QM Nonconformity", 
                txt=self.hierarchy_1, 
                searchfield="name", 
                start=0, 
                page_len=20, 
                filters={'process': self.qm_process}
            )
            if len(allowed_hierarchy_1s) == 0:
                frappe.throw( _("Invalid value in 'Hierarchy 1'. Please select from the available values."), _("Validation") )
        
        if self.hierarchy_2:
            allowed_hierarchy_2s = get_allowed_classification_for_hierarchy(
                doctype="QM Nonconformity", 
                txt=self.hierarchy_2, 
                searchfield="name", 
                start=0, 
                page_len=20, 
                filters={'hierarchy': self.hierarchy_1}
            )
            if len(allowed_hierarchy_2s) == 0:
                frappe.throw( _("Invalid value in 'Hierarchy 2'. Please select from the available values."), _("Validation") )


@frappe.whitelist()
def set_created(doc, user):
    # pull selected document
    nc = frappe.get_doc("QM Nonconformity", doc)
    check_classification(nc)

    if user != nc.created_by and not user_has_role(user, "QAU"):
        frappe.throw(f"Error creating the QM Nonconformity: Only {nc.created_by} or QAU is allowed to create the QM Nonconformity {nc.name}. Current login user is {user}.")

    nc.created_on = today()
    nc.created_by = user
    nc.save()
    nc.submit()
    frappe.db.commit()
    update_status(nc.name, "Created")


@frappe.whitelist()
def confirm_classification(doc, user):
    nc = frappe.get_doc("QM Nonconformity", doc)
    if user_has_role(user, "QAU") or user == nc.created_by:
        check_classification(nc)
        update_status(nc.name, "Investigation")
    else:
        frappe.throw(f"Only the creator {nc.created_by} or a user with the QAU role is allowed to classify a QM Nonconformity.")
    

def check_classification(nc):
    """
    Check combinations of NC Type, Criticality Classification and Regulatory Classification
    """
    if nc.nc_type == 'Event':
        if nc.criticality_classification != 'non-critical' or nc.regulatory_classification == 'GMP':
            frappe.throw("An Event has to be classified as non-critical and non-GMP. Please change the Classification.")
    elif nc.nc_type == 'OOS':
        if nc.regulatory_classification != 'GMP':
            frappe.throw("An OOS has to be classified as GMP. Please change the Classification.")
        if nc.criticality_classification != 'N/A':
            frappe.throw("Only N/A is allowed as Criticality Classification of an OOS. Please change the Classification.")
    elif nc.nc_type == 'Track & Trend':
        if nc.criticality_classification != 'N/A':
            frappe.throw("Only N/A is allowed as Criticality Classification of Track & Trend. Please change the Classification.")
    elif nc.nc_type not in ['OOS', 'Track & Trend'] and nc.criticality_classification == 'N/A':
        frappe.throw("The Criticality Classification N/A is only allowed for OOS and Track & Trend. Please change the Classification.")


@frappe.whitelist()
def set_status(doc, user, status):
    created_by = frappe.get_value("QM Nonconformity", doc, "created_by")
    if not (user == created_by or user_has_role(user, "QAU")):
        frappe.throw(f"Only Creator or QAU is allowed to set a QM Nonconformity to Status '{status}'.")
    update_status(doc, status)


def update_status(nc, status):
    nc = frappe.get_doc("QM Nonconformity", nc)
    if nc.status == status:
        return
    if nc.status == 'Created':
        check_classification(nc)
    # validate status transitions
    if ((nc.status == 'Draft' and status == 'Created') or
        (nc.status == 'Created' and status == 'Investigation') or
        (nc.status == 'Investigation' and status == 'Planning') or
        (nc.status == 'Planning' and status == 'Plan Approval') or
        (nc.status == 'Plan Approval' and status == 'Planning') or
        (nc.status == 'Plan Approval' and status == 'Implementation') or
        (nc.status == 'Implementation' and status == 'Completed') or
        (nc.status == 'Created' and status == 'Closed') or
        (nc.status == 'Completed' and status == 'Closed') or
        (nc.status == 'Investigation' and status == 'Closed')
       ):
        nc.status = status
        nc.save()
        frappe.db.commit()
    else: 
        frappe.throw(f"Update QM Nonconformity: Status transition is not allowed {nc.status} --> {status}")


@frappe.whitelist()
def send_notification(assign, doc_name, recipient, message):
    if assign == 'true':
        # Assign the given recipient to the given QM Nonconformity with the given message
        add({
            'doctype': "QM Nonconformity",
            'name': doc_name,
            'assign_to': recipient,
            'description': message,
            'notify': True
        })
    else:
        # Send an email to the given recipient with the given message
        make(
            recipients = recipient,
            sender = 'erp@microsynth.ch',
            sender_full_name = 'Microsynth ERP',
            subject = f"Action required for {doc_name}",
            content = f"{message}<br>{get_url_to_form('QM Nonconformity', doc_name)}",
            send_email = True
        )


@frappe.whitelist()
def close(doc, user):
    # pull selected document
    qm_nc = frappe.get_doc("QM Nonconformity", doc)
    if qm_nc.created_by == user or user_has_role(user, "QAU"):
        # set closing user and (current) date
        qm_nc.closed_by = user
        qm_nc.closed_on = date.today()
        qm_nc.in_approval = 0
        qm_nc.save()
        frappe.db.commit()
        update_status(qm_nc.name, "Closed")
    else:
        frappe.throw(f"Only the creator {qm_nc.created_by} or a user with the QAU role is allowed to close this Nonconformity.")


@frappe.whitelist()
def cancel(nc):
    from microsynth.microsynth.utils import force_cancel
    nc_doc = frappe.get_doc("QM Nonconformity", nc)
    if nc_doc.status == "Draft":
        force_cancel("QM Nonconformity", nc_doc.name)
    else:
        try:
            nc_doc.status = 'Cancelled'
            nc_doc.save()
            nc_doc.cancel()
            frappe.db.commit()
        except Exception as err:
            force_cancel("QM Nonconformity", nc_doc.name)


@frappe.whitelist()
def get_corrections(qm_nc):
    corrections = frappe.db.sql(f"""
        SELECT 
            `tabQM Action`.`name`,
            `tabQM Action`.`title`,
            `tabQM Action`.`description`,
            `tabQM Action`.`responsible_person`,
            `tabQM Action`.`initiation_date`,
            `tabQM Action`.`description`,
            `tabQM Action`.`notes`,
            `tabQM Action`.`status`
        FROM `tabQM Action`
        WHERE 
            `tabQM Action`.`document_type` = "QM Nonconformity"
            AND `tabQM Action`.`document_name` = "{qm_nc}"
            AND `tabQM Action`.`type` = "Correction"
        ;""", as_dict=True)
    return corrections


@frappe.whitelist()
def get_corrective_actions(qm_nc):
    corrective_actions = frappe.db.sql(f"""
        SELECT 
            `tabQM Action`.`name`,
            `tabQM Action`.`title`,
            `tabQM Action`.`description`,
            `tabQM Action`.`responsible_person`,
            `tabQM Action`.`initiation_date`,
            `tabQM Action`.`description`,
            `tabQM Action`.`notes`,
            `tabQM Action`.`status`
        FROM `tabQM Action`
        WHERE 
            `tabQM Action`.`document_type` = "QM Nonconformity"
            AND `tabQM Action`.`document_name` = "{qm_nc}"
            AND `tabQM Action`.`type` = "Corrective Action"
        ;""", as_dict=True)
    return corrective_actions


@frappe.whitelist()
def get_effectiveness_checks(qm_nc):
    """
    TODO: Combine functions get_corrections, get_corrective_actions and get_effectiveness_checks
    to function "get_actions" that takes an additional parameter "type",
    change in function get_advanced_dashboard, hooks.py and QM Nonconformity print format (already inserted in ERP-Test)
    """
    effectiveness_checks = frappe.db.sql(f"""
        SELECT 
            `tabQM Action`.`name`,
            `tabQM Action`.`title`,
            `tabQM Action`.`description`,
            `tabQM Action`.`responsible_person`,
            `tabQM Action`.`initiation_date`,
            `tabQM Action`.`description`,
            `tabQM Action`.`notes`,
            `tabQM Action`.`status`
        FROM `tabQM Action`
        WHERE 
            `tabQM Action`.`document_type` = "QM Nonconformity"
            AND `tabQM Action`.`document_name` = "{qm_nc}"
            AND `tabQM Action`.`type` = "NC Effectiveness Check"
        ;""", as_dict=True)
    return effectiveness_checks


@frappe.whitelist()
def get_qm_changes(qm_nc):
    changes = frappe.db.sql(f"""
        SELECT 
            `tabQM Change`.`name`,
            `tabQM Change`.`title`,
            `tabQM Change`.`description`,
            `tabQM Change`.`created_by`,
            `tabQM Change`.`current_state`,
            `tabQM Change`.`description`,
            `tabQM Change`.`status`
        FROM `tabQM Change`
        WHERE 
            `tabQM Change`.`document_type` = "QM Nonconformity"
            AND `tabQM Change`.`document_name` = "{qm_nc}"
        ;""", as_dict=True)
    return changes


@frappe.whitelist()
def get_nc_attachments(qm_nc):
    from frappe.desk.form.load import get_attachments
    attachments = get_attachments("QM Nonconformity", qm_nc)
    return attachments


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


def get_allowed_classification_for_process(doctype, txt, searchfield, start, page_len, filters):
    return frappe.db.sql("""
        SELECT `tabQM Classification Hierarchy Link`.`hierarchy` AS `name`
        FROM `tabQM Classification Hierarchy Link`
        WHERE
            `tabQM Classification Hierarchy Link`.`parent` = "{process}"
            AND `tabQM Classification Hierarchy Link`.`parenttype` = "QM Process"
            AND `tabQM Classification Hierarchy Link`.`hierarchy` LIKE "%{s}%";
        """.format(process=filters['process'], s=txt)
        )


def get_allowed_classification_for_hierarchy(doctype, txt, searchfield, start, page_len, filters):
    return frappe.db.sql("""
        SELECT `tabQM Classification Hierarchy Link`.`hierarchy` AS `name`
        FROM `tabQM Classification Hierarchy Link`
        WHERE
            `tabQM Classification Hierarchy Link`.`parent` = "{hierarchy}"
            AND `tabQM Classification Hierarchy Link`.`parenttype` = "QM Classification Hierarchy"
            AND `tabQM Classification Hierarchy Link`.`hierarchy` LIKE "%{s}%";
        """.format(hierarchy=filters['hierarchy'], s=txt)
        )


@frappe.whitelist()
def fetch_nonconformities(nonconformity_ids):
    """
    bench execute microsynth.qms.doctype.qm_nonconformity.qm_nonconformity.fetch_nonconformities --kwargs "{'nonconformity_ids': ['NC-240011', 'NC-240002']}"
    """
    # for nc in nonconformity_ids:
    #     if not frappe.db.exists("QM Nonconformity", nc):
    #         return {'success': False, 'message': f"At least QM Nonconformity '{nc}' does not exist.", 'nonconformities': None}

    nonconformities = frappe.get_all("QM Nonconformity", filters=[['name', 'IN', nonconformity_ids]], fields=['name', 'title', 'nc_type', 'date', 'description'])

    for n in nonconformities:
        n['url'] = get_url_to_form("QM Nonconformity", n['name'])

    return {'success': True, 'message': 'OK', 'nonconformities': nonconformities}