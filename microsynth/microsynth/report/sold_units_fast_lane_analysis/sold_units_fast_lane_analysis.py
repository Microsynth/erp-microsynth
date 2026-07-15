# Copyright (c) 2026, Microsynth
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.utils import cint, flt
from microsynth.microsynth.utils import get_child_territories


MONTHS = {
	1: _("January"),
	2: _("February"),
	3: _("March"),
	4: _("April"),
	5: _("May"),
	6: _("June"),
	7: _("July"),
	8: _("August"),
	9: _("September"),
	10: _("October"),
	11: _("November"),
	12: _("December"),
}


FAST_LANE_ROWS = [
	{"label": "Easy Run (3050)", "item_codes": ["3050"]},
	{
		"label": "Economy Run (0901, 3000)",
		"item_codes": ["0901", "3000"],
	},
	{"label": "ENS (3200, 3237)", "item_codes": ["3200", "3237"]},
	{"label": "FPS (3260, 3264)", "item_codes": ["3260", "3264"]},
	{"label": "Premium (0903)", "item_codes": ["0903"]},
	{
		"label": "Economy Plate (3120, 3130, 3131)",
		"item_codes": ["3120", "3130", "3131"],
	},
	{
		"label": "Economy Plus Plate (3100, 3110)",
		"item_codes": ["3100", "3110"],
	},
	{
		"label": "ENS Plate (3240, 3252, 3254)",
		"item_codes": ["3240", "3252", "3254"],
	},
	{
		"label": "FPS Plate (3265, 3266)",
		"item_codes": ["3265", "3266"],
	},
]


SPECIAL_ITEM_MULTIPLIERS = {
	"3130": 24,
	"3254": 24,
}


PLATE_96_ITEM_CODES = {
	"3100",
	"3120",
	"3240",
}


def get_item_config():
	item_config = {}
	for row in FAST_LANE_ROWS:
		for item_code in row["item_codes"]:
			default_multiplier = 96 if item_code in PLATE_96_ITEM_CODES else 1
			item_config[item_code] = {
				"label": row["label"],
				"multiplier": SPECIAL_ITEM_MULTIPLIERS.get(item_code, default_multiplier),
			}
	return item_config


def get_columns(filters):
	columns = [
		{"label": _("Fast Lane"), "fieldname": "fast_lane", "fieldtype": "Data", "width": 200}
	]
	for month in range(1, 13):
		columns.append(
			{
				"label": MONTHS[month],
				"fieldname": f"month{month}",
				"fieldtype": "Integer",
				"width": 80,
				"precision": "0",
				"align": "right",
			}
		)
	return columns


def get_raw_data(filters):
	item_config = get_item_config()
	item_codes = sorted(item_config.keys())
	conditions = []
	params = []

	if filters.get("territory"):
		child_territories = get_child_territories(filters.get("territory"))
		if child_territories:
			territory_placeholders = ", ".join(["%s"] * len(child_territories))
			conditions.append(f"`tabSales Invoice`.`territory` IN ({territory_placeholders})")
			params.extend(child_territories)

	if filters.get("fiscal_year"):
		conditions.append("YEAR(`tabSales Invoice`.`posting_date`) = %s")
		params.append(cint(filters.get("fiscal_year")))

	item_code_placeholders = ", ".join(["%s"] * len(item_codes))
	params.extend(item_codes)
	where_clause = ""

	if conditions:
		where_clause = " AND " + " AND ".join(conditions)

	sql_query = f"""
		SELECT
			MONTH(`tabSales Invoice`.`posting_date`) AS `month`,
			`tabSales Invoice Item`.`item_code` AS `item_code`,
			SUM(`tabSales Invoice Item`.`qty`) AS `qty`
		FROM `tabSales Invoice`
		LEFT JOIN `tabTerritory`
			ON `tabTerritory`.`name` = `tabSales Invoice`.`territory`
		INNER JOIN `tabSales Invoice Item`
			ON `tabSales Invoice`.`name` = `tabSales Invoice Item`.`parent`
			AND `tabSales Invoice Item`.`parenttype` = 'Sales Invoice'
		WHERE `tabSales Invoice`.`docstatus` = 1
			AND `tabSales Invoice`.`is_return` = 0
			AND NOT EXISTS (
				SELECT 1
				FROM `tabSales Invoice` `cn`
				WHERE `cn`.`docstatus` = 1
					AND `cn`.`is_return` = 1
					AND `cn`.`return_against` = `tabSales Invoice`.`name`
			)
			{where_clause}
			AND `tabSales Invoice Item`.`item_code` IN ({item_code_placeholders})
		GROUP BY MONTH(`tabSales Invoice`.`posting_date`), `tabSales Invoice Item`.`item_code`
		ORDER BY MONTH(`tabSales Invoice`.`posting_date`), `tabSales Invoice Item`.`item_code`
	"""
	return frappe.db.sql(sql_query, tuple(params), as_dict=True)


def get_data(filters):
	item_config = get_item_config()
	raw_data = get_raw_data(filters)

	rows = {row["label"]: {} for row in FAST_LANE_ROWS}
	total_row = {"fast_lane": "Total"}
	data = []

	for entry in raw_data:
		month_key = f"month{entry['month']}"
		item_code = entry["item_code"]
		config = item_config.get(item_code)
		if not config:
			continue

		units = flt(entry["qty"]) * config["multiplier"]
		label = config["label"]
		rows[label][month_key] = flt(rows[label].get(month_key, 0)) + units
		total_row[month_key] = flt(total_row.get(month_key, 0)) + units

	for row in FAST_LANE_ROWS:
		label = row["label"]
		month_values = rows[label]
		output_row = {"fast_lane": label}

		for month in range(1, 13):
			month_key = f"month{month}"
			if month_key in month_values:
				value = month_values[month_key]
				output_row[month_key] = value

		data.append(output_row)

	data.append(total_row)
	return data

def execute(filters=None):
	columns, data = get_columns(filters), get_data(filters or {})
	return columns, data
