# Copyright (c) 2025, Microsynth
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _


def get_columns(filters):
    return [
        {"label": _("Test Method ID"), "fieldname": "name", "fieldtype": "Dynamic Link", "options": "QM Analytical Procedure", "width": 105 },
        {"label": _("Analyte/Measurand "), "fieldname": "analyte", "fieldtype": "Data", "width": 150 },
        {"label": _("Matrix"), "fieldname": "matrix", "fieldtype": "Data", "width": 150 },
        {"label": _("Test Technique"), "fieldname": "test_technique", "fieldtype": "Data", "width": 150 },
        {"label": _("Test Instrument"), "fieldname": "device_model", "fieldtype": "Data", "width": 150 },
        {"label": _("Quality Control"), "fieldname": "quality_control", "fieldtype": "Data", "width": 200 },
        {"label": _("Company"), "fieldname": "company", "fieldtype": "Data", "width": 155 },
        {"label": _("QM Document ID"), "fieldname": "qm_document_id", "fieldtype": "Link", "options": "QM Document", "width": 125 },
        {"label": _("QM Document Title"), "fieldname": "title", "fieldtype": "Data", "width": 325 },
        {"label": _("Valid from"), "fieldname": "valid_from", "fieldtype": "Date", "width": 75 },
        {"label": _("Version"), "fieldname": "version", "fieldtype": "Data", "width": 65 },
    ]


def get_data(filters):
    query = f"""
        SELECT
            `tabQM Analytical Procedure`.`name`,
            `tabQM Analytical Procedure`.`analyte`,
            `tabQM Analytical Procedure`.`matrix`,
            `tabQM Analytical Procedure`.`test_technique`,
            `tabQM Analytical Procedure`.`device_model`,
            `tabQM Analytical Procedure`.`quality_control`,
            `tabQM Document`.`company`,
            `tabQM Document`.`name` AS `qm_document_id`,
            `tabQM Document`.`title`,
            `tabQM Document`.`valid_from`,
            `tabQM Document`.`version`
        FROM `tabQM Analytical Procedure`
        LEFT JOIN `tabQM Document Link` ON `tabQM Document Link`.`parent` = `tabQM Analytical Procedure`.`name`
        LEFT JOIN `tabQM Document` ON SUBSTRING_INDEX(`tabQM Document`.`name`, '-', 1) = SUBSTRING_INDEX(`tabQM Document Link`.`qm_document`, '-', 1)
        WHERE `tabQM Analytical Procedure`.`docstatus` = 1
        ORDER BY `tabQM Analytical Procedure`.`name` ASC
        ;"""
    return frappe.db.sql(query, as_dict=True)


def execute(filters=None):
    columns, data = get_columns(filters), get_data(filters)
    return columns, data
