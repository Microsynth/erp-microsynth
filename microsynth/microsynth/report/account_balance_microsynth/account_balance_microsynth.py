# Copyright (c) 2024, Microsynth, libracore and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _


def get_columns():
    return [
        {"label": _("Account"), "fieldname": "account", "fieldtype": "Link", "options": "Account", "width": 300},
        {"label": _("Total Credit"), "fieldname": "total_credit", "fieldtype": "Currency", "options": "currency", "width": 110},
        {"label": _("Total Debit"), "fieldname": "total_debit", "fieldtype": "Currency", "options": "currency", "width": 110},
        {"label": _("Difference"), "fieldname": "difference", "fieldtype": "Currency", "options": "currency", "width": 110}
    ]


@frappe.whitelist()
def get_data(filters=None):
    data = []
    for account in ['1090 - Transferkonto CHF (Geld unterwegs) - BAL', '1091 - Transferkonto USD (Geld unterwegs) - BAL', '1092 - Transferkonto EUR (Geld unterwegs) - BAL']:
        entry = frappe.db.sql(f"""
            SELECT DISTINCT `account_currency`,
                SUM(`credit`) as `total_credit`,
                SUM(`debit`) as `total_debit`                
            FROM `tabGL Entry` 
            WHERE `account` = '{account}'
        """, as_dict=True)

        if len(entry) != 1:
            frappe.log_error(f"Found {len(entry)} GL Entries with different currencies for Account '{account}' but expected exactly one.", "account_balance_microsynth")

        total_credit_rounded = round(entry[0]['total_credit'], 2)
        total_debit_rounded = round(entry[0]['total_debit'], 2)
        difference = total_credit_rounded - total_debit_rounded
        if difference >= 0.01:
            data.append({
                'account': account,
                'total_credit': total_credit_rounded,
                'total_debit': total_debit_rounded,
                'difference': difference,
                'currency': entry[0]['account_currency']
            })
    return data


def execute(filters=None):
    columns = get_columns()
    data = get_data(filters)
    return columns, data
