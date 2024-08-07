# Copyright (c) 2024, Microsynth, libracore and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _


def get_columns(filters):
    return [
        {"label": _("User"), "fieldname": "user_name", "fieldtype": "Link", "options": "User Settings", "width": 250}
    ]


def get_data(filters):
    conditions = ""
    if filters:
        if filters.get('chapter'):
            conditions += f"AND (`tabQM User Process Assignment`.`chapter` = '{filters.get('chapter')}' OR `tabQM User Process Assignment`.`all_chapters` = 1)"
        if filters.get('company'):
            conditions += f"AND `tabQM User Process Assignment`.`company` = '{filters.get('company')}'"

        query = f"""
            SELECT DISTINCT 
                `tabUser Settings`.`name`,
                `tabUser Settings`.`name` as `user_name`,
                `tabQM User Process Assignment`.`company`
            FROM `tabUser Settings`
            LEFT JOIN `tabQM User Process Assignment` ON `tabQM User Process Assignment`.`parent` = `tabUser Settings`.`name`
            WHERE `tabQM User Process Assignment`.`process_number` = '{filters.get('process_number')}'
                AND `tabQM User Process Assignment`.`subprocess_number` = '{filters.get('subprocess_number')}'
                {conditions}
            """
        return frappe.db.sql(query, as_dict=True)
    else:
        return None


def execute(filters=None):
    columns, data = get_columns(filters), get_data(filters)
    return columns, data


def get_sql_list(list):
    if list:
        return (','.join('"{0}"'.format(e) for e in list))
    else:
        return '""'


@frappe.whitelist()
def get_users(qm_processes, companies=None):
    if not qm_processes and not companies:
        return None

    companies_list = frappe.parse_json(companies)    
    if companies and len(companies_list) > 0:
        company_condition = f"`tabQM User Process Assignment`.`company` IN ({get_sql_list(companies_list)})"
    else:
        company_condition = "TRUE"

    qm_processes_list = frappe.parse_json(qm_processes)
    if qm_processes and len(qm_processes_list) > 0:
        qm_process_conditions = "AND (FALSE "
        for qm_process in qm_processes_list:
            qm_process_doc = frappe.get_doc("QM Process", qm_process)
            qm_process_conditions += f" OR (`tabQM User Process Assignment`.`process_number` = '{qm_process_doc.process_number}' AND `tabQM User Process Assignment`.`subprocess_number` = '{qm_process_doc.subprocess_number}'"
            if qm_process_doc.chapter:
                qm_process_conditions += f" AND (`tabQM User Process Assignment`.`chapter` = '{qm_process_doc.chapter}' OR `tabQM User Process Assignment`.`all_chapters` = 1))"
            else:
                qm_process_conditions += ")"
        qm_process_conditions += ")"
    else:
        qm_process_conditions = ""

    query = f"""
        SELECT DISTINCT
            `tabUser Settings`.`name`,
            `tabUser Settings`.`name` as `user_name`
        FROM `tabUser Settings`
        LEFT JOIN `tabQM User Process Assignment` ON `tabQM User Process Assignment`.`parent` = `tabUser Settings`.`name`
        WHERE {company_condition}
            {qm_process_conditions}
        """
    return frappe.db.sql(query, as_dict=True)
