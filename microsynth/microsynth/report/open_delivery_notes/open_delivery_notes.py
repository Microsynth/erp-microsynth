# Copyright (c) 2025, Microsynth
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _


def get_columns():
    return [
        {"label": _("Delivery Note"), "fieldname": "name", "fieldtype": "Link", "options": "Delivery Note", "width": 125},
        {"label": _("Posting Date"), "fieldname": "posting_date", "fieldtype": "Date", "width": 90},
        {"label": _("Total"), "fieldname": "total", "fieldtype": "Currency", "options": "currency", "width": 100},
        {"label": _("Customer ID"), "fieldname": "customer_id", "fieldtype": "Link", "options": "Customer", "width": 90},
        {"label": _("Customer Name"), "fieldname": "customer_name", "fieldtype": "Data", "width": 250},
        {"label": _("Invoicing Method"), "fieldname": "inv_method_customer", "fieldtype": "Data", "width": 115},
        {"label": _("Customer's Purchase Order No"), "fieldname": "po_no", "fieldtype": "Data", "width": 200},
        {"label": _("Is Punchout"), "fieldname": "is_punchout", "fieldtype": "Check", "width": 85},
        {"label": _("Web Order ID"), "fieldname": "web_order_id", "fieldtype": "Data", "width": 95},
        {"label": _("Product Type"), "fieldname": "product_type", "fieldtype": "Data", "width": 105},
        {"label": _("First Sales Invoice"), "fieldname": "first_sales_invoice", "fieldtype": "Link", "options": "Sales Invoice", "width": 125},
        {"label": _("First Credit Note"), "fieldname": "first_credit_note", "fieldtype": "Link", "options": "Sales Invoice", "width": 125},
        {"label": _("Invoice Count"), "fieldname": "sales_invoice_count", "fieldtype": "Int", "width": 95},
    ]

    
def get_data(filters):
    filters = filters or {}

    # fallback: if to_date not provided, default to 30 days before today
    if not filters.get("to_date"):
        filters['to_date'] = frappe.utils.add_days(frappe.utils.today(), -30)

    conditions = """
        `tabDelivery Note`.`per_billed` < 0.01
        AND `tabDelivery Note`.`posting_date` <= %(to_date)s
        AND `tabDelivery Note`.`docstatus` = 1
        AND `tabDelivery Note`.`status` NOT IN ('Closed', 'Completed')
        AND `tabDelivery Note`.`total` > 0
    """

    if filters.get("from_date"):
        conditions += " AND `tabDelivery Note`.`posting_date` >= %(from_date)s"

    query = f"""
        SELECT
            `tabDelivery Note`.`name`,
            `tabDelivery Note`.`posting_date`,
            ROUND(`tabDelivery Note`.`total`, 2) AS `total`,
            `tabDelivery Note`.`currency`,
            `tabDelivery Note`.`customer` AS `customer_id`,
            SUBSTRING(`tabDelivery Note`.`customer_name`, 1, 50) AS `customer_name`,
            `tabCustomer`.`invoicing_method` AS `inv_method_customer`,
            `tabDelivery Note`.`po_no`,
            `tabDelivery Note`.`is_punchout`,
            `tabDelivery Note`.`web_order_id`,
            `tabDelivery Note`.`product_type`,
            (
                SELECT `tabSales Invoice Item`.`parent`
                FROM `tabSales Invoice Item`
                JOIN `tabSales Invoice` ON `tabSales Invoice`.`name` = `tabSales Invoice Item`.`parent`
                WHERE `tabSales Invoice Item`.`delivery_note` = `tabDelivery Note`.`name`
                  AND `tabSales Invoice`.`is_return` = 0
                  AND `tabSales Invoice`.`docstatus` = 1
                ORDER BY `tabSales Invoice`.`posting_date` ASC
                LIMIT 1
            ) AS `first_sales_invoice`,
            (
                SELECT `tabSales Invoice Item`.`parent`
                FROM `tabSales Invoice Item`
                JOIN `tabSales Invoice` ON `tabSales Invoice`.`name` = `tabSales Invoice Item`.`parent`
                WHERE `tabSales Invoice Item`.`delivery_note` = `tabDelivery Note`.`name`
                  AND `tabSales Invoice`.`is_return` = 1
                  AND `tabSales Invoice`.`docstatus` = 1
                ORDER BY `tabSales Invoice`.`posting_date` ASC
                LIMIT 1
            ) AS `first_credit_note`,
            (
                SELECT COUNT(DISTINCT `tabSales Invoice Item`.`parent`)
                FROM `tabSales Invoice Item`
                JOIN `tabSales Invoice` ON `tabSales Invoice`.`name` = `tabSales Invoice Item`.`parent`
                WHERE `tabSales Invoice Item`.`delivery_note` = `tabDelivery Note`.`name`
                  AND `tabSales Invoice`.`docstatus` = 1
            ) AS `sales_invoice_count`
        FROM `tabDelivery Note`
        LEFT JOIN `tabCustomer` ON `tabCustomer`.`name` = `tabDelivery Note`.`customer`
        WHERE {conditions}
        ORDER BY `tabCustomer`.`invoicing_method`,
                 `tabDelivery Note`.`customer`,
                 `tabDelivery Note`.`posting_date`
    """
    data = frappe.db.sql(query, filters, as_dict=True)

    return data


def execute(filters=None):
    columns = get_columns()
    data = get_data(filters)
    return columns, data

