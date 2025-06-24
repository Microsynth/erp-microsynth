# -*- coding: utf-8 -*-
# Copyright (c) 2025, Microsynth, libracore and contributors
# For license information, please see license.txt

import frappe
import json


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


@frappe.whitelist(allow_guest=True)
def get_item_details(item_code):
    if not item_code:
        return None
    item = frappe.get_value("Item", item_code, ["name", "item_name", "material_code"], as_dict=True)
    return item


@frappe.whitelist(allow_guest=True)
def create_stock_entry(items, warehouse):
    if isinstance(items, str):
        items = json.loads(items)

    if not warehouse or not items:
        frappe.throw("Warehouse and items are required.")

    company_code = warehouse[-3:]
    company = frappe.get_value("Company", {"abbr": company_code}, "name") or company_code

    stock_entry = frappe.new_doc("Stock Entry")
    stock_entry.stock_entry_type = "Material Issue"
    stock_entry.company = company
    stock_entry.set_warehouse = warehouse

    for item in items:
        stock_entry.append("items", {
            "item_code": item.get("item_code"),
            "qty": item.get("qty"),
            "batch_no": item.get("batch_no"),
            "s_warehouse": warehouse
        })

    stock_entry.insert(ignore_permissions=True)
    stock_entry.submit()
    frappe.db.commit()

    return stock_entry.name
