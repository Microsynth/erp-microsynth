# -*- coding: utf-8 -*-
# Copyright (c) 2022, libracore (https://www.libracore.com) and contributors
# For license information, please see license.txt
#
# For more details, refer to https://github.com/Microsynth/erp-microsynth/
#

import os
import traceback
import frappe
from frappe import _
from frappe.utils.background_jobs import enqueue
from microsynth.microsynth.report.invoiceable_services.invoiceable_services import get_data
from frappe.utils import cint
from erpnext.stock.doctype.delivery_note.delivery_note import make_sales_invoice
from erpnextswiss.erpnextswiss.attach_pdf import create_folder, execute
from frappe.utils.file_manager import save_file
from frappe.core.doctype.communication.email import make
from frappe.desk.form.load import get_attachments
from microsynth.microsynth.naming_series import get_naming_series
from microsynth.microsynth.utils import get_physical_path, get_billing_address, get_alternative_account, get_alternative_income_account, get_name, get_name_line, get_posting_datetime, replace_none
from microsynth.microsynth.credits import allocate_credits, book_credit, get_total_credit, get_total_credit_without_project
from microsynth.microsynth.jinja import get_destination_classification
import datetime
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import json
import random
from erpnextswiss.erpnextswiss.finance import get_exchange_rate

@frappe.whitelist()
def create_invoices(mode, company, customer):
    kwargs={
        'mode': mode,
        'company': company,
        'customer': customer
    }
    
    enqueue("microsynth.microsynth.invoicing.async_create_invoices",
        queue='long',
        timeout=15000,
        **kwargs)
    return {'result': _('Invoice creation started...')}


def get_tax_templates(delivery_notes):
    taxes = []
    for dn in delivery_notes:
        t = frappe.db.get_value("Delivery Note", dn, "taxes_and_charges")
        if t not in taxes:
            taxes.append(t)
    return taxes


def get_product_types(delivery_notes):
    product_types = set()
    for dn in delivery_notes:
        product_type = frappe.db.get_value('Delivery Note', dn, 'product_type')
        if product_type == 'Project':
            product_types.add(product_type)
        else:
            product_types.add('')
    return product_types


def make_collective_invoices(delivery_notes):
    """
    Make collective invoices from the given Delivery Notes. All documents must 
    be for a single customer and from the same company. 
    Considers customer credits if available.

    bench execute microsynth.microsynth.invoicing.make_collective_invoices --kwargs "{'delivery_notes': ['DN-BAL-23034973', 'DN-BAL-23114748'] }"
    """
    invoices = []

    if len(delivery_notes) > 0:

        customers = []
        companies = []
        for d in delivery_notes:
            cust = frappe.db.get_value("Delivery Note", d, "customer")
            if cust not in customers:
                customers.append(cust)
            comp = frappe.db.get_value("Delivery Note", d, "company")
            if comp not in companies:
                companies.append(comp)

        # validation: 
        if len(set(customers)) != 1:
            frappe.log_error("The provided Delivery Notes do not have a single customer.\nDelivery Notes: {0}\nCustomers: {1}".format(delivery_notes, customers), "invocing.make_collective_invoices")
            return invoices
        if len(set(companies)) != 1:
            frappe.log_error("The provided Delivery Notes are not from a single company.\nDelivery Notes: {0}\nCompanies: {1}".format(delivery_notes, companies), "invocing.make_collective_invoices")
            return invoices

        customer = customers[0]
        company = companies[0]

        # check if there are multiple tax templates
        taxes = get_tax_templates(delivery_notes)
        product_types = get_product_types(delivery_notes)

        # create one invoice per tax template
        for tax in taxes:
            for product_type in product_types:
                filtered_dns = []
                for d in delivery_notes:
                    taxes_and_charges = frappe.db.get_value("Delivery Note", d, "taxes_and_charges")
                    d_product_type = frappe.db.get_value("Delivery Note", d, "product_type")
                    prod_type_fit = d_product_type == product_type or (d_product_type != 'Project' and product_type == '')
                    if taxes_and_charges == tax and prod_type_fit:
                        total = frappe.get_value("Delivery Note", d, "total")
                        if product_type == 'Project':
                            credit = get_total_credit(customer, company, product_type)
                        else:
                            credit = get_total_credit_without_project(customer, company)
                        customer_credits = frappe.get_value("Customer", customer, "customer_credits")
                        if credit is not None and customer_credits == 'Credit Account':
                            # there is some credit - check if it is sufficient
                            if total <= credit:
                                filtered_dns.append(d)
                                credit = credit - total
                            else:
                                frappe.log_error("Delivery Note '{0}': \nInsufficient credit for customer {1}".format(d, customer), "invocing.async_create_invoices")
                        else:
                            # there is no credit account
                            filtered_dns.append(d)

                if len(filtered_dns) > 0:
                    si = make_collective_invoice(filtered_dns)
                    invoices.append(si)

    return invoices


def make_carlo_erba_invoices(company):
    """
    run
    bench execute microsynth.microsynth.invoicing.make_carlo_erba_invoices --kwargs "{'company': 'Microsynth Seqlab GmbH'}"
    """
    all_invoiceable = get_data(filters={'company': company, 'customer': None})
    invoices = []
    for dn in all_invoiceable:
        if (dn.get('invoicing_method').upper() == "CARLO ERBA" 
            and cint(dn.get('collective_billing')) == 0):  # Do not allow collective billing for Carlo Erba because the distributor must pass the invoices to the order customer individually

            si = make_invoice(dn.get('delivery_note'))
            invoices.append(si)
        else:
            continue

    return invoices


