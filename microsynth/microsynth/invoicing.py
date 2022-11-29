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
import datetime
import json

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
            if cint(dn.get('collective_billing')) == 0:
                if mode == "Post":
                    if dn.get('invoicing_method') == "Post":
                        make_invoice(dn.get('delivery_note'))
                else:
                    if dn.get('invoicing_method') != "Post":
                        make_invoice(dn.get('delivery_note'))
    else:
        # colletive invoices
        customers = []
        for dn in all_invoiceable:
            if cint(dn.get('collective_billing')) == 1 and dn.get('customer') not in customers:
                customers.append(dn.get('customer'))
        
        # for each customer, create one invoice for all dns
        for c in customers:
            dns = []
            for dn in all_invoiceable:
                if cint(dn.get('collective_billing')) == 1 and dn.get('customer') == c:
                    dns.append(dn.get('delivery_note'))
                    
            if len(dns) > 0:
                make_collective_invoice(dns)
            
    return

def make_invoice(delivery_note):
    sales_invoice_content = make_sales_invoice(delivery_note)
    # compile document
    sales_invoice = frappe.get_doc(sales_invoice_content)
    sales_invoice.set_advances()    # get advances (customer credit)
    sales_invoice.insert()
    sales_invoice.submit()
    transmit_sales_invoice(sales_invoice.name)
    frappe.db.commit()
    return
    
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
    transmit_sales_invoice(sales_invoice.name)
    frappe.db.commit()
    return

def create_list_of_item_dicts_for_cxml(sales_invoice):
    """creates a list of dictionaries of all items of a sales_invoice (including shipping item)"""

    list_of_invoiced_items = []
    
    invoice_item_dicts = {}
    for item in sales_invoice.items:
        invoice_item_dicts[item.item_code] = item

    invoiced_oligos = {}
    invoice_position = 0
    for oligo_link in sales_invoice.oligos: 
        invoice_position += 1 
        oligo_object = frappe.get_doc("Oligo", oligo_link.as_dict()["oligo"])
        #print ("\nOLIGO '%s', OLIGO-Info:\n====\n%s"  %(oligo_link.as_dict()["oligo"], oligo_object.as_dict() ))
        oligo_details = {}
        oligo_details[oligo_object.name] = oligo_object
        oligo_details["position"] = invoice_position
        oligo_details["price"] = 0
        for oligo_item in oligo_object.items:
            oligo_details["price"] += oligo_item.qty * invoice_item_dicts[oligo_item.item_code].rate
        invoiced_oligos[oligo_object.name] = oligo_details
    list_of_invoiced_items.append(invoiced_oligos)
    
    # TODO
    #for item in sales_invoice.samples:
            # list_of_item_dicts.append(item_dict)

    return list_of_invoiced_items


def get_shipping_item(items):
    for i in reversed(items):
        if i.item_group == "Shipping":
            return i.item_code


def create_country_name_to_code_dict(): 
    
    country_codes = {}
    country_query = frappe.get_all("Country", fields=['name', 'code'])
    for dict in country_query:
        country_codes[dict['name']] = dict['code']
    return country_codes


