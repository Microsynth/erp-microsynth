# Copyright (c) 2025, Microsynth
# For license information, please see license.txt

import frappe
from frappe import _


def get_columns():
    return [
        {"label": _("Payment Entry"), "fieldname": "name", "fieldtype": "Link", "options": "Payment Entry", "width": 100},
        {"label": _("Posting Date"), "fieldname": "posting_date", "fieldtype": "Date", "width": 90},
        {"label": _("Company"), "fieldname": "company", "fieldtype": "Link", "options": "Company", "width": 155},
        {"label": _("Party Type"), "fieldname": "party_type", "fieldtype": "Data", "width": 80},
        {"label": _("Party"), "fieldname": "party", "fieldtype": "Data", "width": 145},
        {"label": _("Paid Amount"), "fieldname": "paid_amount", "fieldtype": "Currency", "options": "currency", "width": 100},
        {"label": _("Received Amount"), "fieldname": "received_amount", "fieldtype": "Currency", "options": "currency", "width": 115},
        {"label": _("Unallocated Amount"), "fieldname": "unallocated_amount", "fieldtype": "Currency", "options": "currency", "width": 130},
        #{"label": _("Mode of Payment"), "fieldname": "mode_of_payment", "fieldtype": "Data", "width": 115},
        {"label": _("Payment Type"), "fieldname": "payment_type", "fieldtype": "Data", "width": 105},
        {"label": _("Reference No"), "fieldname": "reference_no", "fieldtype": "Data", "width": 205},
        {"label": _("Reference Date"), "fieldname": "reference_date", "fieldtype": "Date", "width": 105},
        {"label": _("Remarks"), "fieldname": "remarks", "fieldtype": "Small Text", "width": 1200}
    ]


def get_data(filters=None):
    if not filters:
        filters = {}

    conditions = ""
    if filters.get("from_date"):
        conditions += " AND `tabPayment Entry`.`posting_date` >= %(from_date)s "
    if filters.get("to_date"):
        conditions += " AND `tabPayment Entry`.`posting_date` <= %(to_date)s "
    if filters.get("party_type"):
        conditions += " AND `tabPayment Entry`.`party_type` = %(party_type)s "
    if filters.get("party"):
        conditions += " AND `tabPayment Entry`.`party` = %(party)s "
    if filters.get("payment_type"):
        conditions += " AND `tabPayment Entry`.`payment_type` = %(payment_type)s "
    if filters.get("company"):
        conditions += " AND `tabPayment Entry`.`company` = %(company)s "

    data = frappe.db.sql(f"""
        SELECT 
            `tabPayment Entry`.`name`,
            `tabPayment Entry`.`posting_date`,
            `tabPayment Entry`.`company`,
            `tabPayment Entry`.`party_type`,
            `tabPayment Entry`.`party`,
            `tabPayment Entry`.`paid_amount`,
            `tabPayment Entry`.`received_amount`,
            `tabPayment Entry`.`unallocated_amount`,
            `tabPayment Entry`.`paid_from_account_currency`,
            `tabPayment Entry`.`paid_to_account_currency`,
            `tabPayment Entry`.`mode_of_payment`,
            `tabPayment Entry`.`payment_type`,
            `tabPayment Entry`.`reference_no`,
            `tabPayment Entry`.`reference_date`,
            `tabPayment Entry`.`remarks`
        FROM 
            `tabPayment Entry`
        WHERE 
            `tabPayment Entry`.`docstatus` = 1
            AND `tabPayment Entry`.`unallocated_amount` != 0 
            {conditions}
    """, filters, as_dict=True)

    for row in data:
        if row.get('payment_type') == 'Pay':
            row['currency'] = row.get('paid_to_account_currency')
        else:
            row['currency'] = row.get('paid_from_account_currency')
    return data


def execute(filters=None):
    columns = get_columns()
    data = get_data(filters)
    return columns, data