def async_create_invoices(mode, company, customer):
    """
    run 
    bench execute microsynth.microsynth.invoicing.async_create_invoices --kwargs "{ 'mode':'Electronic', 'company': 'Microsynth AG', 'customer': '1234' }"
    """
    import traceback
    # # Not implemented exceptions to catch cases that are not yet developed
    # if company != "Microsynth AG":
    #     frappe.throw("Not implemented: async_create_invoices for company '{0}'".format(company))
    #     return
    if mode not in ["Post", "Electronic", "Collective", "CarloErba"]:
        frappe.throw("Not implemented: async_create_invoices for mode '{0}'".format(mode))
        return

    # Standard processing
    if (mode in ["Post", "Electronic"]):
        # individual invoices
        all_invoiceable = get_data(filters={'company': company, 'customer': customer})
        count = 0
        insufficient_credit_warnings = {}

        for dn in all_invoiceable:
            try:
                # # TODO: implement for other export categories
                # if dn.region != "CH":
                #     continue

                # TODO: implement for other product types. Requires setting the income accounts.
                # if dn.product_type not in ["Oligos", "Labels", "Sequencing"]:
                #     continue

                if cint(dn.get('is_punchout') == 1) and mode != "Electronic":
                    # All punchout invoices must be send electronically
                    frappe.log_error("Cannot invoice {0}: \nPunchout invoices must be send electronically".format(dn.get('delivery_note')), "invoicing.async_create_invoices")
                    continue

                # process punchout orders separately
                if cint(dn.get('is_punchout') == 1):
                    punchout_shop = frappe.get_value("Delivery Note", dn.get('delivery_note'), "punchout_shop")
                    if punchout_shop == "IMP-WIE":
                        # Do not create single invoices because a collective invoice should be sent
                        continue
                    # if (punchout_shop == "EPFL" or punchout_shop == "UNI-ZUR") and dn.get('product_type') == "Sequencing":
                    #     # Do not create punchout invoices of Sequencing orders because of positions with 0.00 cost that cause errors at EPFL
                    #     # TODO: Fix issue with EPFL and UNI-ZUR and remove this condition
                    #     continue
                    if (punchout_shop in [ "EAWAG", "EPFL", "ETHZ", "NOV-BAS", "ROC-BASGEP", "UNI-BAS", "UNI-GOE", "UNI-MAR", "UNI-GIE", "UNI-ZUR"] or
                        (punchout_shop == "ROC-PENGEP" and company == "Microsynth AG" ) or      # invoices transmitted by email. unclear if invoices get paid.
                        (punchout_shop == "ROC-PENGEP" and company == "Microsynth Seqlab GmbH") ):
                        si = make_punchout_invoice(dn.get('delivery_note'))
                        transmit_sales_invoice(si)
                        continue
                    else:
                        # TODO implement punchout orders
                        frappe.log_error("Cannot invoice {0}: \nThe punchout shop '{1}' is not implemented for invoicing".format(dn.get('delivery_note'), punchout_shop), "invoicing.async_create_invoices")
                        continue

                # check credit
                if dn.get('product_type') == 'Project':
                    credit = get_total_credit(dn.get('customer'), company, dn.get('product_type'))
                else:
                    credit = get_total_credit_without_project(dn.get('customer'), company)
                customer_credits = frappe.get_value("Customer", dn.get('customer'),"customer_credits")
                if credit is not None and customer_credits == 'Credit Account':
                    delivery_note =  dn.get('delivery_note')
                    total = frappe.get_value("Delivery Note", delivery_note, "total")
                    if total > credit:
                        dn_customer = dn.get('customer')                
                        if not dn_customer in insufficient_credit_warnings:
                            insufficient_credit_warnings[dn_customer] = {}
                        insufficient_credit_warnings[dn_customer][delivery_note] = {'total': total,
                                                                                 'currency': dn.get('currency'),
                                                                                 'credit': round(credit, 2),
                                                                                 'customer_name': dn.get('customer_name')}
                        continue

                # only process DN that are invoiced individually, not collective billing
                if cint(dn.get('collective_billing')) == 0:
                    if mode == "Post":
                        if dn.get('invoicing_method') == "Post":
                            si = make_invoice(dn.get('delivery_note'))
                            transmit_sales_invoice(si)

                            count += 1
                            # if count >= 20 and company != "Microsynth AG":
                            #     break

                    else:
                        # TODO process other invoicing methods

                        if dn.get('invoicing_method').upper() == "CARLO ERBA":
                            # do not process Carlo Erba invoices with electronic and Post invoices
                            continue

                        if dn.get('invoicing_method') not in ["Email", "Paynet"]:
                            continue

                        # TODO there seems to be an issue here: both branches ("Post"/ not "Post") do the same
                        if dn.get('invoicing_method') != "Post":
                            si = make_invoice(dn.get('delivery_note'))
                            transmit_sales_invoice(si)
                            count += 1
                            # if count >= 20 and company != "Microsynth AG":
                            #     break
            except Exception as err:
                message = f"Cannot invoice {dn.get('delivery_note')}: \n{err}\n{traceback.format_exc()}"
                frappe.log_error(message, "invoicing.async_create_invoices")
                #print(message)

        for dn_customer, warnings in insufficient_credit_warnings.items():  # should contain always one customer
            if len(warnings) < 1:
                continue
            subject = f"Insufficient credit: Customer {dn_customer} at {company}"
            dn_details = ""

            for delivery_note, values in warnings.items():
                currency = values['currency']
                dn_details += f"{delivery_note}: {values['total']} {currency}<br>"
                customer_name = values['customer_name']
                credit = values['credit']

            message = f"Dear Administration,<br><br>this is an automatic email to inform you that Customer '{dn_customer}' ({customer_name}) "
            message += f"has a credit balance of {credit} {currency} at {company} and therefore not enough to invoice the following Delivery Note(s):<br><br>"
            message += dn_details
            message += f"<br>Please request the Customer to recharge the credit account or close it.<br><br>Best regards,<br>Jens"
            non_html_message = message.replace("<br>","\n")
            frappe.log_error(non_html_message, subject)
            #print(non_html_message)
            make(
                recipients = "info@microsynth.ch",
                sender = "jens.petermann@microsynth.ch",
                #cc = "rolf.suter@microsynth.ch",
                subject = "[ERP] " + subject,
                content = message,
                send_email = True
            )

    elif mode == "CarloErba":
        invoices = make_carlo_erba_invoices(company = company)
        transmit_carlo_erba_invoices(invoices)

    elif mode == "Collective":
        # colletive invoices

        all_invoiceable = get_data(filters={'company': company, 'customer': customer})

        customers = []
        for dn in all_invoiceable:

            # TODO process other invoicing methods
            if dn.get('invoicing_method') not in  ["Email", "Post"]:
                frappe.log_error("Cannot invoice {0}: \nThe invoicing method '{1}' is not implemented for collective billing".format(dn.get('delivery_note'), dn.get('invoicing_method')), "invoicing.async_create_invoices")
                continue

            if (cint(dn.get('collective_billing')) == 1 and 
                (cint(dn.get('is_punchout')) != 1 or dn.get('customer') in ['57022', '57023'] ) and  # allow collective billing for IMP / IMBA despite punchout
                dn.get('customer') not in customers):
                customers.append(dn.get('customer'))

        # for each customer, create one invoice per tax template for all dns
        for c in customers:
            try:
                dns = []
                for dn in all_invoiceable:
                    if (cint(dn.get('collective_billing')) == 1 and 
                        (cint(dn.get('is_punchout')) != 1 or c in ['57022', '57023'] ) and  # allow collective billing for IMP / IMBA despite punchout
                        dn.get('customer') == c):
                        dns.append(dn.get('delivery_note'))

                invoices = make_collective_invoices(dns)
                for invoice in invoices:
                    transmit_sales_invoice(invoice)

            except Exception as err:
                frappe.log_error("Cannot create collective invoice for customer {0}: \n{1}".format(c, err), "invoicing.async_create_invoices")
    else:
        frappe.throw("Unknown mode '{0}' for async_create_invoices".format(mode))

    return


def set_income_accounts(sales_invoice):
    """
    Sets the income account for each item of a sales invoice based on the original income account entry and the country. 
    For the credit item, the alternative account is defined by the currency. Requires a sales invoice object as input.
    """
    if sales_invoice.shipping_address_name:
        address = sales_invoice.shipping_address_name
    else:
        address = sales_invoice.customer_address
    country = frappe.db.get_value("Address", address, "country")

    for item in sales_invoice.items:
        if item.item_code == "6100":
            # credit item
            item.income_account = get_alternative_account(item.income_account, sales_invoice.currency)
        else:
            # all other items
            item.income_account = get_alternative_income_account(item.income_account, country)
    sales_invoice.save()


@frappe.whitelist()
def get_income_accounts(address, currency, sales_invoice_items):

    if type(sales_invoice_items) == str:
        sales_invoice_items = json.loads(sales_invoice_items)
    country = frappe.db.get_value("Address", address, "country")
    income_accounts = []
    for item in sales_invoice_items:
        if item.get("item_code") == "6100":
            # credit item
            income_accounts.append(get_alternative_account(item.get("income_account"), currency))
        else:
            # all other items
            income_accounts.append(get_alternative_income_account(item.get("income_account"), country))
    return income_accounts


def make_invoice(delivery_note):
    """
    Includes customer credits. Do not use for customer projects.

    run
    bench execute microsynth.microsynth.invoicing.make_invoice --kwargs "{'delivery_note':'DN-BAL-23106510'}"
    """
    sales_invoice_content = make_sales_invoice(delivery_note)
    # compile document
    sales_invoice = frappe.get_doc(sales_invoice_content)
    company = frappe.get_value("Delivery Note", delivery_note, "company")
    sales_invoice.naming_series = get_naming_series("Sales Invoice", company)
    if not sales_invoice.invoice_to:
        sales_invoice.invoice_to = frappe.get_value("Customer", sales_invoice.customer, "invoice_to") # replace contact with customer's invoice_to contact
    #sales_invoice.set_advances()    # get advances (customer credit)
    sales_invoice = allocate_credits(sales_invoice)         # check and allocated open customer credits
    
    # force-set tax_id (intrastat!)
    if not sales_invoice.tax_id:
        sales_invoice.tax_id = frappe.get_value("Customer", sales_invoice.customer, "tax_id")
    
    sales_invoice.insert()
    # get time-true conversion rate (not from predecessor)
    sales_invoice.conversion_rate = get_exchange_rate(from_currency=sales_invoice.currency, company=sales_invoice.company, date=sales_invoice.posting_date)
    # set income accounts
    set_income_accounts(sales_invoice)
    # for payment reminders: set 10 days goodwill period
    sales_invoice.exclude_from_payment_reminder_until = datetime.strptime(sales_invoice.due_date, "%Y-%m-%d") + timedelta(days=10)
    sales_invoice.submit()
    # if a credit was allocated, book credit account
    if cint(sales_invoice.total_customer_credit) > 0:
        book_credit(sales_invoice.name)
        
    frappe.db.commit()

    return sales_invoice.name