def create_dict_of_invoice_info_for_cxml(sales_invoice=None): 
    """ Doc string """

    print ("\n1")
    #for key, value in (sales_invoice.as_dict()["taxes"][0].items()): 
    #    print ("%s: %s" %(key, value))

    shipping_address = frappe.get_doc("Address", sales_invoice.shipping_address_name)
    
    print ("\n1")
    billing_address = frappe.get_doc("Address", sales_invoice.customer_address)
    #for key, value in (billing_address.as_dict().items()): 
    #    print ("%s: %s" %(key, value))

    customer = frappe.get_doc("Customer", sales_invoice.customer)
    #for key, value in (customer.as_dict().items()): 
    #   print ("%s: %s" %(key, value))
    # print(customer.as_dict())

    print ("\n-----0-----")
    company_details = frappe.get_doc("Company", sales_invoice.company)
    #print(company_details.as_dict())
    #for key, value in (company_details.as_dict().items()): 
    #   print ("%s: %s" %(key, value))
    
    #for key, value in (company_details.as_dict().items()): 
    #   print ("%s: %s" %(key, value))
    # print(company_details.default_bank_account.split("-")[1].strip().split(" ")[1].strip())

    print ("\n-----0A-----")
    company_address = frappe.get_doc("Address", sales_invoice.company_address)
    #print(company_address.as_dict())

    print ("\n-----0B-----")
    if sales_invoice.currency in ["EUR", "USD"]:
        bank_accounts = frappe.get_all("Account", 
                        filters = {
                            "company" : sales_invoice.company, 
                            "account_type" : "Bank",
                            "currency": sales_invoice.currency, 
                            "disabled": 0
                            },
                            fields = ["name"]
                        )
        if len(bank_accounts) > 0: 
            bank_account = frappe.get_doc("Account", bank_accounts[0]["name"])
        else:
            frappe.throw("No valid bank account")
    else: 
        bank_account = frappe.get_doc("Account", company_details.default_bank_account)

    # Wenn curr = eur dann company = sales_invoice.company, account type=bank,  

    #for key, value in (bank_account.as_dict().items()): 
    #   print ("%s: %s" %(key, value))

    #print(sales_invoice.as_dict()["taxes"][0]["creation"].strftime("%Y-%m-%dT%H:%M:%S+01:00"),
    #for key, value in (company_details.as_dict().items()): 
    #    print ("%s: %s" %(key, value))

    country_codes = create_country_name_to_code_dict()
    itemList = create_list_of_item_dicts_for_cxml(sales_invoice)
    data2 = {'basics' : {'sender_network_id' :  'AN01429401165-DEV',
                        'receiver_network_id':  'AN01003603018-DEV',
                        'shared_secret':        'secret1',
                        'paynet_sender_pid':    '41010164914873673', 
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
                        'iso_country_code': country_codes[company_address.country], 
                        'supplier_tax_id':  company_details.tax_id + ' MWST' 
                        },
            'billTo' : {'address_id':       'TODO: C028Bau WSJ103', 
                        'name':             billing_address.name,
                        'street':           billing_address.address_line1,
                        'pin':              billing_address.pincode,
                        'city':             billing_address.city,
                        'iso_country_code': country_codes[billing_address.country]
                        },
            'from' :    {'name':            company_details.company_name,
                        'street':           company_address.address_line1, 
                        'pin':              company_address.pincode,
                        'city':             company_address.city,
                        'iso_country_code': country_codes[company_address.country]
                        }, 
            'soldTo' :  {'address_id':      'TODO: C028Bau WSJ103', 
                        'name':             sales_invoice.customer_name,
                        'street':           billing_address.address_line1,
                        'pin':              billing_address.pincode,
                        'city':             billing_address.city,
                        'iso_country_code': country_codes[billing_address.country]
                        }, 
            'shipFrom' : {'name':           company_details.name, 
                        'street':           company_address.address_line1,
                        'pin':              company_address.pincode,
                        'city':             company_address.city,
                        'iso_country_code': country_codes[company_address.country]
                        },
            'shipTo' : {'address_id':       '', # TODO: !!! shipping address must be read from order specific shippign address transferred during punchout
                        'name':             shipping_address.name,
                        'street':           shipping_address.address_line1,
                        'pin':              shipping_address.pincode,
                        'city':             shipping_address.city,
                        'iso_country_code': country_codes[shipping_address.country]
                        }, 
            'receivingBank' : {'swift_id':  bank_account.bic,
                        'iban_id':          bank_account.iban,
                        'account_name':     bank_account.company,
                        'account_id':       bank_account.iban,
                        'account_type':     'Checking',  
                        'branch_name':      "" # TODO bank_account.branch
                        }, 
            'extrinsic' : {'buyerVatID':                customer.tax_id + ' MWST',
                        'supplierVatID':                company_details.tax_id + ' MWST',
                        'supplierCommercialIdentifier': company_details.tax_id + 'VAT' 
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
                        'taxPointDate':         sales_invoice.as_dict()["taxes"][0]["creation"].strftime("%Y-%m-%dT%H:%M:%S+01:00"),
                        'description':          '0.0' + '% shipping tax'
                        }, 
            'summary' : {'subtotal_amount' :        sales_invoice.base_total,
                        'shipping_amount' :         '0.00',
                        'gross_amount' :            sales_invoice.net_total,
                        'total_amount_without_tax': sales_invoice.net_total,
                        'net_amount' :              sales_invoice.net_total,
                        'due_amount' :              sales_invoice.rounded_total
                        }
            }
    return data2


def transmit_sales_invoice():
#def transmit_sales_invoice(sales_invoice_name):
    """
    This function will check a transfer moe and transmit the invoice
    """

    sales_invoice_name = "SI-BAL-22000002"

    sales_invoice = frappe.get_doc("Sales Invoice", sales_invoice_name)
    customer = frappe.get_doc("Customer", sales_invoice.customer)
    
    # TODO: comment-in after development to handle invoice paths other than ariba
    '''
    if customer.invoicing_method == "Email":
        # send by mail
        target_email = customer.get("invoice_email") or sales_invoice.get("contact_email")
        if not target_email:
            frappe.log_error( "Unable to send {0}: no email address found.".format(sales_invoice__name), "Sending invoice email failed")
            return
        
        # TODO: send email with content & attachment
        
    elif customer.invoicing_method == "Post":
        # create and attach pdf
        execute({
            'doctype': 'Sales Invoice',
            'name': sales_invoice_name,
            'title': sales_invoice.title,
            'lang': sales_invoice.language,
            'print_format': "Sales Invoice",             # TODO: from configuration
            'is_private': 1
        })
        attachments = get_attachments("Communication", communication)
        fid = None
        for a in attachments:
            fid = a['name']
        # send mail to printer relais
        send(
            recipients="print@microsynth.local",        # TODO: config 
            subject=sales_invoice_name, 
            message=sales_invoice_name, 
            reference_doctype="Sales Invoice", 
            reference_name=sales_invoice_name,
            attachments=[{'fid': fid}]
        )
                
        pass
    elif customer.invoicing_method == "ARIBA":
    '''    
        # create ARIBA cXML input data dict
    data = sales_invoice.as_dict()
    data['customer_record'] = customer.as_dict()

    cxml_data = create_dict_of_invoice_info_for_cxml(sales_invoice)

    cxml = frappe.render_template("microsynth/templates/includes/ariba_cxml.html", cxml_data)
    #print(cxml)

    # TODO: comment in after development to save ariba file to filesystem
    '''
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

    elif customer.invoicing_method == "Paynet":
       
        cxml_data = create_dict_of_invoice_info_for_cxml(sales_invoice)

        cxml = frappe.render_template("microsynth/templates/includes/paynet_cxml.html", cxml_data)
        #print(cxml)

        # TODO: comment in after development to save ariba file to filesystem
    
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

        # transmit to target
        # TODO
        
    return
        
        
