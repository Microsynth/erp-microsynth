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
def create_stock_entry(items, warehouse, user):
    if isinstance(items, str):
        items = json.loads(items)

    if not warehouse or not items or not user:
        frappe.throw("Warehouse, items and user are required.")

    company_code = warehouse[-3:]
    company = frappe.get_value("Company", {"abbr": company_code}, "name") or company_code

    stock_entry = frappe.new_doc("Stock Entry")
    stock_entry.stock_entry_type = "Material Issue"
    stock_entry.company = company
    stock_entry.set_warehouse = warehouse
    stock_entry.owner = user

    for item in items:
        has_batch_no = frappe.get_value("Item", item.get("item_code"), "has_batch_no")
        if has_batch_no and not item.get("batch_no"):
            frappe.throw(f"Batch number is required for item {item.get('item_code')} as it has batch management enabled.")

    for item in items:
        item_row = {
            "item_code": item.get("item_code"),
            "qty": item.get("qty"),
            "s_warehouse": warehouse
        }
        batch_no = item.get("batch_no")
        if batch_no:
            item_row["batch_no"] = batch_no
        stock_entry.append("items", item_row)

    stock_entry.insert(ignore_permissions=True)
    stock_entry.submit()
    frappe.db.commit()

    return stock_entry.name
