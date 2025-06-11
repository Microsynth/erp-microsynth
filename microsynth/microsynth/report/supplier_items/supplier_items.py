# Copyright (c) 2025, Microsynth
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _


def get_columns():
    return [
        {"label": _("Item"), "fieldname": "item_code", "fieldtype": "Link", "options": "Item", "width": 470, "align": "left"},
        {"label": _("Material Code"), "fieldname": "material_code", "fieldtype": "Data", "width": 95},
        {"label": _("Stock UOM"), "fieldname": "stock_uom", "fieldtype": "Data", "width": 90},
        {"label": _("Supplier"), "fieldname": "supplier", "fieldtype": "Link", "options": "Supplier", "width": 80},
        {"label": _("Supplier Name"), "fieldname": "supplier_name", "fieldtype": "Data", "width": 250},
        {"label": _("Supplier Part Number"), "fieldname": "supplier_part_no", "fieldtype": "Data", "width": 200, "align": "left"},
        {"label": _("Substitute Status"), "fieldname": "substitute_status", "fieldtype": "Data", "width": 120}
    ]


def get_data(filters):
    conditions = ""
    values = {}

    if filters.get("item_id"):
        conditions += " AND `tabItem`.`name` = %(item_id)s"
        values["item_id"] = filters["item_id"]
    if filters.get("item_name"):
        conditions += " AND `tabItem`.`item_name` LIKE %(item_name)s"
        values["item_name"] = "%" + filters["item_name"] + "%"
    if filters.get("supplier"):
        conditions += " AND `tabItem Supplier`.`supplier` = %(supplier)s"
        values["supplier"] = filters["supplier"]
    if filters.get("supplier_part_no"):
        conditions += " AND `tabItem Supplier`.`supplier_part_no` LIKE %(supplier_part_no)s"
        values["supplier_part_no"] = "%" + filters["supplier_part_no"] + "%"

    query = """
        SELECT
            `tabItem`.`name` AS item_code,
            `tabItem`.`item_name`,
            `tabItem`.`material_code`,
            `tabItem Supplier`.`supplier`,
            `tabSupplier`.`supplier_name`,
            `tabItem Supplier`.`supplier_part_no`,
            `tabItem Supplier`.`substitute_status`,
            `tabItem`.`item_group`,
            `tabItem`.`stock_uom`
        FROM `tabItem`
        LEFT JOIN `tabItem Supplier`
            ON `tabItem Supplier`.`parent` = `tabItem`.`name`
        LEFT JOIN `tabSupplier`
            ON `tabSupplier`.`name` = `tabItem Supplier`.`supplier`
        WHERE `tabItem`.`item_group` = 'Purchasing'
        {conditions}
    """.format(conditions=conditions)

    return frappe.db.sql(query, values, as_dict=True)


def execute(filters=None):
    filters = filters or {}
    columns = get_columns()
    data = get_data(filters)
    return columns, data