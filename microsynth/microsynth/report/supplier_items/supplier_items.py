# Copyright (c) 2025, Microsynth
# For license information, please see license.txt

from __future__ import unicode_literals
import json
import frappe
from frappe import _


def get_columns():
    return [
        {"label": _("Supplier Part Number"), "fieldname": "supplier_part_no", "fieldtype": "Data", "width": 180, "align": "left"},
        {"label": _("Item"), "fieldname": "item_code", "fieldtype": "Link", "options": "Item", "width": 450, "align": "left"},
        {"label": _("Material Code"), "fieldname": "material_code", "fieldtype": "Data", "width": 100},
        {"label": _("Supplier"), "fieldname": "supplier", "fieldtype": "Link", "options": "Supplier", "width": 80},
        {"label": _("Supplier Name"), "fieldname": "supplier_name", "fieldtype": "Data", "width": 250},
        {"label": _("Stock UOM"), "fieldname": "stock_uom", "fieldtype": "Data", "width": 100},
        {"label": _("Price List Rate"), "fieldname": "price_list_rate", "fieldtype": "Currency", "options": "currency", "width": 105},
        {"label": _("Substitute Status"), "fieldname": "substitute_status", "fieldtype": "Data", "width": 125},
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
            `tabItem`.`stock_uom`,
            `tabItem Price`.`price_list_rate`,
            `tabItem Price`.`currency`
        FROM `tabItem`
        LEFT JOIN `tabItem Supplier`
            ON `tabItem Supplier`.`parent` = `tabItem`.`name`
        LEFT JOIN `tabSupplier`
            ON `tabSupplier`.`name` = `tabItem Supplier`.`supplier`
        LEFT JOIN `tabItem Price`
            ON `tabItem Price`.`item_code` = `tabItem`.`name`
            AND `tabItem Price`.`price_list` = `tabSupplier`.`default_price_list`
            AND `tabItem Price`.`min_qty` = 1
        WHERE `tabItem`.`item_group` = 'Purchasing'
        {conditions}
    """.format(conditions=conditions)

    return frappe.db.sql(query, values, as_dict=True)


def execute(filters=None):
    filters = filters or {}
    columns = get_columns()
    data = get_data(filters)
    return columns, data


@frappe.whitelist()
def create_purchasing_item(data):

    if isinstance(data, str):
        data = json.loads(data)

    # Extract core fields
    material_code = data.get('material_code')
    item_code = data.get('item_code')
    item_name = data.get('item_name')

    # --- Validation ---
    if frappe.db.exists("Item", item_code):
        frappe.throw(_("An item with Item Code {0} already exists").format(item_code))

    if frappe.db.exists("Item", {"item_name": item_name}):
        frappe.throw(_("An item with Item Name {0} already exists").format(item_name))

    if material_code:
        existing = frappe.db.exists("Item", {"material_code": material_code})
        if existing:
            frappe.throw(_("An item with Material Code {0} already exists: {1}").format(material_code, existing))

    if float(data.get("shelf_life_in_years") or 0) <= 0:
        frappe.throw(_("Shelf Life in Years must be greater than 0."))

    # --- Create Item ---
    item = frappe.new_doc("Item")
    item.item_code = item_code
    item.item_name = item_name
    item.material_code = material_code
    item.stock_uom = data.get("stock_uom")
    item.shelf_life_in_days = int(float(data.get("shelf_life_in_years") or 0) * 365)
    item.item_group = "Purchasing"
    item.is_purchase_item = 1
    item.is_sales_item = 0
    item.is_stock_item = 1

    # --- UOM Conversion (single entry) ---
    if data.get("uom"):
        item.append("uoms", {
            "uom": data.get("uom"),
            "conversion_factor": data.get("conversion_factor") or 1.0
        })

    # --- Item Default (single entry) ---
    if data.get("company"):
        item.append("item_defaults", {
            "company": data.get("company"),
            "expense_account": data.get("expense_account"),
            "default_supplier": data.get("default_supplier")
        })

    # --- Supplier Item (single entry) ---
    if data.get("supplier"):
        item.append("supplier_items", {
            "supplier": data.get("supplier"),
            "supplier_part_no": data.get("supplier_part_no"),
            "substitute_status": data.get("substitute_status")
        })

    item.insert(ignore_permissions=True)
    frappe.db.commit()

    return item.name
