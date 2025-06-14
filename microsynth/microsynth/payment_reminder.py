# -*- coding: utf-8 -*-
# Copyright (c) 2024, libracore (https://www.libracore.com), Microsynth and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.core.doctype.communication.email import make
from erpnextswiss.erpnextswiss.attach_pdf import save_and_attach, create_folder
from frappe.desk.form.load import get_attachments
from erpnextswiss.erpnextswiss.doctype.payment_reminder.payment_reminder import enqueue_create_payment_reminders


def extend_values(self, event):
    """
    After creation of a new payment reminder, extend meta data with specific values
    """
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


@frappe.whitelist()
def create_prm_for_all_companies():
    """
    Create Payment Reminders for all Companies.
    If "Auto Submit" in the ERPNextSwiss Settings is activated,
    Payment Reminders will be submitted and transmitted.

    Run by a weekly cron job on mondays at 17:20:
    20 17 * * 1  cd /home/frappe/frappe-bench && /usr/local/bin/bench --site erp.microsynth.local execute microsynth.microsynth.payment_reminder.create_prm_for_all_companies

    bench execute microsynth.microsynth.payment_reminder.create_prm_for_all_companies
    """
    for company in frappe.get_all("Company", fields=['name']):
        if company['name'] != "Microsynth France SAS":
            enqueue_create_payment_reminders(company['name'])


@frappe.whitelist()
def get_email_subject(prm):
    if type(prm) == str:
        prm = frappe.get_doc("Payment Reminder", prm)
    frappe.local.lang = frappe.db.get_value("Payment Reminder", prm.name, "language")
    subject_addition = " " + prm.name + " | " + _("Customer ID") + " " + prm.customer
    if (prm.language == "de"):
        if (prm.highest_level == 1):
            subject = _("Microsynth Zahlungserinnerung") + subject_addition
        elif (prm.highest_level >= 2):
            subject = _("Microsynth Mahnung") + " " + subject_addition
        else:
            frappe.log_error(f"Payment Reminder {prm.name} has highest level 0.", "payment_reminder.get_email_subject")
            subject = _("Microsynth Zahlungserinnerung") + subject_addition 
    else:
        subject = _("Microsynth Payment Reminder") + " " + subject_addition
    return subject


@frappe.whitelist()
def get_html_message(prm):
    if type(prm) == str:
        prm = frappe.get_doc("Payment Reminder", prm)
    frappe.local.lang = frappe.db.get_value("Payment Reminder", prm.name, "language")
    html = "<p>" + _("Dear Sir or Madam") + "</p><p><br></p>"
    if (prm.highest_level == 1):
        html += "<p>" + _("The following invoice(s) has(have) already been due for payment.") + " "
        html += _("We assume that the punctual payment has escaped your notice and would be grateful for a rapid settlement of the invoice(s).") + "</p>"
        html += "<p>" + _("Should you have questions about the invoice(s), please feel free to contact us.") + "</p>"
        html += "<p>" + _("If the payment has already been authorized, please ignore this message.") + "</p>"
    elif (prm.highest_level == 2 or prm.highest_level == 3):
        html += "<p>" + _("Everyday business life can be hectic and invoices can be forgotten.") + " "
        html += _("We would therefore like to remind you a second time that the following invoice(s) is(are) due for payment.") + " "
        html += _("Should you have questions about the invoice(s), please feel free to contact us.") + " "
        html += _("Otherwise, we would be grateful for an immediate payment within 10 days.") + "</p>"
        html += "<p>" + _("If the payment has already been authorized, please ignore this message.") + "</p>"
    else:
        html += "<p>" + _("As per our accounting department, this invoice(s) is (are) due for payment since a long time.") + " "
        html += _("Please check the invoice(s) and report any dissension immediately to Microsynth.") + "</p>"
    html += "<p><br>" + _("Kind regards") + "<br>" + _("Microsynth Administration") + "<br><br></p>"
    return html


@frappe.whitelist()
def get_message(prm):
    """
    Returns the non-HTML message for a given Payment Reminder
    """
    if type(prm) == str:
        prm = frappe.get_doc("Payment Reminder", prm)
    html = get_html_message(prm)
    return html.replace('<p>', '').replace('</p>', '\n').replace('<br>', '\n')


