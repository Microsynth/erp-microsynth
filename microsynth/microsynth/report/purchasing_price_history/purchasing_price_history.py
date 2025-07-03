# Copyright (c) 2025, Microsynth
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _


def get_columns():
    return [
        {"label": _("Date"), "fieldname": "posting_date", "fieldtype": "Date", "width": 85},
        {"label": _("Item"), "fieldname": "item_code", "fieldtype": "Link", "options": "Item", "width": 320},
        #{"label": _("Item Name"), "fieldname": "item_name", "fieldtype": "Data", "width": 180},
        {"label": _("Supplier"), "fieldname": "supplier", "fieldtype": "Link", "options": "Supplier", "width": 70},
        {"label": _("Supplier Name"), "fieldname": "supplier_name", "fieldtype": "Data", "width": 320},
        {"label": _("Quantity"), "fieldname": "qty", "fieldtype": "Float", "width": 80},
		{"label": _("UOM"), "fieldname": "uom", "fieldtype": "Link", "options": "UOM", "width": 90},
        {"label": _("Rate"), "fieldname": "rate", "fieldtype": "Currency", "options": "currency", "width": 110},
        {"label": _("Amount"), "fieldname": "amount", "fieldtype": "Currency", "options": "currency", "width": 120},
		{"label": _("Invoice"), "fieldname": "invoice", "fieldtype": "Link", "options": "Purchase Invoice", "width": 90},
        {"label": _("Currency"), "fieldname": "currency", "fieldtype": "Link", "options": "Currency", "width": 80}
    ]


def get_data(filters):
    if not filters:
        #frappe.msgprint(_("Please set filters to fetch data."))
        return []
    conditions = ""
    if filters.get("item_code"):
        conditions += " AND `tabPurchase Invoice Item`.`item_code` = %(item_code)s"
    if filters.get("supplier"):
        conditions += " AND `tabPurchase Invoice`.`supplier` = %(supplier)s"
    if filters.get("from_date"):
        conditions += " AND `tabPurchase Invoice`.`posting_date` >= %(from_date)s"
    if filters.get("to_date"):
        conditions += " AND `tabPurchase Invoice`.`posting_date` <= %(to_date)s"

    conditions += " AND `tabItem`.`item_group` != 'Financial Accounting'"

    return frappe.db.sql("""
        SELECT
            `tabPurchase Invoice`.`posting_date`,
            `tabPurchase Invoice Item`.`item_code`,
            `tabPurchase Invoice Item`.`item_name`,
            `tabPurchase Invoice Item`.`uom`,
            `tabPurchase Invoice`.`supplier`,
            `tabPurchase Invoice`.`supplier_name`,
            `tabPurchase Invoice`.`name` AS `invoice`,
            `tabPurchase Invoice Item`.`qty`,
            `tabPurchase Invoice Item`.`rate`,
            `tabPurchase Invoice Item`.`amount`,
            `tabPurchase Invoice`.`currency`
        FROM
            `tabPurchase Invoice`,
            `tabPurchase Invoice Item`,
            `tabItem`
        WHERE
            `tabPurchase Invoice`.`name` = `tabPurchase Invoice Item`.`parent`
            AND `tabPurchase Invoice Item`.`item_code` = `tabItem`.`name`
            AND `tabPurchase Invoice`.`docstatus` = 1
            {conditions}
        ORDER BY
            `tabPurchase Invoice`.`posting_date` DESC;
    """.format(conditions=conditions), filters, as_dict=True)


def execute(filters=None):
    columns = get_columns()
    data = get_data(filters)
    return columns, data
