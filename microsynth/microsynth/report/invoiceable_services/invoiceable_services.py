# Copyright (c) 2022, Microsynth, libracore and contributors and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _

def execute(filters=None):
    columns = get_columns()
    data = get_data(filters)
    return columns, data

def get_columns():
    return [
        {"label": _("Date"), "fieldname": "date", "fieldtype": "Date", "width": 80},
        {"label": _("Delivery Note"), "fieldname": "delivery_note", "fieldtype": "Link", "options": "Delivery Note", "width": 120},
        {"label": _("Customer"), "fieldname": "customer", "fieldtype": "Link", "options": "Customer", "width": 70},
        {"label": _("Customer name"), "fieldname": "customer_name", "fieldtype": "Data", "width": 200},
        {"label": _("Method"), "fieldname": "invoicing_method", "fieldtype": "Data", "width": 70},
        {"label": _("Customer Credits"), "fieldname": "customer_credits", "fieldtype": "Data", "width": 65},
        {"label": _("Collective billing"), "fieldname": "collective_billing", "fieldtype": "Check", "width": 65},
        {"label": _("Punchout"), "fieldname": "is_punchout", "fieldtype": "Check", "width": 55},
        {"label": _("PO number"), "fieldname": "po_no", "fieldtype": "Data", "width": 120},
        {"label": _("Region"), "fieldname": "region", "fieldtype": "Data", "width": 60},
        {"label": _("Tax ID"), "fieldname": "tax_id", "fieldtype": "Data", "width": 130},
        # {"label": _("Shipment type"), "fieldname": "shipment_type", "fieldtype": "Data", "width": 80},
        {"label": _("Base amount"), "fieldname": "base_net_total", "fieldtype": "Currency", "options": "currency", "width": 95},
        # {"label": _("Currency"), "fieldname": "currency", "fieldtype": "Data", "width": 80},
        {"label": _("Remaining credit amount"), "fieldname": "remaining_credits", "fieldtype": "Currency", "options": "currency", "width": 120},
        {"label": _("Product"), "fieldname": "product_type", "fieldtype": "Data", "width": 80},
        #{"label": _("Hold Invoice"), "fieldname": "hold_invoice", "fieldtype": "Check", "width": 65},
        #{"label": _("Order Customer"), "fieldname": "order_customer", "fieldtype": "Link", "options": "Customer", "width": 70},
        #{"label": _("Order Customer Collective Billing"), "fieldname": "order_customer_collective_billing", "fieldtype": "Check", "width": 65}
    ]


def get_data(filters=None):
    company = filters.get("company")
    conditions = ""
    params = {"company": company}

    if filters.get("customer"):
        conditions += " AND `tabCustomer`.`name` = %(customer)s"
        params["customer"] = filters.get("customer")

    if filters.get("exclude_punchout"):
        conditions += " AND `tabDelivery Note`.`is_punchout` != 1"

    if filters.get("collective_billing"):
        conditions += " AND `tabCustomer`.`collective_billing` = 1"

    invoiceable_services = frappe.db.sql("""
        SELECT
            `tabDelivery Note`.`posting_date` AS `date`,
            `tabDelivery Note`.`name` AS `delivery_note`,
            `tabDelivery Note`.`customer` AS `customer`,
            `tabDelivery Note`.`customer_name` AS `customer_name`,
            `tabDelivery Note`.`base_net_total` AS `base_net_total`,
            `tabDelivery Note`.`currency` AS `currency`,
            `tabCustomer`.`invoicing_method` AS `invoicing_method`,
            `tabCustomer`.`customer_credits` AS `customer_credits`,
            CASE
                WHEN EXISTS (
                    SELECT 1
                    FROM `tabDelivery Note Item`
                    INNER JOIN `tabSales Order`
                        ON `tabSales Order`.`name` = `tabDelivery Note Item`.`against_sales_order`
                    INNER JOIN `tabCredit Account Link`
                        ON `tabCredit Account Link`.`parent` = `tabSales Order`.`name`
                        AND `tabCredit Account Link`.`parenttype` = 'Sales Order'
                        AND `tabCredit Account Link`.`parentfield` = 'credit_accounts'
                    WHERE `tabDelivery Note Item`.`parent` = `tabDelivery Note`.`name`
                )
                THEN 0
                ELSE `tabCustomer`.`collective_billing`
            END AS `collective_billing`,

            `tabDelivery Note`.`is_punchout` AS `is_punchout`,
            `tabDelivery Note`.`po_no` AS `po_no`,
            `tabCountry`.`export_code` AS `region`,
            `tabCustomer`.`tax_id` AS `tax_id`,
            `tabDelivery Note`.`shipment_type` AS `shipment_type`,
            `tabDelivery Note`.`product_type` AS `product_type`,
            `tabDelivery Note`.`order_customer` AS `order_customer`,
            `tabOrderCustomer`.`collective_billing` AS `order_customer_collective_billing`
        FROM `tabDelivery Note`
        LEFT JOIN `tabCustomer`
            ON `tabDelivery Note`.`customer` = `tabCustomer`.`name`
        LEFT JOIN `tabCustomer` AS `tabOrderCustomer`
            ON `tabDelivery Note`.`order_customer` = `tabOrderCustomer`.`name`
        LEFT JOIN `tabAddress`
            ON `tabDelivery Note`.`shipping_address_name` = `tabAddress`.`name`
        LEFT JOIN `tabCountry`
            ON `tabCountry`.`name` = `tabAddress`.`country`

        WHERE
            `tabDelivery Note`.`docstatus` = 1
            AND `tabDelivery Note`.`company` = %(company)s
            AND `tabDelivery Note`.`creation` > '2022-12-31'
            AND `tabDelivery Note`.`status` != "Closed"
            AND `tabCustomer`.`invoicing_method` NOT LIKE "%%Prepayment%%"

            /* --- no Sales Invoice exists --- */
            AND NOT EXISTS (
                SELECT 1
                FROM `tabSales Invoice Item`
                WHERE
                    `tabSales Invoice Item`.`docstatus` = 1
                    AND `tabSales Invoice Item`.`delivery_note` = `tabDelivery Note`.`name`
            )
            /* --- no hold_invoice condition --- */
            AND NOT EXISTS (
                SELECT 1
                FROM `tabDelivery Note Item`
                LEFT JOIN `tabSales Order`
                    ON `tabSales Order`.`name` = `tabDelivery Note Item`.`against_sales_order`
                WHERE
                    `tabDelivery Note Item`.`parent` = `tabDelivery Note`.`name`
                    AND (
                        `tabSales Order`.`per_billed` = 100
                        OR IFNULL(`tabSales Order`.`hold_invoice`, 0) = 1
                    )
            )
            {conditions}
        ORDER BY
            `tabCountry`.`export_code`,
            `tabDelivery Note`.`customer` ASC
    """.format(conditions=conditions), params, as_dict=True)

    if filters.get("show_remaining_credits"):
        from microsynth.microsynth.credits import get_total_credit
        remaining_credits = {}
        for dn in invoiceable_services:
            credit_type = 'Project' if dn.get('product_type') == 'Project' else 'Standard'
            key = (dn['customer'], company, credit_type)

            if key not in remaining_credits:
                remaining_credits[key] = get_total_credit(*key)
            dn['remaining_credits'] = remaining_credits[key]

    return invoiceable_services
