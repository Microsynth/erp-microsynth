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
from frappe.email.queue import send
from frappe.desk.form.load import get_attachments
from microsynth.microsynth.utils import get_physical_path
from microsynth.microsynth.credits import allocate_credits, book_credit
import datetime
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
    all_invoiceable = get_data(filters={'company': company})
    
    if (mode in ["Post", "Electronic"]):
        # individual invoices
        for dn in all_invoiceable:
            if cint(dn.get('is_punchout') == 1):
                si = make_punchout_invoice(dn.get('delivery_note'))
                transmit_sales_invoice(si)

            if cint(dn.get('collective_billing')) == 0:
                if mode == "Post":
                    if dn.get('invoicing_method') == "Post":
                        si = make_invoice(dn.get('delivery_note'))
                        transmit_sales_invoice(si)
                else:
                    # TODO there seems to be an issue here: both branches ("Post"/ not "Post") do the same
                    if dn.get('invoicing_method') != "Post":
                        si = make_invoice(dn.get('delivery_note'))
                        transmit_sales_invoice(si)
    elif mode == "Collective":
        # colletive invoices
        customers = []
        for dn in all_invoiceable:
            if cint(dn.get('collective_billing')) == 1 and cint(dn.get('is_punchout')) != 1 and dn.get('customer') not in customers:
                customers.append(dn.get('customer'))
        
        # for each customer, create one invoice for all dns
        for c in customers:
            dns = []
            for dn in all_invoiceable:
                if cint(dn.get('collective_billing')) == 1 and cint(dn.get('is_punchout')) != 1 and dn.get('customer') == c:
                    dns.append(dn.get('delivery_note'))

            if len(dns) > 0:
                si = make_collective_invoice(dns)
                transmit_sales_invoice(si)
    else:
        frappe.throw("Unknown mode '{0}' for async_create_invoices".format(mode))

    return

def make_invoice(delivery_note):
    """
    Includes customer credits. Do not use for customer projects.

    run
    bench execute microsynth.microsynth.invoicing.make_invoice --kwargs "{'delivery_note':'DN-BAL-23106510'}"
    """
    sales_invoice_content = make_sales_invoice(delivery_note)
    # compile document
    sales_invoice = frappe.get_doc(sales_invoice_content)
    sales_invoice.invoice_to = frappe.get_value("Customer", sales_invoice.customer, "invoice_to") # replace contact with customer's invoice_to contact
    #sales_invoice.set_advances()    # get advances (customer credit)
    sales_invoice = allocate_credits(sales_invoice)         # check and allocated open customer credits
    
    sales_invoice.insert()
    sales_invoice.submit()
    # if a credit was allocated, book credit account
    if cint(sales_invoice.total_customer_credit) > 0:
        book_credit(sales_invoice.name, sales_invoice.total_customer_credit)
        
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
    # create invoice from first delivery note
    sales_invoice_content = make_sales_invoice(delivery_notes[0])
    if len(delivery_notes) > 1:
        for i in range(1, len(delivery_notes)):
            # append items from other delivery notes
            sales_invoice_content = make_sales_invoice(source_name=delivery_notes[i], target_doc=sales_invoice_content)
    
    # compile document
    sales_invoice = frappe.get_doc(sales_invoice_content)
    sales_invoice.set_advances()    # get advances (customer credit)
    sales_invoice.insert()
    sales_invoice.submit()
    frappe.db.commit()

    return sales_invoice.name


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