def make_invoices(delivery_notes):
    """
    Includes customer credits. Do not use for customer projects.
    Create an invoice for a delivery note. Returns the sales invoice IDs

    run
    bench execute microsynth.microsynth.invoicing.make_invoices --kwargs "{'delivery_notes': ['DN-BAL-23106510'] }"
    """
    sales_invoices = []
    for dn in delivery_notes:
        si = make_invoice(dn)
        sales_invoices.append(si)
    return sales_invoices


def make_punchout_invoice(delivery_note):
    """
    Create an invoice for a delivery note of a punchout order. Returns the sales invoice ID.

    run 
    bench execute microsynth.microsynth.invoicing.make_punchout_invoice --kwargs "{'delivery_note':'DN-BAL-23112515'}"
    """

    delivery_note = frappe.get_doc("Delivery Note", delivery_note)

    # get Sales Order to fetch punchout data not saved to the delivery note
    # TODO: remove fetching sales order once all delivery notes have the punchout shop
    sales_orders = []
    for x in delivery_note.items:
        if x.against_sales_order is not None and x.against_sales_order not in sales_orders:
            sales_orders.append(x.against_sales_order)
    
    if len(sales_orders) == 1:
        sales_order = frappe.get_doc("Sales Order", sales_orders[0])
    else:
        frappe.log_error("The delivery note '{0}' originates from none or multiple sales orders".format(delivery_note.name), "invoicing.make_punchout_invoice")
        return None
    
    # set the punchout shop
    if delivery_note.punchout_shop is not None:
        punchout_shop = frappe.get_doc("Punchout Shop", delivery_note.punchout_shop)
    elif sales_order.punchout_shop is not None:
        punchout_shop = frappe.get_doc("Punchout Shop", sales_order.punchout_shop)
    else:
        frappe.log_error("Cannot invoice delivery note '{0}': Punchout Shop is not defined".format(delivery_note.name), "invoicing.make_punchout_invoice")
        return None

    sales_invoice_content = make_sales_invoice(delivery_note.name)

    # compile document
    sales_invoice = frappe.get_doc(sales_invoice_content)
    company = frappe.get_value("Delivery Note", delivery_note.name, "company")
    sales_invoice.naming_series = get_naming_series("Sales Invoice", company)
    
    if punchout_shop.has_static_billing_address and punchout_shop.billing_contact: 
        sales_invoice.invoice_to = punchout_shop.billing_contact

    if punchout_shop.has_static_billing_address and punchout_shop.billing_address:
        sales_invoice.customer_address = punchout_shop.billing_address

    # force-set tax_id (intrastat!)
    if not sales_invoice.tax_id:
        sales_invoice.tax_id = frappe.get_value("Customer", sales_invoice.customer, "tax_id")

    sales_invoice.insert()
    # get time-true conversion rate (not from predecessor)
    sales_invoice.conversion_rate = get_exchange_rate(from_currency=sales_invoice.currency, company=sales_invoice.company, date=sales_invoice.posting_date)
    # set income accounts
    set_income_accounts(sales_invoice)
    # for payment reminders: set 10 days goodwill period
    sales_invoice.exclude_from_payment_reminder_until = datetime.strptime(sales_invoice.due_date, "%Y-%m-%d") + timedelta(days=10)

    sales_invoice.submit()
    frappe.db.commit()

    return sales_invoice.name


def make_punchout_invoices(delivery_notes):
    """
    Create an invoice for each delivery note of a punchout order. Returns the sales invoice IDs.

    run
    bench execute microsynth.microsynth.invoicing.make_punchout_invoices --kwargs "{'delivery_notes': [ 'DN-BAL-23132369', 'DN-BAL-23129612' ] }"
    """
    sales_invoices = []
    for dn in delivery_notes:
        si = make_punchout_invoice(dn)
        sales_invoices.append(si)
    return sales_invoices


def make_collective_invoice(delivery_notes):
    """
    
    run
    bench execute microsynth.microsynth.invoicing.make_collective_invoice --kwargs "{'delivery_notes': ['DN-BAL-23106590', 'DN-BAL-23113391', 'DN-BAL-23114506', 'DN-BAL-23115682']}"
    """

    # create invoice from first delivery note
    sales_invoice_content = make_sales_invoice(delivery_notes[0])
    if len(delivery_notes) > 1:
        for i in range(1, len(delivery_notes)):
            # append items from other delivery notes
            sales_invoice_content = make_sales_invoice(source_name=delivery_notes[i], target_doc=sales_invoice_content)
    
    # compile document
    sales_invoice = frappe.get_doc(sales_invoice_content)
    if not sales_invoice.invoice_to:
        sales_invoice.invoice_to = frappe.get_value("Customer", sales_invoice.customer, "invoice_to") # replace contact with customer's invoice_to contact

    company = frappe.get_value("Delivery Note", delivery_notes[0], "company")
    sales_invoice.naming_series = get_naming_series("Sales Invoice", company)
        
    # sales_invoice.set_advances()    # get advances (customer credit)
    sales_invoice = allocate_credits(sales_invoice)         # check and allocated open customer credits

    # force-set tax_id (intrastat!)
    if not sales_invoice.tax_id:
        sales_invoice.tax_id = frappe.get_value("Customer", sales_invoice.customer, "tax_id")

    sales_invoice.insert()
    # get time-true conversion rate (not from predecessor)
    sales_invoice.conversion_rate = get_exchange_rate(from_currency=sales_invoice.currency, company=sales_invoice.company, date=sales_invoice.posting_date)
    # set income accounts
    set_income_accounts(sales_invoice)
    # for payment reminders: set 10 days goodwill period
    sales_invoice.exclude_from_payment_reminder_until = datetime.strptime(sales_invoice.due_date, "%Y-%m-%d") + timedelta(days=10)

    sales_invoice.submit()

    # if a credit was allocated, book credit account
    if cint(sales_invoice.total_customer_credit) > 0:
        book_credit(sales_invoice.name)

    frappe.db.commit()

    return sales_invoice.name


def make_monthly_collective_invoice(company, customer, month):
    """
    Make monthly collective invoices. Considers customer credits if available.

    run
    bench execute microsynth.microsynth.invoicing.make_monthly_collective_invoice --kwargs "{'company': 'Microsynth AG', 'customer': 35581487, 'month': 4}"
    """

    all_invoiceable = get_data(filters={'company': company, 'customer': customer})
    
    dns = []
    for dn in all_invoiceable:
        if (dn.get('date').month == month
            and cint(dn.get('collective_billing')) == 1 
            and cint(dn.get('is_punchout')) != 1 
            and dn.get('customer') == str(customer) ):
                dns.append(dn.get('delivery_note'))

    invoices = make_collective_invoices(dns)

    return invoices


def make_monthly_collective_invoices(company, customers, months):
    """
    run
    bench execute microsynth.microsynth.invoicing.make_monthly_collective_invoices --kwargs "{ 'company': 'Microsynth AG', 'customers':['35581487', '35581488', '35581490'], 'months': [ 1, 2, 3 ] }"
    """

    sales_invoices = []
    for customer in customers:
        for month in months:
            invoices = make_monthly_collective_invoice(company, customer, month)
            sales_invoices.append(invoices)
    return sales_invoices


