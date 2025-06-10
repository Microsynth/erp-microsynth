# -*- coding: utf-8 -*-
# Copyright (c) 2025, Microsynth, libracore and contributors
# For license information, please see license.txt

import frappe


@frappe.whitelist(allow_guest=True)
def get_processes():
    """
    return a list of all QM Processes
    TODO: flag those QM Processes that need to use the Material Counter page
    """
    processes = frappe.get_all("QM Process", fields=['name'])
    return [''] + [p['name'] for p in processes]


@frappe.whitelist(allow_guest=True)
def get_user_names_by_process(qm_process, company=None):
    if company:
        company_condition = f"`tabQM User Process Assignment`.`company` = '{company}'"
    else:
        company_condition = "TRUE"
    
    qm_process_doc = frappe.get_doc("QM Process", qm_process)
    qm_process_condition = f" AND `tabQM User Process Assignment`.`process_number` = '{qm_process_doc.process_number}' AND `tabQM User Process Assignment`.`subprocess_number` = '{qm_process_doc.subprocess_number}'"
    if qm_process_doc.chapter:
        qm_process_condition += f" AND (`tabQM User Process Assignment`.`chapter` = '{qm_process_doc.chapter}' OR `tabQM User Process Assignment`.`all_chapters` = 1)"
    
    query = f"""
        SELECT DISTINCT
            `tabUser Settings`.`name`,
            `tabUser`.`full_name`
        FROM `tabUser Settings`
        LEFT JOIN `tabQM User Process Assignment` ON `tabQM User Process Assignment`.`parent` = `tabUser Settings`.`name`
        LEFT JOIN `tabUser` ON `tabUser`.`name` = `tabUser Settings`.`name`
        WHERE {company_condition}
            {qm_process_condition}
            AND `tabUser Settings`.`disabled` = 0
        """
    full_names = frappe.db.sql(query, as_dict=True)
    return [''] + [fn['name'] for fn in full_names]