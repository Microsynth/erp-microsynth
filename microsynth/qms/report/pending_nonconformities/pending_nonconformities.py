# Copyright (c) 2024, Microsynth, libracore and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
from microsynth.microsynth.utils import user_has_role


def get_columns(filters):
    return [
        {"label": _("ID"), "fieldname": "name", "fieldtype": "Link", "options": "QM Nonconformity", "width": 80},
        {"label": _("Title"), "fieldname": "title", "fieldtype": "Data", "width": 300},
        {"label": _("Status"), "fieldname": "status", "fieldtype": "Data", "width": 100},
        {"label": _("Creator"), "fieldname": "created_by", "fieldtype": "Link", "options": "User", "width": 200}
    ]


def get_data(filters):

    filter_conditions = ''

    if filters.get('name'):
        filter_conditions += f"AND `tabQM Nonconformity`.`name` = '{filters.get('name')}'"
    if filters.get('title'):
        filter_conditions += f"AND `tabQM Nonconformity`.`title` = '{filters.get('title')}'"
    if filters.get('nc_type'):
        filter_conditions += f"AND `tabQM Nonconformity`.`nc_type` = '{filters.get('nc_type')}'"
    if filters.get('status'):
        filter_conditions += f"AND `tabQM Nonconformity`.`status` = '{filters.get('status')}'"
    if filters.get('created_by'):
        filter_conditions += f"AND `tabQM Nonconformity`.`created_by` = '{filters.get('created_by')}'"
    if filters.get('qm_process'):
        filter_conditions += f"AND `tabQM Nonconformity`.`qm_process` = '{filters.get('qm_process')}'"
    # Created Track & Trend can be closed by the creator
    filter_conditions += f"AND ((`tabQM Nonconformity`.`status` = 'Created' AND `tabQM Nonconformity`.`nc_type` = 'Track & Trend' AND `tabQM Nonconformity`.`created_by` = '{frappe.session.user}') "
    # Completed Event, OOS or Track & Trend can be closed by the creator
    filter_conditions += f" OR (`tabQM Nonconformity`.`status` = 'Completed' AND `tabQM Nonconformity`.`nc_type` IN ('Track & Trend', 'OOS', 'Event') AND `tabQM Nonconformity`.`created_by` = '{frappe.session.user}')"
    if user_has_role(frappe.session.user, "QAU"):
        filter_conditions += f" OR `tabQM Nonconformity`.`status` = 'Plan Approval'"
        filter_conditions += f" OR `tabQM Nonconformity`.`status` = 'Created'"
    filter_conditions += ')'

    query = f"""
        SELECT
            `tabQM Nonconformity`.`name`,
            `tabQM Nonconformity`.`title`,
            `tabQM Nonconformity`.`status`,
            `tabQM Nonconformity`.`created_by`
        FROM `tabQM Nonconformity`
        WHERE `tabQM Nonconformity`.`docstatus` = 1
            {filter_conditions}
    """
    return frappe.db.sql(query, as_dict=True)


def execute(filters=None):
    columns, data = get_columns(filters), get_data(filters)
    return columns, data
