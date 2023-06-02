# -*- coding: utf-8 -*-
# Copyright (c) 2023, libracore (https://www.libracore.com) and contributors
# For license information, please see license.txt

import frappe

"""
After creation of a new payment reminder, extend meta data with specific values
"""
def extend_values(self, event):
    # fetch payment reminder contact > email id
    if self.customer:
        payment_reminder_contact = frappe.get_value("Customer", self.customer, "reminder_to")
        if payment_reminder_contact:
            email_to = frappe.get_value("Contact", payment_reminder_contact, "email_id")
            if email_to:
                self.email = email_to
                self.save()
                frappe.db.commit()
                
    return
