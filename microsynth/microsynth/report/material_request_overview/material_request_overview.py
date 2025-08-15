# Copyright (c) 2025, Microsynth
# For license information, please see license.txt

from __future__ import unicode_literals
import json
import frappe
from frappe import _


def get_columns(mode=None):
    columns = [
        {"label": _("Request"), "fieldname": "material_request", "fieldtype": "Dynamic Link", "options": "request_type", "width": 100},
        {"label": _("Request Date"), "fieldname": "transaction_date", "fieldtype": "Date", "width": 95},
        {"label": _("Required By"), "fieldname": "schedule_date", "fieldtype": "Date", "width": 85},
        {"label": _("Item"), "fieldname": "item_code", "fieldtype": "Link", "options": "Item", "width": 240},
        #{"label": _("Item Name"), "fieldname": "item_name", "fieldtype": "Data", "width": 200},
        {"label": _("Qty"), "fieldname": "qty", "fieldtype": "Int", "width": 50},
    ]
    if mode == "All Material Requests":
        columns += [
            {"label": _("Ordered Qty"), "fieldname": "ordered_qty", "fieldtype": "Int", "width": 90},
            {"label": _("Received Qty"), "fieldname": "received_qty", "fieldtype": "Int", "width": 95},
        ]
    columns += [
        {"label": _("Supplier"), "fieldname": "supplier", "fieldtype": "Link", "options": "Supplier", "width": 65},
        {"label": _("Supplier Name"), "fieldname": "supplier_name", "fieldtype": "Data", "width": 200},
        {"label": _("Supplier Part No."), "fieldname": "supplier_part_no", "fieldtype": "Data", "width": 120},
        {"label": _("Requested By"), "fieldname": "requested_by", "fieldtype": "Link", "options": "User", "width": 200}
    ]
    return columns


