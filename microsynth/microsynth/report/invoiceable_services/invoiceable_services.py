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
        {"label": _("Invoicing method"), "fieldname": "invoicing_method", "fieldtype": "Data", "width": 120},
        {"label": _("Collective billing"), "fieldname": "collective_billing", "fieldtype": "Check", "width": 110},
        {"label": _("Punchout"), "fieldname": "is_punchout", "fieldtype": "Check", "width": 55},
        {"label": _("PO number"), "fieldname": "po_no", "fieldtype": "Data", "width": 80},
        {"label": _("Region"), "fieldname": "region", "fieldtype": "Data", "width": 60},
        {"label": _("Shipment type"), "fieldname": "shipment_type", "fieldtype": "Data", "width": 80},
        {"label": _("Base amount"), "fieldname": "base_net_total", "fieldtype": "Data", "width": 120},
        {"label": _("Currency"), "fieldname": "currency", "fieldtype": "Data", "width": 80},
        {"label": _("Product"), "fieldname": "product_type", "fieldtype": "Data", "width": 80}
    ]

def get_data(filters=None):
    invoiceable_services = frappe.db.sql("""
        SELECT * 
        FROM (
            SELECT 
                `tabDelivery Note`.`posting_date` AS `date`,
                `tabDelivery Note`.`name` AS `delivery_note`,
                `tabDelivery Note`.`customer` AS `customer`,
                `tabDelivery Note`.`customer_name` AS `customer_name`,
                `tabDelivery Note`.`base_net_total` AS `base_net_total`,
                `tabDelivery Note`.`currency` AS `currency`,
                `tabCustomer`.`invoicing_method` AS `invoicing_method`,
                `tabCustomer`.`collective_billing` AS `collective_billing`,
                `tabDelivery Note`.`is_punchout` AS `is_punchout`,
                `tabDelivery Note`.`po_no` AS `po_no`,
                `tabCountry`.`export_code` AS `region`,
                `tabDelivery Note`.`shipment_type` AS `shipment_type`,
                `tabDelivery Note`.`product_type` AS `product_type`,
                (SELECT COUNT(`tabSales Invoice Item`.`name`) 
                 FROM `tabSales Invoice Item`
                 WHERE 
                    `tabSales Invoice Item`.`docstatus` = 1
                    AND `tabSales Invoice Item`.`delivery_note` = `tabDelivery Note`.`name`
                ) AS `has_sales_invoice`,
                (SELECT 
                    IF(`tabSales Order`.`per_billed` = 100, 1,          /* ignore billed sales orders */
                       IFNULL(MAX(`tabSales Order`.`hold_invoice`), 0)) /* or if hold_invoice is set */
                 FROM `tabSales Order`
                 LEFT JOIN `tabDelivery Note Item` ON
                    (`tabSales Order`.`name` = `tabDelivery Note Item`.`against_sales_order`)
                 WHERE `tabDelivery Note Item`.`parent` = `tabDelivery Note`.`name`
                ) AS `hold_invoice` 
            FROM `tabDelivery Note`
            LEFT JOIN `tabCustomer` ON
                (`tabDelivery Note`.`customer` = `tabCustomer`.`name`)
            LEFT JOIN `tabAddress` ON
                (`tabDelivery Note`.`shipping_address_name` = `tabAddress`.`name`)
            LEFT JOIN `tabCountry` ON
                (`tabCountry`.`name` = `tabAddress`.`country`)
            WHERE 
                `tabDelivery Note`.`docstatus` = 1
                AND `tabDelivery Note`.`company` = "{company}"
        ) AS `raw`
        WHERE `raw`.`has_sales_invoice` = 0
          AND `raw`.`hold_invoice` = 0
        ORDER BY `raw`.`customer` ASC;
    """.format(company=filters.get("company")), as_dict=True)
    
    return invoiceable_services
