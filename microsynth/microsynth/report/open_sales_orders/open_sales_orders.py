# Copyright (c) 2024, Microsynth, libracore and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _


def get_columns():
    return [
        {"label": _("Sales Order"), "fieldname": "name", "fieldtype": "Link", "options": "Sales Order", "width": 125},
        {"label": _("Date"), "fieldname": "date", "fieldtype": "Date", "width": 80},
        {"label": _("Total"), "fieldname": "total", "fieldtype": "Currency", "options": "currency", "width": 95},
        {"label": _("Customer"), "fieldname": "customer", "fieldtype": "Link", "options": "Customer", "width": 80},
        {"label": _("Customer Name"), "fieldname": "customer_name", "fieldtype": "Data", "width": 180},
        {"label": _("Invoicing Method"), "fieldname": "inv_method_customer", "fieldtype": "Data", "width": 115},
        {"label": _("Web Order ID"), "fieldname": "web_order_id_html", "fieldtype": "HTML", "width": 90},
        {"label": _("DNs"), "fieldname": "dns", "fieldtype": "Integer", "width": 45},
        {"label": _("Product Type"), "fieldname": "product_type", "fieldtype": "Data", "width": 100},
        {"label": _("Pending Samples"), "fieldname": "pending_samples", "fieldtype": "Data", "width": 45},
        {"label": _("Open Oligos"), "fieldname": "open_oligos", "fieldtype": "Data", "width": 45},
        {"label": _("Status"), "fieldname": "status", "fieldtype": "Data", "width": 90},
        {"label": _("Comments"), "fieldname": "comments", "fieldtype": "Int", "width": 80},
        {"label": _("Company"), "fieldname": "company", "fieldtype": "Data", "width": 155},
        {"label": _("Punchout"), "fieldname": "is_punchout", "fieldtype": "Check", "width": 75},
        {"label": _("Hold Order"), "fieldname": "hold_order", "fieldtype": "Check", "width": 80},
        {"label": _("Hold Inv."), "fieldname": "hold_invoice", "fieldtype": "Check", "width": 70},
        {"label": _("Creator"), "fieldname": "owner", "fieldtype": "Link", "options": "User", "width": 220},
        {"label": _("Items"), "fieldname": "items", "fieldtype": "Data", "width": 500}
    ]


