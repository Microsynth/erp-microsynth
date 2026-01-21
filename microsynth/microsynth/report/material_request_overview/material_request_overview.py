# Copyright (c) 2025, Microsynth
# For license information, please see license.txt

from __future__ import unicode_literals
import json
import frappe
from frappe import _
from microsynth.qms.report.users_by_process.users_by_process import get_users


def get_columns(mode=None):
    columns = [
        {"label": _("Request"), "fieldname": "material_request", "fieldtype": "Dynamic Link", "options": "request_type", "width": 95},
        {"label": _("Request Date"), "fieldname": "transaction_date", "fieldtype": "Date", "width": 95},
        {"label": _("Required By"), "fieldname": "schedule_date", "fieldtype": "Date", "width": 85},
        {"label": _("Item"), "fieldname": "item_code", "fieldtype": "Link", "options": "Item", "width": 350},
        #{"label": _("Item Name"), "fieldname": "item_name", "fieldtype": "Data", "width": 200},
        {"label": _("Qty"), "fieldname": "qty", "fieldtype": "Int", "width": 45},
        {"label": _("UOM"), "fieldname": "uom", "fieldtype": "Data", "width": 50},
    ]
    if mode != "To Order":
        columns += [
            {"label": _("Ordered Qty"), "fieldname": "ordered_qty", "fieldtype": "Int", "width": 85},
            {"label": _("Purchase Order"), "fieldname": "purchase_order", "fieldtype": "Link", "options": "Purchase Order", "width": 105},
            {"label": _("Received Qty"), "fieldname": "received_qty", "fieldtype": "Int", "width": 95},
        ]
    columns += [
        {"label": _("Supplier"), "fieldname": "supplier", "fieldtype": "Link", "options": "Supplier", "width": 65},
        {"label": _("Supplier Name"), "fieldname": "supplier_name", "fieldtype": "Data", "width": 250},
        {"label": _("Supplier Item Code"), "fieldname": "supplier_part_no", "fieldtype": "Data", "width": 125},
        {"label": _("Requested By"), "fieldname": "requested_by", "fieldtype": "Link", "options": "User", "width": 150},
        {"label": _("Comment"), "fieldname": "comment", "fieldtype": "Data", "width": 200, "align": "left"},
        {"label": _("QM Process"), "fieldname": "qm_processes", "fieldtype": "Data", "width": 400, "align": "left"}
    ]
    return columns


