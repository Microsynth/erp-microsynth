# -*- coding: utf-8 -*-
# Copyright (c) 2025, Microsynth, libracore and contributors and contributors
# For license information, please see license.txt

import json
import frappe
from frappe.model.document import Document

class CreditAccount(Document):
    def validate(self):
        # Ensure that once there are transactions, certain fields cannot be changed
        if self.has_transactions and frappe.db.exists("Credit Account", self.name):
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
def create_promotion_credit_account(account_name, customer_id, company, webshop_account, currency, product_types, expiry_date, description, amount, override_item_name=None):
    """
    Create a new Enforced (Promotion) Credit Account for the given webshop_account (Contact ID) with the given name, description, company and product types.

    bench execute microsynth.microsynth.doctype.credit_account.credit_account.create_promotion_credit_account --kwargs "{'account_name': 'Test', 'customer_id': '8003', 'company': 'Microsynth AG', 'webshop_account': '215856', 'currency': 'CHF', 'product_types': ['Oligos', 'Sequencing'], 'expiry_date': '2025-12-31', 'description': 'some description', 'amount': 123.45 }"
    """
    from microsynth.microsynth.webshop import create_deposit_invoice

    if isinstance(product_types, str):
        product_types = json.loads(product_types)

    credit_account = frappe.get_doc({
        'doctype': 'Credit Account',
        'account_name': account_name,
        'account_type': 'Enforced Credit',
        'customer': customer_id,
        'company': company,
        'contact_person': webshop_account,
        'currency': currency,
        'status': 'Active',
        'product_types_locked': 1,
        'expiry_date': expiry_date,
        'description': description
    })
    # Add product types
    for pt in product_types:
        credit_account.append("product_types", {
            "product_type": pt
        })
    credit_account.insert(ignore_permissions=True)
    # create deposit Sales Invoice
    response = create_deposit_invoice(webshop_account, credit_account.name, amount, currency, override_item_name, company, customer_id, customer_order_number='', ignore_permissions=True)
    if not response['success']:
        frappe.throw(response.get('message'))
    sales_invoice_id = response.get('reference')
    # TODO: create Journal Entry
    return sales_invoice_id