def get_data(filters):
    mode = filters.get("mode") if filters else None
    conditions = ""
    if filters and filters.get("supplier"):
        conditions += " AND `tabItem Supplier`.`supplier` = %(supplier)s"

    if mode == "All Material Requests":
        data = frappe.db.sql(f"""
            SELECT
                `tabMaterial Request`.`name` AS `material_request`,
                'Material Request' AS `request_type`,
                `tabMaterial Request`.`transaction_date`,
                `tabMaterial Request Item`.`schedule_date`,
                `tabMaterial Request Item`.`item_code`,
                `tabMaterial Request Item`.`item_name`,
                `tabMaterial Request Item`.`qty`,
                `tabMaterial Request Item`.`name` AS `material_request_item`,
                (
                    SELECT IFNULL(SUM(`tabPurchase Order Item`.`qty`), 0)
                    FROM `tabPurchase Order Item`
                    WHERE
                        `tabPurchase Order Item`.`docstatus` = 1
                        AND `tabPurchase Order Item`.`material_request_item` = `tabMaterial Request Item`.`name`
                ) AS `ordered_qty`,
                (
                    SELECT IFNULL(SUM(`tabPurchase Receipt Item`.`qty`), 0)
                    FROM `tabPurchase Receipt Item`
                    WHERE
                        `tabPurchase Receipt Item`.`docstatus` = 1
                        AND `tabPurchase Receipt Item`.`material_request_item` = `tabMaterial Request Item`.`name`
                ) AS `received_qty`,
                `tabItem Supplier`.`supplier`,
                `tabSupplier`.`supplier_name`,
                `tabItem Supplier`.`supplier_part_no`,
                IFNULL(`tabMaterial Request`.`requested_by`, `tabMaterial Request`.`owner`) AS `requested_by`
            FROM
                `tabMaterial Request Item`
            LEFT JOIN `tabMaterial Request`
                ON `tabMaterial Request Item`.`parent` = `tabMaterial Request`.`name`
            LEFT JOIN `tabItem Supplier`
                ON `tabItem Supplier`.`parent` = `tabMaterial Request Item`.`item_code`
                AND `tabItem Supplier`.`parenttype` = 'Item'
                AND `tabItem Supplier`.`idx` = 1
            LEFT JOIN `tabSupplier`
                ON `tabItem Supplier`.`supplier` = `tabSupplier`.`name`
            WHERE
                `tabMaterial Request`.`material_request_type` = 'Purchase'
                AND `tabMaterial Request`.`docstatus` = 1
                {conditions}
            ORDER BY `tabMaterial Request`.`transaction_date` ASC
        """, filters, as_dict=True)
        return data
    else:
        return frappe.db.sql(f"""
            SELECT
                `tabMaterial Request`.`name` AS `material_request`,
                'Material Request' AS `request_type`,
                `tabMaterial Request`.`transaction_date`,
                `tabMaterial Request Item`.`schedule_date`,
                `tabMaterial Request Item`.`item_code`,
                `tabMaterial Request Item`.`item_name`,
                (`tabMaterial Request Item`.`qty` - IFNULL(SUM(`tabPurchase Order Item`.`qty`), 0)) AS `qty`,
                `tabMaterial Request Item`.`name` AS `material_request_item`,
                `tabItem Supplier`.`supplier`,
                `tabSupplier`.`supplier_name`,
                `tabItem Supplier`.`supplier_part_no`,
                IFNULL(`tabMaterial Request`.`requested_by`, `tabMaterial Request`.`owner`) AS `requested_by`
            FROM
                `tabMaterial Request Item`
            LEFT JOIN `tabMaterial Request`
                ON `tabMaterial Request Item`.`parent` = `tabMaterial Request`.`name`
            LEFT JOIN `tabItem Supplier`
                ON `tabItem Supplier`.`parent` = `tabMaterial Request Item`.`item_code`
                AND `tabItem Supplier`.`parenttype` = 'Item'
                AND `tabItem Supplier`.`idx` = 1
            LEFT JOIN `tabSupplier`
                ON `tabItem Supplier`.`supplier` = `tabSupplier`.`name`
            LEFT JOIN `tabPurchase Order Item`
                ON `tabPurchase Order Item`.`material_request_item` = `tabMaterial Request Item`.`name`
                AND `tabPurchase Order Item`.`docstatus` = 1
            WHERE
                `tabMaterial Request`.`material_request_type` = 'Purchase'
                AND `tabMaterial Request`.`docstatus` = 1
                AND `tabMaterial Request`.`status` != 'Stopped'
                {conditions}
            GROUP BY
                `tabMaterial Request Item`.`name`
            HAVING
                qty > 0

            UNION

            SELECT
                `tabItem Request`.`name` AS `material_request`,
                'Item Request' AS `request_type`,
                DATE(`tabItem Request`.`creation`) AS transaction_date,
                `tabItem Request`.`schedule_date`,
                '-' AS `item_code`,
                `tabItem Request`.`item_name`,
                `tabItem Request`.`qty`,
                NULL AS `material_request_item`,
                `tabItem Request`.`supplier`,
                `tabItem Request`.`supplier_name`,
                `tabItem Request`.`supplier_part_no`,
                `tabItem Request`.`owner` AS `requested_by`
            FROM
                `tabItem Request`
            WHERE
                `tabItem Request`.`docstatus` = 1
                AND `tabItem Request`.`status` = 'Pending'
            ORDER BY
                `schedule_date` ASC
        """, filters, as_dict=True)


def execute(filters=None):
    mode = filters.get("mode") if filters else None
    columns = get_columns(mode)
    data = get_data(filters)
    return columns, data


@frappe.whitelist()
def create_item_request(data):
    # data is JSON string, parse it
    data = json.loads(data)

    required_fields = ['item_name', 'qty', 'company']
    for field in required_fields:
        if not data.get(field):
            frappe.throw(f"Required parameter missing: {field}")

    ir = frappe.new_doc("Item Request")
    ir.item_name = data.get('item_name')
    ir.qty = data.get('qty') or 1
    ir.supplier_part_no = data.get('supplier_part_no')
    ir.supplier = data.get('supplier')
    ir.supplier_name = data.get('supplier_name')
    ir.uom = data.get('uom') or "Pcs"
    ir.rate = data.get('rate')
    ir.currency = data.get('currency')
    ir.company = data.get('company')
    ir.schedule_date = data.get('schedule_date')
    ir.comment = data.get('comment')
    ir.status = "Pending"
    ir.insert()
    ir.submit()
    return ir.name