def get_data(filters):
    mode = filters.get("mode") if filters else None
    conditions = ""
    item_request_conditions = ""

    # Get users assigned to selected QM Process(es)
    user_qm_mapping = {}
    user_filter_clause = ""
    if filters and filters.get("qm_process"):
        # Wrap single process into a list if needed
        qm_processes = [filters.get("qm_process")]
        companies = [filters.get("company")]
        matched_users = get_users(qm_processes=qm_processes, companies=companies)
        users = [u.user_name for u in matched_users]
        if users:
            filters["users"] = users
            user_filter_clause = " AND IFNULL(`tabMaterial Request`.`requested_by`, `tabMaterial Request`.`owner`) IN %(users)s"
        else:
            return []  # No users match QM Process

        # Build user -> QM Process list mapping
        if matched_users:
            user_qm_mapping = {}

            qm_user_rows = frappe.db.sql("""
                SELECT parent AS user, qm_process
                FROM `tabQM User Process Assignment`
                WHERE parent IN %(users)s
            """, {"users": users}, as_dict=True)

            for row in qm_user_rows:
                user_qm_mapping.setdefault(row.user, []).append(row.qm_process)
        conditions += user_filter_clause

    if filters and filters.get("supplier"):
        conditions += " AND `tabItem Supplier`.`supplier` = %(supplier)s"
        item_request_conditions += " AND `tabItem Request`.`supplier` = %(supplier)s"
    if filters and filters.get("from_date"):
        conditions += " AND `tabMaterial Request`.`transaction_date` >= %(from_date)s"
    if filters and filters.get("to_date"):
        conditions += " AND `tabMaterial Request`.`transaction_date` <= %(to_date)s"
    if filters and filters.get("company"):
        conditions += " AND `tabMaterial Request`.`company` = %(company)s"
        item_request_conditions += " AND `tabItem Request`.`company` = %(company)s"

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
                `tabMaterial Request Item`.`uom`,
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
                (
                    SELECT `tabPurchase Order Item`.`parent`
                    FROM `tabPurchase Order Item`
                    WHERE
                        `tabPurchase Order Item`.`docstatus` = 1
                        AND `tabPurchase Order Item`.`material_request_item` = `tabMaterial Request Item`.`name`
                    ORDER BY `tabPurchase Order Item`.`creation` DESC
                    LIMIT 1
                ) AS `purchase_order`,
                IFNULL(`tabMaterial Request Item`.`supplier`, `tabItem Supplier`.`supplier`) AS `supplier`,
                IFNULL(`tabMaterial Request Item`.`supplier_name`, `tabSupplier`.`supplier_name`) AS `supplier_name`,
                `tabItem Supplier`.`supplier_part_no`,
                IFNULL(`tabMaterial Request`.`requested_by`, `tabMaterial Request`.`owner`) AS `requested_by`,
                `tabMaterial Request`.`comment` AS `comment`
            FROM
                `tabMaterial Request Item`
            LEFT JOIN `tabMaterial Request`
                ON `tabMaterial Request Item`.`parent` = `tabMaterial Request`.`name`
            LEFT JOIN `tabItem Supplier`
                ON `tabItem Supplier`.`parent` = `tabMaterial Request Item`.`item_code`
                AND `tabItem Supplier`.`parenttype` = 'Item'
                AND (
                        (
                            IFNULL(`tabMaterial Request Item`.`supplier`, '') = ''
                            AND `tabItem Supplier`.`idx` = 1
                        )
                    OR
                        (
                            IFNULL(`tabMaterial Request Item`.`supplier`, '') != ''
                            AND `tabItem Supplier`.`supplier` = `tabMaterial Request Item`.`supplier`
                        )
                )
            LEFT JOIN `tabSupplier`
                ON `tabItem Supplier`.`supplier` = `tabSupplier`.`name`
            WHERE
                `tabMaterial Request`.`material_request_type` = 'Purchase'
                AND `tabMaterial Request`.`docstatus` = 1
                AND `tabMaterial Request`.`status` != 'Stopped'
                {conditions}
            ORDER BY `tabMaterial Request`.`transaction_date` ASC
        """, filters, as_dict=True)
    elif mode == "Unreceived Material Requests":
        data = frappe.db.sql(f"""
            SELECT *
            FROM (
                SELECT
                    `tabMaterial Request`.`name` AS `material_request`,
                    'Material Request' AS `request_type`,
                    `tabMaterial Request`.`transaction_date`,
                    `tabMaterial Request Item`.`schedule_date`,
                    `tabMaterial Request Item`.`item_code`,
                    `tabMaterial Request Item`.`item_name`,
                    `tabMaterial Request Item`.`qty`,
                    `tabMaterial Request Item`.`uom`,
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
                    (
                        SELECT `tabPurchase Order Item`.`parent`
                        FROM `tabPurchase Order Item`
                        WHERE
                            `tabPurchase Order Item`.`docstatus` = 1
                            AND `tabPurchase Order Item`.`material_request_item` = `tabMaterial Request Item`.`name`
                        ORDER BY `tabPurchase Order Item`.`creation` DESC
                        LIMIT 1
                    ) AS `purchase_order`,
                    IFNULL(`tabMaterial Request Item`.`supplier`, `tabItem Supplier`.`supplier`) AS `supplier`,
                    IFNULL(`tabMaterial Request Item`.`supplier_name`, `tabSupplier`.`supplier_name`) AS `supplier_name`,
                    `tabItem Supplier`.`supplier_part_no`,
                    IFNULL(`tabMaterial Request`.`requested_by`, `tabMaterial Request`.`owner`) AS `requested_by`,
                    `tabMaterial Request`.`comment` AS `comment`
                FROM
                    `tabMaterial Request Item`
                LEFT JOIN `tabMaterial Request`
                    ON `tabMaterial Request Item`.`parent` = `tabMaterial Request`.`name`
                LEFT JOIN `tabItem Supplier`
                    ON `tabItem Supplier`.`parent` = `tabMaterial Request Item`.`item_code`
                    AND `tabItem Supplier`.`parenttype` = 'Item'
                    AND (
                        (
                            IFNULL(`tabMaterial Request Item`.`supplier`, '') = ''
                            AND `tabItem Supplier`.`idx` = 1
                        )
                    OR
                        (
                            IFNULL(`tabMaterial Request Item`.`supplier`, '') != ''
                            AND `tabItem Supplier`.`supplier` = `tabMaterial Request Item`.`supplier`
                        )
                )
                LEFT JOIN `tabSupplier`
                    ON `tabItem Supplier`.`supplier` = `tabSupplier`.`name`
                WHERE
                    `tabMaterial Request`.`material_request_type` = 'Purchase'
                    AND `tabMaterial Request`.`docstatus` = 1
                    AND `tabMaterial Request`.`status` != 'Stopped'
                    {conditions}
            ) AS raw
            WHERE
                raw.received_qty < raw.qty
                -- AND raw.ordered_qty > 0
            ORDER BY
                raw.transaction_date ASC;
            """, filters, as_dict=True)
    elif mode == "To Order":
        data = frappe.db.sql(f"""
            SELECT
                `tabMaterial Request`.`name` AS `material_request`,
                'Material Request' AS `request_type`,
                `tabMaterial Request`.`transaction_date`,
                `tabMaterial Request Item`.`schedule_date`,
                `tabMaterial Request Item`.`item_code`,
                `tabMaterial Request Item`.`item_name`,
                (`tabMaterial Request Item`.`qty` - IFNULL(SUM(`tabPurchase Order Item`.`qty`), 0)) AS `qty`,
                `tabMaterial Request Item`.`uom`,
                `tabMaterial Request Item`.`name` AS `material_request_item`,
                `tabMaterial Request Item`.`rate`,
                `tabMaterial Request Item`.`item_request_currency` AS `currency`,
                IFNULL(`tabMaterial Request Item`.`supplier`, `tabItem Supplier`.`supplier`) AS `supplier`,
                IFNULL(`tabMaterial Request Item`.`supplier_name`, `tabSupplier`.`supplier_name`) AS `supplier_name`,
                `tabItem Supplier`.`supplier_part_no`,
                IFNULL(`tabMaterial Request`.`requested_by`, `tabMaterial Request`.`owner`) AS `requested_by`,
                `tabMaterial Request`.`comment` AS `comment`
            FROM
                `tabMaterial Request Item`
            LEFT JOIN `tabMaterial Request`
                ON `tabMaterial Request Item`.`parent` = `tabMaterial Request`.`name`
            LEFT JOIN `tabItem Supplier`
                ON `tabItem Supplier`.`parent` = `tabMaterial Request Item`.`item_code`
                AND `tabItem Supplier`.`parenttype` = 'Item'
                AND (
                        (
                            IFNULL(`tabMaterial Request Item`.`supplier`, '') = ''
                            AND `tabItem Supplier`.`idx` = 1
                        )
                    OR
                        (
                            IFNULL(`tabMaterial Request Item`.`supplier`, '') != ''
                            AND `tabItem Supplier`.`supplier` = `tabMaterial Request Item`.`supplier`
                        )
                )
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
                `tabItem Request`.`uom`,
                NULL AS `material_request_item`,
                `tabItem Request`.`rate`,
                `tabItem Request`.`currency`,
                `tabItem Request`.`supplier`,
                `tabItem Request`.`supplier_name`,
                `tabItem Request`.`supplier_part_no`,
                `tabItem Request`.`owner` AS `requested_by`,
                `tabItem Request`.`comment` AS `comment`
            FROM
                `tabItem Request`
            WHERE
                `tabItem Request`.`docstatus` = 1
                AND `tabItem Request`.`status` = 'Pending'
                {item_request_conditions}
            ORDER BY
                `schedule_date` ASC
        """, filters, as_dict=True)
    else:
        frappe.throw(_("Invalid mode"))

    for row in data:
        user = row.get("requested_by")
        processes = user_qm_mapping.get(user, [])
        row["qm_processes"] = ", ".join(sorted(set(processes))) if processes else ""

    return data


def execute(filters=None):
    mode = filters.get("mode") if filters else None
    columns = get_columns(mode)
    data = get_data(filters)
    return columns, data


@frappe.whitelist()
def create_item_request(data):
    # data is JSON string, parse it
    data = json.loads(data)

    required_fields = ['item_name', 'supplier_name', 'company', 'qty', 'stock_uom']
    for field in required_fields:
        if not data.get(field):
            frappe.throw(f"Required parameter missing: {field}")

    ir = frappe.new_doc("Item Request")
    ir.item_name = data.get('item_name')
    ir.qty = data.get('qty') or 1
    ir.supplier_part_no = data.get('supplier_part_no')
    ir.supplier = data.get('supplier')
    ir.supplier_name = data.get('supplier_name')
    ir.uom = data.get('purchase_uom') or data.get('stock_uom')
    ir.rate = data.get('rate')
    ir.currency = data.get('currency')  # TODO: How to avoid that it is set to CHF by default if it is not in data?
    ir.conversion_factor = data.get('conversion_factor')
    ir.stock_uom = data.get('stock_uom')
    ir.pack_size = data.get('pack_size')
    ir.pack_uom = data.get('pack_uom')
    ir.company = data.get('company')
    ir.schedule_date = data.get('schedule_date')
    ir.comment = data.get('comment')
    ir.status = "Pending"
    ir.insert()
    ir.submit()
    return ir.name
