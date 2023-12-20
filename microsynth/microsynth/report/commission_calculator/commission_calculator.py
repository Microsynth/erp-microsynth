# Copyright (c) 2023, Microsynth, libracore and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _


def get_columns(filters):
    return [
        {"label": _("Customer"), "fieldname": "customer", "fieldtype": "Link", "options": "Customer", "width": 150 },
        {"label": _("Sales Invoice"), "fieldname": "sales_invoice", "fieldtype": "Link", "options": "Sales Invoice", "width": 125 },
        {"label": _("Payment Entry"), "fieldname": "payment_entry", "fieldtype": "Link", "options": "Payment Entry", "width": 125 },
        {"label": _("Amount"), "fieldname": "amount", "fieldtype": "Currency", "options": "currency", "width": 125 },
        {"label": _("Commission"), "fieldname": "commission", "fieldtype": "Currency", "options": "currency", "width": 125 },
        {"label": _("Currency"), "fieldname": "currency", "fieldtype": "Data", "width": 70 }
    ]


def get_data(filters):
    has_filters = False
    data = []
    if has_filters:
        sql_query = f"""
            SELECT *
            FROM `tabSales Invoice`
            """
        data = frappe.db.sql(sql_query, as_dict=True)
    return data


def execute(filters=None):
    columns, data = get_columns(filters), get_data(filters)
    return columns, data
