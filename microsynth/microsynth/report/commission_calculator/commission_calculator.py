# Copyright (c) 2023, Microsynth, libracore and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import os
import json
from datetime import datetime
import frappe
from frappe import _
from microsynth.microsynth.invoicing import pdf_export


def get_columns(filters):
    return [
        {"label": _("Sales Invoice"), "fieldname": "sales_invoice", "fieldtype": "Link", "options": "Sales Invoice", "width": 125 },
        {"label": _("Customer Name"), "fieldname": "customer_name", "fieldtype": "Data", "options": "Customer", "width": 200 },
        {"label": _("Amount"), "fieldname": "allocated_amount", "fieldtype": "Currency", "options": "currency", "width": 100 },
        {"label": _("Provision Fraction"), "fieldname": "provision_fraction", "fieldtype": "Float", "width": 125 },
        {"label": _("Provision Base Amount"), "fieldname": "provision_base_amount", "fieldtype": "Currency", "options": "currency", "width": 150 },
        {"label": _("Commission"), "fieldname": "commission", "fieldtype": "Currency", "options": "currency", "width": 100 },
        {"label": _("Currency"), "fieldname": "currency", "fieldtype": "Data", "width": 75 },
        {"label": _("Product Type"), "fieldname": "product_type", "fieldtype": "Data", "width": 100 },
        {"label": _("Company"), "fieldname": "company", "fieldtype": "Data", "width": 150 },
        {"label": _("Billing Address"), "fieldname": "customer_address", "fieldtype": "Data", "width": 150 },
    ]


def get_data(filters):
    company_condition = product_type_condition = ''

    if filters.get('company'):
        company_condition += f"AND `company` = '{filters.get('company')}'"
    if filters.get('product_type'):
        product_type_condition += f"AND `product_type` = '{filters.get('product_type')}'"

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
                UNION ALL SELECT
                    `tabJournal Entry Account`.`reference_name`,
                    `tabJournal Entry Account`.`credit_in_account_currency` AS `allocated_amount`,
                    `tabJournal Entry Account`.`account_currency` AS `currency`
                FROM `tabJournal Entry Account`
                LEFT JOIN `tabJournal Entry` ON `tabJournal Entry`.`name` = `tabJournal Entry Account`.`parent`
                WHERE
                    `tabJournal Entry`.`docstatus` = 1
                    AND `tabJournal Entry`.`posting_date` BETWEEN "{filters.get('from_date')}" AND "{filters.get('to_date')}"
                    AND `tabJournal Entry Account`.`reference_type` = "Sales Invoice" /* map to allocated invoices */
            ) AS `gross_cash_flow`
        ) AS `provision_base`
        WHERE `provision_base`.`provision_fraction` != 0
        {company_condition}
        {product_type_condition}
        """
    data = frappe.db.sql(sql_query, as_dict=True)
    return data


def execute(filters=None):
    columns, data = get_columns(filters), get_data(filters)
    return columns, data


@frappe.whitelist()
def async_pdf_export(filters):
    """
    Wrapper to start an asyncronous job for the function pdf_export_cc
    """
    if type(filters) == str:
        filters = json.loads(filters)

    frappe.enqueue(method=pdf_export_cc, queue='long', timeout=600, is_async=True, filters=filters)


def pdf_export_cc(filters):
    """
    Exports the selected Sales Invoices as one PDF each to the specified path.
    """
    path_prefix = frappe.get_value("Microsynth Settings", "Microsynth Settings", "commission_calculator_export_path")

    if not os.path.exists(path_prefix):
        os.mkdir(path_prefix)

    path = path_prefix + "/" + datetime.now().strftime("%Y-%m-%d_%H-%M_") + filters.get('country') + "_from_" + filters.get('from_date') + "_to_" + filters.get('to_date')

    if not os.path.exists(path):
        os.mkdir(path)

    raw_data = get_data(filters)
    sales_invoices = []

    for si in raw_data:
        sales_invoices.append(si['sales_invoice'])

    pdf_export(sales_invoices, path)
