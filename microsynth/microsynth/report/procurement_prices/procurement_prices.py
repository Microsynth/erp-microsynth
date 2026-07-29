# Copyright (c) 2026, Microsynth
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _


def get_columns():
	return [
		{"label": _("Date"), "fieldname": "posting_date", "fieldtype": "Date", "width": 80},
		{"label": _("Item"), "fieldname": "item_code", "fieldtype": "Link", "options": "Item", "width": 300},
		{"label": _("Supplier"), "fieldname": "supplier", "fieldtype": "Link", "options": "Supplier", "width": 70},
		{"label": _("Supplier Name"), "fieldname": "supplier_name", "fieldtype": "Data", "width": 250},
		{"label": _("Supplier Item Code"), "fieldname": "supplier_part_no", "fieldtype": "Data", "width": 125},
		{"label": _("(Min.) Qty"), "fieldname": "qty", "fieldtype": "Float", "width": 80},
		{"label": _("UOM"), "fieldname": "uom", "fieldtype": "Link", "options": "UOM", "width": 60},
		{"label": _("Rate"), "fieldname": "rate", "fieldtype": "Currency", "options": "currency", "width": 100},
		{"label": _("Amount"), "fieldname": "amount", "fieldtype": "Currency", "options": "currency", "width": 100},
		{"label": _("Currency"), "fieldname": "currency", "fieldtype": "Link", "options": "Currency", "width": 70},
		{"label": _("Purchase UOM"), "fieldname": "purchase_uom", "fieldtype": "Link", "options": "UOM", "width": 100},
		{"label": _("Conv. Factor"), "fieldname": "conversion_factor", "fieldtype": "Float", "precision": 2, "width": 90},
		{"label": _("Stock UOM"), "fieldname": "stock_uom", "fieldtype": "Link", "options": "UOM", "width": 80},
		{"label": _("Company"), "fieldname": "company", "fieldtype": "Link", "options": "Company", "width": 155},
		{"label": _("Price List"), "fieldname": "price_list", "fieldtype": "Link", "options": "Price List", "width": 130},
		{"label": _("Purchase Order"), "fieldname": "purchase_order", "fieldtype": "Link", "options": "Purchase Order", "width": 105},
		{"label": _("Item Name"), "fieldname": "item_name", "fieldtype": "Data", "width": 300},
	]


def get_order_history(filters):
	conditions = [
		"`tabPurchase Order`.`docstatus` = 1",
		"`tabPurchase Order Item`.`item_code` != 'P020000'",
	]
	if filters.get("from_date"):
		conditions.append("`tabPurchase Order`.`transaction_date` >= %(from_date)s")
	if filters.get("to_date"):
		conditions.append("`tabPurchase Order`.`transaction_date` <= %(to_date)s")
	if filters.get("item_code"):
		conditions.append("`tabPurchase Order Item`.`item_code` = %(item_code)s")
	if filters.get("item_name"):
		conditions.append("IFNULL(`tabPurchase Order Item`.`item_name`, '') LIKE CONCAT('%%', %(item_name)s, '%%')")
	if filters.get("supplier"):
		conditions.append("`tabPurchase Order`.`supplier` = %(supplier)s")
	if filters.get("supplier_name"):
		conditions.append("IFNULL(`tabPurchase Order`.`supplier_name`, '') LIKE CONCAT('%%', %(supplier_name)s, '%%')")
	if filters.get("supplier_part_no"):
		conditions.append("IFNULL(`tabItem Supplier`.`supplier_part_no`, '') LIKE CONCAT('%%', %(supplier_part_no)s, '%%')")
	if filters.get("company"):
		conditions.append("`tabPurchase Order`.`company` = %(company)s")

	return frappe.db.sql(
		"""
		SELECT
			`tabPurchase Order`.`transaction_date` AS `posting_date`,
			`tabPurchase Order Item`.`item_code`,
			`tabPurchase Order Item`.`item_name`,
			`tabPurchase Order`.`supplier`,
			`tabPurchase Order`.`supplier_name`,
			`tabItem Supplier`.`supplier_part_no`,
			`tabPurchase Order Item`.`qty`,
			`tabPurchase Order Item`.`uom`,
			`tabPurchase Order Item`.`rate`,
			`tabPurchase Order Item`.`amount`,
			`tabPurchase Order`.`currency`,
			`tabItem`.`purchase_uom`,
			`tabItem`.`stock_uom`,
			`tabUOM Conversion Detail`.`conversion_factor`,
			`tabPurchase Order`.`company`,
			NULL AS `price_list`,
			`tabPurchase Order`.`name` AS `purchase_order`
		FROM `tabPurchase Order Item`
		INNER JOIN `tabPurchase Order`
			ON `tabPurchase Order`.`name` = `tabPurchase Order Item`.`parent`
		LEFT JOIN `tabItem`
			ON `tabItem`.`name` = `tabPurchase Order Item`.`item_code`
		LEFT JOIN `tabUOM Conversion Detail`
			ON `tabUOM Conversion Detail`.`parent` = `tabPurchase Order Item`.`item_code`
			AND `tabUOM Conversion Detail`.`uom` = `tabPurchase Order Item`.`uom`
		LEFT JOIN `tabItem Supplier`
			ON `tabItem Supplier`.`parent` = `tabPurchase Order Item`.`item_code`
			AND `tabItem Supplier`.`parenttype` = 'Item'
			AND `tabItem Supplier`.`supplier` = `tabPurchase Order`.`supplier`
		WHERE
			{conditions}
		ORDER BY
			`tabPurchase Order`.`transaction_date` DESC,
			`tabPurchase Order`.`name` DESC,
			`tabPurchase Order Item`.`idx` ASC
		""".format(conditions=" AND ".join(conditions)),
		filters,
		as_dict=True,
	)


