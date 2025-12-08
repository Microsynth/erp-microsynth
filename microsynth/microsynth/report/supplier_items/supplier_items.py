# Copyright (c) 2025, Microsynth
# For license information, please see license.txt

from __future__ import unicode_literals
import json
import frappe
from frappe import _
from microsynth.microsynth.purchasing import get_location_path_string


def get_columns():
    return [
        {"label": _("Supplier Part Nr."), "fieldname": "supplier_part_no", "fieldtype": "Data", "width": 120, "align": "left"},
        {"label": _("Item"), "fieldname": "item_code", "fieldtype": "Link", "options": "Item", "width": 315, "align": "left"},
        {"label": _("Pack Size"), "fieldname": "pack_size", "fieldtype": "Float", "precision": 2, "width": 75},
        {"label": _("Pack UOM"), "fieldname": "pack_uom", "fieldtype": "Data", "width": 80},
        {"label": _("Material Code"), "fieldname": "material_code", "fieldtype": "Data", "width": 95},
        {"label": _("Supplier"), "fieldname": "supplier", "fieldtype": "Link", "options": "Supplier", "width": 65},
        {"label": _("Supplier Name"), "fieldname": "supplier_name", "fieldtype": "Data", "width": 210},
        {"label": _("Price"), "fieldname": "price_list_rate", "fieldtype": "Currency", "options": "currency", "width": 95},
        {"label": _("Purchase UOM"), "fieldname": "purchase_uom", "fieldtype": "Data", "width": 100},
        {"label": _("Conv. Factor"), "fieldname": "conversion_factor", "fieldtype": "Float", "precision": 2, "width": 80},
        {"label": _("Stock UOM"), "fieldname": "stock_uom", "fieldtype": "Data", "width": 80},
        {"label": _("Safety Stock"), "fieldname": "safety_stock", "fieldtype": "Float", "precision": 2, "width": 90},
        {"label": _("Lead Time Days"), "fieldname": "lead_time_days", "fieldtype": "Int", "width": 110},
        {"label": _("Shelf Life Years"), "fieldname": "shelf_life_in_years", "fieldtype": "Float", "precision": 2, "width": 115},
        {"label": _("Shelf Life Days"), "fieldname": "shelf_life_in_days", "fieldtype": "Int", "width": 105, "align": "left"},
        {"label": _("Min Order Qty"), "fieldname": "min_order_qty", "fieldtype": "Float", "width": 100},
        {"label": _("Substitute Status"), "fieldname": "substitute_status", "fieldtype": "Data", "width": 125},
        {"label": _("Locations"), "fieldname": "locations", "fieldtype": "Data", "width": 500},
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
    if filters.get("company"):
        conditions += " AND `tabItem Default`.`company` = %(company)s"
        values["company"] = filters["company"]
    if filters.get("storage_location"):
        conditions += " AND `tabLocation Link`.`location` = %(storage_location)s"
        values["storage_location"] = filters["storage_location"]

    query = """
        SELECT
            `tabItem`.`name` AS item_code,
            `tabItem`.`item_name`,
            `tabItem`.`pack_size`,
            `tabItem`.`pack_uom`,
            `tabItem`.`material_code`,
            `tabItem Supplier`.`supplier`,
            `tabSupplier`.`supplier_name`,
            `tabItem Supplier`.`supplier_part_no`,
            `tabItem Supplier`.`substitute_status`,
            `tabItem`.`item_group`,
            `tabItem`.`purchase_uom`,
            `tabUOM Conversion Detail`.`conversion_factor`,
            `tabItem`.`stock_uom`,
            `tabItem Price`.`price_list_rate`,
            `tabItem`.`min_order_qty`,
            `tabItem`.`safety_stock`,
            `tabItem`.`lead_time_days`,
            `tabItem`.`shelf_life_in_days`,
            ROUND(`tabItem`.`shelf_life_in_days` / 365, 2) AS shelf_life_in_years,
            `tabItem Price`.`currency`
        FROM `tabItem`
        LEFT JOIN `tabUOM Conversion Detail`
            ON `tabUOM Conversion Detail`.`parent` = `tabItem`.`name`
            AND `tabUOM Conversion Detail`.`uom` = `tabItem`.`purchase_uom`
        LEFT JOIN `tabItem Supplier`
            ON `tabItem Supplier`.`parent` = `tabItem`.`name`
        LEFT JOIN `tabItem Default`
            ON `tabItem Default`.`parent` = `tabItem`.`name`
        LEFT JOIN `tabLocation Link` ON
            `tabLocation Link`.`parent` = `tabItem`.`name`
            AND `tabLocation Link`.`parentfield` = 'storage_locations'
        LEFT JOIN `tabSupplier`
            ON `tabSupplier`.`name` = `tabItem Supplier`.`supplier`
        LEFT JOIN `tabItem Price`
            ON `tabItem Price`.`item_code` = `tabItem`.`name`
            AND `tabItem Price`.`price_list` = `tabSupplier`.`default_price_list`
            AND `tabItem Price`.`min_qty` = 1
        WHERE `tabItem`.`item_group` = 'Purchasing'
        {conditions}
    """.format(conditions=conditions)

    data = frappe.db.sql(query, values, as_dict=True)

    # --- Enrich with Locations ---
    for row in data:
        item_code = row["item_code"]

        # Get child table entries from Table MultiSelect
        links = frappe.get_all(
            "Location Link",
            filters={"parent": item_code, "parentfield": "storage_locations"},
            fields=["location"]
        )
        if not links:
            row["locations"] = ""
            continue

        # Convert each location into "BAL / F1 / R101 / Freezer / Rack 4"
        path_strings = [
            get_location_path_string(link["location"])
            for link in links
            if link.get("location")
        ]
        row["locations"] = "  |  ".join(path_strings)

    return data


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
    item.item_group = "Purchasing"
    item.pack_size = data.get("pack_size")
    item.pack_uom = data.get("pack_uom")
    item.stock_uom = data.get("stock_uom")
    item.material_code = material_code
    item.purchase_uom = data.get("purchase_uom")
    item.shelf_life_in_days = int(float(data.get("shelf_life_in_years") or 0) * 365)
    item.is_purchase_item = 1
    item.is_sales_item = 0
    item.is_stock_item = 1
    item.has_batch_no = 1

    # --- UOM Conversion (single entry) ---
    if data.get("purchase_uom"):
        item.append("uoms", {
            "uom": data.get("purchase_uom"),
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
