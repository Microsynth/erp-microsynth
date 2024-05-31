# Copyright (c) 2024, Microsynth, libracore and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.utils import flt

def execute(filters=None):
    columns = get_columns()
    data = get_data(filters)
    return columns, data


def get_columns():
    columns = [
        {"label": _("Posting Date"), "fieldname": "posting_date", "fieldtype": "Date", "width": 95},
        {"label": _("Customer"), "fieldname": "customer", "fieldtype": "Link", "options": "Customer", "width": 80},
        {"label": _("Customer name"), "fieldname": "customer_name", "fieldtype": "Data", "width": 200},
        {"label": _("Voucher Type"), "fieldname": "voucher_type", "fieldtype": "Data", "width": 125},
        {"label": _("Voucher no"), "fieldname": "voucher_no", "fieldtype": "Dynamic Link", "options": "voucher_type", "width": 125},
        {"label": _("Due Date"), "fieldname": "due_date", "fieldtype": "Date", "width": 80},
        {"label": _("Invoiced Amount"), "fieldname": "invoiced_amount", "fieldtype": "Currency", "width": 125, 'options': 'currency'},
        {"label": _("Paid Amount"), "fieldname": "paid_amount", "fieldtype": "Currency", "width": 125, 'options': 'currency'},
        {"label": _("Credit Note"), "fieldname": "credit_note", "fieldtype": "Currency", "width": 125, 'options': 'currency'},
        {"label": _("Outstanding Amount"), "fieldname": "outstanding_amount", "fieldtype": "Currency", "width": 125, 'options': 'currency'},
        {"label": _("Currency"), "fieldname": "currency", "fieldtype": "Link", "options": "Currency", "width": 100},
        {"label": _("Customer PO"), "fieldname": "customer_po", "fieldtype": "Data", "width": 100},
        #{"label": _("Territory"), "fieldname": "territory", "fieldtype": "Link", "options": "Territory", "width": 100},
        #{"label": _("Customer Group"), "fieldname": "customer_group", "fieldtype": "Link", "options": "Customer Group", "width": 100},
        {"label": _("Invoice Remarks"), "fieldname": "remarks", "fieldtype": "Data", "width": 100}
    ]
    return columns


