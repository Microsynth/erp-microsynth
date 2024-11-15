# Copyright (c) 2021-2024, Microsynth, libracore and contributors
# License: GNU General Public License v3. See license.txt

import frappe
from datetime import date, datetime, timedelta
from frappe.utils.data import today
from frappe.utils import flt, cint
from microsynth.microsynth.utils import (get_alternative_account,
                                         get_alternative_income_account,
                                         send_email_from_template)


def get_available_credits(customer, company, credit_type):
    from microsynth.microsynth.report.customer_credits.customer_credits import \
        get_data
    customer_credits = get_data({'customer': customer, 'company': company, 'credit_type': credit_type})
    return customer_credits


@frappe.whitelist()
def has_credits(customer, credit_type=None):
    """
    Called in customer.js
    """
    # get all companies
    companies = frappe.get_all("Company", fields=['name'])
    # loop through the companies and call get_available_credits
    for company in companies:
        credits = get_available_credits(customer, company['name'], credit_type)
        if len(credits) > 0:
            return True
    return False


def get_total_credit(customer, company, credit_type):
    """
    Return the total credit amount available to a customer for the specified company and credit_type. Returns None if there is no credit account.

    Run
    bench execute microsynth.microsynth.credits.get_total_credit --kwargs "{ 'customer': '1194', 'company': 'Microsynth AG', 'credit_type': 'Project' }"
    """
    credits = get_available_credits(customer, company, credit_type)

    if len(credits) == 0:
        return None

    total = 0
    for credit in credits:
        if not 'outstanding' in credit: 
            continue
        total = total + credit['outstanding']
    return total


# def get_total_credit_without_project(customer, company):
#     """
#     Return the total credit amount available to a customer for the specified company excluding credits with product type project.
#     Returns None if there is no credit account.

#     Run
#     bench execute microsynth.microsynth.credits.get_total_credit_without_project --kwargs "{ 'customer': '1194', 'company': 'Microsynth AG' }"
#     """
#     credits = get_available_credits(customer, company, None)

#     if len(credits) == 0:
#         return None

#     total = 0
#     for credit in credits:
#         if credit['credit_type'] == "Project":
#             continue
#         if not 'outstanding' in credit: 
#             continue
#         total = total + credit['outstanding']
#     return total


def allocate_credits(sales_invoice_doc):
    """
    Allocate the matching customer credit (Project / non-Project) to the given Sales Invoice.
    """
    if frappe.get_value("Customer", sales_invoice_doc.customer, "customer_credits") == 'blocked':
        return sales_invoice_doc
    
    if sales_invoice_doc.product_type and sales_invoice_doc.product_type == "Project":
        credit_type = "Project"
    else:
        credit_type = "Standard"

    customer_credits = get_available_credits(sales_invoice_doc.customer, sales_invoice_doc.company, credit_type)
    total_customer_credit = get_total_credit(sales_invoice_doc.customer, sales_invoice_doc.company, credit_type)
    if len(customer_credits) > 0:
        if hasattr(sales_invoice_doc, 'customer_credits') and sales_invoice_doc.customer_credits and len(sales_invoice_doc.customer_credits) > 0:
            for credit_entry in sales_invoice_doc.customer_credits:
                # Substract allocated amount of credit_entry from Additional Discount Amount before deleting already existing credit entries
                sales_invoice_doc.discount_amount -= credit_entry.allocated_amount
                if sales_invoice_doc.discount_amount < 0:
                    frappe.log_error(f"Negative Additional Discount Amount on Sales Invoice '{sales_invoice_doc.name}'", "credits.allocate_credits")
            # Delete already existing customer credit entries on the Sales Invoice
            sales_invoice_doc.customer_credits = []
            sales_invoice_doc.save()
        invoice_amount = sales_invoice_doc.net_total
        allocated_amount = 0
        for credit in reversed(customer_credits):       # customer credits are sorted newest to oldest
            if credit.currency != sales_invoice_doc.currency:
                frappe.throw("The currency of Sales Invoice '{0}' does not match the currency of the credit account. Cannot allocate credits.".format(sales_invoice_doc.name))
            if not 'outstanding' in credit or flt(credit['outstanding']) < 0.01:
                continue
            # if sales_invoice_doc.product_type != "Project" and credit['product_type'] == "Project":
            #     # don't pay non-Project invoice with Project credits
            #     continue
            # if sales_invoice_doc.product_type == "Project" and credit['product_type'] != "Project":
            #     # don't pay Project invoice with non-Project credits
            #     continue
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


