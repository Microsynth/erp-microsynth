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
        {"label": _("DocType"), "fieldname": "doctype", "fieldtype": "Data", "width": 100},
        {"label": _("Document Name"), "fieldname": "docname", "fieldtype": "Dynamic Link", "options": "doctype", "width": 125},
        {"label": _("Customer"), "fieldname": "customer", "fieldtype": "Link", "options": "Customer", "width": 70},
        {"label": _("Customer name"), "fieldname": "customer_name", "fieldtype": "Data", "width": 200},
        {"label": _("Method"), "fieldname": "invoicing_method", "fieldtype": "Data", "width": 70},
        {"label": _("Customer Credits"), "fieldname": "customer_credits", "fieldtype": "Data", "width": 65},
        {"label": _("Collective billing"), "fieldname": "collective_billing", "fieldtype": "Check", "width": 65},
        {"label": _("Punchout"), "fieldname": "is_punchout", "fieldtype": "Check", "width": 55},
        {"label": _("PO number"), "fieldname": "po_no", "fieldtype": "Data", "width": 120},
        {"label": _("Region"), "fieldname": "region", "fieldtype": "Data", "width": 60},
        {"label": _("Tax ID"), "fieldname": "tax_id", "fieldtype": "Data", "width": 130},
        {"label": _("Base amount"), "fieldname": "base_net_total", "fieldtype": "Currency", "options": "currency", "width": 95},
        # {"label": _("Currency"), "fieldname": "currency", "fieldtype": "Data", "width": 80},
        {"label": _("Remaining credit amount"), "fieldname": "remaining_credits", "fieldtype": "Currency", "options": "currency", "width": 120},
        {"label": _("Product"), "fieldname": "product_type", "fieldtype": "Data", "width": 80}
    ]

