# Copyright (c) 2013, Microsynth, libracore and contributors and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe


def execute(filters=None):
    if not filters:
        filters = {}

    from_date = filters.get("from_date")
    to_date = filters.get("to_date")
    product_type = filters.get("product_type")

    conditions = ["docstatus = 1", "base_total > 0"]

    if from_date:
        conditions.append("transaction_date >= %(from_date)s")
    if to_date:
        conditions.append("transaction_date <= %(to_date)s")
    if product_type:
        conditions.append("product_type = %(product_type)s")

    condition_sql = " AND ".join(conditions)

    query = f"""
        WITH ordered_sales_orders AS (
            SELECT
                name,
                base_total,
                ROW_NUMBER() OVER (ORDER BY base_total) AS rn,
                COUNT(*) OVER () AS total_count
            FROM `tabSales Order`
            WHERE {condition_sql}
        ),
        percentiles AS (
            SELECT 10 AS percentile
            UNION ALL SELECT 20
            UNION ALL SELECT 30
            UNION ALL SELECT 40
            UNION ALL SELECT 50
            UNION ALL SELECT 60
            UNION ALL SELECT 70
            UNION ALL SELECT 80
            UNION ALL SELECT 90
        )
        SELECT
            p.percentile,
            o.base_total
        FROM percentiles p
        JOIN ordered_sales_orders o
            ON o.rn = FLOOR((p.percentile / 100) * o.total_count)
        ORDER BY p.percentile
    """

    data = frappe.db.sql(query, filters, as_dict=True)

    columns = [
        {"label": "Percentile", "fieldname": "percentile", "fieldtype": "Int", "width": 100},
        {"label": "Base Total", "fieldname": "base_total", "fieldtype": "Currency", "width": 150}
    ]

    return columns, data