def book_credit(sales_invoice, event=None):
    """
    Create Journal Entries for booking the credits of a sales invoice from the credit account to the income account.

    bench execute microsynth.microsynth.credits.book_credit --kwargs "{'sales_invoice': 'SI-BAL-23000538'}"
    """
    if type(sales_invoice) == str:
        sales_invoice = frappe.get_doc("Sales Invoice", sales_invoice)
    if not sales_invoice or not sales_invoice.total_customer_credit or sales_invoice.total_customer_credit <= 0:  # if this invoice has no applied customer credit, skip
        return None
        
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


def cancel_credit_journal_entry(sales_invoice, event=None):
    """
    Cancel the journal entry used for booking credits from the credit account with the book_credit function    

    bench execute microsynth.microsynth.credits.cancel_credit_journal_entry --kwargs "{'sales_invoice': 'SI-BAL-23006789'}"
    """
    if type(sales_invoice) == str:
        sales_invoice = frappe.get_doc("Sales Invoice", sales_invoice)
    
    if flt(sales_invoice.total_customer_credit) <= 0:            # if this invoice has no applied customer credit, skip
        return None
        
    journal_entries = frappe.get_all("Journal Entry",
        filters={'user_remark': "Credit from {0}".format(sales_invoice.name)},
        fields=['name'])

    if len(journal_entries) != 1:
        msg = "Cannot cancel credit Journal Entry for Sales Invoice {0}:\nNone or multiple Journal Entries found".format(sales_invoice.name)
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


@frappe.whitelist()
def create_full_return(sales_invoice):
    from erpnext.accounts.doctype.sales_invoice.sales_invoice import make_sales_return
    from microsynth.microsynth.naming_series import get_naming_series

    credit_note = frappe.get_doc(make_sales_return(sales_invoice)) 
    credit_note.naming_series = get_naming_series("Credit Note", credit_note.company)
    credit_note.remaining_customer_credit = None
    credit_note.insert()
    credit_note.submit()

    frappe.db.commit()

    return credit_note.name


