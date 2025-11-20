# -*- coding: utf-8 -*-
# Copyright (c) 2025, Microsynth, libracore and contributors and contributors
# For license information, please see license.txt

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
