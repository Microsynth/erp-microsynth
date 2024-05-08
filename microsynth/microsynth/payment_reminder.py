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
        reminder_contact = frappe.get_value("Customer", self.customer, "reminder_to")
        if not reminder_contact:
            reminder_contact = frappe.get_value("Customer", self.customer, "invoice_to")
        if reminder_contact:
            email_to = frappe.get_value("Contact", reminder_contact, "email_id")
            if email_to:
                self.email = email_to
                self.save()
                frappe.db.commit()
    return


def check_and_print(self, event):
    """
    Print the Payment Reminder if the Customer has Invoicing Method "Post"
    or if the highest reminder level is greater 3.
    """
    if self.highest_level > 3 or frappe.get_value("Customer", self.customer, "invoicing_method") == "Post":
        frappe.local.lang = frappe.db.get_value("Payment Reminder", self.name, "language")

        from erpnextswiss.erpnextswiss.attach_pdf import save_and_attach, create_folder
        from frappe.desk.form.load import get_attachments
        from microsynth.microsynth.utils import get_physical_path

        doctype = format = "Payment Reminder"
        title = frappe.db.get_value(doctype, self.name, "title")
        doctype_folder = create_folder(doctype, "Home")
        title_folder = create_folder(title, doctype_folder)
        filecontent = frappe.get_print(doctype, self.name, format, doc=None, as_pdf = True, no_letterhead=False)

        save_and_attach(
            content = filecontent,
            to_doctype = doctype,
            to_name = self.name,
            folder = title_folder,
            hashname = None,
            is_private = True)

        attachments = get_attachments("Payment Reminder", self.name)
        fid = None
        for a in attachments:
            fid = a['name']
        frappe.db.commit()

        # print the pdf with cups
        path = get_physical_path(fid)
        PRINTER = frappe.get_value("Microsynth Settings", "Microsynth Settings", "invoice_printer")
        import subprocess
        subprocess.run(["lp", path, "-d", PRINTER])