def get_buying_prices(filters):
	conditions = ["`tabItem`.`item_group` = 'Purchasing'", "`tabItem`.`disabled` = 0"]
	item_default_join = "`tabItem Default`.`parent` = `tabItem`.`name` AND `tabItem Default`.`idx` = 1"

	if filters.get("from_date"):
		conditions.append("IFNULL(`tabItem Price`.`valid_from`, `tabItem Price`.`creation`) >= %(from_date)s")
	if filters.get("to_date"):
		conditions.append("IFNULL(`tabItem Price`.`valid_from`, `tabItem Price`.`creation`) <= %(to_date)s")
	if filters.get("item_code"):
		conditions.append("`tabItem`.`name` = %(item_code)s")
	if filters.get("item_name"):
		conditions.append("IFNULL(`tabItem`.`item_name`, '') LIKE CONCAT('%%', %(item_name)s, '%%')")
	if filters.get("supplier"):
		conditions.append("`tabItem Supplier`.`supplier` = %(supplier)s")
	if filters.get("supplier_name"):
		conditions.append("IFNULL(`tabSupplier`.`supplier_name`, '') LIKE CONCAT('%%', %(supplier_name)s, '%%')")
	if filters.get("supplier_part_no"):
		conditions.append("IFNULL(`tabItem Supplier`.`supplier_part_no`, '') LIKE CONCAT('%%', %(supplier_part_no)s, '%%')")
	if filters.get("company"):
		item_default_join = "`tabItem Default`.`parent` = `tabItem`.`name` AND `tabItem Default`.`company` = %(company)s"
		conditions.append("`tabItem Default`.`company` = %(company)s")

	conditions.append("IFNULL(`tabItem Price`.`buying`, 0) = 1")

	return frappe.db.sql(
		"""
		SELECT
			IFNULL(`tabItem Price`.`valid_from`, DATE(`tabItem Price`.`creation`)) AS `posting_date`,
			`tabItem`.`name` AS `item_code`,
			`tabItem`.`item_name`,
			`tabItem Supplier`.`supplier`,
			`tabSupplier`.`supplier_name`,
			`tabItem Supplier`.`supplier_part_no`,
			`tabItem Price`.`min_qty` AS `qty`,
			IFNULL(`tabItem Price`.`uom`, IFNULL(`tabItem`.`purchase_uom`, `tabItem`.`stock_uom`)) AS `uom`,
			`tabItem Price`.`price_list_rate` AS `rate`,
			(`tabItem Price`.`price_list_rate` * IFNULL(`tabItem Price`.`min_qty`, 0)) AS `amount`,
			`tabItem Price`.`currency`,
			`tabItem`.`purchase_uom`,
			`tabItem`.`stock_uom`,
			`tabUOM Conversion Detail`.`conversion_factor`,
			`tabItem Default`.`company`,
			`tabItem Price`.`price_list`,
			NULL AS `purchase_order`
		FROM `tabItem Price`
		INNER JOIN `tabItem`
			ON `tabItem`.`name` = `tabItem Price`.`item_code`
		LEFT JOIN `tabItem Default`
			ON `tabItem Default`.`parent` = `tabItem`.`name`
			AND {item_default_join}
		LEFT JOIN `tabItem Supplier`
			ON `tabItem Supplier`.`parent` = `tabItem`.`name`
			AND `tabItem Supplier`.`parenttype` = 'Item'
			AND (
				(
					`tabItem Default`.`default_supplier` IS NOT NULL
					AND `tabItem Supplier`.`supplier` = `tabItem Default`.`default_supplier`
				)
				OR (
					`tabItem Default`.`default_supplier` IS NULL
					AND `tabItem Supplier`.`idx` = 1
				)
			)
		LEFT JOIN `tabSupplier`
			ON `tabSupplier`.`name` = `tabItem Supplier`.`supplier`
		LEFT JOIN `tabUOM Conversion Detail`
			ON `tabUOM Conversion Detail`.`parent` = `tabItem`.`name`
			AND `tabUOM Conversion Detail`.`uom` = IFNULL(`tabItem Price`.`uom`, IFNULL(`tabItem`.`purchase_uom`, `tabItem`.`stock_uom`))
		WHERE
			{conditions}
		ORDER BY
			`tabItem`.`name` ASC,
			IFNULL(`tabItem Price`.`valid_from`, `tabItem Price`.`creation`) DESC,
			`tabItem Price`.`price_list` ASC
		""".format(
			conditions=" AND ".join(conditions),
			item_default_join=item_default_join,
		),
		{"company": filters.get("company"), **filters},
		as_dict=True,
	)


def get_data(filters):
	if filters.get("mode") == "Buying Prices":
		return get_buying_prices(filters)
	return get_order_history(filters)


def execute(filters=None):
	filters = filters or {}
	return get_columns(), get_data(filters)