@frappe.whitelist()
def get_data(filters=None):
    filters = filters or {}
    outer_conditions = inner_conditions = ''
    values = []

    if not filters.get('include_zero'):
        outer_conditions += " AND `raw`.`total` > 0"
    if not filters.get('include_orders_on_hold'):
        inner_conditions += " AND `tabSales Order`.`hold_order` != 1"
    if filters.get('company'):
        inner_conditions += " AND `tabSales Order`.`company` = %s"
        values.append(filters.get('company'))

    if filters.get('product_type'):
        inner_conditions += " AND `tabSales Order`.`product_type` = %s"
        values.append(filters.get('product_type'))

    if filters.get('include_drafts'):
        inner_conditions += " AND `tabSales Order`.`docstatus` < 2"
    else:
        inner_conditions += " AND `tabSales Order`.`docstatus` = 1"

    if filters.get('to_date'):
        inner_conditions += """
            AND `tabSales Order`.`transaction_date`
            BETWEEN %s AND %s
        """
        values.append(filters.get('from_date'))
        values.append(filters.get('to_date'))
    else:
        # used for Auto Email Reports
        if filters.get('product_type') == 'NGS':
            inner_conditions += """
                AND `tabSales Order`.`transaction_date`
                BETWEEN %s AND DATE_ADD(NOW(), INTERVAL -30 DAY)
            """
            values.append(filters.get('from_date'))
        else:  # if filters.get('product_type') == 'Sequencing'
            inner_conditions += """
                AND `tabSales Order`.`transaction_date`
                BETWEEN %s AND DATE_ADD(NOW(), INTERVAL -14 DAY)
            """
            values.append(filters.get('from_date'))

    if filters.get('item_codes'):
        item_codes = [code.strip() for code in filters.get('item_codes').split(',') if code.strip()]
        if item_codes:
            placeholders = ', '.join(['%s'] * len(item_codes))
            inner_conditions += f"""
                AND `tabSales Order Item`.`item_code` IN ({placeholders})
            """
            values.extend(item_codes)

    data = frappe.db.sql(f"""
        SELECT * FROM (
            SELECT
                `tabSales Order`.`name`,
                `tabSales Order`.`transaction_date` AS `date`,
                ROUND(`tabSales Order`.`total`, 2) AS `total`,
                `tabSales Order`.`currency`,
                `tabSales Order`.`customer`,
                `tabSales Order`.`customer_name`,
                `tabCustomer`.`invoicing_method` AS `inv_method_customer`,
                `tabSales Order`.`web_order_id`,
                CASE
                    WHEN `tabSales Order`.`web_order_id` IS NOT NULL AND `tabSales Order`.`web_order_id` != ''
                    THEN CONCAT(
                        '<a href="/desk#query-report/Sales Document Overview?web_order_id=',
                        `tabSales Order`.`web_order_id`,
                        '" target="_blank">',
                        `tabSales Order`.`web_order_id`,
                        '</a>'
                    )
                    ELSE ''
                END AS `web_order_id_html`,
                `tabSales Order`.`product_type`,
                `tabSales Order`.`status`,
                (
                    SELECT COUNT(*)
                    FROM `tabComment`
                    WHERE `comment_type` = 'Comment'
                      AND `reference_doctype` = 'Sales Order'
                      AND `reference_name` = `tabSales Order`.`name`
                ) AS `comments`,
                `tabSales Order`.`company`,
                `tabSales Order`.`hold_order`,
                `tabSales Order`.`hold_invoice`,
                `tabSales Order`.`is_punchout`,
                `tabSales Order`.`owner`,
                '-' AS `pending_samples`,
                '-' AS `open_oligos`,
                IFNULL(`sii`.`has_sales_invoice`, 0) AS `has_sales_invoice`,
                GROUP_CONCAT(`tabSales Order Item`.`item_code`) AS `items`
            FROM `tabSales Order`
            LEFT JOIN `tabCustomer` ON `tabCustomer`.`name` = `tabSales Order`.`customer`
            LEFT JOIN `tabSales Order Item` ON `tabSales Order Item`.`parent` = `tabSales Order`.`name`
            LEFT JOIN (
                SELECT
                    `sales_order`,
                    COUNT(*) AS `has_sales_invoice`
                FROM `tabSales Invoice Item`
                WHERE `docstatus` = 1
                GROUP BY `sales_order`
            ) AS `sii` ON `sii`.`sales_order` = `tabSales Order`.`name`
            WHERE `tabSales Order`.`per_delivered` < 0.01
              AND `tabSales Order`.`status` NOT IN ('Closed', 'Completed')
              AND NOT (
                `tabCustomer`.`invoicing_method` = 'Stripe Prepayment'
                AND `tabSales Order`.`hold_order` = 1
              )
              {inner_conditions}
            GROUP BY `tabSales Order`.`name`
        ) AS `raw`
        WHERE `raw`.`has_sales_invoice` = 0
        {outer_conditions}
        ORDER BY `raw`.`date`
    """, tuple(values), as_dict=True)

    # Batch delivery notes (by web_order_id)
    web_order_ids = [so["web_order_id"] for so in data if so["web_order_id"]]
    dn_map = {}
    if web_order_ids:
        placeholders = ','.join(['%s'] * len(web_order_ids))
        delivery_notes = frappe.db.sql(f"""
            SELECT `tabDelivery Note`.`web_order_id`, COUNT(DISTINCT `tabDelivery Note Item`.`parent`) AS `count`
            FROM `tabDelivery Note`
            JOIN `tabDelivery Note Item` ON `tabDelivery Note`.`name` = `tabDelivery Note Item`.`parent`
            WHERE `tabDelivery Note`.`web_order_id` IN ({placeholders})
            GROUP BY `tabDelivery Note`.`web_order_id`
        """, tuple(web_order_ids), as_dict=True)
        dn_map = {row["web_order_id"]: row["count"] for row in delivery_notes}

    # Batch fetch: pending samples and open oligos
    so_names = [so["name"] for so in data]
    sample_map = {}
    oligo_map = {}

    if so_names:
        placeholders = ','.join(['%s'] * len(so_names))

        pending_samples = frappe.db.sql(f"""
            SELECT `tabSample Link`.`parent` AS `so_name`, COUNT(`tabSample`.`name`) AS `count`
            FROM `tabSample Link`
            JOIN `tabSample` ON `tabSample Link`.`sample` = `tabSample`.`name`
            JOIN `tabSequencing Label` ON `tabSample`.`sequencing_label` = `tabSequencing Label`.`name`
            WHERE `tabSample Link`.`parent` IN ({placeholders})
              AND `tabSample Link`.`parenttype` = 'Sales Order'
              AND `tabSequencing Label`.`status` NOT IN ('received', 'processed')
            GROUP BY `tabSample Link`.`parent`
        """, tuple(so_names), as_dict=True)
        sample_map = {row["so_name"]: row["count"] for row in pending_samples}

        open_oligos = frappe.db.sql(f"""
            SELECT `tabOligo Link`.`parent` AS `so_name`, COUNT(`tabOligo`.`name`) AS `count`
            FROM `tabOligo Link`
            JOIN `tabOligo` ON `tabOligo Link`.`oligo` = `tabOligo`.`name`
            WHERE `tabOligo Link`.`parent` IN ({placeholders})
              AND `tabOligo Link`.`parenttype` = 'Sales Order'
              AND `tabOligo`.`status` = 'Open'
            GROUP BY `tabOligo Link`.`parent`
        """, tuple(so_names), as_dict=True)
        oligo_map = {row["so_name"]: row["count"] for row in open_oligos}

    for so in data:
        so['dns'] = dn_map.get(so['web_order_id'], 0) if so['web_order_id'] else 0
        if so['product_type'] == 'Sequencing':
            so['pending_samples'] = sample_map.get(so['name'], 0)
        if so['product_type'] == 'Oligos':
            so['open_oligos'] = oligo_map.get(so['name'], 0)

    return data


def execute(filters=None):
    columns = get_columns()
    data = get_data(filters)
    return columns, data
