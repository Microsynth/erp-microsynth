# Copyright (c) 2025, Microsynth, libracore and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.utils import today


def get_columns():
    return [
        {"label": "Credit Account", "fieldname": "name", "fieldtype": "Link", "options": "Credit Account", "width": 100},
        {"label": "Account Name", "fieldname": "account_name", "fieldtype": "Data", "width": 220},
        {"label": "Customer", "fieldname": "customer", "fieldtype": "Link", "options": "Customer", "width": 80},
        {"label": "Customer Name", "fieldname": "customer_name", "fieldtype": "Data", "width": 220},
        {"label": "Contact", "fieldname": "contact_person", "fieldtype": "Link", "options": "Contact", "width": 80},
        {"label": "Company", "fieldname": "company", "fieldtype": "Link", "options": "Company", "width": 150},
        {"label": "Currency", "fieldname": "currency", "fieldtype": "Link", "options": "Currency", "width": 70},
        {"label": "Expiry Date", "fieldname": "expiry_date", "fieldtype": "Date", "width": 85},
        {"label": "Status", "fieldname": "status", "fieldtype": "Data", "width": 75},
        {"label": "Cancel", "fieldname": "cancel_action", "fieldtype": "HTML", "width": 75},
    ]


def get_data(filters):
    expiry_date_before = filters.get("expiry_date_before") or today()
    company = filters.get("company")
    customer = filters.get("customer")
    contact_person = filters.get("contact_person")

    conditions = [
        "`account_type` = 'Enforced Credit'",
        "IFNULL(`expiry_date`, '9999-12-31') < %(expiry_date_before)s"
    ]
    if company:
        conditions.append("`company` = %(company)s")
    if customer:
        conditions.append("`customer` = %(customer)s")
    if contact_person:
        conditions.append("`contact_person` = %(contact_person)s")

    where_clause = " AND ".join(conditions)

    rows = frappe.db.sql(f"""
        SELECT
            `name`,
            `account_name`,
            `customer`,
            `customer_name`,
            `contact_person`,
            `company`,
            `currency`,
            `expiry_date`,
            `status`
        FROM `tabCredit Account`
        WHERE {where_clause}
        ORDER BY `expiry_date` ASC
    """, filters, as_dict=True)

    data = []
    for r in rows:
        data.append({
            "name": r.name,
            "account_name": r.account_name,
            "customer": r.customer,
            "customer_name": r.customer_name,
            "contact_person": r.contact_person,
            "company": r.company,
            "currency": r.currency,
            "expiry_date": r.expiry_date,
            "status": r.status,
            "cancel_action": (
                "<button class='btn btn-danger btn-xs cancel-credit' "
                f"data-ca='{r.name}' data-exp='{r.expiry_date}'>Cancel</button>"
            ),
        })
    return data


def execute(filters=None):
    if not filters:
        filters = {}
    columns = get_columns()
    data = get_data(filters)
    return columns, data


@frappe.whitelist()
def cancel_credit_account(credit_account):
    # Placeholder: will be replaced later with real cancellation logic
    frappe.msgprint(f"Cancellation logic for {credit_account} not implemented yet.")
    return True
