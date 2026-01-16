# Copyright (c) 2025, Microsynth
# For license information, please see license.txt

from __future__ import unicode_literals
import json
import frappe
from frappe import _
from frappe.utils import flt
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
        {"label": _("Item Name"), "fieldname": "item_name", "fieldtype": "Data", "width": 250},
        #{"label": _("Currency"), "fieldname": "currency", "fieldtype": "Data", "width": 1},
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

    # FAx: "Bitte beachte, dass der Material Code bei der Artikelerstellung nicht eindeutig sein muss."
    # if material_code:
    #     existing = frappe.db.exists("Item", {"material_code": material_code})
    #     if existing:
    #         frappe.throw(_("An item with Material Code {0} already exists: {1}").format(material_code, existing))

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


@frappe.whitelist()
def update_supplier_item(data):
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except Exception:
            frappe.throw(_("Invalid JSON input"))

    item_code = data.get('item_code')
    if not item_code:
        frappe.throw(_("Missing item_code"))

    # Check permissions
    if not frappe.has_permission("Item", "write", item_code):
        frappe.throw(_("Not permitted to edit this Item"))

    # Numeric checks
    numeric_fields = {
        "pack_size": 0,
        "conversion_factor": 0,
        "shelf_life_in_years": 0,
        "lead_time_days": 0,
        "min_order_qty": 0,
        "safety_stock": 0,
        "price_list_rate": 0
    }
    for field, min_val in numeric_fields.items():
        if field in data:
            try:
                val = flt(data[field])
                if val < min_val:
                    frappe.throw(_("{0} must be ≥ {1}").format(field.replace("_", " ").title(), min_val))
            except Exception:
                frappe.throw(_("Invalid value for {0}").format(field.replace("_", " ").title()))

    supplier = data.get("supplier").split(":")[0] if data.get("supplier") else None

    item = frappe.get_doc("Item", item_code)

    conversion_factor = flt(data.get("conversion_factor", 1))
    if data.get("stock_uom") and data.get("purchase_uom") and data.get("stock_uom") != data.get("purchase_uom"):
        if abs(conversion_factor) < 0.0001 or abs(conversion_factor - 1) < 0.0001:
            frappe.throw(_("Conversion Factor must not be 0 or 1 when Purchase UOM differs from Stock UOM."))

    # If conversion_factor and purchase_uom are given, check if UOM Conversion entry exists, else create it
    if data.get("conversion_factor") and data.get("purchase_uom"):
        uom_conversion = [u for u in item.uoms if u.uom == data["purchase_uom"]]
        if uom_conversion:
            uom_conversion[0].conversion_factor = data["conversion_factor"]
        else:
            item.append("uoms", {
                "uom": data["purchase_uom"],
                "conversion_factor": data["conversion_factor"]
            })

    # Update allowed fields on Item
    fields_to_update = [
        "item_name", "material_code", "pack_size", "pack_uom", "purchase_uom",
        "stock_uom", "safety_stock", "lead_time_days", "min_order_qty"
    ]

    for field in fields_to_update:
        if field in data:
            setattr(item, field, data[field])

    # Shelf life in years --> shelf_life_in_days (if provided)
    if "shelf_life_in_years" in data:
        try:
            shelf_years = flt(data.get("shelf_life_in_years", 0))
            if shelf_years <= 0:
                frappe.throw(_("Shelf Life in Years must be greater than 0"))
            item.shelf_life_in_days = round(shelf_years * 365)
        except Exception:
            frappe.throw(_("Invalid value for Shelf Life in Years"))

    # Update price_list_rate (Item Price) only if it changed
    if "price_list_rate" in data and supplier and data.get("currency"):
        price_list = frappe.db.get_value("Supplier", supplier, "default_price_list")
        item_prices = frappe.db.get_all("Item Price", filters={"item_code": item_code, "min_qty": 1, "currency": data.get("currency"), "price_list": price_list}, fields=["name"])
        if len(item_prices) == 1:
            price = frappe.get_doc("Item Price", item_prices[0].get("name"))
            if abs(price.price_list_rate - data["price_list_rate"]) > 0.0001:
                price.price_list_rate = data["price_list_rate"]
                price.save()
        elif len(item_prices) > 1:
            # Should not happen
            frappe.log_error(f"Multiple Item Price entries found for Item {item_code} with min_qty 1 in currency {data.get('currency')} on Price List {price_list}. Cannot update price.", "Supplier Items Report")
            pass
        else:
            # Create price if none exists (optional)
            price = frappe.new_doc("Item Price")
            price.item_code = item_code
            price.price_list = price_list
            price.price_list_rate = data["price_list_rate"]
            price.currency = data.get("currency")
            price.min_qty = 1
            price.insert()

    # Update Supplier Item child table entry
    if data.get("supplier_part_no") or supplier:
        # Find the Supplier Item child row
        supplier_item = None
        for si in item.get("supplier_items"):
            if si.supplier == supplier or si.supplier_part_no == data.get("supplier_part_no"):
                supplier_item = si
                break

        if not supplier_item and supplier and data.get("supplier_part_no"):
            # Create new supplier item child row if not found
            supplier_item = item.append("supplier_items", {})

        if supplier_item:
            if "supplier_part_no" in data:
                supplier_item.supplier_part_no = data["supplier_part_no"]
            if supplier:
                supplier_item.supplier = supplier
            if "substitute_status" in data:
                supplier_item.substitute_status = data["substitute_status"]

    item.save()
    return item.name
