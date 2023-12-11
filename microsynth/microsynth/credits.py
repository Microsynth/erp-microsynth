# Copyright (c) 2021-2023, libracore and Contributors
# License: GNU General Public License v3. See license.txt

import frappe
from datetime import datetime

from frappe.utils import flt, cint
from microsynth.microsynth.utils import (get_alternative_account,
                                         get_alternative_income_account)


def get_available_credits(customer, company, product_type):
    from microsynth.microsynth.report.customer_credits.customer_credits import \
        get_data
    customer_credits = get_data({'customer': customer, 'company': company, 'product_type': product_type})
    return customer_credits


@frappe.whitelist()
def has_credits(customer, product_type=None):
    """
    Called in customer.js
    """
    # get all companies
    companies = frappe.get_all("Company", fields=['name'])
    # loop through the companies and call get_available_credits
    for company in companies:
        credits = get_available_credits(customer, company['name'], product_type)
        if len(credits) > 0:
            return True
    return False


def get_total_credit(customer, company, product_type):
    """
    Return the total credit amount available to a customer for the specified company. Returns None if there is no credit account.

    Run
    bench execute microsynth.microsynth.credits.get_total_credit --kwargs "{ 'customer': '1194', 'company': 'Microsynth AG' }"
    """
    credits = get_available_credits(customer, company, product_type)

    if len(credits) == 0:
        return None

    total = 0
    for credit in credits:
        if not 'outstanding' in credit: 
            continue
        total = total + credit['outstanding']
    return total


def allocate_credits(sales_invoice_doc):
    """
    Allocate the matching customer credit (Project / non-Project) to the given Sales Invoice.
    """
    if frappe.get_value("Customer", sales_invoice_doc.customer, "customer_credits") == 'blocked':
        return sales_invoice_doc
    product_type = sales_invoice_doc.product_type if sales_invoice_doc.product_type == "Project" else None
    customer_credits = get_available_credits(sales_invoice_doc.customer, sales_invoice_doc.company, product_type)
    total_customer_credit = get_total_credit(sales_invoice_doc.customer, sales_invoice_doc.company, product_type)
    if len(customer_credits) > 0:
        invoice_amount = sales_invoice_doc.net_total
        allocated_amount = 0
        sales_invoice_doc.customer_credits = []
        for credit in reversed(customer_credits):       # customer credits are sorted newest to oldest
            if credit.currency != sales_invoice_doc.currency:
                frappe.throw("The currency of Sales Invoice '{0}' does not match the currency of the credit account. Cannot allocate credits.".format(sales_invoice_doc.name))
            if not 'outstanding' in credit or flt(credit['outstanding']) < 0.01:
                continue
            if sales_invoice_doc.product_type != "Project" and credit['product_type'] == "Project":
                # don't pay non-Project invoice with Project credits
                continue
            if sales_invoice_doc.product_type == "Project" and credit['product_type'] != "Project":
                # don't pay Project invoice with non-Project credits
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

        sales_invoice_doc.remaining_customer_credit = total_customer_credit - allocated_amount
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
                'account': credit_account if not cint(sales_invoice.is_return) else income_account,  # invert for credit note,
                'debit_in_account_currency': sales_invoice.total_customer_credit if not cint(sales_invoice.is_return) else base_credit_total, 
                'exchange_rate': sales_invoice.conversion_rate if not cint(sales_invoice.is_return) else 1,
                'cost_center': cost_center
            },
            # put into income account e.g. '3300 - 3.1 DNA-Oligosynthese Ausland - BAL'
            {
                'account': income_account if not cint(sales_invoice.is_return) else credit_account,  # invert for credit note,
                'credit_in_account_currency': base_credit_total if not cint(sales_invoice.is_return) else sales_invoice.total_customer_credit,
                'exchange_rate': 1 if not cint(sales_invoice.is_return) else sales_invoice.conversion_rate,
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

"""
Deug function to fnd customer credit transaction per day

Run as
 $ bench execute microsynth.microsynth.credits.get_customer_credit_transactions --kargs "{'currency': 'EUR', 'date': '2023-06-15'}"
 
"""
def get_customer_credit_transactions(currency, date):
    for d in frappe.db.sql("""
        SELECT
            `raw`.`type` AS `type`,
            `raw`.`date` AS `date`,
            `raw`.`customer` AS `customer`,
            `raw`.`customer_name` AS `customer_name`,
            `raw`.`sales_invoice` AS `sales_invoice`,
            `raw`.`net_amount` AS `net_amount`,
            `raw`.`product_type` AS `product_type`,
            `raw`.`status` AS `status`,
            `raw`.`reference` AS `reference`,
            `raw`.`currency` AS `currency`
        FROM (
            SELECT
                "Credit" AS `type`,
                `tabSales Invoice`.`posting_date` AS `date`,
                `tabSales Invoice`.`customer` AS `customer`,
                `tabSales Invoice`.`customer_name` AS `customer_name`,
                `tabSales Invoice`.`name` AS `sales_invoice`,
                SUM(`tabSales Invoice Item`.`net_amount`) AS `net_amount`,
                `tabSales Invoice`.`product_type` AS `product_type`,
                `tabSales Invoice`.`status` AS `status`,
                `tabSales Invoice Item`.`name` AS `reference`,
                `tabSales Invoice`.`currency` AS `currency`
            FROM `tabSales Invoice Item` 
            LEFT JOIN `tabSales Invoice` ON `tabSales Invoice Item`.`parent` = `tabSales Invoice`.`name`
            WHERE 
                `tabSales Invoice`.`docstatus` = 1
                AND `tabSales Invoice Item`.`item_code` = "6100"
                AND `tabSales Invoice`.`company` = 'Microsynth AG'
                AND `tabSales Invoice`.`posting_date` = "{date}"
                AND `tabSales Invoice`.`currency` = '{currency}'
            GROUP BY `tabSales Invoice`.`name`

            UNION SELECT
                "Allocation" AS `type`,
                `tabSales Invoice`.`posting_date` AS `date`,
                `tabSales Invoice`.`customer` AS `customer`,
                `tabSales Invoice`.`customer_name` AS `customer_name`,
                `tabSales Invoice`.`name` AS `sales_invoice`,
                ( IF (`tabSales Invoice`.`is_return` = 1, 1, -1) * `tabSales Invoice Customer Credit`.`allocated_amount`) AS `net_amount`,
                `tabSales Invoice`.`product_type` AS `product_type`,
                `tabSales Invoice`.`status` AS `status`,
                `tabSales Invoice Customer Credit`.`sales_invoice` AS `reference`,
                `tabSales Invoice`.`currency` AS `currency`
            FROM `tabSales Invoice Customer Credit` 
            LEFT JOIN `tabSales Invoice` ON `tabSales Invoice Customer Credit`.`parent` = `tabSales Invoice`.`name`
            WHERE 
                `tabSales Invoice`.`docstatus` = 1
                AND `tabSales Invoice`.`company` = 'Microsynth AG'
                AND `tabSales Invoice`.`posting_date` = "{date}"
                AND `tabSales Invoice`.`currency` = '{currency}'
        ) AS `raw`
        WHERE `raw`.`net_amount` != 0
        ORDER BY `raw`.`date` DESC, `raw`.`sales_invoice` DESC;""".format(currency=currency, date=date), as_dict=True):
        print("{0}|{1}|{2}|{3}|{4}|{5}|{6}|{7}|{8}|{9}".format(d['type'],
            d['date'],
            d['customer'],
            d['customer_name'],
            d['sales_invoice'],
            d['net_amount'],
            d['product_type'],
            d['status'],
            d['reference'],
            d['currency']))
            