def create_pdf_attachment(sales_invoice): 
    """
    Creates the PDF file for a given Sales Invoice name and attaches the file to the record in the ERP.

    run
    bench execute microsynth.microsynth.invoicing.create_pdf_attachment --kwargs "{'sales_invoice': 'SI-BAL-23002642-1'}"
    """

    doctype = "Sales Invoice"
    format = "Sales Invoice"
    name = sales_invoice
    doc = None
    no_letterhead = False
    
    frappe.local.lang = frappe.db.get_value("Sales Invoice", sales_invoice, "language")

    from erpnextswiss.erpnextswiss.attach_pdf import save_and_attach, create_folder

    title = frappe.db.get_value(doctype, name, "title")

    doctype_folder = create_folder(doctype, "Home")
    title_folder = create_folder(title, doctype_folder)

    filecontent = frappe.get_print(doctype, name, format, doc=doc, as_pdf = True, no_letterhead=no_letterhead)

    save_and_attach(
        content = filecontent, 
        to_doctype = doctype, 
        to_name = name,  
        folder = title_folder,
        hashname = None,
        is_private = True )

    return


def get_sales_order_list_and_delivery_note_list(sales_invoice): 
    """creates a dict with two keys sales_orders/delivery_notes with value of a list of respective ids"""

    sales_order_list = []
    delivery_note_list = []

    for item in sales_invoice.items:
        if item.sales_order and item.sales_order not in sales_order_list: 
            sales_order_list.append(item.sales_order)
        if item.delivery_note and item.delivery_note not in delivery_note_list: 
            delivery_note_list.append(item.delivery_note)

    return {"sales_orders": sales_order_list, "delivery_notes": delivery_note_list}


def get_sales_order_id_and_delivery_note_id(sales_invoice): 
    """returns one sales_order_id and one or no delivery_note_id"""

    sos_and_dns = get_sales_order_list_and_delivery_note_list(sales_invoice)
    sales_orders = sos_and_dns["sales_orders"]
    delivery_notes = sos_and_dns["delivery_notes"]
    if len(sales_orders) < 1: 
        frappe.throw("no sales orders. case not known")
    elif len(sales_orders) > 1:
        frappe.throw("too many sales orders. case not implemented.")
    sales_order_id = sales_orders[0]

    delivery_note_id = ""
    if len(delivery_notes) < 1: 
        # may happen, accept this case!
        #frappe.throw("no delivery note")
        pass
    elif len(delivery_notes) > 1:
        frappe.throw("too many delivery notes. case not implemented.")
    else: 
        delivery_note_id = delivery_notes[0]

    return {"sales_order_id":sales_order_id, "delivery_note_id": delivery_note_id}


def get_address_dict(customer, contact, address, country_codes):
    postal_address = {}
    deliver_to = []
    
    if contact:
        name = get_name(contact)

        if name != "":
            deliver_to.append(get_name(contact))

        if contact.department:
            deliver_to.append(contact.department)

        if contact.institute:
            deliver_to.append(contact.institute)

        if contact.room:
            deliver_to.append(contact.room)

    postal_address["id"] = replace_none(address.customer_address_id)
    postal_address["name"] = address.overwrite_company or customer
    postal_address["company_division"] = contact.institute if contact else None
    postal_address["first_name"] = contact.first_name if contact and contact.first_name != "-" else None
    postal_address["last_name"] = contact.last_name if contact else None
    postal_address["deliver_to"] = deliver_to
    postal_address["street1"] = address.address_line1
    postal_address["street2"] = address.address_line2
    postal_address["pin"] = address.pincode
    postal_address["city"] = address.city
    postal_address["country_code"] = country_codes[address.country].upper()
    
    return postal_address


def create_position_list(sales_invoice, exclude_shipping):
    """
    Create a list of the invoice positions of a sales_invoice as a list of dictionaries.
    """
    item_details = {}
    
    for item in sales_invoice.items:
        item_details[item.item_code] = item

    positions = []
    number = 0
    used_items = {}

    tax_rate = sales_invoice.taxes[0].rate if len(sales_invoice.taxes)>0 else 0

    for o in sales_invoice.oligos:
        position = {}
        number += 1
        rate_total = 0
        oligo = frappe.get_doc("Oligo", o.oligo)

        for n in oligo.items:
            if n.item_code in item_details:
                rate_total += n.qty * item_details[n.item_code].rate

            if n.item_code not in used_items:
                used_items[n.item_code] = n.qty
            else:
                used_items[n.item_code] = used_items[n.item_code] + n.qty

        position["number"] = number
        position["item"] = "{0}-{1}".format(sales_invoice.web_order_id, oligo.web_id)
        position["description"] = oligo.oligo_name
        position["quantity"] = 1
        position["uom"] = "Pcs"
        position["rate"] = rate_total
        position["amount"] = rate_total
        position["tax_rate"] = tax_rate if rate_total > 0 else 0
        position["tax_amount"] = tax_rate * rate_total / 100
        if position["amount"] > 0:
            positions.append(position)

    for s in sales_invoice.samples:
        position = {}
        number += 1
        rate_total = 0
        sample = frappe.get_doc("Sample", s.sample)

        for n in sample.items:
            if n.item_code in item_details:
                rate_total += n.qty * item_details[n.item_code].rate

            if n.item_code not in used_items:
                used_items[n.item_code] = n.qty
            else:
                used_items[n.item_code] = used_items[n.item_code] + n.qty

        position["number"] = number
        position["item"] = "{0}-{1}".format(sales_invoice.web_order_id, sample.web_id)
        position["description"] = sample.sample_name
        position["quantity"] = 1
        position["uom"] = "Pcs"
        position["rate"] = rate_total
        position["amount"] = rate_total
        position["tax_rate"] = tax_rate  if rate_total > 0 else 0
        position["tax_amount"] = tax_rate * rate_total / 100
        if position["amount"] > 0:
            positions.append(position)

    for n in sales_invoice.items:
        if n.item_group == "Shipping" and exclude_shipping:
            continue
        elif n.amount == 0:
            # exclude items without cost
            # TODO: This might conflict with PunchoutBuyerShops.ItemZeroPriceHandling or other webshop settings
            continue
        else:
            if n.item_code not in used_items:
                position = {}

                if number > 0:
                    number += 1
                    position["number"] = number
                else:
                    position["number"] = n.idx

                position["item"] = n.item_code
                position["description"] = n.item_name
                position["quantity"] = n.qty
                position["uom"] = n.stock_uom
                position["rate"] = n.rate
                position["amount"] = n.amount
                position["tax_rate"] = tax_rate if n.amount > 0 else 0
                position["tax_amount"] = tax_rate * n.amount / 100
                if position["amount"] > 0:
                    positions.append(position)

            elif n.qty > used_items[n.item_code]:
                # more items in positions than used in oligos and samples
                position = {}

                if number > 0:
                    number += 1
                    position["number"] = number
                else:
                    position["number"] = n.idx

                position["item"] = n.item_code
                position["description"] = n.item_name
                position["quantity"] = n.qty - used_items[n.item_code]
                position["rate"] = n.rate
                position["amount"] = n.amount
                position["tax_rate"] = tax_rate if n.amount > 0 else 0
                position["tax_amount"] = tax_rate * n.amount / 100
                if position["amount"] > 0:
                    positions.append(position)

    return positions


def get_shipping_item(items):
    for i in reversed(items):
        if i.item_group == "Shipping":
            print(i)
            return i.item_code


def create_country_name_to_code_dict(): 
    
    country_codes = {}
    country_query = frappe.get_all("Country", fields=['name', 'code'])
    for dict in country_query:
        country_codes[dict['name']] = dict['code']
    return country_codes


