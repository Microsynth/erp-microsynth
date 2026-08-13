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
        {"label": _("Due Date"), "fieldname": "due_date", "fieldtype": "Date", "width": 80 },
        {"label": _("Signed on"), "fieldname": "signed_on", "fieldtype": "Date", "width": 80 }
    ]


def get_data(filters):

    filter_conditions = ''
    query_values = {}

    if filters:
        if filters.get('user'):
            filter_conditions += "AND `tabQM Training Record`.`trainee` = %(user)s"
            query_values['user'] = filters.get('user')
        if filters.get('qm_process'):
            filter_conditions += "AND `tabQM Document`.`qm_process` = %(qm_process)s"
            query_values['qm_process'] = filters.get('qm_process')
        if filters.get('qm_document'):
            filter_conditions += "AND `tabQM Training Record`.`document_name` = %(qm_document)s"
            query_values['qm_document'] = filters.get('qm_document')
        if filters.get('qm_document_list'):
            qm_document_prefixes = [
                entry.strip() for entry in filters.get('qm_document_list').replace('\n', ',').split(',') if entry.strip()
            ]
            if qm_document_prefixes:
                list_conditions = []
                for i, prefix in enumerate(qm_document_prefixes):
                    key = f'qm_document_prefix_{i}'
                    list_conditions.append(f"`tabQM Training Record`.`document_name` LIKE %({key})s")
                    query_values[key] = f"{prefix}%"
                filter_conditions += "AND ({conditions})".format(conditions=" OR ".join(list_conditions))
        if filters.get('limit_to_valid'):
            filter_conditions += "AND `tabQM Document`.`status` = 'Valid'"
        if filters.get('training_status'):
            training_status_map = {
                'Unsigned': 0,
                'Signed': 1,
                'Cancelled': 2
            }
            mapped_status = training_status_map.get(filters.get('training_status'))
            if mapped_status is not None:
                filter_conditions += "AND `tabQM Training Record`.`docstatus` = %(training_status)s"
                query_values['training_status'] = mapped_status

        query = """
            SELECT `tabQM Training Record`.`name`,
                `tabQM Training Record`.`trainee`,
                `tabQM Training Record`.`docstatus` AS `training_status`,
                CASE
                    WHEN `tabQM Training Record`.`docstatus` = 0 THEN 'Unsigned'
                    WHEN `tabQM Training Record`.`docstatus` = 1 THEN 'Signed'
                    WHEN `tabQM Training Record`.`docstatus` = 2 THEN 'Cancelled'
                END AS `training_status`,
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

        return frappe.db.sql(query, query_values, as_dict=True)
    else:
        return None


def execute(filters=None):
    columns, data = get_columns(filters), get_data(filters)
    return columns, data
