# Copyright (c) 2024, Microsynth, libracore and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _


def get_columns(filters):
    return [
        {"label": _("Document Name"), "fieldname": "name", "fieldtype": "Dynamic Link", "options": "QM Document", "width": 125 },
        {"label": _("Document Title"), "fieldname": "title", "fieldtype": "Data", "width": 290 },
        {"label": _("Released"), "fieldname": "released_on", "fieldtype": "Date", "width": 80 },
        {"label": _("Valid from"), "fieldname": "valid_from", "fieldtype": "Date", "width": 80 },
        {"label": _("Last Revision"), "fieldname": "last_revision_on", "fieldtype": "Date", "width": 85 },
        {"label": _("Valid till"), "fieldname": "valid_till", "fieldtype": "Date", "width": 80 },
        {"label": _("Creator"), "fieldname": "created_by", "fieldtype": "Link", "options":"User", "width": 140 },
        {"label": _("Revision Draft"), "fieldname": "revision", "fieldtype": "Link", "options":"QM Revision", "width": 95 },
        {"label": _("Revision Draft created"), "fieldname": "revision_creation_date", "fieldtype": "Date", "width": 140 },
        {"label": _("Intended Revisor"), "fieldname": "revisor", "fieldtype": "Link", "options":"User", "width": 140 },
        {"label": _("Revision due"), "fieldname": "revision_due_date", "fieldtype": "Date", "width": 90 },
        {"label": _("Revision Draft comments"), "fieldname": "revision_comments", "fieldtype": "Data", "width": 290 }
    ]


def get_data(filters):
    """
    Return all QM Documents that are released more than 33 months ago (reach the 3 years in less than 3 months).
    """
    filter_conditions = ''

    if filters.get('document_type'):
        filter_conditions += f"AND `tabQM Document`.`document_type` = '{filters.get('document_type')}'"

    query = """
        SELECT
            `tabQM Document`.`document_type`,
            `tabQM Document`.`name`,
            `tabQM Document`.`title`,
            `tabQM Document`.`released_on`,
            `tabQM Document`.`valid_from`,
            `tabQM Document`.`last_revision_on`,
            `tabQM Document`.`valid_till`,
            `tabQM Document`.`created_by`
        FROM `tabQM Document`
        WHERE `tabQM Document`.`status` = 'Valid'
            AND `tabQM Document`.`released_on` <= DATE_ADD(NOW(), INTERVAL -34 MONTH)
            AND `tabQM Document`.`last_revision_on` <= DATE_ADD(NOW(), INTERVAL -34 MONTH)
            {filter_conditions}
    """.format(filter_conditions=filter_conditions)

    data = frappe.db.sql(query, as_dict=True)

    for qm_doc in data:
        qmres = frappe.get_all("QM Revision", filters={'docstatus': 0, 'document_name': qm_doc['name'], 'document_type': 'QM Document'}, fields=['name', 'creation', 'revisor', 'due_date', 'comments'])
        if len(qmres) > 1:
            frappe.throw(f"There are {len(qmres)} QM Revision Drafts for QM Document {qm_doc['name']}. Please submit or force cancel all of them except max. one.")
        elif len(qmres) == 1:
            qm_doc['revision'] = qmres[0]['name']
            qm_doc['revision_creation_date'] = qmres[0]['creation']
            qm_doc['revisor'] = qmres[0]['revisor']
            qm_doc['revision_due_date'] = qmres[0]['due_date']
            qm_doc['revision_comments'] = qmres[0]['comments']
        else:
            qm_doc['revision'] = None
            qm_doc['revision_creation_date'] = None
            qm_doc['revisor'] = None
            qm_doc['revision_due_date'] = None
            qm_doc['revision_comments'] = None

    return data


def execute(filters=None):
    columns, data = get_columns(filters), get_data(filters)
    return columns, data
