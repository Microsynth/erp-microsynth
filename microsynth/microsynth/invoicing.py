# -*- coding: utf-8 -*-
# Copyright (c) 2022, libracore (https://www.libracore.com) and contributors
# For license information, please see license.txt
#
# For more details, refer to https://github.com/Microsynth/erp-microsynth/
#

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
from microsynth.microsynth.utils import get_physical_path, get_billing_address, get_alternative_income_account
from microsynth.microsynth.credits import allocate_credits, book_credit, get_total_credit
from microsynth.microsynth.jinja import get_destination_classification
import datetime
from datetime import datetime
import json
import random

@frappe.whitelist()
def create_invoices(mode, company):
    kwargs={
        'mode': mode,
        'company': company
    }
    
    enqueue("microsynth.microsynth.invoicing.async_create_invoices",
        queue='long',
        timeout=15000,
        **kwargs)
    return {'result': _('Invoice creation started...')}
    
def async_create_invoices(mode, company):
    """
    run 
    bench execute microsynth.microsynth.invoicing.async_create_invoices --kwargs "{ 'mode':'Electronic', 'company': 'Microsynth AG' }"
    """

    all_invoiceable = get_data(filters={'company': company})

    # # Not implemented exceptions to catch cases that are not yet developed
    # if company != "Microsynth AG":
    #     frappe.throw("Not implemented: async_create_invoices for company '{0}'".format(company))
    #     return
    if mode not in ["Post", "Electronic", "Collective"]:
        frappe.throw("Not implemented: async_create_invoices for mode '{0}'".format(mode))
        return

    # Standard processing
    if (mode in ["Post", "Electronic"]):
        # individual invoices

        count = 0
        for dn in all_invoiceable:
            try:
                # # TODO: implement for other export categories
                # if dn.region != "CH":
                #     continue

                # TODO: implement for other product types. Requires setting the income accounts.
                # if dn.product_type not in ["Oligos", "Labels", "Sequencing"]:
                #     continue

                # process punchout orders separately
                if cint(dn.get('is_punchout') == 1):
                    # TODO implement punchout orders
                    # si = make_punchout_invoice(dn.get('delivery_note'))
                    # transmit_sales_invoice(si)
                    continue

                credit = get_total_credit(dn.get('customer'), company)
                if credit is not None and frappe.get_value("Customer",c,"has_credit_account"):
                    delivery_note =  dn.get('delivery_note')
                    total = frappe.get_value("Delivery Note", delivery_note, "total")
                    if total > credit:
                        frappe.log_error("Delivery Note '{0}': \nInsufficient credit for customer {c}".format(delivery_note, dn.get('customer')), "invocing.async_create_invoices")

                        subject = "Delivery Note {0}: Insufficient credit".format(delivery_note)
                        message = "Cannot invoice Delivery Note '{delivery_note}' due to insufficient credit balance.<br>Total: {total} {currency}<br>Credit: {credit} {currency}".format(
                            delivery_note = delivery_note,
                            total = total,
                            credit = credit,
                            currency = dn.get('currency'))

                        print(message)
                        # make(
                        #     recipients = "info@microsynth.ch",
                        #     sender = "erp@microsynth.ch",
                        #     cc = "rolf.suter@microsynth.ch",
                        #     subject = subject,
                        #     content = message,
                        #     doctype = "Delivery Note",
                        #     name = delivery_note,
                        #     send_email = True
                        # )
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
                        if dn.get('invoicing_method') not in  ["Email"]:
                            continue

                        # TODO there seems to be an issue here: both branches ("Post"/ not "Post") do the same
                        if dn.get('invoicing_method') != "Post":
                            si = make_invoice(dn.get('delivery_note'))
                            transmit_sales_invoice(si)
                            count += 1
                            # if count >= 20 and company != "Microsynth AG":
                            #     break
            except Exception as err:
                frappe.log_error("Cannot invoice {0}: \n{1}".format(dn.get('delivery_note'), err), "invoicing.async_create_invoices")

    elif mode == "Collective":
        # colletive invoices
        customers = []
        for dn in all_invoiceable:

            # TODO process other invoicing methods
            if dn.get('invoicing_method') not in  ["Email", "Post"]:
                continue

            if cint(dn.get('collective_billing')) == 1 and cint(dn.get('is_punchout')) != 1 and dn.get('customer') not in customers:
                customers.append(dn.get('customer'))

        # for each customer, create one invoice per tax template for all dns
        for c in customers:
            try:
                dns = []
                for dn in all_invoiceable:
                    if cint(dn.get('collective_billing')) == 1 and cint(dn.get('is_punchout')) != 1 and dn.get('customer') == c:
                        dns.append(dn.get('delivery_note'))

                if len(dns) > 0:
                    # check if there are multiple tax templates
                    taxes = []
                    for dn in dns:
                        t = frappe.db.get_value("Delivery Note", dn, "taxes_and_charges")
                        if t not in taxes:
                            taxes.append(t)

                    if len(taxes) > 1:
                        print("multiple taxes for customer '{0}'".format(c), "invocing.async_create_invoices")

                    credit = get_total_credit(c, company)

                    # create one invoice per tax template
                    for tax in taxes:
                        filtered_dns = []
                        for d in dns:
                            if frappe.db.get_value("Delivery Note", d, "taxes_and_charges") == tax:
                                total = frappe.get_value("Delivery Note", d, "total")

                                if credit is not None and frappe.get_value("Customer",c,"has_credit_account"):
                                    # there is some credit - check if it is sufficient
                                    if total <= credit:
                                        filtered_dns.append(d)
                                        credit = credit - total
                                    else:
                                        frappe.log_error("Delivery Note '{0}': \nInsufficient credit for customer {1}".format(d, c), "invocing.async_create_invoices")
                                else:
                                    # there is no credit account
                                    filtered_dns.append(d)

                        if len(filtered_dns) > 1:
                            si = make_collective_invoice(filtered_dns)
                            transmit_sales_invoice(si)
                            
            except Exception as err:
                frappe.log_error("Cannot create collective invoice for customer {0}: \n{1}".format(c, err), "invoicing.async_create_invoices")
    else:
        frappe.throw("Unknown mode '{0}' for async_create_invoices".format(mode))

    return