def create_dict_of_invoice_info_for_cxml(sales_invoice, mode): 
    """ Doc string """

    shipping_address = frappe.get_doc("Address", sales_invoice.shipping_address_name)
    shipping_contact = frappe.get_doc("Contact", sales_invoice.shipping_contact or sales_invoice.contact_person)

    customer = frappe.get_doc("Customer", sales_invoice.customer)
    company_details = frappe.get_doc("Company", sales_invoice.company)
    company_address = frappe.get_doc("Address", sales_invoice.company_address)
    contact_person = frappe.get_doc("Contact", sales_invoice.contact_person)

    settings = frappe.get_doc("Microsynth Settings", "Microsynth Settings")

    if sales_invoice.is_punchout:
        punchout_shop = frappe.get_doc("Punchout Shop", sales_invoice.punchout_shop)

    # define billing address
    if sales_invoice.is_punchout and punchout_shop.has_static_billing_address:
        billing_address = frappe.get_doc("Address", punchout_shop.billing_address)
        billing_contact = frappe.get_doc("Contact", punchout_shop.billing_contact)
    else:
        billing_address = frappe.get_doc("Address", sales_invoice.customer_address)
        billing_contact = frappe.get_doc("Contact", sales_invoice.invoice_to)
    
    # define shipping costs on header/item level
    if mode == "ARIBA" or mode == "GEP":
        # shipping for Ariba (standard) is listed on header level, shipping for GEP is listed on item level
        if sales_invoice.is_punchout:
            shipping_as_item = punchout_shop.cxml_shipping_as_item
        elif mode == "GEP":
            shipping_as_item = True
        else:
            shipping_as_item = False 
    elif mode == "Paynet":
        shipping_as_item = True
    else: 
        shipping_as_item = True

    # calculate shipping costs on header level
    shipping_costs = 0
    if not shipping_as_item:
        for n in sales_invoice.items:
            if n.item_group == "Shipping":
                shipping_costs += n.amount

    # TODO Ariba IDs if not punchout --> customer.invoice_network_id, log an error if not set
    # TODO tax detail description: <Description xml:lang = "en">0.0% tax exempt</Description>
    # other data
    
    if mode == "ARIBA":
        sender_network_id = settings.ariba_id
    elif mode == "GEP" and sales_invoice.company == "Microsynth Seqlab GmbH":
        sender_network_id = "SEQLAB"
    elif mode == "GEP" and sales_invoice.is_punchout:
        sender_network_id = punchout_shop.supplier_network_id
    elif mode == "GEP":
        sender_network_id = "MICROSYNTH"
    elif mode == "Paynet":
        sender_network_id = settings.paynet_id

    # validate receiver ID
    if not(customer.invoice_network_id):
        frappe.throw("Customer '{0}' has no 'invoice_network_id'".format(customer.name))

    # validate external supplier id for listed receivers
    if customer.invoice_network_id in [ "41100000239079338" ] and not(customer.ext_supplier_id):
        frappe.throw("Customer '{0}' has no 'ext_supplier_id'".format(customer.name))

    # Supplier tax ID
    if "CHE" in company_details.tax_id and "MWST" not in company_details.tax_id.upper():
        supplier_tax_id = company_details.tax_id + " MWST"
    else:
        supplier_tax_id = company_details.tax_id

    # Fiscal representation
    if (sales_invoice.company == "Microsynth AG" and 
            (sales_invoice.product_type == "Oligos" or 
             sales_invoice.product_type == "Material")):
        from microsynth.microsynth.jinja import get_destination_classification
        destination = get_destination_classification(si=sales_invoice.name)

        if destination == "EU" :
            # overwrite company address and tax ID
            company_address = frappe.get_doc("Address", "Microsynth AG - Fiscal Representation")
            supplier_tax_id = "ATU57564157"

    bank_account = frappe.get_doc("Account", sales_invoice.debit_to)
    tax_rate = sales_invoice.taxes[0].rate if len(sales_invoice.taxes) > 0 else 0

    country_codes = create_country_name_to_code_dict()

    posting_timepoint = get_posting_datetime(sales_invoice)

    ship_to_address = get_address_dict(
        customer = sales_invoice.customer_name,
        contact = shipping_contact,
        address = shipping_address,
        country_codes = country_codes )
    
    bill_to_address = get_address_dict(
        customer = sales_invoice.customer_name,
        contact = billing_contact,
        address = billing_address,
        country_codes = country_codes )

    sender_address = get_address_dict(
        customer = company_details.company_name,
        contact = None,
        address = company_address,
        country_codes = country_codes )

    terms_template = frappe.get_doc("Payment Terms Template", customer.payment_terms)

    # create sets of strings for delivery_note and sales_order
    order_names = []
    delivery_note_names = []
    for n in sales_invoice.items:
        if n.delivery_note:
            if n.delivery_note not in delivery_note_names:
                delivery_note_names.append(n.delivery_note)
        if n.sales_order:
            if n.sales_order not in order_names:
                order_names.append(n.sales_order)

    delivery_note_dates = []
    for del_note in delivery_note_names:
        dn_date = frappe.db.get_value('Delivery Note', del_note, 'posting_date')
        dn_date_str = frappe.utils.get_datetime(dn_date).strftime('%Y%m%d')
        delivery_note_dates.append(dn_date_str)

    # order reference / 
    if sales_invoice.is_punchout:
        order_reference = sales_invoice.po_no    
    elif billing_contact.room and billing_contact.room.upper().strip().startswith("KST"):
        if (sales_invoice.po_no and 
                (sales_invoice.po_no.startswith("4700") or
                 sales_invoice.po_no.startswith("4500"))):
            # Consider orders with purchase order number starting with 4700 or 4500 as orders with reference for UZH
            order_reference = sales_invoice.po_no
        else:
            # Special order reference for UZH
            order_reference = "{mail} / {cost_center} / {po}".format(
                mail = billing_contact.department,
                cost_center = billing_contact.room.replace("KST", "").strip(),
                po = sales_invoice.po_no)
    else:
        order_reference = sales_invoice.po_no

    # Customer id
    if sales_invoice.is_punchout and sales_invoice.punchout_shop == "EPFL":
        customer_id = 11309
    else:
        customer_id = customer.name
    
    raw_timestamp = datetime.now(tz=ZoneInfo('Europe/Zurich')).strftime("%Y-%m-%dT%H:%M:%S%z")
    timestamp = f"{raw_timestamp[:-2]}:{raw_timestamp[-2:]}"  # add a colon to fulfil ISO 8601
    raw_invoice_date = posting_timepoint.replace(tzinfo=ZoneInfo('Europe/Zurich')).strftime("%Y-%m-%dT%H:%M:%S%z")
    invoice_date = f"{raw_invoice_date[:-2]}:{raw_invoice_date[-2:]}"

    data = {'basics' : {'sender_network_id' :   sender_network_id,
                        'receiver_network_id':  customer.invoice_network_id,
                        'shared_secret':        settings.ariba_secret if mode == "ARIBA" else "",
                        'paynet_sender_pid':    settings.paynet_id, 
                        'payload_id':           posting_timepoint.strftime("%Y%m%d%H%M%S") + str(random.randint(0, 10000000)) + "@microsynth.ch",
                        'transaction_id':       sales_invoice.name + "--" + datetime.now().strftime("%Y%m%d%H%M%S"),              # Transaction ID for yellowbill. Max 50 chars, no underscore '_'
                        'timestamp':            timestamp,
                        'supplier_id':          replace_none(customer.ext_supplier_id),
                        'customer_id':          customer_id,
                        'is_punchout':          sales_invoice.is_punchout,
                        'order_id':             replace_none(order_reference), 
                        'currency':             sales_invoice.currency,
                        'invoice_id':           sales_invoice.name,
                        'invoice_date':         invoice_date,
                        'invoice_date_only':    posting_timepoint.strftime("%Y-%m-%d"),
                        'invoice_date_paynet':  posting_timepoint.strftime("%Y%m%d"),
                        'due_date':             sales_invoice.due_date.strftime("%Y-%m-%d"),
                        'pay_in_days':          terms_template.terms[0].credit_days, 
                        'sales_order_id':       sales_invoice.items[0].sales_order,
                        'delivery_note_id':     sales_invoice.items[0].delivery_note, 
                        'delivery_note_date_paynet':  "" # delivery_note.creation.strftime("%Y%m%d"),
                        },
            'cxml' : {},
            'yellowbill': {
                        'has_referenced_positions': 
                                            (sales_invoice.is_punchout or 
                                            (sales_invoice.po_no and 
                                                (sales_invoice.po_no.startswith("4700") or      # Consider orders with purchase order number starting with 4700 or 4500 as orders with reference for UZH
                                                 sales_invoice.po_no.startswith("4500")))
                                            or False)
            },
            'remitTo' : {'name':            sales_invoice.company,
                        'street':           company_address.address_line1, 
                        'pin':              company_address.pincode,
                        'city':             company_address.city, 
                        'iso_country_code': country_codes[company_address.country].upper(), 
                        'supplier_tax_id':  supplier_tax_id
                        },
            'billTo' : {'address':          bill_to_address
                        },
            'from' :    {'name':            company_details.company_name,
                        'street':           company_address.address_line1, 
                        'pin':              company_address.pincode,
                        'city':             company_address.city,
                        'iso_country_code': country_codes[company_address.country].upper(),
                        'address':          sender_address,
                        'supplier_tax_id':  supplier_tax_id
                        }, 
            'soldTo' :  {'address':         bill_to_address
                        }, 
            'shipFrom' : {'name':           company_details.company_name, 
                        'street':           company_address.address_line1,
                        'pin':              company_address.pincode,
                        'city':             company_address.city,
                        'iso_country_code': country_codes[company_address.country].upper()
                        },
            'shipTo' : {'address':          ship_to_address
                        }, 
            'contact':  {'full_name':       contact_person.full_name},
            'order':    {'names':           ", ".join(order_names)
                        },
            'delivery_note': {'names':      ", ".join(delivery_note_names),
                        'dates':            ", ".join(delivery_note_dates)
                        },
            'receivingBank' : {'swift_id':  bank_account.bic,
                        'bic':              bank_account.bic,
                        'iban_id':          bank_account.iban,
                        'account_name':     bank_account.company,
                        'account_id':       bank_account.iban,
                        'account_type':     'Checking',  
                        'branch_name':      bank_account.bank_name + " " + bank_account.bank_branch_name if bank_account.bank_branch_name else bank_account.bank_name
                        }, 
            'extrinsic' : {'buyerVatId':                customer.tax_id,
                        'supplierVatId':                supplier_tax_id,
                        'supplierCommercialIdentifier': company_details.tax_id
                        }, 
            'positions': create_position_list(sales_invoice = sales_invoice, exclude_shipping = not shipping_as_item),
            'tax' :     {'amount' :         sales_invoice.total_taxes_and_charges,
                        'taxable_amount' :  sales_invoice.net_total,
                        'percent' :         tax_rate, 
                        'taxPointDate' :    invoice_date,
                        'description' :     sales_invoice.taxes[0].description if len(sales_invoice.taxes)>0 else 0
                        },
            
            # shipping for Ariba is listed on header level, shipping for GEP is listed on item level
            'shippingTax' : {'taxable_amount':  shipping_costs,
                        'amount':               shipping_costs * tax_rate / 100,
                        'percent':              tax_rate,
                        'taxPointDate':         invoice_date,
                        'description' :         "{0}% shipping tax".format(tax_rate)
                        }, 
            'summary' : {'subtotal_amount' :        sales_invoice.net_total,
                        'shipping_amount' :         shipping_costs,
                        'gross_amount' :            sales_invoice.rounded_total or sales_invoice.grand_total,
                        'total_amount_without_tax': sales_invoice.net_total,
                        'net_amount' :              sales_invoice.rounded_total or sales_invoice.grand_total,
                        'due_amount' :              sales_invoice.rounded_total or sales_invoice.grand_total
                        }
            }
    return data


