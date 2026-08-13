# Copyright (c) 2026, Microsynth
# For license information, please see license.txt

from __future__ import unicode_literals

import frappe


def get_columns():
    return [
        {
            "label": "Customer",
            "fieldname": "customer",
            "fieldtype": "Link",
            "options": "Customer",
            "width": 80,
        },
        {
            "label": "Customer Name",
            "fieldname": "customer_name",
            "fieldtype": "Data",
            "width": 300,
        },
        {
            "label": "Customer Territory",
            "fieldname": "territory",
            "fieldtype": "Link",
            "options": "Territory",
            "width": 280,
        },
        {
            "label": "Customer Sales Manager",
            "fieldname": "account_manager",
            "fieldtype": "Link",
            "options": "User",
            "width": 240,
        },
        {
            "label": "Territory Sales Manager",
            "fieldname": "sales_manager",
            "fieldtype": "Link",
            "options": "User",
            "width": 240,
            "align": "left",
        },
    ]


def get_data():
    return frappe.db.sql(
        """
        SELECT
            `tabCustomer`.`name` AS `customer`,
            `tabCustomer`.`customer_name` AS `customer_name`,
            `tabCustomer`.`territory` AS `territory`,
            `tabCustomer`.`account_manager` AS `account_manager`,
            `tabTerritory`.`sales_manager` AS `sales_manager`
        FROM
            `tabCustomer`
        LEFT JOIN
            `tabTerritory`
        ON
            `tabTerritory`.`name` = `tabCustomer`.`territory`
        WHERE
            IFNULL(`tabCustomer`.`disabled`, 0) = 0
            AND IFNULL(`tabTerritory`.`sales_manager`, '') != IFNULL(`tabCustomer`.`account_manager`, '')
            AND `tabCustomer`.`account_manager` IN (SELECT `tabTerritory`.`sales_manager` FROM `tabTerritory`)
        ORDER BY
            `tabCustomer`.`territory`,
            `tabCustomer`.`account_manager`,
            `tabCustomer`.`name`
        """,
        as_dict=True,
    )


def execute(filters=None):
    columns = get_columns()
    data = get_data()
    return columns, data