def transmit_sales_invoice(sales_invoice_name):
    """
    This function will check the transfer mode and transmit the invoice
    """

    sales_invoice = frappe.get_doc("Sales Invoice", sales_invoice_name)
    customer = frappe.get_doc("Customer", sales_invoice.customer)

    #for k,v in sales_order.as_dict().items():
    #    print ( "%s: %s" %(k,v))

    # TODO: comment-in after development to handle invoice paths other than ariba
    
    # TODO: handle punchout invoices different!
    if sales_invoice.is_punchout:
        return

    if customer.invoicing_method == "Email":
        # send by mail

        # TODO check sales_invoice.invoice_to --> if it has a e-mail --> this is target-email

        target_email = sales_invoice.get("contact_email") # or customer.get("invoice_email")

        if not target_email:
            frappe.log_error( "Unable to send {0}: no email address found.".format(sales_invoice_name), "Sending invoice email failed")
            return
        
        # TODO: send email with content & attachment
        # send(
        #     recipients="print@microsynth.local",        # TODO: config 
        #     subject=sales_invoice_name, 
        #     message=sales_invoice_name, 
        #     reference_doctype="Sales Invoice", 
        #     reference_name=sales_invoice_name,
        #     attachments=[{'fid': fid}]
        # )

    elif customer.invoicing_method == "Post":
        # create and attach pdf to the document
        execute(
            doctype = 'Sales Invoice',
            name =  sales_invoice_name,
            title = sales_invoice.title,
            lang = sales_invoice.language,
            print_format = "Sales Invoice",             # TODO: from configuration
            is_private = 1
        )
        attachments = get_attachments("Sales Invoice", sales_invoice_name)
        fid = None
        for a in attachments:
            fid = a['name']
        frappe.db.commit()
        
        # print the pdf with cups        
        path = get_physical_path(fid)
        PRINTER = "HP_LaserJet_M554"
        import subprocess
        subprocess.run(["lp", path, "-d", PRINTER])

        # # send mail to printer relais
        # send(
        #     recipients="print@microsynth.local",        # TODO: config 
        #     subject=sales_invoice_name, 
        #     message=sales_invoice_name, 
        #     reference_doctype="Sales Invoice", 
        #     reference_name=sales_invoice_name,
        #     attachments=[{'fid': fid}]
        # )
        pass

    elif customer.invoicing_method == "ARIBA":
        # create ARIBA cXML input data dict
        data = sales_invoice.as_dict()
        data['customer_record'] = customer.as_dict()
        cxml_data = create_dict_of_invoice_info_for_cxml(sales_invoice)

        cxml = frappe.render_template("microsynth/templates/includes/ariba_cxml.html", cxml_data)
        #print(cxml)

        # TODO: comment in after development to save ariba file to filesystem
        with open('/home/libracore/Desktop/'+ sales_invoice_name, 'w') as file:
            file.write(cxml)
        '''
        # attach to sales invoice
        folder = create_folder("ariba", "Home")
        # store EDI File  
    
        f = save_file(
            "{0}.txt".format(sales_invoice_name), 
            cxml, 
            "Sales Invoice", 
            sales_invoice_name, 
            folder = '/home/libracore/Desktop',
            # folder=folder, 
            is_private=True
        )
        '''

    elif customer.invoicing_method == "Paynet":
        # create Paynet cXML input data dict
        cxml_data = create_dict_of_invoice_info_for_cxml(sales_invoice)
        
        cxml = frappe.render_template("microsynth/templates/includes/paynet_cxml.html", cxml_data)
        #print(cxml)

        # TODO: comment in after development to save ariba file to filesystem
        with open('/home/libracore/Desktop/'+ sales_invoice_name, 'w') as file:
            file.write(cxml)

        '''
        # TODO: comment in after development to save paynet file to filesystem
    
        # attach to sales invoice
        folder = create_folder("ariba", "Home")
        # store EDI File
        
        f = save_file(
            "{0}.txt".format(sales_invoice_name), 
            cxml, 
            "Sales Invoice", 
            sales_invoice_name, 
            folder=folder, 
            is_private=True
        )
        '''
    
    elif customer.invoicing_method == "GEP":
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
            "{0}.txt".format(sales_invoice_name), 
            cxml, 
            "Sales Invoice", 
            sales_invoice_name, 
            folder=folder, 
            is_private=True
        )
        '''

        
    return
        
        