def escape_chars_for_xml(text):
    """
    Escape characters for ariba cXML 
    """
    return text.replace("&", "&amp;")


@frappe.whitelist()
def transmit_sales_invoice(sales_invoice_id):
    """
    Check the invoicing method of the customer and punchout shop and transmit the invoice accordingly.

    run
    bench execute microsynth.microsynth.invoicing.transmit_sales_invoice --kwargs "{'sales_invoice_id':'SI-BAL-23001808'}"
    """

    try:
        sales_invoice = frappe.get_doc("Sales Invoice", sales_invoice_id)
        customer = frappe.get_doc("Customer", sales_invoice.customer)
        settings = frappe.get_doc("Microsynth Settings", "Microsynth Settings")

        if not sales_invoice:
            frappe.log_error(f"Sales Invoice '{sales_invoice_id}' not found", "invoicing.transmit_sales_invoice")
            return
        if not customer:
            frappe.log_error(f"Customer '{sales_invoice.customer}' not found", "invoicing.transmit_sales_invoice")
            return

        if sales_invoice.is_punchout:
            punchout_billing_contact_id = frappe.get_value("Punchout Shop", sales_invoice.punchout_shop, "billing_contact")

        # TODO: Use punchout shop contact only, if the flag "has_static_billing_address" is activated
        if sales_invoice.is_punchout and punchout_billing_contact_id:
            invoice_contact = frappe.get_doc("Contact", punchout_billing_contact_id)
        elif sales_invoice.invoice_to:
            invoice_contact = frappe.get_doc("Contact", sales_invoice.invoice_to)
        else:
            invoice_contact = frappe.get_doc("Contact", customer.invoice_to)

        #for k,v in sales_order.as_dict().items():
        #    print ( "%s: %s" %(k,v))

        # TODO: comment-in after development to handle invoice paths other than ariba
        
        # The invoice was already sent. Do not send again.
        # if sales_invoice.invoice_sent_on:
        #     print("Invoice '{0}' was already sent on: {1}".format(sales_invoice.name, sales_invoice.invoice_sent_on))
        #     return

        # Do not send any invoice if the items are free of charge
        if sales_invoice.total == 0:
            return

        # Determine transmission mode
        if sales_invoice.is_punchout:
            if (sales_invoice.punchout_shop == "ROC-PENGEP" and sales_invoice.company == "Microsynth AG" ):
                mode = "Email"
            else:
                mode = frappe.get_value("Punchout Shop", sales_invoice.punchout_shop, "invoicing_method")
        else:
            if customer.invoicing_method == "Post":
                # Send all invoices with credit account per mail
                if sales_invoice.net_total == 0:
                    mode = "Email"
                else:
                    mode = "Post"
            elif customer.invoicing_method == "Email":
                mode = "Email"
            elif customer.invoicing_method == "ARIBA":
                mode = "ARIBA"
            elif customer.invoicing_method == "Paynet":
                mode = "Paynet"
            elif customer.invoicing_method == "GEP":
                mode = "GEP"
            else:
                mode = None

        print("Transmission mode for Sales Invoice '{0}': {1}".format(sales_invoice.name, mode))

        if mode == "Email":
            # send by mail

            # TODO check sales_invoice.invoice_to --> if it has a e-mail --> this is target-email

            recipient = invoice_contact.email_id
            if not recipient:
                subject = f"[ERP] Unable to send {sales_invoice.name} to Contact {invoice_contact.name}: no email address found."
                frappe.log_error(subject, "Sending invoice email failed")
                message = f"Dear Administration,<br><br>this is an automatic email to inform you that the ERP did not found an email address " \
                            f"to send '{sales_invoice.name}' to Contact '{invoice_contact.name}'.<br>" \
                            f"Please try to determine the email address and enter it at the appropriate place. <br><br>Best regards,<br>Jens"
                make(
                    recipients = "info@microsynth.ch",
                    sender = "jens.petermann@microsynth.ch",
                    subject = subject,
                    content = message,
                    send_email = True
                    )
                return

            if sales_invoice.company == "Microsynth AG":
                destination = get_destination_classification(si = sales_invoice.name)

                if destination == "EU":
                    footer =  frappe.get_value("Letter Head", "Microsynth AG Wolfurt", "footer")
                else:
                    footer =  frappe.get_value("Letter Head", sales_invoice.company, "footer")
            else: 
                footer = frappe.get_value("Letter Head", sales_invoice.company, "footer")

            create_pdf_attachment(sales_invoice.name)

            attachments = get_attachments("Sales Invoice", sales_invoice.name)
            fid = None
            for a in attachments:
                fid = a['name']
            frappe.db.commit()

            if sales_invoice.language == "de":
                subject = f"Ihre Rechnung {sales_invoice.name}"
                message = f"Sehr geehrte Microsynth Kundin, sehr geehrter Microsynth Kunde,<br><br>\
wir bedanken uns herzlich für Ihren Auftrag und Ihr Vertrauen in unsere Produkte und Dienstleistungen.<br>\
Beiliegend erhalten Sie die Rechnung mit der Nummer '{sales_invoice.name}' für die erbrachten Leistungen.\
Sollten Sie weitere Fragen oder Unklarheiten haben, stehen wir Ihnen selbstverständlich gerne zur Verfügung.<br><br>\
Mit Freundlichen Grüssen<br>\
Ihr Administrations Team<br><br>{footer}"
            elif sales_invoice.language == "fr":
                subject = f"Votre Facture {sales_invoice.name}"
                message = f"Mesdames et Messieurs<br><br>\
Nous vous remercions vivement de votre commande et de votre confiance dans nos produits et services.<br><br>\
Vous trouverez ci-joint la facture avec le numéro '{sales_invoice.name}' pour les prestations fournies.\
Si vous avez d'autres questions ou si vous avez des doutes, nous sommes bien sûr à votre disposition.<br><br>\
Avec nos meilleures salutations<br>\
Votre équipe d'administration<br><br>{footer}"
            else:
                subject = f"Your Invoice {sales_invoice.name}"
                message = f"Dear Microsynth customer,<br><br>\
Thank you very much for your order and your confidence in our products and services.<br><br>\
Enclosed you will find the invoice with the number '{sales_invoice.name}' for the services provided.\
Should you have any further questions or uncertainties, please do not hesitate to contact us.<br><br>\
Kind regards<br>\
Your administration team<br><br>{footer}"

            make(
                recipients = recipient,
                sender = "info@microsynth.ch",
                sender_full_name = "Microsynth",
                cc = "info@microsynth.ch",
                subject = subject, 
                content = message,
                doctype = "Sales Invoice",
                name = sales_invoice.name,
                attachments = [{'fid': fid}],
                send_email = True
            )

        elif mode == "Post":
            create_pdf_attachment(sales_invoice.name)

            attachments = get_attachments("Sales Invoice", sales_invoice.name)
            fid = None
            for a in attachments:
                fid = a['name']
            frappe.db.commit()
            
            # print the pdf with cups
            path = get_physical_path(fid)
            PRINTER = frappe.get_value("Microsynth Settings", "Microsynth Settings", "invoice_printer")
            import subprocess
            subprocess.run(["lp", path, "-d", PRINTER])

            pass

        elif mode == "ARIBA":
            cxml_data = create_dict_of_invoice_info_for_cxml(sales_invoice, mode)
            cxml = frappe.render_template("microsynth/templates/includes/ariba_cxml.html", cxml_data)

            file_path = "{0}/{1}.xml".format(settings.ariba_cxml_export_path, sales_invoice.name)
            with open(file_path, mode='w') as file:
                file.write(escape_chars_for_xml(cxml))

            '''
            # attach to sales invoice
            folder = create_folder("ariba", "Home")
            # store EDI File  
        
            f = save_file(
                "{0}.txt".format(sales_invoice.name), 
                cxml, 
                "Sales Invoice", 
                sales_invoice.name, 
                folder = '/home/libracore/Desktop',
                # folder=folder, 
                is_private=True
            )
            '''

        elif mode == "Paynet":
            # Do not send any invoice if there is nothing to pay
            if sales_invoice.grand_total == 0:
                print("{0}: do not transmit because of 0 costs".format(sales_invoice.name))
                return

            # create Paynet cXML input data dict
            xml_data = create_dict_of_invoice_info_for_cxml(sales_invoice, mode)
            xml = frappe.render_template("microsynth/templates/includes/yellowbill_xml.html", xml_data)

            file_path = "{directory}/{biller_id}_{transaction_id}.xml".format(
                directory = settings.paynet_export_path,
                biller_id = xml_data['basics']['paynet_sender_pid'],
                transaction_id = xml_data['basics']['transaction_id'])

            with open(file_path, 'w') as file:
                file.write(xml)

            '''
            # TODO: comment in after development to save paynet file to filesystem
        
            # attach to sales invoice
            folder = create_folder("ariba", "Home")
            # store EDI File
            
            f = save_file(
                "{0}.txt".format(sales_invoice.name), 
                cxml, 
                "Sales Invoice", 
                sales_invoice.name, 
                folder=folder, 
                is_private=True
            )
            '''

        elif mode == "GEP":
            cxml_data = create_dict_of_invoice_info_for_cxml(sales_invoice, mode)
            cxml = frappe.render_template("microsynth/templates/includes/ariba_cxml.html", cxml_data)

            file_path = "{0}/{1}.xml".format(settings.gep_cxml_export_path, sales_invoice.name)
            with open(file_path, mode='w') as file:
                file.write(cxml)
            '''
            # TODO: comment in after development to save gep file to filesystem

            # attach to sales invoice
            folder = create_folder("ariba", "Home")
            # store EDI File

            f = save_file(
                "{0}.txt".format(sales_invoice.name), 
                cxml, 
                "Sales Invoice", 
                sales_invoice.name, 
                folder=folder, 
                is_private=True
            )
            '''

        else:
            return

        # sales_invoice.invoice_sent_on = datetime.now()
        # sales_invoice.save()
        frappe.db.set_value("Sales Invoice", sales_invoice.name, "invoice_sent_on", datetime.now(), update_modified = False)
        frappe.db.set_value("Sales Invoice", sales_invoice.name, "invoicing_method", mode, update_modified = False)
        frappe.db.commit()

    except Exception as err:
        frappe.log_error("Cannot transmit sales invoice {0}: \n{1}\n{2}".format(
            sales_invoice_id, 
            err,
            traceback.format_exc()), "invoicing.transmit_sales_invoice")

    return


