# Copyright (c) 2024, Microsynth, libracore and contributors and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.utils import flt

def execute(filters=None):
    columns = get_columns()
    data = get_data(filters)
    return columns, data


def get_columns():
    columns = [
        {"label": _("Date"), "fieldname": "date", "fieldtype": "Date", "width": 80},
        {"label": _("ID"), "fieldname": "link", "fieldtype": "Link", "options": "Accounting Note", "width": 80},
        {"label": _("Reference"), "fieldname": "reference_name", "fieldtype": "Dynamic Link", "options": "reference_doctype", "width": 125},
        {"label": _("Note"), "fieldname": "note", "fieldtype": "Data", "width": 200, 'options': 'currency'},
        {"label": _("Amount"), "fieldname": "amount", "fieldtype": "Currency", "options": "currency", "width": 75},
        {"label": _("Status"), "fieldname": "status", "fieldtype": "Data", "width": 60},
        {"label": _("Related"), "fieldname": "related", "fieldtype": "data", "width": 200},
        {"label": _("Remarks"), "fieldname": "remarks", "fieldtype": "Data", "width": 250}
    ]
    return columns


def get_data(filters, short=False):
    conditions = ""
    if filters.account:
        conditions += """ AND `tabAccounting Note`.`account` = "{a}" """.format(a=filters.account)
    if filters.status:
        conditions += """ AND `tabAccounting Note`.`status` = "{s}" """.format(s=filters.status)
        
    sql_query = """
        SELECT
            `tabAccounting Note`.`date`,
            `tabAccounting Note`.`reference_doctype`,
            `tabAccounting Note`.`reference_name`,
            `tabAccounting Note`.`note`,
            `tabAccounting Note`.`amount`,
            `tabAccounting Note`.`currency`,
            `tabAccounting Note`.`status`,
            `tabAccounting Note`.`name` AS `link`,
            SUBSTRING(`tabAccounting Note`.`remarks`, 1, 140) AS `remarks`,
            GROUP_CONCAT(`tabAccounting Note Reference`.`reference_name`) AS `related`
        FROM `tabAccounting Note`
        LEFT JOIN `tabAccounting Note Reference` ON `tabAccounting Note Reference`.`parent` = `tabAccounting Note`.`name`
        WHERE 
            `tabAccounting Note`.`date` BETWEEN "{from_date}" AND "{to_date}"
            {conditions}
        GROUP BY `tabAccounting Note`.`name`
        ORDER BY `tabAccounting Note`.`date` ASC;
    """.format(from_date=filters.from_date, to_date=filters.to_date, conditions=conditions)
    
    data = frappe.db.sql(sql_query, as_dict=True)
                
    return data
