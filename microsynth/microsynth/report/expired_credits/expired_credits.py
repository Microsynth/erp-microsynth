# Copyright (c) 2025, Microsynth, libracore and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import json
import traceback
import frappe
from frappe import _
from frappe.utils import today
from microsynth.microsynth.credits import reverse_credit


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


def get_outstanding_credit(sales_invoice_doc):
    """
    Helper function to get the outstanding credit amount for a given deposit Sales Invoice.
    """
    # TODO
    return 0.0


def cancel_internal_deposit_invoice(sales_invoice_id):
    """
    Create a partial Credit Note for the unspent portion of the given deposit
    Sales Invoice and create the reversing Journal Entry via reverse_credit.

    Logic:
    - determine the unspent credit based on the Sales Invoice outstanding_amount
    - if there is an unspent amount, call reverse_credit(sales_invoice, net_amount)
      which will create the Credit Note (partial return) and create a reversing JV
      referencing the original Sales Invoice.
    - returns a dict with result and any errors
    """
    result = {'sales_invoice': sales_invoice_id, 'credit_note': None, 'reversing_journal_entry': None, 'errors': []}
    try:
        sales_invoice_doc = frappe.get_doc("Sales Invoice", sales_invoice_id)
    except Exception as e:
        result['errors'].append(f"Sales Invoice not found: {e}")
        return result

    if sales_invoice_doc.docstatus != 1:
        result['errors'].append("Sales Invoice not submitted")
        return result

    # Determine unspent credit.
    net_amount_to_return = get_outstanding_credit(sales_invoice_doc)
    if net_amount_to_return <= 0:
        result['errors'].append("No unspent credit to return")
        return result
    try:
        # Reuse existing logic in reverse_credit which creates a Credit Note for the
        # requested net_amount and creates the necessary reversing Journal Entry.
        credit_note_name = reverse_credit(sales_invoice_id, net_amount_to_return)
        result['credit_note'] = credit_note_name

        # Attempt to find the reversing Journal Entry created by reverse_credit
        jvs = frappe.get_all("Journal Entry",
                             filters={'user_remark': ("Reverse Credit for {0}".format(sales_invoice_id))},
                             fields=['name'])
        if jvs:
            # return the first found reversing JV name
            result['reversing_journal_entry'] = jvs[0]['name']
    except Exception as e:
        frappe.log_error(traceback.format_exc(), "expired_credits.cancel_internal_deposit_invoice:reverse_credit_error")
        result['errors'].append(f"Failed to reverse credit for Sales Invoice {sales_invoice_id}: {e}")

    return result


@frappe.whitelist()
def cancel_credit_account(credit_account_id):
    """
    Cancel an Enforced Credit Account by creating Credit Notes for related deposit
    Sales Invoices and disabling the Credit Account.

    Steps:
    - validate Credit Account is Enforced Credit
    - find deposit Sales Invoices (credit item) linked to this Credit Account (submitted)
    - for each deposit Sales Invoice: call cancel_internal_deposit_invoice
    - set Credit Account status to 'Disabled'
    """
    try:
        credit_account_doc = frappe.get_doc("Credit Account", credit_account_id)
    except Exception as e:
        frappe.throw(f"Credit Account '{credit_account_id}' not found: {e}")

    if credit_account_doc.account_type != "Enforced Credit":
        frappe.throw("Only Enforced Credit Accounts can be cancelled via this method.")

    credit_item_code = frappe.get_value("Microsynth Settings", "Microsynth Settings", "credit_item")
    if not credit_item_code:
        frappe.throw("Please define a credit item in the Microsynth Settings.")

    # Find deposit Sales Invoices that belong to this Credit Account and contain the credit item
    sql = """
        SELECT DISTINCT si.name AS invoice_name
        FROM `tabSales Invoice` si
        JOIN `tabSales Invoice Item` sii ON sii.parent = si.name
        WHERE si.docstatus = 1
          AND si.credit_account = %s
          AND sii.item_code = %s
    """
    deposit_invoices = frappe.db.sql(sql, (credit_account_id, credit_item_code), as_dict=True)

    results = {'processed_invoices': [], 'skipped_invoices': [], 'errors': []}

    for invoice_row in deposit_invoices:
        invoice_name = invoice_row.get('invoice_name')
        try:
            res = cancel_internal_deposit_invoice(invoice_name)
            if res.get('errors'):
                results['errors'].append({invoice_name: res.get('errors')})
            else:
                results['processed_invoices'].append({'sales_invoice': invoice_name, 'credit_note': res.get('credit_note')})
        except Exception as e:
            frappe.log_error(traceback.format_exc(), "expired_credits.cancel_credit_account:process_invoice_error")
            results['errors'].append({invoice_name: str(e)})

    # After attempting to cancel related invoices, disable the Credit Account
    try:
        credit_account_doc.status = 'Disabled'
        credit_account_doc.save()
    except Exception as e:
        frappe.log_error(traceback.format_exc(), "expired_credits.cancel_credit_account:disable_ca_error")
        results['errors'].append(f"Failed to disable Credit Account: {e}")

    # Show a user-friendly message for the UI if called from frontend
    if frappe.local.request and getattr(frappe.local.request, 'method', None) == 'POST':
        if results['errors']:
            frappe.msgprint({
                'title': _("Partial failure"),
                'indicator': 'orange',
                'message': _("Cancellation completed with errors. See logs for details.")
            })
        else:
            frappe.msgprint({
                'title': _("Success"),
                'indicator': 'green',
                'message': _("Credit Account {0} cancelled and disabled.").format(credit_account_id)
            })
    return results


def cancel_promo_credit_accounts(credit_account_ids):
    """
    Cancel multiple promotional credit accounts.
    """
    if isinstance(credit_account_ids, str):
        credit_account_ids = json.loads(credit_account_ids)

    for ca_id in credit_account_ids:
        cancel_credit_account(ca_id)