def transmit_sales_invoices(sales_invoices):
    """
    Transmit multiple sales invoices with the `transmit_sales_invoice` function. 

    run
    bench execute microsynth.microsynth.invoicing.transmit_sales_invoices --kwargs "{'sales_invoices': [ 'SI-BAL-23014018', 'SI-BAL-23014019' ]}"
    """
    for si in sales_invoices:
        transmit_sales_invoice(si)
    return


def transmit_sales_invoices_from_file(file):
    """
    Read a file with a list of Sales Invoice IDs and transmit the Sales Invoices with the `transmit_sales_invoice` function.

    run
    bench execute microsynth.microsynth.invoicing.transmit_sales_invoices_from_file --kwargs "{'file':'/mnt/erp_share/Invoices/invoices.txt'}"
    """
    print(file)
    invoices = []
    with open(file) as file:
        for line in file:
            invoices.append(line.strip())

    for si in invoices:
        transmit_sales_invoice(si)
    return


def get_delivery_notes(sales_invoice):
    """
    run
    bench execute microsynth.microsynth.invoicing.get_delivery_notes --kwargs "{'sales_invoice': 'SI-GOE-23002450' }"
    """
        
    delivery_notes = []

    items = frappe.db.get_all("Sales Invoice Item",
        filters={'parent': sales_invoice },
        fields=['delivery_note'])

    for item in items:
        if item.delivery_note not in delivery_notes:
            delivery_notes.append(item.delivery_note)

    return delivery_notes


def pdf_export(sales_invoices, path):
    for sales_invoice in sales_invoices:
        content_pdf = frappe.get_print(
            "Sales Invoice", 
            sales_invoice, 
            print_format="Sales Invoice", 
            as_pdf=True)
        file_name = "{0}/{1}.pdf".format(path, sales_invoice)
        with open(file_name, mode='wb') as file:
            file.write(content_pdf)


