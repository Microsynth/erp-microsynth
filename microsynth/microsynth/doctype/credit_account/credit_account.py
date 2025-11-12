# -*- coding: utf-8 -*-
# Copyright (c) 2025, Microsynth, libracore and contributors and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document

class CreditAccount(Document):
	def validate(self):
		# Ensure that once there are transactions, certain fields cannot be changed
		if self.has_transactions:
			original = frappe.get_doc("Credit Account", self.name)
			if self.customer != original.customer:
				frappe.throw("Cannot change Customer of Credit Account with existing transactions.")
			if self.company != original.company:
				frappe.throw("Cannot change Company of Credit Account with existing transactions.")
			if self.currency != original.currency:
				frappe.throw("Cannot change Currency of Credit Account with existing transactions.")
			if self.account_type != original.account_type:
				frappe.throw("Cannot change Account Type of Credit Account with existing transactions.")


@frappe.whitelist()
def get_dashboard_data(credit_account):
    """
    Return related Sales Orders and Sales Invoices (up to 50 each) for a given Credit Account.
    """
    sales_orders = frappe.db.sql("""
        SELECT
            `tabSales Order`.`name`,
            `tabSales Order`.`transaction_date`,
            `tabSales Order`.`customer`,
            `tabSales Order`.`customer_name`,
            `tabSales Order`.`currency`,
            `tabSales Order`.`grand_total`,
            `tabSales Order`.`status`
        FROM `tabSales Order`
        INNER JOIN `tabCredit Account Link`
            ON `tabCredit Account Link`.`parent` = `tabSales Order`.`name`
        WHERE
            `tabCredit Account Link`.`parenttype` = 'Sales Order'
            AND `tabCredit Account Link`.`credit_account` = %s
            AND `tabSales Order`.`docstatus` < 2
        ORDER BY `tabSales Order`.`transaction_date` DESC
        LIMIT 50
    """, (credit_account,), as_dict=True)

    sales_invoices = frappe.db.sql("""
        SELECT
            `tabSales Invoice`.`name`,
            `tabSales Invoice`.`posting_date`,
            `tabSales Invoice`.`customer`,
            `tabSales Invoice`.`customer_name`,
            `tabSales Invoice`.`currency`,
            `tabSales Invoice`.`grand_total`,
            `tabSales Invoice`.`status`
        FROM `tabSales Invoice`
        INNER JOIN `tabCredit Account Link`
            ON `tabCredit Account Link`.`parent` = `tabSales Invoice`.`name`
        WHERE
            `tabCredit Account Link`.`parenttype` = 'Sales Invoice'
            AND `tabCredit Account Link`.`credit_account` = %s
            AND `tabSales Invoice`.`docstatus` < 2
        ORDER BY `tabSales Invoice`.`posting_date` DESC
        LIMIT 50
    """, (credit_account,), as_dict=True)

    return {
        "sales_orders": sales_orders,
        "sales_invoices": sales_invoices
    }
