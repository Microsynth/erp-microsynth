# Copyright (c) 2025, Microsynth
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _


def get_columns():
    return [
        {"label": _("Sales Invoice"), "fieldname": "sales_invoice", "fieldtype": "Link", "options": "Sales Invoice", "width": 120},
        {"label": _("Invoice Date"), "fieldname": "posting_date", "fieldtype": "Date", "width": 90},
        {"label": _("Invoice Total"), "fieldname": "total", "fieldtype": "Currency", "options": "currency", "width": 100},
        {"label": _("Customer"), "fieldname": "customer", "fieldtype": "Link", "options": "Customer", "width": 180},
        {"label": _("Customer Name"), "fieldname": "customer_name", "fieldtype": "Data", "options": "Customer", "width": 300},
        {"label": _("Quotation"), "fieldname": "quotation", "fieldtype": "Link", "options": "Quotation", "width": 100},
        {"label": _("Quotation Date"), "fieldname": "quotation_date", "fieldtype": "Date", "width": 100},
        {"label": _("Quotation Owner"), "fieldname": "quotation_owner", "fieldtype": "Link", "options": "User", "width": 200}
    ]


def get_data(filters):
    conditions = ""
    if filters.get("from_date"):
        conditions += " AND `tabSales Invoice`.`posting_date` >= %(from_date)s"
    if filters.get("to_date"):
        conditions += " AND `tabSales Invoice`.`posting_date` <= %(to_date)s"

    return frappe.db.sql("""
        SELECT DISTINCT
            `tabSales Invoice`.`name` AS `sales_invoice`,
            `tabSales Invoice`.`posting_date`,
            `tabSales Invoice`.`customer`,
            `tabSales Invoice`.`customer_name`,
            `tabQuotation`.`name` AS `quotation`,
            `tabQuotation`.`transaction_date` AS `quotation_date`,
            `tabQuotation`.`owner` AS `quotation_owner`,
            `tabSales Invoice`.`total`,
            `tabSales Invoice`.`currency`
        FROM
            `tabSales Invoice`
        INNER JOIN
            `tabSales Invoice Item` ON `tabSales Invoice Item`.`parent` = `tabSales Invoice`.`name`
        LEFT JOIN
            `tabSales Order Item` ON `tabSales Order Item`.`parent` = `tabSales Invoice Item`.`sales_order`
        LEFT JOIN
            `tabQuotation` ON `tabQuotation`.`name` = `tabSales Order Item`.`prevdoc_docname`
        WHERE
            `tabSales Invoice`.`docstatus` = 1
            AND `tabQuotation`.`owner` IN (
                SELECT `tabUser`.`name`
                FROM `tabUser`
                INNER JOIN `tabHas Role` ON `tabHas Role`.`parent` = `tabUser`.`name`
                WHERE `tabHas Role`.`role` = 'Contract Research User'
            )
            {conditions}
        ORDER BY `tabSales Invoice`.`posting_date` DESC
    """.format(conditions=conditions), filters, as_dict=True)


def execute(filters=None):
    columns = get_columns()
    data = get_data(filters)
    return columns, data
