# Copyright (c) 2024, Microsynth, libracore and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _


def get_columns(filters):
    return [
        {"label": _("Company"), "fieldname": "company", "fieldtype": "Data", "width": 160 },
        {"label": _("Item Code"), "fieldname": "item_code", "fieldtype": "Link", "options": "Item", "width": 75 },
        {"label": _("Quantity"), "fieldname": "count", "fieldtype": "Int", "width": 65 }
    ]


def get_data(filters):

    sql_query = f"""
        SELECT `company`,
            `item_code`,
            COUNT(`name`) AS `count`
        FROM (
            SELECT 
                `name`, 
                `item_code`,
                IFNULL (`company`, 
                    (SELECT `default_company` FROM `tabCustomer` WHERE `tabCustomer`.`name` = `base`.`customer`)) AS `company`,
                `sales_order`,
                `dn_posting_date`
            FROM (
                SELECT
                    `tabSequencing Label`.`name`,

                    `tabSequencing Label`.`item` AS `item_code`,

                    `tabSequencing Label`.`sales_order`,

                    (SELECT `company`
                    FROM `tabSales Order`
                    WHERE `tabSales Order`.`name` = `tabSequencing Label`.`sales_order`) AS `company`,

                    (SELECT `link_name` 
                    FROM `tabDynamic Link` 
                    WHERE `tabDynamic Link`.`link_doctype` = "Customer"
                    AND `tabDynamic Link`.`parenttype`= "Contact"
                    AND `tabDynamic Link`.`parent` = `tabSequencing Label`.`contact`) AS `customer`,

                    (SELECT DISTINCT `tabDelivery Note`.`posting_date`
                    FROM `tabDelivery Note Item`
                    LEFT JOIN `tabDelivery Note` ON `tabDelivery Note`.`name` = `tabDelivery Note Item`.`parent`
                    WHERE `tabDelivery Note Item`.`against_sales_order` = `tabSequencing Label`.`sales_order`
                        AND `tabDelivery Note`.`docstatus` = 1
                    ORDER BY `tabDelivery Note`.`posting_date` DESC
                        LIMIT 1) AS `dn_posting_date`

                FROM `tabSequencing Label`
            ) AS `base`
            WHERE `base`.`dn_posting_date` IS NOT NULL
                AND `base`.`dn_posting_date` BETWEEN DATE('{filters.get('from_date')}') AND DATE('{filters.get('to_date')}')
        )  AS `raw`
        WHERE `raw`.`company` = '{filters.get('company')}'
        GROUP BY CONCAT(`raw`.`company`, ":", `raw`.`item_code`);
        """
    data = frappe.db.sql(sql_query, as_dict=True)
    return data


def execute(filters):
    columns, data = get_columns(filters), get_data(filters)
    return columns, data
