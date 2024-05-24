# Copyright (c) 2024, Microsynth, libracore and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _


def get_columns():
    return [
        {"label": _("Sales Order"), "fieldname": "name", "fieldtype": "Link", "options": "Sales Order", "width": 125},
        {"label": _("Date"), "fieldname": "date", "fieldtype": "Date", "width": 80},
        {"label": _("Total"), "fieldname": "total", "fieldtype": "Currency", "options": "currency", "width": 95},
        {"label": _("Customer"), "fieldname": "customer", "fieldtype": "Link", "options": "Customer", "width": 80},
        {"label": _("Customer Name"), "fieldname": "customer_name", "fieldtype": "Data", "width": 200},
        {"label": _("Invoicing Method"), "fieldname": "inv_method_customer", "fieldtype": "Data", "width": 120},
        {"label": _("Web Order ID"), "fieldname": "web_order_id", "fieldtype": "Data", "width": 95},
        {"label": _("First unlinked DN"), "fieldname": "unlinked_dn_name", "fieldtype": "Link", "options": "Delivery Note", "width": 125},
        {"label": _("DNs"), "fieldname": "dns", "fieldtype": "Integer", "width": 50},
        {"label": _("Product Type"), "fieldname": "product_type", "fieldtype": "Data", "width": 95},
        {"label": _("Pending Samples"), "fieldname": "pending_samples", "fieldtype": "Integer", "width": 50},
        {"label": _("Company"), "fieldname": "company", "fieldtype": "Data", "width": 155},
        {"label": _("Punchout"), "fieldname": "is_punchout", "fieldtype": "Check", "width": 75},
        {"label": _("Hold Order"), "fieldname": "hold_order", "fieldtype": "Check", "width": 80},
        {"label": _("Hold Invoice"), "fieldname": "hold_invoice", "fieldtype": "Check", "width": 90},
        {"label": _("Creator"), "fieldname": "owner", "fieldtype": "Data", "options": "User", "width": 220}
    ]


@frappe.whitelist()
def get_data(filters=None):
    filter_conditions = company_condition = ''

    if not filters.get('include_zero'):
        filter_conditions += "AND `raw`.`total` > 0"
    if filters.get('company'):
        company_condition += f"AND `company` = '{filters.get('company')}'"

    data = frappe.db.sql(f"""
        SELECT * FROM
            (SELECT `tabSales Order`.`name`,
                `tabSales Order`.`transaction_date` AS `date`,
                ROUND(`tabSales Order`.`total`, 2) AS `total`,
                `tabSales Order`.`currency`,
                `tabSales Order`.`customer`,
                `tabSales Order`.`customer_name`,
                `tabCustomer`.`invoicing_method` AS `inv_method_customer`,
                `tabSales Order`.`web_order_id`,
                `tabSales Order`.`product_type`,
                `tabSales Order`.`company`,
                `tabSales Order`.`hold_order`,
                `tabSales Order`.`hold_invoice`,
                `tabSales Order`.`is_punchout`,
                `tabSales Order`.`owner`,
                (SELECT COUNT(`tabSales Invoice Item`.`name`) 
                    FROM `tabSales Invoice Item`
                    WHERE `tabSales Invoice Item`.`docstatus` = 1
                        AND `tabSales Invoice Item`.`sales_order` = `tabSales Order`.`name`
                ) AS `has_sales_invoice`
            FROM `tabSales Order`
            LEFT JOIN `tabCustomer` ON `tabCustomer`.`name` = `tabSales Order`.`customer`
            WHERE `tabSales Order`.`per_delivered` < 0.01
                AND `tabSales Order`.`transaction_date` BETWEEN "{filters.get('from_date')}" AND "{filters.get('to_date')}"
                AND `tabSales Order`.`docstatus` = 1
                AND `tabSales Order`.`status` NOT IN ('Closed', 'Completed')
                {company_condition}
            ) AS `raw`
        WHERE `raw`.`has_sales_invoice` = 0
            {filter_conditions}
        ORDER BY `raw`.`date`;
    """, as_dict=True)

    for so in data:
        if so['web_order_id']:
            delivery_notes = frappe.db.sql(f"""
                SELECT DISTINCT `tabDelivery Note Item`.`parent` AS `unlinked_dn_name`
                FROM `tabDelivery Note Item`
                LEFT JOIN `tabDelivery Note` ON `tabDelivery Note`.`name` = `tabDelivery Note Item`.`parent`
                WHERE `tabDelivery Note`.`web_order_id` = {so['web_order_id']};
                """, as_dict=True)

            if len(delivery_notes) > 0:
                so['unlinked_dn_name'] = delivery_notes[0]['unlinked_dn_name']
            so['dns'] = len(delivery_notes)
        if 'product_type' in so and so['product_type'] == 'Sequencing':
            pending_samples = frappe.db.sql(f"""
                SELECT 
                    `tabSample`.`name`
                FROM `tabSample Link`
                LEFT JOIN `tabSample` ON `tabSample Link`.`sample` = `tabSample`.`name`
                LEFT JOIN `tabSequencing Label` on `tabSample`.`sequencing_label`= `tabSequencing Label`.`name`
                WHERE
                    `tabSample Link`.`parent` = "{so['name']}"
                    AND `tabSample Link`.`parenttype` = "Sales Order"
                    AND `tabSequencing Label`.`status` NOT IN ("received", "processed");
                """, as_dict=True)
            so['pending_samples'] = len(pending_samples)

    return data


def execute(filters=None):
    columns = get_columns()
    data = get_data(filters)
    return columns, data
