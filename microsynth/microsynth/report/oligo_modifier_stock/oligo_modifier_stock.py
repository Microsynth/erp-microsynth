# Copyright (c) 2026, Microsynth
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _


def get_columns():
	return [
		{"label": _("Material Code"), "fieldname": "material_code", "fieldtype": "Data", "width": 100, "align": "left"},
		{"label": _("Location"), "fieldname": "location", "fieldtype": "Link", "options": "Location", "width": 80},
		{"label": _("Item"), "fieldname": "item_code", "fieldtype": "Link", "options": "Item", "width": 340},
		{"label": _("Pack Size"), "fieldname": "pack_size", "fieldtype": "Float", "precision": 2, "width": 75},
		{"label": _("Pack UOM"), "fieldname": "pack_uom", "fieldtype": "Link", "options": "UOM", "width": 80},
		{"label": _("Stock Qty"), "fieldname": "stock_qty", "fieldtype": "Int", "width": 85},
		{"label": _("Requested Qty"), "fieldname": "requested_qty", "fieldtype": "Int", "width": 100},
		{"label": _("Ordered Qty"), "fieldname": "ordered_qty", "fieldtype": "Int", "width": 90},
		{"label": _("Stock UOM"), "fieldname": "stock_uom", "fieldtype": "Link", "options": "UOM", "width": 80},
		{"label": _("Shelf Life (m)"), "fieldname": "shelf_life_in_months", "fieldtype": "Int", "width": 100},
		{"label": _("Supplier Item Code"), "fieldname": "supplier_item_code", "fieldtype": "Data", "width": 160},
		{"label": _("Substitute Status"), "fieldname": "substitute_status", "fieldtype": "Data", "width": 120, "align": "left"},
	]


def get_data(filters=None):
	mode = get_mode(filters)
	if mode == "Empty Locations":
		data = get_empty_locations()
	elif mode == "All Locations":
		data = get_filled_locations()
		data.extend(get_empty_locations())
	else:
		data = get_filled_locations()

	sort_rows_by_location_and_item(data)
	return data


