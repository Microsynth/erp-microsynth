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
    
    list_of_item_dicts = []
    
    for item in sales_invoice.items:
        item_dict = {}
        item_dict['invoiceLineNumber']  = item.idx
        item_dict['quantity']           = item.qty
        item_dict['unit_of_measure']    = 'EA' if item.stock_uom == "Nos" else "???"
        item_dict['unit_price']         = item.rate
        item_dict['supplier_part_id']   = item.item_code
        item_dict['description']        = item.description
        item_dict['subtotal_amount']    = item.amount
        item_dict['tax_amount']         = round(json.loads(sales_invoice.as_dict()["taxes"][0]["item_wise_tax_detail"])[item_dict['supplier_part_id']][1], 2)
        item_dict['tax_rate']           = json.loads(sales_invoice.as_dict()["taxes"][0]["item_wise_tax_detail"])[item_dict['supplier_part_id']][0]
        item_dict['tax_taxable_amount'] = item.amount
        item_dict['tax_description']    = 'TODO!!!!'
        item_dict['gross_amount']       = item_dict['tax_amount']
        item_dict['net_amount']         = item_dict['tax_amount']
        list_of_item_dicts.append(item_dict)
    return list_of_item_dicts


def create_dict_of_invoice_info_for_cxml(sales_invoice=None): 
    """ Doc string """


    #for key, value in (sales_invoice.as_dict().items()): 
    #    print ("%s: %s" %(key, value))
    #print(sales_invoice.as_dict()["creation"].strftime("%Y-%m-%dT%H:%M:%S+01:00"))

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

    # TODO
    #company_address = frappe.get_doc("Address", sales_invoice.shipping_address_name)
    company_address = {}

    print ("\n-----0B-----")
    bank_account = frappe.get_doc("Account", company_details.default_bank_account)
    #for key, value in (bank_account.as_dict().items()): 
    #   print ("%s: %s" %(key, value))

    #print(sales_invoice.as_dict()["taxes"][0]["creation"].strftime("%Y-%m-%dT%H:%M:%S+01:00"),
    #for key, value in (company_details.as_dict().items()): 
    #    print ("%s: %s" %(key, value))

    # load all country codes
    country_codes = {}

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
                        'delivery_note_id':     "", # delivery_note.name,
                        'delivery_note_date_paynet':  "" # delivery_note.as_dict()["creation"].strftime("%Y%m%d"),
                        },
            'remitTo' : {'name':            sales_invoice.company,
                        'street':           "", # company_address.address_line1, 
                        'pin':              "", # company_address.pincode,
                        'city':             "", # company_address.city, 
                        'iso_country_code': "CH", #country_codes[company_address.country], 
                        'supplier_tax_id':  'CHE-107.542.107 MWST' # might be company.tax_id
                        },
            'billTo' : {'address_id':       'TODO: C028Bau WSJ103', 
                        'name':             billing_address.name,
                        'street':           billing_address.address_line1,
                        'pin':              billing_address.pincode,
                        'city':             billing_address.city,
                        'iso_country_code': "CH" #country_codes[billing_address.country]
                        },
            'from' :    {'name':            company_details.company_name,
                        'street':           "", # company_address.address_line1, 
                        'pin':              "", # company_address.pincode,
                        'city':             "", # company_address.city,
                        'iso_country_code': "CH" # country_codes[company_address.country]
                        }, 
            'soldTo' :  {'address_id':      'TODO: C028Bau WSJ103', 
                        'name':             sales_invoice.customer_name,
                        'street':           billing_address.address_line1,
                        'pin':              billing_address.pincode,
                        'city':             billing_address.city,
                        'iso_country_code': "CH" #country_codes[billing_address.country]
                        }, 
            'shipFrom' : {'name':           company_details.name, 
                        'street':           "", # company_address.address_line1,
                        'pin':              "", # company_address.pincode,
                        'city':             "", # company_address.city,
                        'iso_country_code': "CH" #country_codes[company_address.country]
                        },
            'shipTo' : {'address_id':       '', # TODO: !!! shipping address must be read from order specific shippign address transferred during punchout
                        'name':             shipping_address.name,
                        'street':           shipping_address.address_line1,
                        'pin':              shipping_address.pincode,
                        'city':             shipping_address.city,
                        'iso_country_code': "CH" #country_codes[shipping_address.country]
                        }, 
            'receivingBank' : {'swift_id':  'swift_id',     # TODO
                        'iban_id':          bank_account.iban,
                        'account_name':     bank_account.company,
                        'account_id':       'account_id',   # TODO
                        'account_type':     'Checking',     # TODO
                        'branch_name':      'branch_name'   # TODO
                        }, 
            'extrinsic' : {'buyerVatID':                sales_invoice.tax_id + ' MWST',
                        'supplierVatID':                'CHE-107.542.107 MWST', # might be company.tax_id
                        'supplierCommercialIdentifier': 'CHE-107.542.107 VAT'   # might be company.tax_id
                        }, 
            'items' :   itemList, 
            'tax' :     {'amount' :         sales_invoice.as_dict()["taxes"][0]["tax_amount"],
                        'taxable_amount' :  sales_invoice.as_dict()["taxes"][0]["total"],
                        'percent' :         sales_invoice.as_dict()["taxes"][0]["rate"],
                        'taxPointDate' :    sales_invoice.as_dict()["taxes"][0]["creation"].strftime("%Y-%m-%dT%H:%M:%S+01:00"),
                        'description' :     str(sales_invoice.as_dict()["taxes"][0]["rate"]) + '% Swiss VAT'
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
    #print("DictXY: " + str(data2["items"]))
    return data2


def transmit_sales_invoice():
#def transmit_sales_invoice(sales_invoice_name):
    """
    This function will check a transfer moe and transmit the invoice
    """

    sales_invoice_name = "SI-BAL-22000001"

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
    '''

        # transmit to target
        # TODO
        
    return
        
        
