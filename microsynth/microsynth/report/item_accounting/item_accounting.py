# Copyright (c) 2025, Microsynth
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _


def get_columns():
    return [
        {"label": _("Item"), "fieldname": "name", "fieldtype": "Link", "options": "Item", "width": 300},
        {"label": _("Account BAL"), "fieldname": "account_BAL", "fieldtype": "Link", "options": "Account", "width": 280, "align": "left"},
        {"label": _("Account GOE"), "fieldname": "account_GOE", "fieldtype": "Link", "options": "Account", "width": 280, "align": "left"},
        {"label": _("Account LYO"), "fieldname": "account_LYO", "fieldtype": "Link", "options": "Account", "width": 280, "align": "left"},
        {"label": _("Account WIE"), "fieldname": "account_WIE", "fieldtype": "Link", "options": "Account", "width": 280, "align": "left"},
        {"label": _("Account ECO"), "fieldname": "account_ECO", "fieldtype": "Link", "options": "Account", "width": 280, "align": "left"}
    ]


@frappe.whitelist()
def get_data(filters=None):
    filter_conditions = ""
    if filters.get('item_group'):
        filter_conditions += f" AND `tabItem`.`item_group` = '{filters.get('item_group')}'"
    if filters.get('account_type') == 'Expense':
        account_type = 'expense_account'
    else:
        account_type = 'income_account'

    data = frappe.db.sql(f"""
        SELECT DISTINCT
            `tabItem`.`name`,
            `tabItem`.`item_name`,
            (SELECT `tabItem Default`.`{account_type}`
                FROM `tabItem Default`
                WHERE `tabItem Default`.`parent` = `tabItem`.`name`
                    AND `tabItem Default`.`company` = 'Microsynth AG'
                LIMIT 1) AS `account_BAL`,
            (SELECT `tabItem Default`.`{account_type}`
                FROM `tabItem Default`
                WHERE `tabItem Default`.`parent` = `tabItem`.`name`
                    AND `tabItem Default`.`company` = 'Ecogenics GmbH'
                LIMIT 1) AS `account_ECO`,
            (SELECT `tabItem Default`.`{account_type}`
                FROM `tabItem Default`
                WHERE `tabItem Default`.`parent` = `tabItem`.`name`
                    AND `tabItem Default`.`company` = 'Microsynth Seqlab GmbH'
                LIMIT 1) AS `account_GOE`,
            (SELECT `tabItem Default`.`{account_type}`
                FROM `tabItem Default`
                WHERE `tabItem Default`.`parent` = `tabItem`.`name`
                    AND `tabItem Default`.`company` = 'Microsynth France SAS'
                LIMIT 1) AS `account_LYO`,
            (SELECT `tabItem Default`.`{account_type}`
                FROM `tabItem Default`
                WHERE `tabItem Default`.`parent` = `tabItem`.`name`
                    AND `tabItem Default`.`company` = 'Microsynth Austria GmbH'
                LIMIT 1) AS `account_WIE`
        FROM `tabItem`
        LEFT JOIN `tabItem Default` ON `tabItem Default`.`parent` = `tabItem`.`name`
        WHERE `tabItem`.`disabled` = 0
            {filter_conditions}
        ORDER BY `tabItem`.`name` ASC;
    """, as_dict=True)
    
    return data


def execute(filters=None):
    columns = get_columns()
    data = get_data(filters)
    return columns, data
