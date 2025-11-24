# Copyright (c) 2025, Microsynth
# For license information, please see license.txt

import urllib.parse
import calendar
import frappe
from frappe import _
from microsynth.microsynth.shipping import SHIPPING_SERVICES


def validate_filters(filters):
    if not filters.get("from_date"):
        frappe.throw("From Date is required")

    if filters.get("to_date") and filters.get("to_date") < filters.get("from_date"):
        frappe.throw("To Date cannot be before From Date")


def get_data(filters):
    # ---- Build SQL conditions ----
    conditions = [
        "`DN`.`docstatus` = 1",
        "`Item`.`item_group` = 'Shipping'",
        "`Item`.`disabled` = 0",
        "`DN`.`posting_date` >= %(from_date)s"
    ]
    sql_params = {"from_date": filters["from_date"]}

    if filters.get("to_date"):
        conditions.append("`DN`.`posting_date` <= %(to_date)s")
        sql_params["to_date"] = filters["to_date"]

    if filters.get("shipping_item"):
        conditions.append("`Item`.`name` = %(shipping_item)s")
        sql_params["shipping_item"] = filters["shipping_item"]

    where_clause = " AND ".join(conditions)

    # ---- Fetch raw data ----
    results = frappe.db.sql(
        f"""
        SELECT
            DATE_FORMAT(`DN`.`posting_date`, '%%Y-%%m') AS `month`,
            `Item`.`name` AS `item_code`,
            `Item`.`item_name` AS `item_name`,
            COUNT(DISTINCT `DN`.`name`) AS `dn_count`
        FROM `tabDelivery Note` AS `DN`
        LEFT JOIN `tabDelivery Note Item` AS `DNI`
            ON `DNI`.`parent` = `DN`.`name`
        LEFT JOIN `tabItem` AS `Item`
            ON `Item`.`name` = `DNI`.`item_code`
        WHERE {where_clause}
        GROUP BY `month`, `item_code`, `item_name`
        ORDER BY `item_code`, `month`
        """,
        sql_params,
        as_dict=True
    )

    # ---- Extract unique items and months ----
    items = sorted({r["item_code"] for r in results})
    months = sorted({r["month"] for r in results})

    # ---- Prepare pivot structure with all 0s ----
    pivot = {item: {m: 0 for m in months} for item in items}
    item_names = {r["item_code"]: r["item_name"] for r in results}

    # ---- Fill pivot with counts ----
    for r in results:
        pivot[r["item_code"]][r["month"]] = r["dn_count"]

    # ---- Columns ----
    columns = [{
        "label": _("Shipping Item"),
        "fieldname": "item_code",
        "fieldtype": "Link",
        "options": "Item",
        "width": 375,
        "align": "left"
    },
    {
        "label": _("Internal Note"),
        "fieldname": "internal_note",
        "fieldtype": "Data",
        "width": 90,
        "align": "left"
    }]
    for m in months:
        columns.append({
            "label": m,
            "fieldname": m,
            "fieldtype": "HTML",
            "width": 70,
            "align": "right"
        })
    # Total column
    columns.append({
        "label": _("Total"),
        "fieldname": "total",
        "fieldtype": "Int",
        "width": 70,
        "align": "right"
    })

    # ---- Data rows ----
    data = []
    for item_code, month_counts in pivot.items():
        row = {
            "item_code": item_code,
            "item_name": item_names.get(item_code, ''),
            "internal_note": SHIPPING_SERVICES.get(item_code, "")
        }
        total = 0
        for month, count in month_counts.items():
            year, mon = map(int, month.split("-"))
            last_day = calendar.monthrange(year, mon)[1]

            # URL for clickable cell
            date_filter = ["Between", [f"{year}-{mon:02d}-01", f"{year}-{mon:02d}-{last_day}"]]
            encoded_filter = urllib.parse.quote(str(date_filter).replace("'", '"'))
            url = f'desk#List/Delivery%20Note/List?item_code={item_code}&posting_date={encoded_filter}&docstatus=1'

            # HTML cell with link
            row[month] = f'<a href="{url}" target="_blank">{count}</a>'
            total += count

        row["total"] = total
        data.append(row)

    return columns, data


def execute(filters=None):
    validate_filters(filters)
    columns, data = get_data(filters)
    return columns, data
