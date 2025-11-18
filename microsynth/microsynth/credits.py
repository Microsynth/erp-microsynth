# Copyright (c) 2021-2025, Microsynth, libracore and contributors
# License: GNU General Public License v3. See license.txt

from datetime import date, datetime, timedelta
import frappe
from frappe import _
from frappe.utils import nowdate
from frappe.utils.data import today
from frappe.utils import flt, cint, get_link_to_form
from erpnext.accounts.doctype.sales_invoice.sales_invoice import (SalesInvoice, make_sales_return)
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
        available_credits = get_available_credits(customer, company['name'], credit_type)
        if len(available_credits) > 0:
            return True
    return False


def get_total_credit(customer, company, credit_type):
    """
    Return the total credit amount available to a customer for the specified company and credit_type. Returns None if there is no credit account.

    Run
    bench execute microsynth.microsynth.credits.get_total_credit --kwargs "{ 'customer': '1194', 'company': 'Microsynth AG', 'credit_type': 'Project' }"
    """
    available_credits = get_available_credits(customer, company, credit_type)

    if len(available_credits) == 0:
        return None

    total = 0
    for credit in available_credits:
        if not 'outstanding' in credit:
            continue
        total = total + credit['outstanding']
    return total


def get_applicable_customer_credits(customer, company, credit_accounts):
    """
    Return the customer credits for the specified credit accounts.
    Run
    bench execute microsynth.microsynth.credits.get_multi_credits --kwargs "{ 'customer': '36660316', 'company': 'Microsynth AG', 'credit_accounts': [ 'CA-000003', 'CA-000002', 'CA-000001' ] }"
    """
    # TODO: set the filter exclude_unpaid_deposits=True
    raw_customer_credits = get_customer_credits({'customer': customer, 'company': company, 'credit_accounts': credit_accounts})

    enforced_credits = []
    standard_credits = []

    for credit in reversed(raw_customer_credits):                   # raw_customer_credits are sorted newest to oldest. We want to allocate oldest credits first.
        if 'outstanding' in credit and flt(credit['outstanding']) > 0:
            if credit['account_type'] == "Enforced Credit":
                enforced_credits.append(credit)
            else:
                standard_credits.append(credit)

    return enforced_credits + standard_credits


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


def get_credit_accounts(sales_order_id):
    """
    Return the credit accounts defined in the Sales Order.

    Run
    bench execute microsynth.microsynth.credits.get_credit_accounts --kwargs "{ 'sales_order_id': 'SO-BAL-25043861' }"
    """
    credit_accounts = frappe.get_all("Credit Account Link",
                                        filters={'parent': sales_order_id, 'parenttype': 'Sales Order'},
                                        fields=['credit_account'],
                                        order_by='idx asc')

    return [ account['credit_account'] for account in credit_accounts ]


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

    # get list of applicable credit accounts (fetch data from Sales Order)
    # TODO: consider the field Sales Invoice.override_credit_accounts
    sales_order_ids = set()
    for item in  sales_invoice_doc.items:
        if item.sales_order:
            sales_order_ids.add(item.sales_order)

    if len(sales_order_ids) == 0:
        return sales_invoice_doc
    if len(sales_order_ids) > 1:
        frappe.throw(f"Cannot allocate credits for Sales Invoice '{sales_invoice_doc.name}': Multiple Sales Orders found:\n{', '.join(list(sales_order_ids))}", "Allocate Credits Error")

    credit_account_ids = get_credit_accounts(sales_order_ids.pop())

    # get applicable customer credits
    customer_credits = get_applicable_customer_credits(sales_invoice_doc.customer, sales_invoice_doc.company, credit_account_ids)
    # total_customer_credit is needed only for the print format --> refactor later
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

        for credit in customer_credits:       # customer_credits is sorted by the get_applicable_customer_credits function
            if credit.currency != sales_invoice_doc.currency:
                frappe.throw("The currency of Sales Invoice '{0}' does not match the currency of the credit account. Cannot allocate credits.".format(sales_invoice_doc.name))

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
        # TODO: change Print Format to show remaining customer credits per applied credit account
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


def book_credit(sales_invoice, credit_item, event=None):
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