def get_data(filters, short=False):
    customer_matching_query = ""
    if filters.search_type == "Like":
        customer_matching_query = """ AND `tabSales Invoice`.`customer_name` LIKE "%{s}%" """.format(s=filters.customer)
    elif filters.search_type == "Exact":
        customer_matching_query = """ AND `tabSales Invoice`.`customer_name` = "{s}" """.format(s=filters.customer)
    elif filters.search_type == "Customer IDs":
        customer_ids = (filters.customer or "").replace(" ", "").split(",")
        customer_matching_query = """ AND `tabSales Invoice`.`customer` IN ("{s}") """.format(s='", "'.join(customer_ids))
    
    receivable_accounts = []
    for a in frappe.get_all("Account", 
            filters={
                'company': filters.company,
                'account_type': "Receivable",
                'disabled': 0
            },
            fields=['name']
        ):
        receivable_accounts.append(a['name'])
    receivable_accounts_filter = """ IN ("{0}") """.format('", "'.join(receivable_accounts))
    
    sql_query = """
        SELECT
            0 AS `indent`,
            `tabSales Invoice`.`posting_date` AS `posting_date`,
            `tabSales Invoice`.`customer` AS `customer`,
            `tabSales Invoice`.`customer_name` AS `customer_name`,
            "Sales Invoice" AS `voucher_type`,
            `tabSales Invoice`.`name` AS `voucher_no`,
            `tabSales Invoice`.`due_date` AS `due_date`,
            `tabSales Invoice`.`territory` AS `territory`,
            `tabSales Invoice`.`customer_group` AS `customer_group`,
            `tabSales Invoice`.`remarks` AS `remarks`,
            `tabSales Invoice`.`po_no` AS `customer_po`,
            `debit`.`account_currency` AS `currency`,
            SUM(`debit`.`debit_in_account_currency`) - SUM(`debit`.`credit_in_account_currency`) AS `invoiced_amount`,
            SUM(`credit`.`credit_in_account_currency`) - SUM(`credit`.`debit_in_account_currency`)  AS `paid_amount`,
            SUM(`return`.`credit_in_account_currency`) - SUM(`return`.`debit_in_account_currency`)  AS `credit_note`
        FROM `tabSales Invoice`
        LEFT JOIN `tabGL Entry` AS `debit` ON 
            (`debit`.`voucher_no` = `tabSales Invoice`.`name` 
             AND `debit`.`account` {rec_filter})
        LEFT JOIN `tabGL Entry` AS `credit` ON 
            (`credit`.`against_voucher` = `tabSales Invoice`.`name` 
             AND `credit`.`voucher_type` != "Sales Invoice"
             AND `credit`.`account` {rec_filter})
        LEFT JOIN `tabGL Entry` AS `return` ON 
            (`return`.`against_voucher` = `tabSales Invoice`.`name` 
             AND `return`.`voucher_no` != `tabSales Invoice`.`name`
             AND `return`.`voucher_type` = "Sales Invoice"
             AND `return`.`account` {rec_filter})
        WHERE 
            `tabSales Invoice`.`posting_date` BETWEEN "{from_date}" AND "{to_date}"
            AND `tabSales Invoice`.`company` = "{company}"
            AND `debit`.`name` IS NOT NULL
            {matching_query}
        GROUP BY `tabSales Invoice`.`name`
        ORDER BY `tabSales Invoice`.`posting_date` ASC;
    """.format(
        from_date=filters.from_date, 
        to_date=filters.to_date, 
        company=filters.company, 
        matching_query=customer_matching_query,
        rec_filter=receivable_accounts_filter
        )
    
    data = frappe.db.sql(sql_query, as_dict=True)
    
    enriched = []
    
    for d in data:
        d['outstanding_amount'] = flt(d['invoiced_amount']) - flt(d['paid_amount']) - flt(d['credit_note'])
        # insert receivable (sales invoice) node
        enriched.append(d)
        
        # find against transactions
        against_records = frappe.db.sql("""
            SELECT
                1 AS `indent`,
                `against`.*
            FROM
                (
                    SELECT
                        `credit`.`voucher_type`,
                        `credit`.`voucher_no`,
                        `credit`.`posting_date` AS `posting_date`,
                        SUM(`credit`.`credit_in_account_currency`) 
                         - SUM(`credit`.`debit_in_account_currency`)  AS `paid_amount`,
                        `credit`.`account_currency` AS `currency`
                    FROM `tabGL Entry` AS `credit`
                    WHERE 
                        `credit`.`against_voucher` = "{sinv}" 
                        AND `credit`.`voucher_type` != "Sales Invoice"
                        AND `credit`.`account` {rec_filter}
                    GROUP BY `credit`.`voucher_no`
                    
                    UNION SELECT
                        `return`.`voucher_type`,
                        `return`.`voucher_no`,
                        `return`.`posting_date` AS `posting_date`,
                        SUM(`return`.`credit_in_account_currency`) 
                         - SUM(`return`.`debit_in_account_currency`)  AS `credit_note`,
                        `return`.`account_currency` AS `currency`
                    FROM `tabGL Entry` AS `return` 
                    WHERE
                        `return`.`against_voucher` = "{sinv}" 
                        AND `return`.`voucher_no` != "{sinv}"
                        AND `return`.`voucher_type` = "Sales Invoice"
                        AND `return`.`account` {rec_filter}
                    GROUP BY `return`.`voucher_no`
                ) AS `against`
            ORDER BY `against`.`posting_date` ASC;
        """.format(sinv=d['voucher_no'], rec_filter=receivable_accounts_filter), as_dict=True)
        
        # extend resolving entries (PE, JV, SINV-RET)
        for a in against_records:
            enriched.append(a)
            
    return enriched