def get_income_account(company, country, original_account):
    
    # TODO: zusätzliches Feld auf alternatives accounts? 
    #  country flag (type data: "Switzerland", "Austria", "*", wildcart) wie bei TaxMatrix

        # TODO: get income account depending on company and item_group, inland/foreign

    return 42





def set_income_accounts(sales_invoice):
    """
    Sets the income account for each item of a sales invoice based on the original income account entry, the company and the billing_address country.
    
    run
    bench execute microsynth.microsynth.invoicing.set_income_accounts --kwargs "{'sales_invoice': 'SI-BAL-23000538'}"
    """
    sales_invoice = frappe.get_doc("Sales Invoice", sales_invoice)
    billing_address = get_billing_address(sales_invoice.customer)

    for item in sales_invoice.items:
        item.income_account = get_alternative_income_account(item.income_account, billing_address.country)

    sales_invoice.save()


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
    
    sales_invoice.insert()
    sales_invoice.submit()
    # if a credit was allocated, book credit account
    if cint(sales_invoice.total_customer_credit) > 0:
        book_credit(sales_invoice.name)
        
    frappe.db.commit()

    return sales_invoice.name


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
    else:
        punchout_shop = frappe.get_doc("Punchout Shop", sales_order.punchout_shop)

    sales_invoice_content = make_sales_invoice(delivery_note.name)

    # compile document
    sales_invoice = frappe.get_doc(sales_invoice_content)
    company = frappe.get_value("Delivery Note", delivery_note, "company")
    sales_invoice.naming_series = get_naming_series("Sales Invoice", company)
    
    if punchout_shop.billing_contact: 
        sales_invoice.invoice_to = punchout_shop.billing_contact
    else:    
        sales_invoice.invoice_to = frappe.get_value("Customer", sales_invoice.customer, "invoice_to") # replace contact with customer's invoice_to contact

    if punchout_shop.billing_address:
        sales_invoice.customer_address = punchout_shop.billing_address

    sales_invoice.insert()
    sales_invoice.submit()
    frappe.db.commit()

    return sales_invoice.name


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

    sales_invoice.insert()
    sales_invoice.submit()

    # if a credit was allocated, book credit account
    if cint(sales_invoice.total_customer_credit) > 0:
        book_credit(sales_invoice.name)

    frappe.db.commit()

    return sales_invoice.name


