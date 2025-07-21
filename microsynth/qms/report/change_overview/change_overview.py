# Copyright (c) 2025, Microsynth
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _


def get_columns():
    return [
        {"label": _("Type"), "fieldname": "type", "fieldtype": "Data", "width": 75},
        {"label": _("QM Change"), "fieldname": "qm_change", "fieldtype": "Link", "options": "QM Change", "width": 85},
        {"label": _("QM Action"), "fieldname": "qm_action", "fieldtype": "Link", "options": "QM Action", "width": 85},
        {"label": _("Title"), "fieldname": "title", "fieldtype": "Data", "width": 400},
        {"label": _("Status"), "fieldname": "status", "fieldtype": "Data", "width": 170},
        {"label": _("Responsible Person"), "fieldname": "responsible_person", "fieldtype": "Link", "options": "User", "width": 195},
        {"label": _("Creation"), "fieldname": "created_on", "fieldtype": "Date", "width": 125},
        {"label": _("Due Date"), "fieldname": "due_date", "fieldtype": "Date", "width": 75},
        {"label": _("Completion"), "fieldname": "completion_date", "fieldtype": "Date", "width": 85},
        {"label": _("Process"), "fieldname": "qm_process", "fieldtype": "Link", "options": "QM Process", "width": 145},
        {"label": _("Action Type"), "fieldname": "action_type", "fieldtype": "Data", "width": 145},
        {"label": _("Company"), "fieldname": "company", "fieldtype": "Link", "options": "Company", "width": 150}
    ]


def get_data(filters):
    conditions = ""
    values = {}

    if filters.get("status_qm_change"):
        conditions += " AND `tabQM Change`.`status` = %(status_qm_change)s"
        values["status_qm_change"] = filters["status_qm_change"]

    if filters.get("status_qm_action"):
        conditions += " AND `tabQM Action`.`status` = %(status_qm_action)s"
        values["status_qm_action"] = filters["status_qm_action"]

    if filters.get("person"):
        conditions += """
            AND (
                `tabQM Action`.`responsible_person` = %(person)s OR
                `tabQM Change`.`owner` = %(person)s
            )
        """
        values["person"] = filters["person"]

    if filters.get("qm_process"):
        conditions += " AND (`tabQM Change`.`qm_process` = %(qm_process)s OR `tabQM Action`.`qm_process` = %(qm_process)s)"
        values["qm_process"] = filters["qm_process"]

    if filters.get("company"):
        conditions += " AND `tabQM Change`.`company` = %(company)s"
        values["company"] = filters["company"]

    if filters.get("action_type"):
        conditions += " AND `tabQM Action`.`type` = %(action_type)s"
        values["action_type"] = filters["action_type"]

    query = f"""
        SELECT
            `tabQM Change`.`name` AS `qm_change`,
            `tabQM Change`.`title` AS `qm_change_title`,
            `tabQM Change`.`status` AS `qm_change_status`,
            `tabQM Change`.`owner` AS `qm_owner`,
            `tabQM Change`.`qm_process` AS `qm_change_process`,
            `tabQM Change`.`company` AS `qm_change_company`,
            `tabQM Change`.`created_on` AS `qm_change_created_on`,
            `tabQM Action`.`name` AS `qm_action`,
            `tabQM Action`.`title` AS `qm_action_title`,
            `tabQM Action`.`status` AS `qm_action_status`,
            `tabQM Action`.`responsible_person`,
            `tabQM Action`.`due_date`,
            `tabQM Action`.`completion_date`,
            `tabQM Action`.`type` AS `action_type`,
            `tabQM Action`.`qm_process` AS `qm_action_process`,
            `tabQM Action`.`creation` AS `qm_action_created_on`
        FROM `tabQM Change`
        LEFT JOIN `tabQM Action`
            ON `tabQM Action`.`document_type` = 'QM Change' AND `tabQM Action`.`document_name` = `tabQM Change`.`name`
        WHERE TRUE
            {conditions}
        ORDER BY `tabQM Change`.`name` DESC, `tabQM Action`.`due_date` ASC
    """

    results = frappe.db.sql(query, values, as_dict=True)
    output = []

    for row in results:
        if not any(r for r in output if r.get("qm_change") == row.qm_change and r.get("indent") == 0):
            output.append({
                "type": "Change",
                "title": row.qm_change_title,
                "status": row.qm_change_status,
                "responsible_person": row.qm_owner,
                "due_date": "",
                "completion_date": "",
                "qm_change": row.qm_change,
                "qm_action": "",
                "qm_process": row.qm_change_process,
                "company": row.qm_change_company,
                "action_type": "",
                "created_on": row.qm_change_created_on,
                "indent": 0
            })

        if row.qm_action:
            output.append({
                "type": "Action",
                "title": row.qm_action_title,
                "status": row.qm_action_status,
                "responsible_person": row.responsible_person,
                "due_date": row.due_date,
                "completion_date": row.completion_date,
                "qm_change": row.qm_change,
                "qm_action": row.qm_action,
                "qm_process": row.qm_action_process,
                "company": row.qm_change_company,
                "action_type": row.action_type,
                "created_on": row.qm_action_created_on,
                "indent": 1
            })

    return output


def execute(filters=None):
    filters = filters or {}
    columns = get_columns()
    data = get_data(filters)
    return columns, data