def validate_invoice_credit_account(sales_invoice, credit_item, event=None):
    """
    Check that the Sales Invoice has a valid credit_account set.
    """
    for item in sales_invoice.items:
        if item.item_code == credit_item:
            # check that the sales invoice has a valid credit_account set
            if not sales_invoice.credit_account:
                frappe.throw("Please set a valid Credit Account.")
            else:
                credit_account_doc = frappe.get_doc("Credit Account", sales_invoice.credit_account)
                if credit_account_doc.company != sales_invoice.company:
                    frappe.throw(f"Sales Invoice has Company '{sales_invoice.company}', but the selected Credit Account {sales_invoice.credit_account} has Company '{credit_account_doc.company}'.")
                if credit_account_doc.currency != sales_invoice.currency:
                    frappe.throw(f"Sales Invoice has currency '{sales_invoice.currency}', but the selected Credit Account {sales_invoice.credit_account} has currency '{credit_account_doc.currency}'.")
                # if credit_account_doc.customer != sales_invoice.customer:
                #     frappe.throw(f"Sales Invoice has Customer '{sales_invoice.customer}', but the selected Credit Account {sales_invoice.credit_account} has Customer '{credit_account_doc.customer}'.")
            return


def sales_invoice_on_submit(sales_invoice, event=None):
    """
    Wrapper that is called on_submit of a Sales Invoice, see hooks.py
    """
    credit_item = frappe.get_doc("Item",
        frappe.get_value("Microsynth Settings", "Microsynth Settings", "credit_item"))
    #validate_invoice_credit_account(sales_invoice, credit_item, event)  # TODO: Comment in on go-live of Credit Accounts
    book_credit(sales_invoice, credit_item, event)


