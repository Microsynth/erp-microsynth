# Copyright (c) 2026, Microsynth, libracore and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import flt


def get_columns():
    return [
        {"label": "Item Code", "fieldname": "item_code", "fieldtype": "Link", "options": "Item", "width": 360},
        #{"label": "Item Name", "fieldname": "item_name", "fieldtype": "Data", "width": 350},
        {"label": "Stock UOM", "fieldname": "stock_uom", "fieldtype": "Link", "options": "UOM", "width": 95},
        {"label": "Actual Qty", "fieldname": "actual_qty", "fieldtype": "Float", "precision": 2, "width": 85},
        {"label": "Requested Qty", "fieldname": "requested_qty", "fieldtype": "Float", "precision": 2, "width": 105},
        {"label": "Ordered Qty", "fieldname": "ordered_qty", "fieldtype": "Float", "precision": 2, "width": 90},
        {"label": "Safety Stock", "fieldname": "safety_stock", "fieldtype": "Float", "precision": 2, "width": 95},
        {"label": "Lead Time [d]", "fieldname": "lead_time_days", "fieldtype": "Int", "width": 100},
        {"label": "Avg Consumption / month", "fieldname": "avg_consumption", "fieldtype": "Float", "precision": 2, "width": 170},
        {"label": "To Order (3 months)", "fieldname": "to_order", "fieldtype": "Float", "precision": 2, "width": 130}
    ]


def get_data(filters):
    conditions = []
    values = {}

    if filters.get("company"):
        conditions.append("`tabWarehouse`.`company` = %(company)s")
        values["company"] = filters.get("company")

    if filters.get("warehouse"):
        conditions.append("`tabBin`.`warehouse` = %(warehouse)s")
        values["warehouse"] = filters.get("warehouse")

    if filters.get("item_code"):
        conditions.append("`tabItem`.`name` = %(item_code)s")
        values["item_code"] = filters.get("item_code")

    supplier_join = ""
    if filters.get("supplier"):
        supplier_join = """
            INNER JOIN `tabItem Supplier`
                ON `tabItem Supplier`.`parent` = `tabItem`.`name`
                AND `tabItem Supplier`.`supplier` = %(supplier)s
        """
        values["supplier"] = filters.get("supplier")

    conditions.append("`tabItem`.`disabled` = 0")

    where_clause = " AND ".join(conditions)
    if where_clause:
        where_clause = "WHERE " + where_clause

    data = frappe.db.sql(f"""
        SELECT
            `tabItem`.`name` AS `item_code`,
            `tabItem`.`item_name`,
            `tabItem`.`stock_uom`,

            IFNULL(`tabBin`.`actual_qty`, 0) AS `actual_qty`,

            (
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
                    AND `tabMaterial Request Item`.`warehouse` = `tabBin`.`warehouse`
            ) AS `requested_qty`,

            (
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
                    AND `tabPurchase Order Item`.`warehouse` = `tabBin`.`warehouse`
            ) AS `ordered_qty`,

            IFNULL(`tabItem`.`safety_stock`, 0) AS `safety_stock`,
            IFNULL(`tabItem`.`lead_time_days`, 0) AS `lead_time_days`,

            (
                SELECT
                    CASE
                        WHEN COUNT(DISTINCT DATE(`tabStock Entry`.`posting_date`)) < 2 THEN 0
                        ELSE
                            SUM(ABS(`tabStock Entry Detail`.`qty`))
                            / DATEDIFF(MAX(`tabStock Entry`.`posting_date`), MIN(`tabStock Entry`.`posting_date`))
                            * 30
                    END
                FROM `tabStock Entry Detail`
                INNER JOIN `tabStock Entry`
                    ON `tabStock Entry`.`name` = `tabStock Entry Detail`.`parent`
                WHERE
                    `tabStock Entry`.`docstatus` = 1
                    AND `tabStock Entry`.`stock_entry_type` = 'Material Issue'
                    AND `tabStock Entry Detail`.`item_code` = `tabItem`.`name`
                    AND `tabStock Entry Detail`.`s_warehouse` = `tabBin`.`warehouse`
            ) AS `avg_consumption`

        FROM `tabItem`
        INNER JOIN `tabBin` ON `tabBin`.`item_code` = `tabItem`.`name`
        INNER JOIN `tabWarehouse` ON `tabWarehouse`.`name` = `tabBin`.`warehouse`
        {supplier_join}
        {where_clause}
        ORDER BY `tabItem`.`item_code` ASC
    """, values, as_dict=True)

    # Python-side "To Order" calculation
    for row in data:
        avg_consumption = flt(row.avg_consumption)
        lead_time_days = flt(row.lead_time_days)
        monthly_consumption = avg_consumption
        daily_consumption = monthly_consumption / 30 if monthly_consumption else 0
        demand_next_3_months = monthly_consumption * 3
        demand_lead_time = daily_consumption * lead_time_days
        required = demand_next_3_months + demand_lead_time + flt(row.safety_stock)

        available = (
            flt(row.actual_qty)
            + flt(row.requested_qty)
            + flt(row.ordered_qty)
        )
        row.to_order = max(required - available, 0)

    data.sort(key=lambda row: (row.to_order, row.item_code), reverse=True)

    return data


def execute(filters=None):
    filters = filters or {}
    columns = get_columns()
    data = get_data(filters)
    return columns, data
