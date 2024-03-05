# Copyright (c) 2024, Microsynth, libracore and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _


def get_columns(filters):
    return [
        {"label": _("Document Name"), "fieldname": "name", "fieldtype": "Dynamic Link", "options": "document_type", "width": 150 },
        {"label": _("Document Title"), "fieldname": "title", "fieldtype": "Data", "width": 300 },
        {"label": _("Status"), "fieldname": "status", "fieldtype": "Data", "width": 100 },
        {"label": _("Valid from"), "fieldname": "valid_from", "fieldtype": "Date", "width": 75 },
        {"label": _("Valid till"), "fieldname": "valid_till", "fieldtype": "Date", "width": 75 },
        {"label": _("Created"), "fieldname": "created_on", "fieldtype": "Date", "width": 75 },
        {"label": _("Creator"), "fieldname": "created_by", "fieldtype": "Link", "options":"User", "width": 200 }
    ]


def get_data(filters):

    filter_conditions = ''

    if filters.get('created_by'):
        filter_conditions += f"AND `tabQM Document`.`created_by` = '{filters.get('created_by')}'"
    if filters.get('document_type'):
        filter_conditions += f"AND `tabQM Document`.`document_type` = '{filters.get('document_type')}'"

    query = """
        SELECT
            `tabQM Document`.`document_type`,
            `tabQM Document`.`name`,
            `tabQM Document`.`title`,
            `tabQM Document`.`status`,
            `tabQM Document`.`valid_from`,
            `tabQM Document`.`valid_till`,
            `tabQM Document`.`created_on`,
            `tabQM Document`.`created_by`
        FROM `tabQM Document`
        WHERE (`tabQM Document`.`status` = 'Reviewed'
            OR (`tabQM Document`.`document_type` IN ('PROT', 'LIST', 'FORM', 'CL')
                AND `tabQM Document`.`status` = 'Created'))
            {filter_conditions}
    """.format(filter_conditions=filter_conditions)

    return frappe.db.sql(query, as_dict=True)


def execute(filters=None):
    columns, data = get_columns(filters), get_data(filters)
    return columns, data
