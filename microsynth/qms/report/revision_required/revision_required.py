# Copyright (c) 2024, Microsynth, libracore and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _


def get_columns(filters):
    return [
        {"label": _("Document Name"), "fieldname": "name", "fieldtype": "Dynamic Link", "options": "QM Document", "width": 150 },
        {"label": _("Document Title"), "fieldname": "title", "fieldtype": "Data", "width": 300 },
        {"label": _("Released"), "fieldname": "released_on", "fieldtype": "Date", "width": 75 },
        {"label": _("Valid from"), "fieldname": "valid_from", "fieldtype": "Date", "width": 75 },
        {"label": _("Last Revision"), "fieldname": "last_revision", "fieldtype": "Date", "width": 95 },
        {"label": _("Valid till"), "fieldname": "valid_till", "fieldtype": "Date", "width": 75 },
        {"label": _("Creator"), "fieldname": "created_by", "fieldtype": "Link", "options":"User", "width": 200 }
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
            `tabQM Document`.`valid_till`,
            `tabQM Document`.`created_by`
        FROM `tabQM Document`
        WHERE `tabQM Document`.`status` = 'Valid'
            AND `tabQM Document`.`released_on` < DATE_ADD(NOW(), INTERVAL -33 MONTH)
            {filter_conditions}
    """.format(filter_conditions=filter_conditions)

    raw_data = frappe.db.sql(query, as_dict=True)
    refined_data = []

    for doc in raw_data:
        # TODO: Replace modified by date of signature
        revisions = frappe.get_all("QM Revision", filters=[['document_name', '=', doc['name']]], fields=['name', 'modified'], order_by='modified desc')
        if len(revisions) == 0:
            refined_data.append(doc)
            continue
        else:
            doc['last_revision'] = revisions[0]['modified']
            refined_data.append(doc)

    return refined_data


def execute(filters=None):
    columns, data = get_columns(filters), get_data(filters)
    return columns, data
