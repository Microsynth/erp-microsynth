# Copyright (c) 2026, Microsynth
# For license information, please see license.txt

import frappe
from frappe.utils import getdate, nowdate


# Promo Campaign configuration
PROMO_CAMPAIGNS = {
    "Oligo Bonus Credit – Prepaid Labels": {
        "item_name": "Oligo Bonus Credit – Prepaid Labels",  # Sales Invoice Item.item_name
        "product_type": "Oligos"
    }
}


def get_columns():
    return [
        {"label": "Person ID", "fieldname": "person_id", "fieldtype": "Link", "options": "Contact", "width": 120},
        {"label": "Full Name", "fieldname": "full_name", "fieldtype": "Data", "width": 180},
        {"label": "Credit Account", "fieldname": "credit_account", "fieldtype": "Link", "options": "Credit Account", "width": 140},
        {"label": "Customer ID", "fieldname": "customer", "fieldtype": "Link", "options": "Customer", "width": 120},
        {"label": "Customer Name", "fieldname": "customer_name", "fieldtype": "Data", "width": 180},
        {"label": "Given Promo Credits", "fieldname": "given_credits", "fieldtype": "Currency", "width": 140},
        {"label": "Used Promo Credits", "fieldname": "used_credits", "fieldtype": "Currency", "width": 140},
        {"label": "Remaining Valid Promo Credits", "fieldname": "remaining_valid_credits", "fieldtype": "Currency", "width": 180},
        {"label": "Sales (Period)", "fieldname": "sales_amount", "fieldtype": "Currency", "width": 140},
    ]


def get_conditions(filters):
    ca_conditions = ""
    si_conditions = ""
    params = {}

    if filters.get("person_id"):
        ca_conditions += " AND `tabCredit Account`.`contact_person` = %(person_id)s"
        si_conditions += " AND `tabSales Invoice`.`contact_person` = %(person_id)s"
        params["person_id"] = filters.get("person_id")

    if filters.get("customer"):
        ca_conditions += " AND `tabCredit Account`.`customer` = %(customer)s"
        si_conditions += " AND `tabSales Invoice`.`customer` = %(customer)s"
        params["customer"] = filters.get("customer")

    return ca_conditions, si_conditions, params


def get_data(filters):
    campaign = filters.get("promo_campaign")

    if not campaign:
        frappe.throw("Promo Campaign is required.")
    if campaign not in PROMO_CAMPAIGNS:
        frappe.throw(f"Unknown Promo Campaign: {campaign}")

    from_date = filters.get("from_date")
    to_date = filters.get("to_date")

    if not from_date or not to_date:
        frappe.throw("From Date and To Date are required.")

    credit_item_code = frappe.get_value(
        "Microsynth Settings",
        "Microsynth Settings",
        "credit_item"
    )
    if not credit_item_code:
        frappe.throw(f"No Item found for campaign '{campaign}'")

    config = PROMO_CAMPAIGNS[campaign]
    product_type = config["product_type"]
    today = getdate(nowdate())
    ca_conditions, si_conditions, params = get_conditions(filters)

    deposit_rows = frappe.db.sql(f"""
        SELECT
            `tabSales Invoice`.`credit_account`,
            `tabSales Invoice`.`customer`,
            `tabSales Invoice`.`customer_name`,
            `tabCredit Account`.`contact_person`,
            `tabSales Invoice`.`contact_display`,
            SUM(`tabSales Invoice Item`.`net_amount`) AS `amount`
        FROM `tabSales Invoice`
        INNER JOIN `tabSales Invoice Item`
            ON `tabSales Invoice Item`.`parent` = `tabSales Invoice`.`name`
        INNER JOIN `tabCredit Account`
            ON `tabCredit Account`.`name` = `tabSales Invoice`.`credit_account`
        WHERE
            `tabSales Invoice`.`docstatus` = 1
            AND `tabSales Invoice Item`.`item_code` = %(credit_item_code)s
            AND `tabSales Invoice Item`.`item_name` = %(item_name)s
            AND `tabSales Invoice`.`credit_account` IS NOT NULL
            AND `tabCredit Account`.`account_type` = 'Enforced Credit'
            AND `tabCredit Account`.`expiry_date` IS NOT NULL
            {ca_conditions}
        GROUP BY `tabSales Invoice`.`credit_account`
    """, {
        **params,
        "credit_item_code": credit_item_code,
        "item_name": config["item_name"]
    }, as_dict=True)

    if not deposit_rows:
        return []

    credit_accounts = [d.credit_account for d in deposit_rows]

    # Allocations
    allocation_rows = frappe.db.sql(f"""
        SELECT
            `deposit_invoice`.`credit_account`,
            SUM(
                IF(`tabSales Invoice`.`is_return` = 1, 1, -1)
                * `tabSales Invoice Customer Credit`.`allocated_amount`
            ) AS `amount`
        FROM `tabSales Invoice Customer Credit`
        INNER JOIN `tabSales Invoice`
            ON `tabSales Invoice Customer Credit`.`parent` = `tabSales Invoice`.`name`
        INNER JOIN `tabSales Invoice` AS `deposit_invoice`
            ON `deposit_invoice`.`name` = `tabSales Invoice Customer Credit`.`sales_invoice`
        WHERE
            `tabSales Invoice`.`docstatus` = 1
            AND `deposit_invoice`.`docstatus` = 1
            AND `deposit_invoice`.`credit_account` IN ({",".join(["%s"] * len(credit_accounts))})
        GROUP BY `deposit_invoice`.`credit_account`
    """, tuple(credit_accounts), as_dict=True)

    allocation_map = {a.credit_account: a.amount for a in allocation_rows}

    # Sales in period
    sales_rows = frappe.db.sql(f"""
        SELECT
            `tabSales Invoice`.`contact_person`,
            SUM(`tabSales Invoice`.`net_total`) AS `sales_amount`
        FROM `tabSales Invoice`
        WHERE
            `tabSales Invoice`.`docstatus` = 1
            AND `tabSales Invoice`.`product_type` = %(product_type)s
            AND `tabSales Invoice`.`posting_date` >= %(from_date)s
            AND `tabSales Invoice`.`posting_date` <= %(to_date)s
            {si_conditions}
        GROUP BY `tabSales Invoice`.`contact_person`
    """, {
        **params,
        "product_type": product_type,
        "from_date": from_date,
        "to_date": to_date
    }, as_dict=True)

    sales_map = {s.contact_person: s.sales_amount for s in sales_rows}
    data = []

    for d in deposit_rows:
        credit_account_doc = frappe.get_doc("Credit Account", d.credit_account)
        given = d.amount or 0
        used = abs(allocation_map.get(d.credit_account, 0) or 0)
        remaining = given - used
        sales_amount = sales_map.get(d.contact_person, 0)

        # expiry logic
        if credit_account_doc.expiry_date and credit_account_doc.expiry_date < today:
            remaining_valid = 0
        else:
            remaining_valid = remaining

        data.append({
            "person_id": d.contact_person,
            "full_name": d.contact_display,
            "credit_account": d.credit_account,
            "customer": d.customer,
            "customer_name": d.customer_name,
            "given_credits": given,
            "used_credits": used,
            "remaining_valid_credits": remaining_valid,
            "sales_amount": sales_amount
        })
    return data


def execute(filters=None):
    if not filters:
        filters = {}
    columns = get_columns()
    data = get_data(filters)
    return columns, data
