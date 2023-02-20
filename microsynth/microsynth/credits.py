# Copyright (c) 2021-2023, libracore and Contributors
# License: GNU General Public License v3. See license.txt

import frappe

def get_available_credits(customer, company):
    from microsynth.microsynth.report.customer_credits.customer_credits import get_data
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
    
def book_credit(sales_invoice, net_amount):
    sinv = frappe.get_doc("Sales Invoice", sales_invoice)
    credit_item = frappe.get_doc("Item", 
        frappe.get_value("Microsynth Settings", "Microsynth Settings", "credit_item"))
    credit_account = None
    for d in credit_item.item_defaults:
        if d.company == sinv.company:
            credit_account = d.income_account
    if not credit_account:
        frappe.throw("Please define an income account for the Microsynth Item {0}".format(credit_item.name))

    revenue_account = sinv.items[0].income_account

    if not revenue_account:
        frappe.throw("Please define a default revenue account for {0}".format(sinv.company))

    # credit_account  --> get alternative account  (currency)
    # revenue_account --> get alternative account  (country)

    jv = frappe.get_doc({
        'doctype': 'Journal Entry',
        'posting_date': sinv.posting_date,
        'company': sinv.company,
        'accounts': [
            # Take from the credit account e.g. '2020 - Anzahlungen von Kunden EUR - BAL'
            {
                'account': credit_account,      
                'debit_in_account_currency': sinv.total   
            },
            # put into income account e.g. '3300 - 3.1 DNA-Oligosynthese Ausland - BAL'
            {
                'account': revenue_account,               
                'credit_in_account_currency': sinv.base_total    # TODO: handle other currencies than base currency
            }
        ],
        'user_remark': "Credit from {0}".format(sales_invoice)
    })
    jv.insert(ignore_permissions=True)
    jv.submit()
    frappe.db.commit()
    return jv.name
    
