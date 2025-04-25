# Copyright (c) 2025, Microsynth
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe


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
        SELECT
            `tabSales Invoice`.`name` AS `sales_invoice`,
            `tabSales Invoice`.`customer`,
            `tabSales Invoice`.`customer_name`,
            `tabSales Invoice`.`posting_date`,
            `tabSales Invoice`.`due_date`,
            `tabSales Invoice`.`outstanding_amount`,
            `tabSales Invoice`.`currency`,
            COUNT(`tabPayment Reminder Invoice`.`parent`) AS `reminder_count`,
            CONCAT_WS(', ',
                IFNULL(`reminder_phones`.`phones`, NULL),
                IFNULL(`invoice_phones`.`phones`, NULL)
            ) AS `phone_numbers`,
            `tabSales Invoice`.`contact_person`,
            `tabSales Invoice`.`contact_display`,
            `tabCustomer`.`invoice_to`,
            `tabCustomer`.`reminder_to`,
            (SELECT `tabAccounting Note`.`name`
                FROM `tabAccounting Note`
                LEFT JOIN `tabAccounting Note Reference` ON `tabAccounting Note Reference`.`parent` = `tabAccounting Note`.`name`
                WHERE 
                    `tabAccounting Note`.`reference_name` = `tabSales Invoice`.`name`
                    OR `tabAccounting Note Reference`.`reference_name` = `tabSales Invoice`.`name`
                GROUP BY `tabAccounting Note`.`name`
                ORDER BY `tabAccounting Note`.`date` ASC
                LIMIT 1
            ) AS `accounting_note_id`,
            (SELECT `tabAccounting Note`.`note`
                FROM `tabAccounting Note`
                LEFT JOIN `tabAccounting Note Reference` ON `tabAccounting Note Reference`.`parent` = `tabAccounting Note`.`name`
                WHERE 
                    `tabAccounting Note`.`reference_name` = `tabSales Invoice`.`name`
                    OR `tabAccounting Note Reference`.`reference_name` = `tabSales Invoice`.`name`
                GROUP BY `tabAccounting Note`.`name`
                ORDER BY `tabAccounting Note`.`date` ASC
                LIMIT 1
            ) AS `note`,
            (SELECT `tabAccounting Note`.`remarks`
                FROM `tabAccounting Note`
                LEFT JOIN `tabAccounting Note Reference` ON `tabAccounting Note Reference`.`parent` = `tabAccounting Note`.`name`
                WHERE 
                    `tabAccounting Note`.`reference_name` = `tabSales Invoice`.`name`
                    OR `tabAccounting Note Reference`.`reference_name` = `tabSales Invoice`.`name`
                GROUP BY `tabAccounting Note`.`name`
                ORDER BY `tabAccounting Note`.`date` ASC
                LIMIT 1
            ) AS `remarks`
        FROM
            `tabSales Invoice`
        LEFT JOIN
            `tabPayment Reminder Invoice` ON `tabPayment Reminder Invoice`.`sales_invoice` = `tabSales Invoice`.`name`
        LEFT JOIN
            `tabPayment Reminder` ON `tabPayment Reminder Invoice`.`parent` = `tabPayment Reminder`.`name`
        LEFT JOIN
            `tabCustomer` ON `tabSales Invoice`.`customer` = `tabCustomer`.`name`
        LEFT JOIN
            (
                SELECT
                    `tabContact`.`name` AS `contact_name`,
                    GROUP_CONCAT(`tabContact Phone`.`phone` SEPARATOR ', ') AS `phones`
                FROM
                    `tabContact`
                LEFT JOIN
                    `tabContact Phone` ON `tabContact`.`name` = `tabContact Phone`.`parent`
                GROUP BY
                    `tabContact`.`name`
            ) AS `reminder_phones` ON `tabCustomer`.`reminder_to` = `reminder_phones`.`contact_name`
        LEFT JOIN
            (
                SELECT
                    `tabContact`.`name` AS `contact_name`,
                    GROUP_CONCAT(`tabContact Phone`.`phone` SEPARATOR ', ') AS `phones`
                FROM
                    `tabContact`
                LEFT JOIN
                    `tabContact Phone` ON `tabContact`.`name` = `tabContact Phone`.`parent`
                GROUP BY
                    `tabContact`.`name`
            ) AS `invoice_phones` ON `tabCustomer`.`invoice_to` = `invoice_phones`.`contact_name`
        WHERE
            `tabSales Invoice`.`docstatus` = 1
            AND `tabSales Invoice`.`outstanding_amount` > 0
            AND `tabSales Invoice`.`due_date` < NOW()
            AND `tabPayment Reminder`.`docstatus` = 1
        GROUP BY
            `tabSales Invoice`.`name`
        ORDER BY
            `reminder_count` DESC;
        """, as_dict=True)
    return data


def execute(filters=None):
    columns = get_columns()
    data = get_data(filters)
    return columns, data


@frappe.whitelist()
def set_accounting_note(accounting_note_id, note, remarks, sales_invoice_id):
    frappe.log_error(f"{accounting_note_id=}")
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
            'date': si_doc.posting_date,
            'account': si_doc.debit_to,
            'reference_doctype': 'Sales Invoice',
            'reference_name': si_doc.name,
            'amount': si_doc.outstanding_amount,
            'currency': si_doc.currency
        })
        accounting_note_doc.insert()
    else:
        frappe.throw("Unable to edit or create an Accounting Note. Please provide an Accounting Note ID or a Sales Invoice ID.")
