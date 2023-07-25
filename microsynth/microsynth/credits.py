# Copyright (c) 2021-2023, libracore and Contributors
# License: GNU General Public License v3. See license.txt

import frappe
from datetime import datetime

from microsynth.microsynth.utils import (get_alternative_account,
                                         get_alternative_income_account)


def get_available_credits(customer, company):
    from microsynth.microsynth.report.customer_credits.customer_credits import \
        get_data
    customer_credits = get_data({'customer': customer, 'company': company})
    return customer_credits


def get_total_credit(customer, company):
    """
    Return the total credit amount available to a customer for the specified company. Returns None if there is no credit account.

    Run
    bench execute microsynth.microsynth.credits.get_total_credit --kwargs "{ 'customer': '1194', 'company': 'Microsynth AG' }"
    """
    credits = get_available_credits(customer, company)

    if len(credits) == 0:
        return None
    
    total = 0
    for credit in credits:
        if not 'outstanding' in credit: 
            continue
        total = total + credit['outstanding']
    return total


def allocate_credits(sales_invoice_doc):
    customer_credits = get_available_credits(sales_invoice_doc.customer, sales_invoice_doc.company)
    if len(customer_credits) > 0:
        invoice_amount = sales_invoice_doc.net_total
        allocated_amount = 0
        for credit in reversed(customer_credits):       # customer credits are sorted newest to oldest
            if credit.currency != sales_invoice_doc.currency:
                frappe.throw("The currency of Sales Invoice '{0}' does not match the currency of the credit account. Cannot allocate credits.".format(sales_invoice_doc.name))
            if not 'outstanding' in credit or credit['outstanding'] == 0:
                continue
            if credit['outstanding'] <= invoice_amount:
                # outstanding invoice amount greater or equal this credit
                sales_invoice_doc.append('customer_credits', {
                    'sales_invoice': credit['sales_invoice'],
                    'credit_amount': credit['outstanding'],
                    'allocated_amount': credit['outstanding']
                })
                allocated_amount += credit['outstanding']
                invoice_amount -= credit['outstanding']
            else:
                # this credit is sufficient to cover the whole invoice
                sales_invoice_doc.append('customer_credits', {
                    'sales_invoice': credit['sales_invoice'],
                    'credit_amount': credit['outstanding'],
                    'allocated_amount': invoice_amount
                })
                allocated_amount += invoice_amount
                invoice_amount -= invoice_amount
            if invoice_amount == 0:
                break
        # allocate discount
        if allocated_amount > 0:
            initial_discount = (sales_invoice_doc.discount_amount or 0)
            sales_invoice_doc.apply_discount_on = "Net Total"
            sales_invoice_doc.additional_discount_percentage = 0
            sales_invoice_doc.discount_amount = initial_discount + allocated_amount
            sales_invoice_doc.total_customer_credit = allocated_amount
            
    return sales_invoice_doc


@frappe.whitelist()
def allocate_credits_to_invoice(sales_invoice):
    """
    Allocate customer credits to a sales invoice.

    run
    bench execute microsynth.microsynth.credits.allocate_credits_to_invoice --kwargs "{'sales_invoice': 'SI-BAL-23000538'}"
    """
    sales_invoice = frappe.get_doc("Sales Invoice", sales_invoice)
    allocate_credits(sales_invoice)
    sales_invoice.save()


