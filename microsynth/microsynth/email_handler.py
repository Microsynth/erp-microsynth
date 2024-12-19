# -*- coding: utf-8 -*-
# Copyright (c) 2023-2024, libracore and contributors
# For license information, please see license.txt
#

import frappe


"""
Hook from Communication
"""
def communication_on_insert(self, event):
    try:
        # when there is a communication on a Sales Invoice, consider it sent
        if self.reference_doctype == "Sales Invoice":
            sinv = frappe.get_doc(self.reference_doctype, self.reference_name)
            if not sinv.invoice_sent_on:
                sinv.invoice_sent_on = self.creation.strftime("%Y-%m-%d %H:%M:%S")
                sinv.save()
                frappe.db.commit()
        
    except Exception as err:
        frappe.log_error(err, "Communication hook failed")
    return