def create_pdf_attachment(prm):
    """
    Creates the PDF file for a given Payment Reminder name and attaches the file to the record in the ERP.
    """
    doctype = format = "Payment Reminder"
    name = prm
    frappe.local.lang = frappe.db.get_value("Payment Reminder", prm, "language")
    title = frappe.db.get_value(doctype, name, "title")
    doctype_folder = create_folder(doctype, "Home")
    title_folder = create_folder(title, doctype_folder)
    filecontent = frappe.get_print(doctype, name, format, doc=None, as_pdf=True, no_letterhead=False)

    save_and_attach(
        content = filecontent,
        to_doctype = doctype,
        to_name = name,
        folder = title_folder,
        hashname = None,
        is_private = True)


def send_prm_email(prm):
    """
    Sends the given Payment Reminder via email.
    """
    attachments = get_attachments("Payment Reminder", prm.name)
    fid = None
    for a in attachments:
        fid = a['name']
    frappe.db.commit()

    make(
        recipients = prm.email,
        sender = "info@microsynth.ch",
        sender_full_name = "Microsynth",
        cc = "info@microsynth.ch",
        subject = get_email_subject(prm),
        content = get_html_message(prm),
        doctype = "Payment Reminder",
        name = prm.name,
        attachments = [{'fid': fid}],
        send_email = True
    )


def print_payment_reminder(prm):
    """
    Sends the Payment Reminder to the printer.
    """
    frappe.local.lang = frappe.db.get_value("Payment Reminder", prm.name, "language")

    from frappe.desk.form.load import get_attachments
    from microsynth.microsynth.utils import get_physical_path

    attachments = get_attachments("Payment Reminder", prm.name)
    fid = None
    for a in attachments:
        fid = a['name']
    frappe.db.commit()

    # print the pdf with cups
    path = get_physical_path(fid)
    PRINTER = frappe.get_value("Microsynth Settings", "Microsynth Settings", "invoice_printer")
    import subprocess
    subprocess.run(["lp", path, "-d", PRINTER])


@frappe.whitelist()
def transmit_payment_reminder(self, event):
    """
    Takes a Payment Reminder object or name/ID, creates the PDF attachment
    and sends the Payment Reminder either via email or to the printer.
    The Payment Reminder is sent to the printer if the Customer has Invoicing Method "Post"
    or if the highest reminder level is greater 3.

    bench execute microsynth.microsynth.payment_reminder.transmit_payment_reminder --kwargs "{'prm': 'PRM-09311'}"
    """
    if type(self) == str:
        self = frappe.get_doc("Payment Reminder", self)
    
    create_pdf_attachment(self.name)

    if self.highest_level > 3 or frappe.get_value("Customer", self.customer, "invoicing_method") == "Post":
        print_payment_reminder(self)
    else:
        send_prm_email(self)


def get_all_outstanding_invoices(customer):
    """
    Returns all Sales Invoice records for a given customer
    where `outstanding_amount` > 0 and `docstatus` = 1.
    """
    if not customer:
        return []

    invoices = frappe.db.sql("""
        SELECT
            `tabSales Invoice`.`name`,
            `tabSales Invoice`.`posting_date`,
            `tabSales Invoice`.`due_date`,
            `tabSales Invoice`.`outstanding_amount` AS `outstanding_amount`,
            `tabSales Invoice`.`currency`,
            `tabSales Invoice`.`rounded_total`,
            `tabSales Invoice`.`conversion_rate`,
            `tabSales Invoice`.`invoicing_method`,
            `tabSales Invoice`.`debit_to`,
            `tabAccount`.`account_currency`
        FROM
            `tabSales Invoice`
        LEFT JOIN
            `tabAccount` ON `tabAccount`.`name` = `tabSales Invoice`.`debit_to`
        WHERE
            `tabSales Invoice`.`customer` = %s
            AND `tabSales Invoice`.`docstatus` = 1
            AND `tabSales Invoice`.`outstanding_amount` > 0
        ORDER BY
            `tabSales Invoice`.`due_date` ASC
    """, (customer,), as_dict=True)  # single-element tuple (tuple or list expected)

    return invoices