def reverse_credit(sales_invoice, net_amount):
    """
    Reverse previously booked credit for a sales invoice.

    bench execute microsynth.microsynth.credits.reverse_credit --kwargs "{'sales_invoice': 'SI-BAL-25025600', 'net_amount': 50.0}"
    """
    credit_note_doc = frappe.get_doc(make_sales_return(sales_invoice))

    if len(credit_note_doc.items) != 1:
        frappe.throw(f"Cannot reverse credit for Sales Invoice {sales_invoice}: Return Sales Invoice has multiple items", "credits.reverse_credit")

    if credit_note_doc.items[0].qty != -1:
        frappe.throw(f"Cannot reverse credit for Sales Invoice {sales_invoice}: Return Sales Invoice item has quantity different from -1", "credits.reverse_credit")

    credit_note_doc.items[0].rate = net_amount
    # TODO: check naming series of the credit_note_doc: Currently, it is SI-BAL-...
    # TODO: check entries in customer credit table of the credit_note_doc
    credit_note_doc.invoice_sent_on = None
    credit_note_doc.insert()
    credit_note_doc.submit()

    sales_invoice_outstanding = frappe.get_value("Sales Invoice", sales_invoice, "outstanding_amount")

    if sales_invoice_outstanding == 0:
        return credit_note_doc.name

    if sales_invoice_outstanding > 0:
        frappe.throw(f"Cannot reverse credit for Sales Invoice {sales_invoice}: Outstanding amount greater than zero", "credits.reverse_credit")

    # fetch original journal entry
    jvs = frappe.get_all("Journal Entry",
        filters={
            'docstatus': 1,
            'reference_type': "Sales Invoice",
            'reference_name': sales_invoice},
        fields=['name'])

    if len(jvs) != 1:
        frappe.throw(f"Cannot reverse credit for Sales Invoice {sales_invoice}: {len(jvs)} Journal Entries found", "credits.reverse_credit")

    original_jv = frappe.get_doc("Journal Entry", jvs[0].name)

    for entry in original_jv.accounts:
        if entry.debit > 0:
            expense_account = entry.account
            break

    jv = frappe.get_doc({
        'doctype': 'Journal Entry',
        'posting_date': credit_note_doc.posting_date,
        'company': credit_note_doc.company,
        'accounts': [
            # Take from the debtor account e.g. '1102 - Debitoren EUR - BAL'
            {
                'account': credit_note_doc.debit_to,
                'debit_in_account_currency': sales_invoice_outstanding * -1,
                'exchange_rate': credit_note_doc.conversion_rate,
                'cost_center': credit_note_doc.items[0].cost_center,
                'party_type': "Customer",
                'party': credit_note_doc.customer,
                'reference_type': "Sales Invoice",
                'reference_name': sales_invoice
            },
            # put into expense account e.g. '6600 - Werbung Allgemein - BAL'
            {
                'account': expense_account,
                'credit_in_account_currency': sales_invoice_outstanding * credit_note_doc.conversion_rate * -1,
                'exchange_rate': 1 ,
                'cost_center': credit_note_doc.items[0].cost_center
            }
        ],
        'user_remark': f"Reverse Credit for {sales_invoice}",
        'multi_currency': 1
    })
    jv.insert()
    jv.submit()

    return credit_note_doc.name


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
def get_linked_customer_credit_bookings(sales_invoice):
    """
    Return linked customer credit booking records

    bench execute microsynth.microsynth.credits.get_linked_customer_credit_bookings --kwargs "{'sales_invoice': 'SI-BAL-23006789'}"
    """
    if type(sales_invoice) == SalesInvoice:
        sales_invoice = sales_invoice.name

    journal_entries = frappe.get_all("Journal Entry",
        filters={
            'user_remark': "Credit from {0}".format(sales_invoice),
            'docstatus': 1
        },
        fields=['name'])

    if len(journal_entries) > 0:
        links = []
        for jv in journal_entries:
            links.append(get_link_to_form("Journal Entry", jv['name']))

        html = frappe.render_template('microsynth/templates/includes/credit_booking_links.html', {'links': ", ".join(links)})

        return {'journal_entries': journal_entries, 'links': links, 'html': html}
    else:
        return None

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
    credit_item_code = frappe.get_value("Microsynth Settings", "Microsynth Settings", "credit_item")
    if not credit_item_code:
        frappe.throw("Please define a credit item in the Microsynth Settings.")
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
                AND `tabSales Invoice Item`.`item_code` = "{credit_item_code}"
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
        ORDER BY `raw`.`date` DESC, `raw`.`sales_invoice` DESC;""".format(credit_item_code=credit_item_code, currency=currency, date=date, company=company), as_dict=True):
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

    if isinstance(to_date, str):
        to_date = datetime.strptime(to_date, "%Y-%m-%d").date()
    credit_filters=frappe._dict({'company': company, 'to_date': to_date, 'currency': currency})
    customer_credits = get_customer_credits(credit_filters)
    total_outstanding = 0
    for credit in customer_credits:
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


@frappe.whitelist()
def get_available_credit_accounts(company, currency, customer, product_types=None):
    """
    Returns active, non-expired Credit Accounts for the given company, currency, and customer.
    If product_types is provided, it filters by them.
    If a Credit Account has no Product Types, it is returned even when product_types is given.

    bench execute microsynth.microsynth.credits.get_available_credit_accounts --kwargs "{'company': 'Microsynth Austria GmbH', 'currency': 'EUR', 'customer': '840931', 'product_types': ['Oligos', 'Project']}"
    """
    today = nowdate()
    product_types = product_types or []

    conditions = [
        "`tabCredit Account`.`company` = %(company)s",
        "`tabCredit Account`.`currency` = %(currency)s",
        "`tabCredit Account`.`customer` = %(customer)s",
        "`tabCredit Account`.`status` = 'Active'",
        "(`tabCredit Account`.`expiry_date` IS NULL OR `tabCredit Account`.`expiry_date` = '' OR `tabCredit Account`.`expiry_date` >= %(today)s)"
    ]
    # Apply special filter only if product_types provided
    if product_types:
        # Match product types OR include accounts with no product types at all
        conditions.append(
            "(`tabProduct Type Link`.`product_type` IN %(product_types)s "
            "OR `tabProduct Type Link`.`product_type` IS NULL)"
        )
    where_clause = " AND ".join(conditions)

    query = f"""
        SELECT
            `tabCredit Account`.`name`,
            `tabCredit Account`.`account_name`,
            `tabCredit Account`.`account_type`,
            `tabCredit Account`.`company`,
            `tabCredit Account`.`currency`,
            `tabCredit Account`.`customer`,
            `tabCredit Account`.`expiry_date`,
            GROUP_CONCAT(`tabProduct Type Link`.`product_type`
                         ORDER BY `tabProduct Type Link`.`product_type`
                         SEPARATOR ', ') AS `product_types`
        FROM `tabCredit Account`
        LEFT JOIN `tabProduct Type Link`
            ON `tabProduct Type Link`.`parent` = `tabCredit Account`.`name`
            AND `tabProduct Type Link`.`parenttype` = 'Credit Account'
            AND `tabProduct Type Link`.`parentfield` = 'product_types'
        WHERE {where_clause}
        GROUP BY
            `tabCredit Account`.`name`,
            `tabCredit Account`.`account_name`,
            `tabCredit Account`.`account_type`,
            `tabCredit Account`.`expiry_date`
        ORDER BY
            `tabCredit Account`.`account_type`,
            `tabCredit Account`.`expiry_date`,
            `tabCredit Account`.`creation`
    """
    return frappe.db.sql(
        query,
        {
            "company": company,
            "currency": currency,
            "customer": customer,
            "today": today,
            "product_types": tuple(product_types) if product_types else None,
        },
        as_dict=True,
    )


@frappe.whitelist()
def change_si_credit_accounts(sales_invoice, new_credit_accounts):
    """
    Creates a Credit Note for the given Sales Invoice and a new Sales Invoice with updated Credit Accounts.

    Steps:
    1. Validate and load target accounts.
    2. Create and submit Credit Note (full refund).
    3. Duplicate Sales Invoice.
    4. Adjust customer if different.
    5. Update override_credit_accounts.
    6. Call credit allocation logic.
    7. Return new Sales Invoice name.
    """
    if isinstance(new_credit_accounts, str):
        import json
        new_credit_accounts = json.loads(new_credit_accounts)

    si_doc = frappe.get_doc("Sales Invoice", sales_invoice)
    if si_doc.docstatus != 1 or si_doc.is_return:
        frappe.throw(_("You can only change Credit Accounts for submitted, non-return Sales Invoices."))

    # Load Credit Account docs and check consistency
    credit_accounts = [frappe.get_doc("Credit Account", acc) for acc in new_credit_accounts]
    if not credit_accounts:
        frappe.throw(_("No Credit Accounts selected."))

    # Validate all accounts
    for acc in credit_accounts:
        if acc.status != "Active":
            frappe.throw(_("Credit Account {0} is not active.").format(acc.name))
        if acc.company != si_doc.company or acc.currency != si_doc.currency:
            frappe.throw(_("Credit Account {0} does not match Company or Currency.").format(acc.name))
        if acc.expiry_date and acc.expiry_date < nowdate():
            frappe.throw(_("Credit Account {0} is expired.").format(acc.name))

    # Ensure all selected accounts share same customer
    customers = {acc.customer for acc in credit_accounts if acc.customer}
    new_customer = customers.pop() if customers else None
    if len(customers) > 0:
        frappe.throw(_("Selected Credit Accounts must all belong to the same Customer."))

    # Create and submit Credit Note
    credit_note_doc = frappe.get_doc(make_sales_return(sales_invoice))
    credit_note_doc.flags.ignore_permissions = True
    credit_note_doc.insert()
    credit_note_doc.submit()

    # Create new Sales Invoice by copying
    new_si = frappe.copy_doc(si_doc)
    new_si.is_return = 0
    new_si.return_against = None
    new_si.docstatus = 0
    new_si.name = None

    # Adjust customer if different
    if new_customer and new_customer != si_doc.customer:
        new_si.customer = new_customer
        new_si.customer_name = frappe.db.get_value("Customer", new_customer, "customer_name")
        # Remove linkages that reference previous customer
        for item in new_si.items:
            item.sales_order = None
            item.delivery_note = None
            item.project = None

    # Reset override_credit_accounts
    new_si.set("override_credit_accounts", [])
    for acc in credit_accounts:
        new_si.append("override_credit_accounts", {"credit_account": acc.name})

    # Save and run credit allocation logic
    new_si.insert()
    frappe.get_doc("Sales Invoice", new_si.name)
    frappe.get_attr("microsynth.microsynth.credits.allocate_credits_to_invoice")(new_si.name)

    frappe.db.commit()
    return new_si.name
