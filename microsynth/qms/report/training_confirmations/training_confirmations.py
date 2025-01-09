# Copyright (c) 2024, Microsynth, libracore and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _


def get_columns(filters):
    return [
        {"label": _("Training Record"), "fieldname": "name", "fieldtype": "Link", "options": "QM Training Record", "width": 110 },
        {"label": _("Trainee"), "fieldname": "trainee", "fieldtype": "Link", "options": "User", "width": 210 },
        {"label": _("Training Status"), "fieldname": "training_status", "fieldtype": "Data", "width": 105 },
        {"label": _("Document Type"), "fieldname": "document_type", "fieldtype": "Data", "options": "DocType", "width": 105 },
        {"label": _("Document Name"), "fieldname": "document_name", "fieldtype": "Dynamic Link", "options": "document_type", "width": 135 },
        {"label": _("Document Title"), "fieldname": "title", "fieldtype": "Data", "width": 300 },
        {"label": _("Document Status"), "fieldname": "status", "fieldtype": "Data", "width": 115 },
        {"label": _("Request Date"), "fieldname": "creation", "fieldtype": "Date", "width": 125 },
        {"label": _("Due Date"), "fieldname": "due_date", "fieldtype": "Date", "width": 75 },
        {"label": _("Signed on"), "fieldname": "signed_on", "fieldtype": "Date", "width": 75 }
    ]


def get_data(filters):

    filter_conditions = ''

    if filters:
        if filters.get('user'):
            filter_conditions += f"AND `tabQM Training Record`.`trainee` = '{filters.get('user')}'"
        if filters.get('qm_document'):
            filter_conditions += f"AND `tabQM Training Record`.`document_name` = '{filters.get('qm_document')}'"
        if filters.get('limit_to_valid'):
            filter_conditions += f"AND `tabQM Document`.`status` = 'Valid'"
    
        query = """
            SELECT `tabQM Training Record`.`name`,
                `tabQM Training Record`.`trainee`,
                `tabQM Training Record`.`docstatus` AS `training_status`,
                IF(`tabQM Training Record`.`docstatus` = 1, 'Signed', 'Unsigned') as `training_status`,
                `tabQM Training Record`.`document_type`,
                `tabQM Training Record`.`document_name`,
                `tabQM Document`.`title`,
                `tabQM Document`.`status`,
                `tabQM Training Record`.`creation`,
                `tabQM Training Record`.`due_date`,
                `tabQM Training Record`.`signed_on`
            FROM `tabQM Training Record`
            LEFT JOIN `tabQM Document` ON `tabQM Document`.`name` = `tabQM Training Record`.`document_name` 
                AND `tabQM Training Record`.`document_type` = "QM Document"
            WHERE TRUE
                {filter_conditions}
        """.format(filter_conditions=filter_conditions)

        return frappe.db.sql(query, as_dict=True)
    else:
        return None


def execute(filters=None):
    columns, data = get_columns(filters), get_data(filters)
    return columns, data