@frappe.whitelist()
def book_credit(sales_invoice):
    """
    Create Journal Entries for booking the credits of a sales invoice from the credit account to the income account.

    run
    bench execute microsynth.microsynth.credits.book_credit --kwargs "{'sales_invoice': 'SI-BAL-23000538'}"
    """

    sales_invoice = frappe.get_doc("Sales Invoice", sales_invoice)
    credit_item = frappe.get_doc("Item", 
        frappe.get_value("Microsynth Settings", "Microsynth Settings", "credit_item"))
    
    if sales_invoice.shipping_address_name:
        country = frappe.get_value("Address", sales_invoice.shipping_address_name, "country")
    else:
        country = frappe.get_value("Address", sales_invoice.customer_address, "country")
    
    credit_account = None
    for d in credit_item.item_defaults:
        if d.company == sales_invoice.company:
            credit_account = get_alternative_account(d.income_account, sales_invoice.currency)
    if not credit_account:
        frappe.throw("Please define an income account for the credit item {0}".format(credit_item.name))

    income_account = get_alternative_income_account(sales_invoice.items[0].income_account, country)
    if not income_account:
        frappe.throw("Please define a default income account for {0}".format(sales_invoice.company))

    base_credit_total = sales_invoice.total_customer_credit * sales_invoice.conversion_rate
    cost_center = frappe.db.get_value("Company", sales_invoice.company, "cost_center")
    multi_currency = sales_invoice.currency != frappe.get_value("Account", income_account, "account_currency")

    jv = frappe.get_doc({
        'doctype': 'Journal Entry',
        'posting_date': sales_invoice.posting_date,
        'company': sales_invoice.company,
        'accounts': [
            # Take from the credit account e.g. '2020 - Anzahlungen von Kunden EUR - BAL'
            {
                'account': credit_account,
                'debit_in_account_currency': sales_invoice.total_customer_credit,
                'exchange_rate': sales_invoice.conversion_rate,
                'cost_center': cost_center
            },
            # put into income account e.g. '3300 - 3.1 DNA-Oligosynthese Ausland - BAL'
            {
                'account': income_account,
                'credit_in_account_currency': base_credit_total,
                'cost_center': cost_center
            }
        ],
        'user_remark': "Credit from {0}".format(sales_invoice.name),
        'multi_currency': 1 if multi_currency else 0
    })
    jv.insert(ignore_permissions=True)
    # frappe.throw(income_account)
    jv.submit()
    # frappe.db.commit()
    return jv.name
    

@frappe.whitelist()
def cancel_credit_journal_entry(sales_invoice):
    """
    Cancel the journal entry used for booking credits from the credit account with the book_credit function    

    run
    bench execute microsynth.microsynth.credits.cancel_credit_journal_entry --kwargs "{'sales_invoice': 'SI-BAL-23006789'}"
    """
     
    journal_entries = frappe.get_all("Journal Entry",
        filters={'user_remark': "Credit from {0}".format(sales_invoice)},
        fields=['name'])

    if len(journal_entries) != 1:
        msg = "Cannot cancel credit Journal Entry for Sales Invoice {0}:\nNone or multiple Journal Entries found".format(sales_invoice)
        frappe.log_error(msg, "credits.cancel_credit_journal_entry")
        print(msg)
        return None
    
    journal_entry = frappe.get_doc("Journal Entry", journal_entries[0].name)
    journal_entry.cancel()

    return journal_entry.name
    
@frappe.whitelist()
def close_invoice_against_expense(sales_invoice, account):
    sinv = frappe.get_doc("Sales Invoice", sales_invoice)
    debit_currency = frappe.get_cached_value("Account", account, "account_currency")
    credit_currency = frappe.get_cached_value("Account", sinv.debit_to, "account_currency")
    
    jv = frappe.get_doc({
        'doctype': 'Journal Entry',
        'company': sinv.company,
        'posting_date': datetime.now(),
        'accounts': [
            {
                'account': account,
                'debit_in_account_currency': (sinv.conversion_rate or 1) * sinv.outstanding_amount,
                'account_currency': debit_currency,
                'cost_center': sinv.items[0].cost_center
            },
            {
                'account': sinv.debit_to,
                'credit_in_account_currency': sinv.outstanding_amount,
                'exchange_rate': sinv.conversion_rate,
                'account_currency': credit_currency,
                'cost_center': sinv.items[0].cost_center,
                'party_type': "Customer",
                'party': sinv.customer,
                'reference_type': "Sales Invoice",
                'reference_name': sales_invoice
            }
        ],
        'user_remark': "Close against expense account {0}".format(sales_invoice),
        'multi_currency': 0 if credit_currency == debit_currency else 1
    })
    jv.insert(ignore_permissions=True)
    jv.submit()
    frappe.db.commit()
    return jv.name