def create_pdf_attachment(sales_invoice): 
    """
    Creates the PDF file for a given Sales Invoice name and attaches the file to the record in the ERP.

    run
    bench execute microsynth.microsynth.utils.create_pdf_attachment --kwargs "{'sales_invoice': 'SI-BAL-23002642-1'}"
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
            delivery_note_list.append(item.sales_order)

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


def create_list_of_item_dicts_for_cxml(sales_invoice):
    """creates a list of dictionaries of all items of a sales_invoice (including shipping item)"""

    list_of_invoiced_items = []
    invoice_item_dicts = {}
    invoice_position = 0

    # need a dict of all item to predict price of an oligo artice
    all_sole_items = {}
    item_list = sales_invoice.items
    for item in item_list:
        all_sole_items[item.item_code] = item 
        #print ("\n")
        #for k, v in item.as_dict().items():
        #    print ("{}: {}".format(k, v))

    # oligo article
    invoiced_oligos = {}
    for oligo_link in sales_invoice.oligos: 
        invoice_position += 1 
        oligo_object = frappe.get_doc("Oligo", oligo_link.as_dict()["oligo"])
        oligo_details = {}
        oligo_details["oligo_article"] = oligo_object
        oligo_details["invoice_position"] = invoice_position
        oligo_details["quantity"] = 1
        oligo_details["description"] = oligo_object.oligo_name
        oligo_details["price"] = 0
        oligo_details["base_price"] = 0
        for oligo_item in oligo_object.items:
            oligo_details["price"] += oligo_item.qty * all_sole_items[oligo_item.item_code].rate
            oligo_details["base_price"] = oligo_item.qty * all_sole_items[oligo_item.item_code].base_rate
        list_of_invoiced_items.append(oligo_details)
        #print ("\n")
        #for k, v in oligo_object.as_dict().items():
        #    print ("{}: {}".format(k, v))

    # other articles incl shipping 
    for item in sales_invoice.items:
        invoice_item_dicts[item.item_code] = item
        if item.item_group not in ["3.1 DNA/RNA Synthese", "Shipping"]: 
            for k, v in item.as_dict().items(): 
                print ("{}: {}".format(k, v))
            # other items (labels)
            invoice_other_items = {}
            invoice_position += 1
            invoice_other_items["other_article"] = item
            invoice_other_items["invoice_position"] = invoice_position
            invoice_other_items["quantity"] = item.qty
            invoice_other_items["description"] = item.item_name
            invoice_other_items["price"] = item.rate
            invoice_other_items["base_price"] = item.base_rate
            list_of_invoiced_items.append(invoice_other_items)

        elif item.item_group == "Shipping": 
            # shipping
            invoice_position += 1
            invoiced_shipping = {}
            invoiced_shipping["shipping_article"] = item
            invoiced_shipping["invoice_position"] = invoice_position
            invoiced_shipping["quantity"] = 1
            invoiced_shipping["description"] = item.item_name
            invoiced_shipping["price"] = item.amount
            invoiced_shipping["base_price"] = item.base_amount
            list_of_invoiced_items.append(invoiced_shipping)
    
    return list_of_invoiced_items


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


def create_dict_of_invoice_info_for_cxml(sales_invoice=None): 
    """ Doc string """

    print ("\n1a")
    #for key, value in (sales_invoice.as_dict().items()): 
    #    print ("%s: %s" %(key, value))

    #TODO: !! with punchout-orders, you may take other billing_address, shipping_address
    shipping_address = frappe.get_doc("Address", sales_invoice.shipping_address_name)
    #for key, value in (shipping_address.as_dict().items()): 
    #    print ("%s: %s" %(key, value))

    print ("\n1b")
    billing_address = frappe.get_doc("Address", sales_invoice.customer_address)
    #for key, value in (billing_address.as_dict().items()): 
    #    print ("%s: %s" %(key, value))

    customer = frappe.get_doc("Customer", sales_invoice.customer)
    #for key, value in (customer.as_dict().items()): 
    #   print ("%s: %s" %(key, value))
    
    print ("\n-----0-----")
    company_details = frappe.get_doc("Company", sales_invoice.company)
    #print(company_details.as_dict())
    #for key, value in (company_details.as_dict().items()): 
    #   print ("%s: %s" %(key, value))

    print ("\n-----0A-----")
    company_address = frappe.get_doc("Address", sales_invoice.company_address)

    print ("\n-----0B-----")
    customer_contact = frappe.get_doc("Contact", sales_invoice.customer_address)
    #for key, value in (customer_contact.as_dict().items()): 
    #    print ("%s: %s" %(key, value))

    invoice_contact = frappe.get_doc("Contact", sales_invoice.contact_person)
    #for key, value in (invoice_contact.as_dict().items()): 
    #    print ("%s: %s" %(key, value))

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
    
    #print("orders: % s" %", ".join(order_names))
    #print("notes: %s" %", ".join(delivery_note_names))
    #print("dates: %s" %", ".join(delivery_note_dates))

    print ("\n-----0C-----")
    try: 
        settings = frappe.get_doc("Microsynth Settings", "Microsynth Settings")
    except: 
        frappe.throw("Cannot access 'Microsynth Settings'. Invoice cannot be created")
    #print("settings: %s" % settings.as_dict())

    default_account = frappe.get_doc("Account", company_details.default_bank_account)
    if sales_invoice.currency == default_account.account_currency:
        bank_account = default_account
    else: 
        preferred_accounts = frappe.get_all("Account", 
                    filters = {
                        "company" : sales_invoice.company, 
                        "account_type" : "Bank",
                        "account_currency": sales_invoice.currency, 
                        "disabled": 0, 
                        "preferred": 1
                        },
                        fields = ["name"]
                    )
        if len(preferred_accounts) == 1: 
            preferred_account = frappe.get_doc("Account", preferred_accounts[0]["name"])
        else: 
            frappe.throw("No or too many valid bank account")
        
        bank_account = preferred_account
            
    #for key, value in (bank_account.as_dict().items()): 
    #   print ("%s: %s" %(key, value))

    #print(sales_invoice.as_dict()["taxes"][0]["creation"].strftime("%Y-%m-%dT%H:%M:%S+01:00"),
    #for key, value in (company_details.as_dict().items()): 
    #    print ("%s: %s" %(key, value))

    soId_and_dnId = get_sales_order_id_and_delivery_note_id(sales_invoice)
    sales_order_id = soId_and_dnId["sales_order_id"] # can be called directly in dict "data" creation on-the-fly
    delivery_note_id = soId_and_dnId["delivery_note_id"] # can be called directly in dict "data" creation on-the-fly

    country_codes = create_country_name_to_code_dict()
    itemList = create_list_of_item_dicts_for_cxml(sales_invoice)

    data2 = {'basics' : {'sender_network_id' :  settings.ariba_id,
                        'receiver_network_id':  customer.invoice_network_id,
                        'shared_secret':        settings.ariba_secret,
                        'paynet_sender_pid':    settings.paynet_id, 
                        'payload':              sales_invoice.creation.strftime("%Y%m%d%H%M%S") + str(random.randint(0, 10000000)) + "@microsynth.ch"
,
                        'order_id':             sales_invoice.po_no, 
                        'currency':             sales_invoice.currency,
                        'invoice_id':           sales_invoice.name,
                        'invoice_date':         sales_invoice.as_dict()["creation"].strftime("%Y-%m-%dT%H:%M:%S+01:00"),
                        'invoice_date_paynet':  sales_invoice.as_dict()["creation"].strftime("%Y%m%d"),
                        'delivery_note_id':     sales_invoice.items[0].delivery_note, 
                        'delivery_note_date_paynet':  "" # delivery_note.as_dict()["creation"].strftime("%Y%m%d"),
                        },
            'remitTo' : {'name':            sales_invoice.company,
                        'street':           company_address.address_line1, 
                        'pin':              company_address.pincode,
                        'city':             company_address.city, 
                        'iso_country_code': country_codes[company_address.country].upper(), 
                        'supplier_tax_id':  company_details.tax_id
                        },
            'billTo' : {'address_id':       billing_address.name, 
                        'name':             sales_invoice.customer_name,
                        'department':       invoice_contact.department,
                        'street':           billing_address.address_line1,
                        'pin':              billing_address.pincode,
                        'city':             billing_address.city,
                        'iso_country_code': country_codes[billing_address.country].upper()
                        },
            'from' :    {'name':            company_details.company_name,
                        'street':           company_address.address_line1, 
                        'pin':              company_address.pincode,
                        'city':             company_address.city,
                        'iso_country_code': country_codes[company_address.country].upper()
                        }, 
            'soldTo' :  {'address_id':      billing_address.name, 
                        'name':             sales_invoice.customer_name,
                        'department':       invoice_contact.department,
                        'street':           billing_address.address_line1,
                        'pin':              billing_address.pincode,
                        'city':             billing_address.city,
                        'iso_country_code': country_codes[billing_address.country].upper()
                        }, 
            'shipFrom' : {'name':           company_details.name, 
                        'street':           company_address.address_line1,
                        'pin':              company_address.pincode,
                        'city':             company_address.city,
                        'iso_country_code': country_codes[company_address.country].upper()
                        },
            'shipTo' : {'address_id':       shipping_address.customer_address_id,
                        'name':             shipping_address.name,
                        'street':           shipping_address.address_line1,
                        'pin':              shipping_address.pincode,
                        'city':             shipping_address.city,
                        'iso_country_code': country_codes[shipping_address.country].upper()
                        }, 
            'contact':  {'full_name':       invoice_contact.full_name, 
                        'department':       customer_contact.department,
                        'room':             customer_contact.room,
                        'institute':        customer_contact.institute
                        },
            'order':    {'names':           ", ".join(order_names)
                        },
            'del_note': {'names':           ", ".join(delivery_note_names),
                        'dates':            ", ".join(delivery_note_dates)
                        },
            'receivingBank' : {'swift_id':  bank_account.bic,
                        'iban_id':          bank_account.iban,
                        'account_name':     bank_account.company,
                        'account_id':       bank_account.iban,
                        'account_type':     'Checking',  
                        'branch_name':      bank_account.bank_name + " " + bank_account.bank_branch_name
                        }, 
            'extrinsic' : {'buyerVatId':                customer.tax_id + ' MWST',
                        'supplierVatId':                company_details.tax_id + ' MWST',
                        'supplierCommercialIdentifier': company_details.tax_id + ' VAT' 
                        }, 
            'items' :   itemList, 
            'tax' :     {'amount' :         sales_invoice.total_taxes_and_charges,
                        'taxable_amount' :  sales_invoice.net_total,
                        'percent' :         sales_invoice.taxes[0].rate if len(sales_invoice.taxes)>0 else 0, 
                        'taxPointDate' :    sales_invoice.posting_date.strftime("%Y-%m-%dT%H:%M:%S+01:00"),
                        'description' :     sales_invoice.taxes[0].description if len(sales_invoice.taxes)>0 else 0
                        },
            # shipping is listed on item level, not header level.
            'shippingTax' : {'taxable_amount':  '0.00',
                        'amount':               '0.00',
                        'percent':              '0.0',
                        'taxPointDate':         sales_invoice.posting_date.strftime("%Y-%m-%dT%H:%M:%S+01:00"),
                        'description' :         '0.0' + '% shipping tax'
                        }, 
            'summary' : {'subtotal_amount' :        sales_invoice.base_total,
                        'shipping_amount' :         '0.00',
                        'gross_amount' :            sales_invoice.rounded_total,
                        'total_amount_without_tax': sales_invoice.net_total,
                        'net_amount' :              sales_invoice.rounded_total,
                        'due_amount' :              sales_invoice.rounded_total
                        }
            }
    #for k,v in data2.items(): 
    #    print ("{}: {}".format(k,v))
    return data2


def transmit_sales_invoice(sales_invoice):
    """
    This function will check the transfer mode and transmit the invoice

    run
    bench execute microsynth.microsynth.invoicing.transmit_sales_invoice --kwargs "{'sales_invoice':'SI-BAL-23001808'}"
    """

    try:
        sales_invoice = frappe.get_doc("Sales Invoice", sales_invoice)
        customer = frappe.get_doc("Customer", sales_invoice.customer)
        
        if sales_invoice.invoice_to:
            invoice_contact = frappe.get_doc("Contact", sales_invoice.invoice_to)
        else:
            invoice_contact = frappe.get_doc("Contact", sales_invoice.contact_person)
        #for k,v in sales_order.as_dict().items():
        #    print ( "%s: %s" %(k,v))

        # TODO: comment-in after development to handle invoice paths other than ariba
        
        # TODO: handle punchout invoices different!
        if sales_invoice.is_punchout:
            return

        # The invoice was already sent. Do not send again.
        if sales_invoice.invoice_sent_on:
            print("Invoice '{0}' was already sent on: {1}".format(sales_invoice.name, sales_invoice.invoice_sent_on))
            return

        # Do not send any invoice if the items are free of charge
        if sales_invoice.total == 0:
            return

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

            target_email = invoice_contact.email_id
            if not target_email:
                frappe.log_error( "Unable to send {0}: no email address found.".format(sales_invoice.name), "Sending invoice email failed")
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
                subject = "Rechnung {0}".format(sales_invoice.name)
                message = "Sehr geehrter Kunde<br>Bitte beachten Sie die angehängte Rechnung '{0}'.<br>Beste Grüsse<br>Administration<br><br>{1}".format(sales_invoice.name, footer)
            elif sales_invoice.language == "fr":
                subject = "Facture {0}".format(sales_invoice.name)
                message = "Cher client<br>Veuillez consulter la facture ci-jointe '{0}'.<br>Meilleures salutations<br>Administration<br><br>{1}".format(sales_invoice.name, footer)
            else:
                subject = "Invoice {0}".format(sales_invoice.name)
                message = "Dear Customer<br>Please find attached the invoice '{0}'.<br>Best regards<br>Administration<br><br>{1}".format(sales_invoice.name, footer)

            make(
                recipients = target_email,
                sender = "info@microsynth.ch",
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
            # create ARIBA cXML input data dict
            data = sales_invoice.as_dict()
            data['customer_record'] = customer.as_dict()
            cxml_data = create_dict_of_invoice_info_for_cxml(sales_invoice)

            cxml = frappe.render_template("microsynth/templates/includes/ariba_cxml.html", cxml_data)
            #print(cxml)

            # TODO: comment in after development to save ariba file to filesystem
            with open('/home/libracore/Desktop/'+ sales_invoice.name, 'w') as file:
                file.write(cxml)
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
            # create Paynet cXML input data dict
            cxml_data = create_dict_of_invoice_info_for_cxml(sales_invoice)
            
            cxml = frappe.render_template("microsynth/templates/includes/paynet_cxml.html", cxml_data)
            #print(cxml)

            # TODO: comment in after development to save ariba file to filesystem
            with open('/home/libracore/Desktop/'+ sales_invoice.name, 'w') as file:
                file.write(cxml)

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
            print("IN GEP")
            # create Gep cXML input data dict
            cxml_data = create_dict_of_invoice_info_for_cxml(sales_invoice)
            cxml = frappe.render_template("microsynth/templates/includes/gep_cxml.html", cxml_data)
            print(cxml)

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

        frappe.db.commit()

    except Exception as err:
        frappe.log_error("Cannot transmit sales invoice {0}: \n{1}".format(sales_invoice.name, err), "invoicing.transmit_sales_invoice")

    return
