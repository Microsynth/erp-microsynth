# Copyright (c) 2025, Microsynth
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _


def get_columns():
    return [
        {"label": _("Material Request"), "fieldname": "material_request", "fieldtype": "Link", "options": "Material Request", "width": 115},
        {"label": _("Request Date"), "fieldname": "transaction_date", "fieldtype": "Date", "width": 95},
        {"label": _("Required By"), "fieldname": "schedule_date", "fieldtype": "Date", "width": 85},
        {"label": _("Item"), "fieldname": "item_code", "fieldtype": "Link", "options": "Item", "width": 240},
        #{"label": _("Item Name"), "fieldname": "item_name", "fieldtype": "Data", "width": 200},
        #{"label": _("Description"), "fieldname": "description", "fieldtype": "Data", "width": 200},
        {"label": _("Qty"), "fieldname": "qty", "fieldtype": "Int", "width": 50},
        {"label": _("Supplier"), "fieldname": "supplier", "fieldtype": "Link", "options": "Supplier", "width": 65},
        {"label": _("Supplier Name"), "fieldname": "supplier_name", "fieldtype": "Data", "width": 200},
        {"label": _("Supplier Part No."), "fieldname": "supplier_part_no", "fieldtype": "Data", "width": 120},
        {"label": _("Requested By"), "fieldname": "requested_by", "fieldtype": "Link", "options": "User", "width": 200}
    ]


def get_data(filters):
    conditions = ""
    if filters and filters.get("supplier"):
        conditions += " AND `tabItem Supplier`.`supplier` = %(supplier)s"

    return frappe.db.sql(f"""
        SELECT
            `tabMaterial Request`.`name` AS material_request,
            `tabMaterial Request`.`transaction_date`,
            `tabMaterial Request Item`.`schedule_date`,
            `tabMaterial Request Item`.`item_code`,
            `tabMaterial Request Item`.`item_name`,
            `tabMaterial Request Item`.`description`,
            `tabMaterial Request Item`.`qty`,
            `tabMaterial Request Item`.`name` AS `material_request_item`,
            `tabItem Supplier`.`supplier`,
            `tabSupplier`.`supplier_name`,
            `tabItem Supplier`.`supplier_part_no`,
            IFNULL(`tabMaterial Request`.`requested_by`, `tabMaterial Request`.`owner`) AS `requested_by`
        FROM
            `tabMaterial Request Item`
        LEFT JOIN `tabMaterial Request`
            ON `tabMaterial Request Item`.`parent` = `tabMaterial Request`.`name`
        LEFT JOIN `tabItem Supplier`
            ON `tabItem Supplier`.`parent` = `tabMaterial Request Item`.`item_code`
            AND `tabItem Supplier`.`parenttype` = 'Item'
            AND `tabItem Supplier`.`idx` = 1
        LEFT JOIN `tabSupplier`
            ON `tabItem Supplier`.`supplier` = `tabSupplier`.`name`
        WHERE
            `tabMaterial Request`.`material_request_type` = 'Purchase'
            AND `tabMaterial Request`.`docstatus` = 1
            AND `tabMaterial Request`.`status` != 'Stopped'
            AND NOT EXISTS (
                SELECT 1
                FROM `tabPurchase Order Item`
                WHERE `tabPurchase Order Item`.`material_request` = `tabMaterial Request Item`.`parent`
                AND `tabPurchase Order Item`.`material_request_item` = `tabMaterial Request Item`.`name`
            )
            {conditions}
        ORDER BY
            `tabMaterial Request`.`schedule_date` ASC
    """, filters, as_dict=True)


def execute(filters=None):
    columns = get_columns()
    data = get_data(filters)
    return columns, data