def pdf_export_delivery_notes(delivery_notes, path):
    for delivery_note in delivery_notes:
        content_pdf = frappe.get_print(
            "Delivery Note", 
            delivery_note, 
            print_format="Delivery Note", 
            as_pdf=True)
        file_name = "{0}/{1}.pdf".format(path, delivery_note)
        with open(file_name, mode='wb') as file:
            file.write(content_pdf)


def transmit_carlo_erba_invoices(sales_invoices):
    """
    run
    bench execute microsynth.microsynth.invoicing.transmit_carlo_erba_invoices --kwargs "{'sales_invoices': ['SI-GOE-23002450']}"
    """

    path = frappe.get_value("Microsynth Settings", "Microsynth Settings", "carlo_erba_export_path") + "/" + datetime.now().strftime("%Y-%m-%d__%H-%M")
    if not os.path.exists(path):
        os.mkdir(path)

    pdf_export(sales_invoices, path)

    for so in sales_invoices:
        delivery_notes = get_delivery_notes(so)
        pdf_export_delivery_notes(delivery_notes, path)

    lines = []

    for invoice_name in sales_invoices:
        si = frappe.get_doc("Sales Invoice", invoice_name)

        # Cliente (sold-to-party)
        # Billing address of the order customer
        order_customer_id = si.order_customer if si.order_customer else si.customer
        order_contact_id = frappe.db.get_value("Customer", order_customer_id, "invoice_to")

        order_customer = si.order_customer_display if si.order_customer_display else si.customer_name
        order_contact = frappe.get_doc("Contact", order_contact_id if order_contact_id else si.contact_person)
        order_address = get_billing_address(order_customer_id)

        # Acquiren (ship-to-party)
        shipping_customer = si.order_customer_display if si.order_customer_display else si.customer_name
        shipping_contact = frappe.get_doc("Contact", si.shipping_contact if si.shipping_contact else si.contact_person)
        shipping_address = frappe.get_doc("Address", si.shipping_address_name)

        # Billing (bill-to-party)
        # Billing address of Carlo Erba who needs to pay the invoice
        billing_customer = si.customer_name
        billing_contact = frappe.get_doc("Contact", si.invoice_to)
        billing_address = frappe.get_doc("Address", si.customer_address)

        # First delivery note
        delivery_note = si.items[0].delivery_note
        delivery_date = datetime.combine(
            frappe.get_value("Delivery Note", delivery_note, "posting_date"), 
            (datetime.min + frappe.get_value("Delivery Note", delivery_note, "posting_time")).time())

        positions_count = 0
        for item in si.items:
            if item.amount == 0:
                continue
            else:
                positions_count += 1

        # Find Sales Order
        orders = []
        for item in si.items:
            if item.sales_order not in orders:
                orders.append(item.sales_order)

        if len(orders) == 1:
            order_name = orders[0]
        else:
            frappe.log_error("Cannot transmit invoice {0}: \nNone or multiple orders: {1}".format(invoice_name, orders), "invoicing.transmit_carlo_erba_invoices")
            continue

        # Header
        header = [
            "Header",                                                                       # record_type(8)
            si.web_order_id or order_name,                                                  # sales_order_number(8)
            si.name,                                                                        # invoice_number(8)
            si.po_no if si.po_no else "",                                                   # customer_po_number(22)
            si.posting_date.strftime("%d.%m.%Y"),                                           # invoice_date(8)
            delivery_date.strftime("%d.%m.%Y"),                                             # shipping_date(8)    // use first Delivery Note
            si.customer,                                                                    # customer_number(8)
            shipping_contact.name,                                                          # shipping_number(8)
            billing_contact.name,                                                           # bill_to_number(8)
            delivery_note,                                                                  # delivery_number(30) // use first Delivery Note
            str(positions_count),                                                           # trailer_amount(8)   // number of positions?
            str(si.total),                                                                  # netto_amount(15)
            str(si.grand_total) ]                                                           # total_amount(15)

        lines.append(header)

        # Addresses
        def get_address_data(type, customer_name, contact, address):
            data = [
                type,                                                                       # record_type(8)
                si.web_order_id or order_name,                                              # sales_order_number(8)
                si.name,                                                                    # invoice_number(8)
                contact.name,                                                               # customer_number(8)
                contact.designation if contact.designation else "",                         # titel(8)
                get_name(contact),                                                          # name(60)
                address.overwrite_company if address.overwrite_company else customer_name,  # adress1(60)
                contact.department if contact.department else "",                           # adress2(60)
                address.address_line1 if address.address_line1 else "",                     # adress3(51)
                (frappe.get_value("Country", address.country, "code")).upper(),             # country_code(2)
                address.pincode if address.pincode else "",                                 # postal_code(10)
                address.city if address.city else "",                                       # city(20)
                get_name(contact),                                                          # contact_person(24)
                contact.email_id if contact.email_id else "",                               # email(40)
                contact.phone if contact.phone else "",                                     # phone_number(20)
                "",                                                                         # fax_number(20)
            ]
            return data

        # Sold-to-party
        client = get_address_data(
            type = "Cliente",
            customer_name = order_customer,
            contact = order_contact,
            address = order_address)

        # Ship-to-party
        shipping = get_address_data(
            type = "Acquiren",
            customer_name = shipping_customer,
            contact = shipping_contact,
            address = shipping_address)

        # bill-to-party
        billing = get_address_data(
            type = "Billing",
            customer_name = billing_customer,
            contact = billing_contact,
            address = billing_address)

        lines.append(client)
        lines.append(shipping)
        lines.append(billing)

        # Comments
                                                                                            # record_type(8)
                                                                                            # sales_order_number(8)
                                                                                            # invoice_number(8)
                                                                                            # comments(76)

        # Position
        i = 1
        for item in si.items:
            if item.amount == 0:
                continue
            position = [
                "Pos",                                                                      # record_type(8)
                si.web_order_id or order_name,                                              # sales_order_number(8)
                si.name,                                                                    # invoice_number(8)
                str(i),                                                                     # position_line(3)
                item.item_code,                                                             # kit_item(18)
                str(item.qty),                                                              # kit_quantity(17)
                str(item.rate),                                                             # list_price(17)
                "0",                                                                        # discount_percent(17)
                str(item.amount),                                                           # kit_price(17)
                "",                                                                         # serial_number(24)
                item.description,                                                           # description1(24)
                ""                                                                          # description2(24)
            ]
            lines.append(position)
            i += 1

        # Components
                                                                                            # record_type(8)
                                                                                            # sales_order_number(8)
                                                                                            # invoice_number(8)
                                                                                            # position_line(3)
                                                                                            # component_number(18)
                                                                                            # component_quantity(17)
                                                                                            # component_price(17)
                                                                                            # component_feature(12)
                                                                                            # description1(24)
                                                                                            # description2(24)

    text = "\r\n".join( [ "\t".join(line) for line in lines ] )

    file = open(path + "/export.txt", "w")
    file.write(text)
    file.close()

    for invoice_name in sales_invoices:
        frappe.db.set_value("Sales Invoice", invoice_name, "invoice_sent_on", datetime.now(), update_modified = True)

    return


def process_daily_invoices():
    """
    Executed by a Cron job every evening to transmit sales invoices electronically or via Post.

    for testing: run
    bench execute microsynth.microsynth.invoicing.process_daily_invoices
    """
    for company in frappe.db.get_all('Company', fields=['name']):  #['Microsynth AG', 'Microsynth Seqlab GmbH', 'Microsynth Austria GmbH', 'Microsynth France SAS', 'Ecogenics GmbH']:
        for mode in ['Electronic']:
            async_create_invoices(mode, company['name'], None)


def process_collective_invoices_monthly():
    """
    Executed by a Cron job every month to transmit collective sales invoices.

    for testing: run
    bench execute microsynth.microsynth.invoicing.process_collective_invoices_monthly
    """
    # TODO: split up collective invoices into Post and electronic invoices
    return
    # for company in frappe.db.get_all('Company', fields=['name']):
    #     async_create_invoices("Collective", company['name'], None)
