# Copyright (c) 2025, Microsynth
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.utils.data import today


def get_columns():
    return [
        {"label": "Invoice", "fieldname": "sales_invoice", "fieldtype": "Link", "options": "Sales Invoice", "width": 120},
        {"label": "Customer", "fieldname": "customer", "fieldtype": "Link", "options": "Customer", "width": 75},
        {"label": "Customer Name", "fieldname": "customer_name", "fieldtype": "Data", "width": 230},
        {"label": "Posting Date", "fieldname": "posting_date", "fieldtype": "Date", "width": 90},
        {"label": "Due Date", "fieldname": "due_date", "fieldtype": "Date", "width": 80},
        {"label": "Outstanding", "fieldname": "outstanding_amount", "fieldtype": "Currency", "options": "currency", "width": 95},
        {"label": "Reminders", "fieldname": "reminder_count", "fieldtype": "Int", "width": 80},
        {"label": "Phone Numbers", "fieldname": "phone_numbers", "fieldtype": "Data", "width": 230},
        {"label": "Contact Person", "fieldname": "contact_person", "fieldtype": "Link", "options": "Contact", "width": 105},
        {"label": "Contact Person Name", "fieldname": "contact_display", "fieldtype": "Data", "width": 135},
        {"label": "Note", "fieldname": "note", "fieldtype": "Data", "width": 195},
        {"label": "Remarks", "fieldname": "remarks", "fieldtype": "Data", "width": 195},
        {"label": "Accounting Note ID", "fieldname": "accounting_note_id", "fieldtype": "Link", "options": "Accounting Note", "width": 130},
        {"label": "Invoice to", "fieldname": "invoice_to", "fieldtype": "Link", "options": "Contact", "width": 75},
        {"label": "Reminder to", "fieldname": "reminder_to", "fieldtype": "Link", "options": "Contact", "width": 85}
    ]


def get_data(filters=None):
    data = frappe.db.sql("""
        WITH contact_phones AS (
            SELECT
                `tabContact`.`name` AS contact_name,
                GROUP_CONCAT(`tabContact Phone`.`phone` SEPARATOR ', ') AS contact_phone_numbers
            FROM `tabContact`
            LEFT JOIN `tabContact Phone` ON `tabContact`.`name` = `tabContact Phone`.`parent`
            GROUP BY `tabContact`.`name`
        )
        SELECT
            sales_invoice.`name` AS sales_invoice,
            sales_invoice.`customer` AS customer,
            sales_invoice.`customer_name` AS customer_name,
            sales_invoice.`posting_date` AS posting_date,
            sales_invoice.`due_date` AS due_date,
            sales_invoice.`outstanding_amount` AS outstanding_amount,
            sales_invoice.`currency` AS currency,
            COUNT(payment_reminder_invoice.`parent`) AS reminder_count,
            CONCAT_WS(', ',
                NULLIF(reminder_contact_phones.`contact_phone_numbers`, NULL),
                NULLIF(invoice_contact_phones.`contact_phone_numbers`, NULL)
            ) AS phone_numbers,
            sales_invoice.`contact_person` AS contact_person,
            sales_invoice.`contact_display` AS contact_display,
            customer.`invoice_to` AS invoice_to,
            customer.`reminder_to` AS reminder_to,
            (
                SELECT accounting_note.note
                FROM `tabAccounting Note` AS accounting_note
                LEFT JOIN `tabAccounting Note Reference` AS reference ON reference.parent = accounting_note.name
                WHERE reference.reference_name = sales_invoice.name
                    OR accounting_note.reference_name = sales_invoice.name
                ORDER BY accounting_note.creation ASC
                LIMIT 1
            ) AS note,
            (
                SELECT accounting_note.remarks
                FROM `tabAccounting Note` AS accounting_note
                LEFT JOIN `tabAccounting Note Reference` AS reference ON reference.parent = accounting_note.name
                WHERE reference.reference_name = sales_invoice.name
                    OR accounting_note.reference_name = sales_invoice.name
                ORDER BY accounting_note.creation ASC
                LIMIT 1
            ) AS remarks,
            (
                SELECT accounting_note.name
                FROM `tabAccounting Note` AS accounting_note
                LEFT JOIN `tabAccounting Note Reference` AS reference ON reference.parent = accounting_note.name
                WHERE reference.reference_name = sales_invoice.name
                    OR accounting_note.reference_name = sales_invoice.name
                ORDER BY accounting_note.date ASC, accounting_note.creation ASC
                LIMIT 1
            ) AS accounting_note_id
        FROM `tabSales Invoice` AS sales_invoice
        LEFT JOIN `tabPayment Reminder Invoice` AS payment_reminder_invoice ON payment_reminder_invoice.`sales_invoice` = sales_invoice.`name`
        LEFT JOIN `tabPayment Reminder` AS payment_reminder ON payment_reminder_invoice.`parent` = payment_reminder.`name`
        LEFT JOIN `tabCustomer` AS customer ON sales_invoice.`customer` = customer.`name`
        LEFT JOIN contact_phones AS reminder_contact_phones ON customer.`reminder_to` = reminder_contact_phones.`contact_name`
        LEFT JOIN contact_phones AS invoice_contact_phones ON customer.`invoice_to` = invoice_contact_phones.`contact_name`
        WHERE
            sales_invoice.`docstatus` = 1
            AND sales_invoice.`outstanding_amount` > 0
            AND sales_invoice.`due_date` < NOW()
            AND payment_reminder.`docstatus` = 1
        GROUP BY sales_invoice.`name`
        ORDER BY reminder_count DESC;
        """, as_dict=True)
    return data


def execute(filters=None):
    columns = get_columns()
    data = get_data(filters)
    return columns, data


@frappe.whitelist()
def set_accounting_note(accounting_note_id, note, remarks, sales_invoice_id):
    if accounting_note_id:
        accounting_note = frappe.get_doc("Accounting Note", accounting_note_id)
        accounting_note.note = note
        accounting_note.remarks = remarks
        accounting_note.save()
        frappe.db.commit()
    elif sales_invoice_id:
        # Create a new Accounting Note
        si_doc = frappe.get_doc("Sales Invoice", sales_invoice_id)
        accounting_note_doc = frappe.get_doc({
            'doctype': 'Accounting Note',
            'note': note,
            'remarks': remarks,
            'date': today(),
            'account': si_doc.debit_to,
            'reference_doctype': 'Sales Invoice',
            'reference_name': si_doc.name,
            'amount': si_doc.outstanding_amount,
            'currency': si_doc.currency
        })
        accounting_note_doc.insert()
    else:
        frappe.throw("Unable to edit or create an Accounting Note. Please provide an Accounting Note ID or a Sales Invoice ID.")
