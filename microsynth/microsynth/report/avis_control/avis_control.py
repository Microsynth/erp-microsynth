# Copyright (c) 2024, Microsynth, libracore and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _


def execute(filters=None):
    columns = get_columns()
    data = get_data(filters)
    return columns, data


def get_columns():
    columns = [
        {"label": _("Posting Date"), "fieldname": "posting_date", "fieldtype": "Date", "width": 90},
        {"label": _("Payment Entry"), "fieldname": "payment_entry", "fieldtype": "Link", "options": "Payment Entry", "width": 125},
        {"label": _("PE Amount"), "fieldname": "payment_amount", "fieldtype": "Currency", "width": 100, 'options': 'currency'},
        {"label": _("Journal Entry"), "fieldname": "journal_entry", "fieldtype": "Link", "options": "Journal Entry", "width": 125},
        {"label": _("JV Amount"), "fieldname": "allocated_amount", "fieldtype": "Currency", "width": 100, 'options': 'currency'},
        {"label": _("Account"), "fieldname": "account", "fieldtype": "Link", "options": "Account", "width": 300},
        {"label": _("Currency"), "fieldname": "currency", "fieldtype": "Data", "width": 70},
        {"label": _("Difference"), "fieldname": "difference", "fieldtype": "Data", "width": 85}
    ]
    return columns


def get_data(filters, short=False):
    conditions = ""
    if filters.account:
        conditions += """ AND `tabPayment Entry`.`paid_from` = "{a}" """.format(a=filters.account)

    sql_query = """
        SELECT
            *,
            (SELECT 
                SUM(`tabGL Entry`.`credit_in_account_currency`) 
                 - SUM(`tabGL Entry`.`debit_in_account_currency`)
             FROM `tabGL Entry`
             WHERE 
                `tabGL Entry`.`voucher_type` = "Journal Entry"
                AND `tabGL Entry`.`voucher_no` = `avis_pairs`.`journal_entry`
                AND `tabGL Entry`.`account` = `avis_pairs`.`account`
            ) AS `allocated_amount`
        FROM (
            SELECT
                `tabPayment Entry`.`posting_date` AS `posting_date`,
                `tabPayment Entry`.`name` AS `payment_entry`,
                `tabPayment Entry`.`paid_amount` AS `payment_amount`,
                `tabPayment Entry`.`paid_to_account_currency` AS `currency`,
                `tabPayment Entry`.`paid_from` AS `account`,
                `tabJournal Entry`.`name` AS `journal_entry`
            FROM `tabPayment Entry`
            LEFT JOIN `tabJournal Entry` ON `tabJournal Entry`.`user_remark` = `tabPayment Entry`.`name`
            WHERE 
                `tabPayment Entry`.`posting_date` BETWEEN "{from_date}" AND "{to_date}"
                AND `tabJournal Entry`.`company` = "{company}"
                AND `tabJournal Entry`.`docstatus` = 1
                AND `tabPayment Entry`.`docstatus` = 1
                {conditions}
        ) AS `avis_pairs`
        ORDER BY `avis_pairs`.`posting_date`
        ;
    """.format(from_date=filters.from_date, to_date=filters.to_date, company=filters.company, conditions=conditions)

    data = frappe.db.sql(sql_query, as_dict=True)

    # mark differences
    for d in data:
        difference = (d.get("payment_amount") or 0) + (d.get("allocated_amount") or 0)
        if difference != 0:
            d['currency'] = "<span style=\"color: red; \">{0}</span>".format(d.get("currency"))
            d['difference'] = "<span style=\"color: red; \">{:.2f}</span>".format(difference)
        else:
            d['difference'] = "{:.2f}".format(difference)

    return data
