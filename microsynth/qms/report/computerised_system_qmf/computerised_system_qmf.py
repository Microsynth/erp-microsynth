# Copyright (c) 2026, Microsynth
# For license information, please see license.txt

from __future__ import unicode_literals

import frappe


def get_columns():
    return [
        {"label": "ID", "fieldname": "system_id", "fieldtype": "Link", "options": "QM Computerised System", "width": 90},
        {"label": "Name", "fieldname": "cs_name", "fieldtype": "Data", "width": 160},
        {"label": "Type", "fieldname": "cs_type", "fieldtype": "Data", "width": 100},
        {"label": "Regulatory Classification", "fieldname": "regulatory_classification", "fieldtype": "Data", "width": 90},
        {"label": "GAMP5 Class", "fieldname": "gamp5_class", "fieldtype": "Data", "width": 120},
        {"label": "Primary Version Control Method", "fieldname": "version_control", "fieldtype": "Data", "width": 160},
        {"label": "Process", "fieldname": "process", "fieldtype": "Data", "width": 135},
        {"label": "Company", "fieldname": "company", "fieldtype": "Link", "options": "Company", "width": 125},
        {"label": "Description", "fieldname": "description", "fieldtype": "Text", "width": 240, "align": "left"},
        {"label": "Status", "fieldname": "status", "fieldtype": "Data", "width": 80},
        {"label": "Version", "fieldname": "version", "fieldtype": "Data", "width": 65, "align": "left"},
        {"label": "Log Book ID", "fieldname": "logbook_id", "fieldtype": "Link", "options": "QM Log Book", "width": 95, "align": "left"},
        {"label": "Log Book Date", "fieldname": "logbook_date", "fieldtype": "Date", "width": 100},
        {"label": "Log Book Type", "fieldname": "logbook_type", "fieldtype": "Data", "width": 100, "align": "left"},
    ]


def get_conditions(filters):
    conditions = []
    values = {}

    for key in [
        "cs_type",
        "regulatory_classification",
        "gamp5_class",
        "primary_version_control_method",
    ]:
        value = (filters or {}).get(key)
        if value:
            conditions.append(f"`tabQM Computerised System`.`{key}` = %({key})s")
            values[key] = value

    status = (filters or {}).get("status")
    if status:
        conditions.append("`tabQM Computerised System`.`status` = %(status)s")
        values["status"] = status
    else:
        conditions.append("`tabQM Computerised System`.`status` != 'Decommissioned'")

    return conditions, values


def get_data(filters=None):
    filters = filters or {}
    conditions, values = get_conditions(filters)
    where_clause = "\n\t\t\tAND " + "\n\t\t\tAND ".join(conditions) if conditions else ""

    logbook_type = filters.get("logbook_type") or '(Re-)Validation'
    values["logbook_type"] = logbook_type

    return frappe.db.sql(f"""
        SELECT
            `tabQM Computerised System`.`name` AS `system_id`,
            `tabQM Computerised System`.`cs_name`,
            `tabQM Computerised System`.`cs_type`,
            `tabQM Computerised System`.`regulatory_classification`,
            `tabQM Computerised System`.`gamp5_class`,
            `tabQM Computerised System`.`primary_version_control_method` AS `version_control`,
            `tabQM Computerised System`.`qm_process` AS `process`,
            `tabQM Computerised System`.`company`,
            `tabQM Computerised System`.`description`,
            `tabQM Computerised System`.`status`,
            `tabQM Computerised System`.`version`,
            `tabQM Log Book`.`name` AS `logbook_id`,
            `tabQM Log Book`.`date` AS `logbook_date`,
            `tabQM Log Book`.`entry_type` AS `logbook_type`
        FROM `tabQM Computerised System`
        LEFT JOIN `tabQM Log Book`
            ON `tabQM Log Book`.`document_type` = 'QM Computerised System'
            AND `tabQM Log Book`.`document_name` = `tabQM Computerised System`.`name`
            AND `tabQM Log Book`.`docstatus` = 1
            AND `tabQM Log Book`.`entry_type` = %(logbook_type)s
        WHERE 1 = 1
        {where_clause}
        ORDER BY `tabQM Computerised System`.`name` ASC, `tabQM Log Book`.`date` ASC, `tabQM Log Book`.`name` ASC
    """, values, as_dict=True)


def execute(filters=None):
    if not filters:
        filters = {}
    columns = get_columns()
    data = get_data(filters)
    return columns, data