def get_customer_credit_transactions(currency, date, company="Microsynth AG"):
    """
    Debug function to find customer credit transactions per day

    run
    bench execute microsynth.microsynth.credits.get_customer_credit_transactions --kwargs "{'currency': 'EUR', 'date': '2023-06-15'}"
    """
    results = []
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
                AND `tabSales Invoice`.`company` = '{company}'
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
                AND `tabSales Invoice`.`company` = '{company}'
                AND `tabSales Invoice`.`posting_date` = "{date}"
                AND `tabSales Invoice`.`currency` = '{currency}'
        ) AS `raw`
        WHERE `raw`.`net_amount` != 0
        ORDER BY `raw`.`date` DESC, `raw`.`sales_invoice` DESC;""".format(currency=currency, date=date, company=company), as_dict=True):
        results.append("{0}|{1}|{2}|{3}|{4}|{5}|{6}|{7}|{8}|{9}".format(d['type'],
            d['date'],
            d['customer'],
            d['customer_name'],
            d['sales_invoice'],
            d['net_amount'],
            d['product_type'],
            d['status'],
            d['reference'],
            d['currency']))
    return results


def get_total_credit_difference(company, currency, account, to_date):
    """
    Returns the difference between the Outstanding sum from the Customer Credits report and the Closing Balance in the General Ledger.

    bench execute microsynth.microsynth.credits.get_total_credit_difference --kwargs "{'company': 'Microsynth AG', 'currency': 'CHF', 'account': '2010 - Anzahlungen von Kunden CHF - BAL', 'to_date': '2024-09-23'}"
    """
    from microsynth.microsynth.report.customer_credits.customer_credits import get_data as get_customer_credits

    def get_closing(company, account, to_date):
        from erpnext.accounts.report.general_ledger.general_ledger import get_gl_entries, initialize_gle_map, get_accountwise_gle
        gl_filters=frappe._dict({'company': company, 'from_date': to_date, 'to_date': to_date, 'account': account})
        gl_entries = get_gl_entries(gl_filters)
        gle_map = initialize_gle_map(gl_entries, gl_filters)
        totals, _ = get_accountwise_gle(gl_filters, gl_entries, gle_map)
        closing = totals.get('closing')
        return closing.get('debit_in_account_currency') - closing.get('credit_in_account_currency')

    if type(to_date) == str:
        to_date = datetime.strptime(to_date, "%Y-%m-%d").date()
    credit_filters=frappe._dict({'company': company, 'to_date': to_date, 'currency': currency})
    credits = get_customer_credits(credit_filters)
    total_outstanding = 0
    for credit in credits:
        total_outstanding += credit['outstanding']
    gl_closing = get_closing(company, account, to_date)
    diff = gl_closing + total_outstanding
    return diff


def daterange(from_date: date, to_date: date):
    days = int((to_date - from_date).days)
    for n in range(days):
        yield from_date + timedelta(n)


def print_total_credit_differences(company, currency, account, from_date, to_date):
    """
    Calls get_total_credit_difference for each day from the given date till today and prints the results.

    bench execute microsynth.microsynth.credits.print_total_credit_differences --kwargs "{'company': 'Microsynth AG', 'currency': 'EUR', 'account': '2020 - Anzahlungen von Kunden EUR - BAL', 'from_date': '2023-12-31', 'to_date': '2024-09-25'}"
    """
    from_date = datetime.strptime(from_date, "%Y-%m-%d").date()
    to_date = datetime.strptime(to_date, "%Y-%m-%d").date()
    for single_date in daterange(from_date, to_date):
        diff = get_total_credit_difference(company, currency, account, single_date)
        diff_str = f"{diff:,.2f}".replace(",", "'")
        print(f"{single_date.strftime('%d.%m.%Y')}: {diff_str} {currency}")


def get_and_check_diff(company, currency, account, my_date, previous_diff):
    diff = get_total_credit_difference(company, currency, account, my_date)
    if abs(diff - previous_diff) >= 0.01:
        credit_transactions = get_customer_credit_transactions(currency, my_date, company)
        diff_str = f"{diff:,.2f}".replace(",", "'")
        print(f"\n{company}, {currency}, {account}: {my_date.strftime('%d.%m.%Y')}: {diff_str} {currency}")
        if len(credit_transactions) > 0 and my_date != date(2023, 12, 31):
            print(f"Transactions from {my_date.strftime('%d.%m.%Y')}:")
            for transaction in credit_transactions:
                print(transaction)
    return diff


def check_credit_balance(from_date, to_date=today()):
    """
    bench execute microsynth.microsynth.credits.check_credit_balance --kwargs "{'from_date': '2023-12-31', 'to_date': '2024-10-15'}"
    """
    from_date = datetime.strptime(from_date, '%Y-%m-%d').date()
    if type(to_date) == str:
        to_date = datetime.strptime(to_date, '%Y-%m-%d').date()
    # get Credit Item from Microsynth Settings
    credit_item_code = frappe.get_value("Microsynth Settings", "Microsynth Settings", "credit_item")
    credit_item = frappe.get_doc("Item", credit_item_code)
    # iterate over item_defaults
    for default in credit_item.item_defaults:
        previous_diff = 0
        company = default.company
        account = default.income_account
        currency = frappe.get_value("Account", account, "account_currency")
        print(f"\n{company=}; {account=}; {currency=}")
        for single_date in daterange(from_date, to_date):
            diff = get_and_check_diff(company, currency, account, single_date, previous_diff)
            previous_diff = diff
        for currency in ['USD', 'EUR', 'CHF']:
            alternative_account = get_alternative_account(account, currency)
            if alternative_account != account:
                print(f"\n{company=}; {alternative_account=}; {currency=}")
                previous_diff = 0
                for single_date in daterange(from_date, to_date):
                    diff = get_and_check_diff(company, currency, alternative_account, single_date, previous_diff)
                    previous_diff = diff


def report_credit_balance_diff():
    """
    Should be run by a daily cronjob in the evening:
    25 16 * * * cd /home/frappe/frappe-bench && /usr/local/bin/bench --site erp.microsynth.local execute microsynth.microsynth.credits.report_credit_balance_diff

    bench execute microsynth.microsynth.credits.report_credit_balance_diff
    """
    # get Credit Item from Microsynth Settings
    credit_item_code = frappe.get_value("Microsynth Settings", "Microsynth Settings", "credit_item")
    credit_item = frappe.get_doc("Item", credit_item_code)
    diffs = []
    # iterate over item_defaults
    for default in credit_item.item_defaults:
        company = default.company
        account = default.income_account
        currency = frappe.get_value("Account", account, "account_currency")
        diff = get_total_credit_difference(company, currency, account, today())
        if abs(diff) >= 0.01:
            diffs.append(f"{company}: Account {account}: {diff:.2f} {currency}")
        for currency in ['USD', 'EUR', 'CHF']:
            alternative_account = get_alternative_account(account, currency)
            if alternative_account != account:
                diff = get_total_credit_difference(company, currency, alternative_account, today())
                if abs(diff) >= 0.01:
                    diffs.append(f"{company}: Account {alternative_account}: {diff:.2f} {currency}<br>")

    if len(diffs) > 0:
        email_template = frappe.get_doc("Email Template", "Credit Balance Difference")
        details = ""
        for diff in diffs:
            details += diff
        rendered_content = frappe.render_template(email_template.response, {'details': details})
        send_email_from_template(email_template, rendered_content)
