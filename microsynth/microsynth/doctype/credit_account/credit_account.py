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
def create_credit_account(account_name, account_type, customer_id, company, currency, contact_id, product_types,
                          product_types_locked=0, expiry_date=None, description=None, ignore_permissions=False):
    """
    Create a Credit Account with the given values and return its ID.
    """
    if isinstance(product_types, str):
        product_types = json.loads(product_types)

    credit_account = frappe.get_doc({
        "doctype": "Credit Account",
        "account_name": account_name,
        "account_type": account_type,
        "customer": customer_id,
        "company": company,
        "currency": currency,
        "contact_person": contact_id,
        "product_types_locked": product_types_locked,
        "expiry_date": expiry_date,
        "description": description,
        "status": "Active",
    })

    for pt in product_types:
        credit_account.append("product_types", {"product_type": pt})

    credit_account.insert(ignore_permissions=ignore_permissions)
    return credit_account.name
