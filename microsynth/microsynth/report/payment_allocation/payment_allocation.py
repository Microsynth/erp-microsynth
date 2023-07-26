# Copyright (c) 2023, Microsynth, libracore and contributors and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _

def execute(filters=None):
    columns = get_columns(filters)
    data = get_data(filters)
    return columns, data

def get_columns(filters):   
    columns = [
        {"label": _("Date"), "fieldname": "date", "fieldtype": "Date", "width": 80},
        {"label": _("Document"), "fieldname": "dn", "fieldtype": "Dynamic Link", "options": "dt", "width": 120},
        {"label": _("Currency"), "fieldname": "currency", "fieldtype": "Data", "width": 80},
        {"label": _("Account"), "fieldname": "account", "fieldtype": "Link", "options": "Account", "width": 120},
        {"label": _("Total amount"), "fieldname": "total", "fieldtype": "Currency", "options": "currency", "width": 90},
        {"label": _("Allocated to"), "fieldname": "dtn", "fieldtype": "Dynamic Link", "options": "dta", "width": 120},
        {"label": _("Allocated amount"), "fieldname": "allocated_amount", "fieldtype": "Currency", "options": "currency", "width": 90},
        {"label": _("Customer"), "fieldname": "customer", "fieldtype": "Link", "options": "Customer", "width": 100},
        {"label": _("Customer Name"), "fieldname": "customer_name", "fieldtype": "Data", "width": 200},
        {"label": _("Customer Ext Ref"), "fieldname": "customer_ext_ref", "fieldtype": "Data", "width": 120},
        {"label": _(""), "fieldname": "blank", "fieldtype": "Data", "width": 20}
    ]

    return columns

def get_data(filters):
    sql_query = """
        SELECT *
        FROM (
            SELECT
                `pe`.`posting_date` AS `date`,
                "Payment Entry" AS `dt`,
                `pe`.`name` AS `dn`,
                `pe`.`paid_from` AS `account`,
                `pe`.`paid_from_account_currency` AS `currency`,
                `pe`.`paid_amount` AS `total`,
                `per`.`reference_doctype` AS `dta`,
                `per`.`reference_name` AS `dtn`,
                `per`.`allocated_amount` AS `allocated_amount`,
                `per`.`idx` AS `idx`,
                `c1`.`name` AS `customer`,
                `c1`.`customer_name` As `customer_name`,
                `c1`.`ext_debitor_number` AS `customer_ext_ref`
            FROM `tabPayment Entry` AS `pe`
            LEFT JOIN `tabPayment Entry Reference` AS `per` ON `per`.`parent` = `pe`.`name`
            LEFT JOIN `tabCustomer` AS `c1` ON `c1`.`name` = `pe`.`party`
            WHERE 
                `pe`.`posting_date` BETWEEN "{from_date}" AND "{to_date}"
                AND `pe`.`docstatus` = 1
                AND `pe`.`company` = "{company}"
                AND `pe`.`payment_type` = "Receive"
            
            UNION SELECT
                `jv`.`posting_date` AS `date`,
                "Journal Entry" AS `dt`,
                `jv`.`name` AS `dn`,
                `jva`.`account` AS `account`,
                `jva`.`account_currency` AS `currency`,
                `jva`.`credit_in_account_currency` AS `total`,
                `jva`.`reference_type` AS `dta`,
                `jva`.`reference_name` AS `dtn`,
                `jva`.`credit_in_account_currency` AS `allocated_amount`,
                `jva`.`idx` AS `idx`,
                `c2`.`name` AS `customer`,
                `c2`.`customer_name` As `customer_name`,
                `c2`.`ext_debitor_number` AS `customer_ext_ref`
            FROM `tabJournal Entry` AS `jv`
            LEFT JOIN `tabJournal Entry Account` AS `jva` ON `jva`.`parent` = `jv`.`name`
            LEFT JOIN `tabCustomer` AS `c2` ON `c2`.`name` = `jva`.`party`
            WHERE 
                `jv`.`posting_date` BETWEEN "{from_date}" AND "{to_date}"
                AND `jv`.`docstatus` = 1
                AND `jv`.`company` = "{company}"
                AND `jva`.`account` IN (
                    SELECT `name`
                    FROM `tabAccount`
                    WHERE `account_type` = "Receivable" AND `company` = "{company}")
        ) AS `data`
        
        ORDER BY `data`.`date` ASC, `data`.`dn` ASC, `data`.`idx` ASC
        ;
    
    """.format(from_date=filters.get('from_date'), to_date=filters.get('to_date'), company=filters.get('company'))
    
    data = frappe.db.sql(sql_query, as_dict=True)
    
    return data
