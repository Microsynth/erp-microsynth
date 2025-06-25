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
    currency = frappe.get_value("Account", filters.get('account'), 'account_currency')
    return [
        {"label": _("Date"), "fieldname": "date", "fieldtype": "Date", "width": 80},
        #{"label": _("Debit"), "fieldname": "debit", "fieldtype": "Float", "precision": 2, "width": 80},
        {"label": "{0} {1}".format(_("Credit"), currency) , "fieldname": "credit", "fieldtype": "Float", "precision": 2, "width": 80},
        {"label": _("Voucher"), "fieldname": "voucher_no", "fieldtype": "Dynamic Link", "options": "voucher_type", "width": 120},
        {"label": _("Against Voucher"), "fieldname": "against_voucher", "fieldtype": "Link", "options": "Sales Invoice", "width": 120},
        {"label": _("Customer"), "fieldname": "customer", "fieldtype": "Link", "options": "Customer", "width": 100},
        {"label": _("Customer Name"), "fieldname": "customer_name", "fieldtype": "Data", "width": 200},
        {"label": _("Customer Ext Ref"), "fieldname": "customer_ext_ref", "fieldtype": "Data", "width": 120},
        {"label": _(""), "fieldname": "blank", "fieldtype": "Data", "width": 20}
    ]

def get_data(filters=None):
    payments = frappe.db.sql("""
        SELECT
            `tabGL Entry`.`posting_date` AS `date`,
            `tabGL Entry`.`debit_in_account_currency` AS `debit`,
            `tabGL Entry`.`credit_in_account_currency` AS `credit`,
            `tabGL Entry`.`voucher_type` AS `voucher_type`,
            `tabGL Entry`.`voucher_no` AS `voucher_no`,
            `tabGL Entry`.`against_voucher` AS `against_voucher`,
            `tabCustomer`.`name` AS `customer`,
            `tabCustomer`.`customer_name` AS `customer_name`,
            `tabCustomer`.`ext_debitor_number` AS `customer_ext_ref`
        FROM `tabGL Entry`
        LEFT JOIN `tabCustomer` ON `tabCustomer`.`name` = `tabGL Entry`.`party`
        WHERE
            `tabGL Entry`.`company` = "{company}"
            AND `tabGL Entry`.`account` = "{account}"
            AND `tabGL Entry`.`posting_date` BETWEEN "{from_date}" AND "{to_date}"
            AND `tabGL Entry`.`credit` > 0
        ORDER BY `tabGL Entry`.`posting_date` ASC;
    """.format(
        company=filters.get("company"),
        account=filters.get("account"),
        from_date=filters.get("from_date"),
        to_date=filters.get("to_date")
        ), as_dict=True)

    return payments
