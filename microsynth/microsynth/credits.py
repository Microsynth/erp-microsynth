# Copyright (c) 2021-2023, libracore and Contributors
# License: GNU General Public License v3. See license.txt

import frappe

from microsynth.microsynth.utils import (get_alternative_account,
                                         get_alternative_income_account)


def get_available_credits(customer, company):
    from microsynth.microsynth.report.customer_credits.customer_credits import \
        get_data
    customer_credits = get_data({'customer': customer, 'company': company})
    return customer_credits

def get_total_credit(customer, company):
    """
    Return the total credit amount available to a customer for the specified company.

    Run
    bench execute microsynth.microsynth.credits.get_total_credit --kwargs "{ 'customer': '1194', 'company': 'Microsynth AG' }"
    """
    credits = get_available_credits(customer, company)
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
            if not 'outstanding' in credit:
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
            sales_invoice_doc.apply_discount_on = "Net Total"
            sales_invoice_doc.discount_amount = (sales_invoice_doc.discount_amount or 0) + allocated_amount
            sales_invoice_doc.total_customer_credit = allocated_amount
            
    return sales_invoice_doc
    
def book_credit(sales_invoice):
    """
    Create Journal Entries for booking the credits of a sales invoice from the credit account to the income account.

    run
    bench execute microsynth.microsynth.invoicing.book_credit --kwargs "{'sales_invoice': 'SI-BAL-23000538'}"
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
                'exchange_rate': sales_invoice.conversion_rate
            },
            # put into income account e.g. '3300 - 3.1 DNA-Oligosynthese Ausland - BAL'
            {
                'account': income_account,
                'credit_in_account_currency': base_credit_total
            }
        ],
        'user_remark': "Credit from {0}".format(sales_invoice.name),
        'multi_currency': 1 if multi_currency else 0
    })
    jv.insert(ignore_permissions=True)
    jv.submit()
    # frappe.db.commit()
    return jv.name
    