def get_filled_locations():
	query = """
		SELECT DISTINCT
			`tabLocation`.`name` AS `location`,
			`tabItem`.`name` AS `item_code`,
			`tabItem`.`pack_size` AS `pack_size`,
			`tabItem`.`pack_uom` AS `pack_uom`,
			(
				SELECT `tabItem Supplier`.`supplier_part_no`
				FROM `tabItem Supplier`
				WHERE
					`tabItem Supplier`.`parent` = `tabItem`.`name`
					AND `tabItem Supplier`.`supplier` = (
						SELECT `tabItem Default`.`default_supplier`
						FROM `tabItem Default`
						WHERE
							`tabItem Default`.`parent` = `tabItem`.`name`
							AND IFNULL(`tabItem Default`.`default_supplier`, '') != ''
						ORDER BY `tabItem Default`.`idx` ASC
						LIMIT 1
					)
				LIMIT 1
			) AS `supplier_item_code`,
			`tabItem`.`item_name` AS `item_name`,
			`tabItem`.`material_code` AS `material_code`,
			IFNULL(FLOOR(`tabItem`.`shelf_life_in_days` * 12 / 365), 0) AS `shelf_life_in_months`,
			CAST(ROUND(IFNULL(`tabItem Stock`.`actual_qty`, 0), 0) AS SIGNED) AS `stock_qty`,
			CAST(ROUND((
				SELECT IFNULL(SUM(
					GREATEST(
						(`tabMaterial Request Item`.`qty` * IFNULL(`tabMaterial Request Item`.`conversion_factor`, 1))
						-
						(IFNULL(`tabMaterial Request Item`.`ordered_qty`, 0) * IFNULL(`tabMaterial Request Item`.`conversion_factor`, 1)),
						0
					)
				), 0)
				FROM `tabMaterial Request Item`
				INNER JOIN `tabMaterial Request`
					ON `tabMaterial Request`.`name` = `tabMaterial Request Item`.`parent`
				WHERE
					`tabMaterial Request`.`docstatus` = 1
					AND `tabMaterial Request`.`status` != 'Stopped'
					AND `tabMaterial Request Item`.`item_code` = `tabItem`.`name`
			), 0) AS SIGNED) AS `requested_qty`,
			CAST(ROUND((
				SELECT IFNULL(SUM(
					GREATEST(
						(`tabPurchase Order Item`.`qty` * IFNULL(`tabPurchase Order Item`.`conversion_factor`, 1))
						-
						(IFNULL(`tabPurchase Order Item`.`received_qty`, 0) * IFNULL(`tabPurchase Order Item`.`conversion_factor`, 1)),
						0
					)
				), 0)
				FROM `tabPurchase Order Item`
				INNER JOIN `tabPurchase Order`
					ON `tabPurchase Order`.`name` = `tabPurchase Order Item`.`parent`
				WHERE
					`tabPurchase Order`.`docstatus` = 1
					AND `tabPurchase Order Item`.`item_code` = `tabItem`.`name`
			), 0) AS SIGNED) AS `ordered_qty`,
			`tabItem`.`stock_uom` AS `stock_uom`,
			(
				SELECT `tabItem Supplier`.`substitute_status`
				FROM `tabItem Supplier`
				WHERE
					`tabItem Supplier`.`parent` = `tabItem`.`name`
					AND `tabItem Supplier`.`supplier` = (
						SELECT `tabItem Default`.`default_supplier`
						FROM `tabItem Default`
						WHERE
							`tabItem Default`.`parent` = `tabItem`.`name`
							AND IFNULL(`tabItem Default`.`default_supplier`, '') != ''
						ORDER BY `tabItem Default`.`idx` ASC
						LIMIT 1
					)
				LIMIT 1
			) AS `substitute_status`
		FROM `tabLocation` AS `tabBase Location`
		INNER JOIN `tabLocation`
			ON `tabLocation`.`lft` > `tabBase Location`.`lft`
			AND `tabLocation`.`rgt` < `tabBase Location`.`rgt`
		INNER JOIN `tabLocation Link`
			ON `tabLocation Link`.`location` = `tabLocation`.`name`
			AND `tabLocation Link`.`parenttype` = 'Item'
			AND `tabLocation Link`.`parentfield` = 'storage_locations'
		INNER JOIN `tabItem`
			ON `tabItem`.`name` = `tabLocation Link`.`parent`
		LEFT JOIN (
			SELECT
				`tabBin`.`item_code`,
				SUM(`tabBin`.`actual_qty`) AS `actual_qty`
			FROM `tabBin`
			GROUP BY `tabBin`.`item_code`
		) AS `tabItem Stock`
			ON `tabItem Stock`.`item_code` = `tabItem`.`name`
		WHERE
			`tabBase Location`.`name` = '11-03 Oligo Synthesis'
			AND `tabLocation`.`name` != 'L08 Laborschublade'
			AND `tabItem`.`disabled` = 0
		ORDER BY LOWER(`tabItem`.`material_code`), `tabLocation`.`name` ASC, `tabItem`.`name` ASC
	"""
	return frappe.db.sql(query, as_dict=True)


def get_empty_locations():
	query = """
		SELECT
			`tabLocation`.`name` AS `location`
		FROM `tabLocation` AS `tabBase Location`
		INNER JOIN `tabLocation`
			ON `tabLocation`.`lft` > `tabBase Location`.`lft`
			AND `tabLocation`.`rgt` < `tabBase Location`.`rgt`
		WHERE
			`tabBase Location`.`name` = '11-03 Oligo Synthesis'
			AND IFNULL(`tabLocation`.`is_group`, 0) = 0
			AND `tabLocation`.`name` != 'L08 Laborschublade'
			AND NOT EXISTS (
				SELECT 1
				FROM `tabLocation Link`
				WHERE
					`tabLocation Link`.`location` = `tabLocation`.`name`
					AND `tabLocation Link`.`parenttype` = 'Item'
					AND `tabLocation Link`.`parentfield` = 'storage_locations'
			)
		ORDER BY `tabLocation`.`name` ASC
	"""
	rows = frappe.db.sql(query, as_dict=True)
	for row in rows:
		row.setdefault("item_code", None)
		row.setdefault("pack_size", None)
		row.setdefault("pack_uom", None)
		row.setdefault("material_code", None)
		row.setdefault("stock_qty", None)
		row.setdefault("requested_qty", None)
		row.setdefault("ordered_qty", None)
		row.setdefault("stock_uom", None)
		row.setdefault("shelf_life_in_months", None)
		row.setdefault("supplier_item_code", None)
		row.setdefault("substitute_status", None)
	return rows


def get_mode(filters):
	if not filters:
		return "Filled Locations"
	mode = filters.get("mode")
	if mode not in ("Filled Locations", "Empty Locations", "All Locations"):
		return "Filled Locations"
	return mode


def sort_rows_by_location_and_item(data):
	data.sort(key=lambda row: ((row.get("material_code") or "").lower(), (row.get("location") or ""), (row.get("item_code") or "")))


def execute(filters=None):
	columns = get_columns()
	data = get_data(filters)
	return columns, data