def get_data(filters=None):
    """
    bench execute microsynth.microsynth.report.invoiceable_services.invoiceable_services.execute --kwargs "{'filters': {'company': 'Microsynth AG'}}"
    """
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
            `raw`.*
        FROM (
            SELECT
                `tabDelivery Note`.`posting_date`               AS `date`,
                'Delivery Note'                                 AS `doctype`,
                `tabDelivery Note`.`name`                       AS `docname`,
                `tabDelivery Note`.`customer`                   AS `customer`,
                `tabDelivery Note`.`customer_name`              AS `customer_name`,
                `tabDelivery Note`.`base_net_total`             AS `base_net_total`,
                `tabDelivery Note`.`currency`                   AS `currency`,
                `tabCustomer`.`invoicing_method`                AS `invoicing_method`,
                `tabCustomer`.`customer_credits`                AS `customer_credits`,

                CASE
                    WHEN `credit_accounts`.`has_credit_accounts` > 0
                    THEN 0
                    ELSE `tabCustomer`.`collective_billing`
                END                                             AS `collective_billing`,

                `tabDelivery Note`.`is_punchout`                AS `is_punchout`,
                `tabDelivery Note`.`po_no`                      AS `po_no`,
                `tabCountry`.`export_code`                      AS `region`,
                `tabCustomer`.`tax_id`                          AS `tax_id`,
                `tabDelivery Note`.`shipment_type`              AS `shipment_type`,
                `tabDelivery Note`.`product_type`               AS `product_type`,
                IFNULL(`sales_invoice_counts`.`has_sales_invoice`, 0) AS `has_sales_invoice`,
                IFNULL(`sales_order_hold`.`hold_invoice`, 0)    AS `hold_invoice`

            FROM `tabDelivery Note`

            INNER JOIN `tabCustomer`
                ON `tabCustomer`.`name` = `tabDelivery Note`.`customer`

            LEFT JOIN `tabAddress`
                ON `tabAddress`.`name` = `tabDelivery Note`.`shipping_address_name`

            LEFT JOIN `tabCountry`
                ON `tabCountry`.`name` = `tabAddress`.`country`

            /* ---- precomputed Sales Invoice count per Delivery Note ---- */
            LEFT JOIN (
                SELECT
                    `tabSales Invoice Item`.`delivery_note`,
                    COUNT(*) AS `has_sales_invoice`
                FROM `tabSales Invoice Item`
                WHERE `tabSales Invoice Item`.`docstatus` = 1
                GROUP BY `tabSales Invoice Item`.`delivery_note`
            ) AS `sales_invoice_counts`
                ON `sales_invoice_counts`.`delivery_note` = `tabDelivery Note`.`name`

            /* ---- precomputed hold_invoice per Delivery Note ---- */
            LEFT JOIN (
                SELECT
                    `tabDelivery Note Item`.`parent` AS `delivery_note`,
                    MAX(
                        IF(
                            `tabSales Order`.`per_billed` = 100,
                            1,
                            IFNULL(`tabSales Order`.`hold_invoice`, 0)
                        )
                    ) AS `hold_invoice`
                FROM `tabDelivery Note Item`
                INNER JOIN `tabSales Order`
                    ON `tabSales Order`.`name` = `tabDelivery Note Item`.`against_sales_order`
                GROUP BY `tabDelivery Note Item`.`parent`
            ) AS `sales_order_hold`
                ON `sales_order_hold`.`delivery_note` = `tabDelivery Note`.`name`

            /* ---- precomputed credit account detection ---- */
            LEFT JOIN (
                SELECT
                    `tabDelivery Note Item`.`parent` AS `delivery_note`,
                    COUNT(`tabCredit Account Link`.`name`) AS `has_credit_accounts`
                FROM `tabDelivery Note Item`
                INNER JOIN `tabSales Order`
                    ON `tabSales Order`.`name` = `tabDelivery Note Item`.`against_sales_order`
                LEFT JOIN `tabCredit Account Link`
                    ON `tabCredit Account Link`.`parent` = `tabSales Order`.`name`
                AND `tabCredit Account Link`.`parenttype` = 'Sales Order'
                AND `tabCredit Account Link`.`parentfield` = 'credit_accounts'
                GROUP BY `tabDelivery Note Item`.`parent`
            ) AS `credit_accounts`
                ON `credit_accounts`.`delivery_note` = `tabDelivery Note`.`name`

            WHERE
                `tabDelivery Note`.`docstatus` = 1
                AND `tabDelivery Note`.`company` = %(company)s
                AND `tabDelivery Note`.`creation` > '2022-12-31'
                AND `tabDelivery Note`.`status` != 'Closed'
                AND `tabCustomer`.`invoicing_method` NOT LIKE '%%Prepayment%%'
                {conditions}
                AND IFNULL(`sales_invoice_counts`.`has_sales_invoice`, 0) = 0
                AND IFNULL(`sales_order_hold`.`hold_invoice`, 0) = 0

            /* UNION ALL

            SELECT
                `tabSales Order`.`transaction_date`              AS `date`,
                'Sales Order'                                    AS `doctype`,
                `tabSales Order`.`name`                          AS `docname`,
                `tabSales Order`.`customer`                      AS `customer`,
                `tabSales Order`.`customer_name`                 AS `customer_name`,
                `tabSales Order`.`base_net_total`                AS `base_net_total`,
                `tabSales Order`.`currency`                      AS `currency`,
                `tabCustomer`.`invoicing_method`                 AS `invoicing_method`,
                `tabCustomer`.`customer_credits`                 AS `customer_credits`,
                `tabCustomer`.`collective_billing`               AS `collective_billing`,
                `tabSales Order`.`is_punchout`                   AS `is_punchout`,
                `tabSales Order`.`po_no`                         AS `po_no`,
                `tabCountry`.`export_code`                       AS `region`,
                `tabCustomer`.`tax_id`                           AS `tax_id`,
                NULL                                             AS `shipment_type`,
                `tabSales Order`.`product_type`                  AS `product_type`,
                0                                                AS `has_sales_invoice`,
                IFNULL(`tabSales Order`.`hold_invoice`, 0)       AS `hold_invoice`

            FROM `tabSales Order`

            INNER JOIN `tabCustomer`
                ON `tabCustomer`.`name` = `tabSales Order`.`customer`

            LEFT JOIN `tabAddress`
                ON `tabAddress`.`name` = `tabSales Order`.`shipping_address_name`

            LEFT JOIN `tabCountry`
                ON `tabCountry`.`name` = `tabAddress`.`country`

            WHERE
                `tabSales Order`.`docstatus` = 1
                AND `tabSales Order`.`company` = %(company)s
                AND `tabSales Order`.`per_billed` < 100
                AND `tabCustomer`.`invoicing_method` NOT LIKE '%%Prepayment%%'
                AND IFNULL(`tabSales Order`.`hold_invoice`, 0) = 0

                AND EXISTS (
                    SELECT 1
                    FROM `tabSales Invoice`
                    WHERE
                        `tabSales Invoice`.`docstatus` = 1
                        AND `tabSales Invoice`.`po_no` IS NOT NULL
                        AND `tabSales Invoice`.`po_no` != ''
                        AND `tabSales Invoice`.`po_no` LIKE CONCAT('%%', `tabSales Order`.`name`, '%%')  -- this is most likely a performance killer
                )
                AND NOT EXISTS (
                    SELECT 1
                    FROM `tabSales Invoice Item`
                    WHERE
                        `tabSales Invoice Item`.`docstatus` = 1
                        AND `tabSales Invoice Item`.`sales_order` = `tabSales Order`.`name`
                ) */
        ) AS `raw`

        ORDER BY
            `raw`.`region`,
            `raw`.`customer` ASC;
    """.format(conditions=conditions), params, as_dict=True)

    if filters.get("show_remaining_credits"):
        from microsynth.microsynth.credits import get_total_credit
        # store remaining credits in a dictionary because there might be Delivery Notes
        # with the same combination of Customer, Company and credit_type
        remaining_credits = {}
        for dn in invoiceable_services:
            credit_type = 'Project' if 'product_type' in dn and dn['product_type'] == 'Project' else 'Standard'
            if (dn['customer'], company, credit_type) in remaining_credits:
                dn['remaining_credits'] = remaining_credits[(dn['customer'], company, credit_type)]
            else:
                total_credits = get_total_credit(dn['customer'], company, credit_type)
                dn['remaining_credits'] = total_credits
                remaining_credits[(dn['customer'], company, credit_type)] = total_credits

    return invoiceable_services
