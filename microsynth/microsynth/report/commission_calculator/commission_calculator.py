# Copyright (c) 2023, Microsynth, libracore and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _


def get_columns(filters):
    return [
        
        {"label": _("Sales Invoice"), "fieldname": "sales_invoice", "fieldtype": "Link", "options": "Sales Invoice", "width": 125 },
        {"label": _("Customer"), "fieldname": "customer_name", "fieldtype": "Data", "options": "Customer", "width": 200 },
        {"label": _("Amount"), "fieldname": "allocated_amount", "fieldtype": "Currency", "options": "currency", "width": 80 },
        {"label": _("Provision Fraction"), "fieldname": "provision_fraction", "fieldtype": "Float", "width": 125 },
        {"label": _("Provision Base Amount"), "fieldname": "provision_base_amount", "fieldtype": "Currency", "options": "currency", "width": 150 },
        {"label": _("Commission"), "fieldname": "commission", "fieldtype": "Currency", "options": "currency", "width": 90 },
        {"label": _("Currency"), "fieldname": "currency", "fieldtype": "Data", "width": 70 },
        {"label": _("Product Type"), "fieldname": "product_type", "fieldtype": "Data", "width": 90 },
        {"label": _("Company"), "fieldname": "company", "fieldtype": "Data", "width": 150 },
        {"label": _("Billing Address"), "fieldname": "customer_address", "fieldtype": "Data", "width": 150 },
    ]


def get_data(filters):
    company_condition = ''

    if filters.get('company'):
        company_condition += f"AND `company` = '{filters.get('company')}'"

    sql_query = f"""
        SELECT
            `provision_base`.`reference_name` AS `sales_invoice`,
            `provision_base`.`allocated_amount`,
            `provision_base`.`currency`,
            `provision_base`.`provision_fraction`,
            `provision_base`.`customer_name`,
            `provision_base`.`product_type`,
            `provision_base`.`company`,
            `provision_base`.`customer_address`,
            (`provision_base`.`allocated_amount` * `provision_base`.`provision_fraction`) AS `provision_base_amount`,
            (`provision_base`.`allocated_amount` * `provision_base`.`provision_fraction` * ({filters.get('factor')} / 100)) AS `commission`
        FROM
        (
            SELECT
                `gross_cash_flow`.`reference_name`,
                `gross_cash_flow`.`allocated_amount`,
                `gross_cash_flow`.`currency`,
                IFNULL (
                 (SELECT SUM(`tabSales Invoice Item`.`net_amount`) / `tabSales Invoice`.`grand_total`
                  FROM `tabSales Invoice Item`
                  LEFT JOIN `tabSales Invoice` ON `tabSales Invoice`.`name` = `tabSales Invoice Item`.`parent`
                  WHERE `tabSales Invoice Item`.`parent` = `gross_cash_flow`.`reference_name`
                    AND `tabSales Invoice Item`.`item_group` NOT IN ("Shipping", "Shipping Threshold", "Internal Invoices", "Financial Accounting")
                    AND
                      (SELECT `tabAddress`.`country`
                       FROM `tabAddress`
                       WHERE `tabAddress`.`name` = `tabSales Invoice`.`customer_address`) = "{filters.get('country')}" ), 0) AS `provision_fraction`,
                (SELECT `tabSales Invoice`.`customer_name`
                FROM `tabSales Invoice`
                WHERE `tabSales Invoice`.`name` = `gross_cash_flow`.`reference_name`) AS `customer_name`,
                (SELECT `tabSales Invoice`.`product_type`
                FROM `tabSales Invoice`
                WHERE `tabSales Invoice`.`name` = `gross_cash_flow`.`reference_name`) AS `product_type`,
                (SELECT `tabSales Invoice`.`address_display`
                FROM `tabSales Invoice`
                WHERE `tabSales Invoice`.`name` = `gross_cash_flow`.`reference_name`) AS `customer_address`,
                (SELECT `tabSales Invoice`.`company`
                FROM `tabSales Invoice`
                WHERE `tabSales Invoice`.`name` = `gross_cash_flow`.`reference_name`) AS `company`                
            FROM
            (
                SELECT
                    `tabPayment Entry Reference`.`reference_name`,
                    `tabPayment Entry Reference`.`allocated_amount`,
                    `tabPayment Entry`.`paid_from_account_currency` AS `currency`
                FROM `tabPayment Entry Reference`
                LEFT JOIN `tabPayment Entry` ON `tabPayment Entry`.`name` = `tabPayment Entry Reference`.`parent`
                WHERE 
                    `tabPayment Entry`.`docstatus` = 1
                    AND `tabPayment Entry`.`posting_date` BETWEEN "{filters.get('from_date')}" AND "{filters.get('to_date')}"
                    AND `tabPayment Entry Reference`.`reference_doctype` = "Sales Invoice" /* map to allocated invoices */
            ) AS `gross_cash_flow`
        ) AS `provision_base`
        WHERE `provision_base`.`provision_fraction` != 0
        {company_condition}
        """
    data = frappe.db.sql(sql_query, as_dict=True)
    return data


def execute(filters=None):
    columns, data = get_columns(filters), get_data(filters)
    return columns, data
