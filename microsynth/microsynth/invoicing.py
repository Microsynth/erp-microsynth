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
        item_dict['invoiceLineNumber']  = 'val'
        item_dict['quantity']           = item.qty
        item_dict['unit_of_measure']    = 'EA' if item.stock_uom == "Nos" else "???"
        item_dict['unit_price']         = item.rate
        item_dict['supplier_part_id']   = 'val'
        item_dict['description']        = 'val'
        item_dict['subtotal_amount']    = item.amount
        item_dict['tax_amount']         = 'val'
        item_dict['tax_rate']           = item.item_tax_rate
        item_dict['tax_taxable_amount'] = 'val'
        item_dict['tax_description']    = 'val'
        item_dict['gross_amount']       = 'val'
        item_dict['net_amount']         = 'val'
        list_of_item_dicts.append(item_dict)
    return list_of_item_dicts


def create_dict_of_invoice_info_for_cxml(sales_invoice=None): 
    """ Doc string """

    shipping_address = frappe.get_doc("Address", sales_invoice.shipping_address_name)
    billing_address = frappe.get_doc("Address", sales_invoice.customer_address)
    customer = frappe.get_doc("Customer", sales_invoice.customer)
    # print(customer.as_dict())
    
    company_details = frappe.get_doc("Company", sales_invoice.company)
    # print(company_details.as_dict())
    print ("\n-----0-----")
    for key, value in (company_details.as_dict().items()): 
        print ("%s: %s" %(key, value))
    
    print ("\n-----0A-----")
    print(company_details.default_bank_account.split("-")[1].strip().split(" ")[1].strip())
    
    # for key, value in (sales_invoice.as_dict().items()): 
    #    print ("%s: %s" %(key, value))
    
    print ("\n1")
    #for key, value in (sales_invoice.as_dict()["taxes"][0].items()): 
    #    print ("%s: %s" %(key, value))
    
    itemList = create_list_of_item_dicts_for_cxml(sales_invoice)
    data2 = {'basics' : {'sender_network_id' :  'AN01429401165-DEV',
                        'receiver_network_id':  'AN01003603018-DEV',
                        'shared_secret':        'secret1',
                        'order_id':             '1234567', 
                        'currency':             sales_invoice.currency,
                        'invoice_id':           'id_123',
                        'invoice_date':         'invoice_date2022'},
            'remitTo' : {'name':            sales_invoice.company,
                        'street':           'sender_street1', 
                        'zip':              'sender_zip1',
                        'town':             'sender_town1', 
                        'iso_country_code': 'CH', 
                        'supplier_tax_id':  'CHE-107.542.107 MWST'
                        },
            'billTo' : {'address_id':       'C028Bau WSJ103', 
                        'name':             billing_address.name,
                        'street':           billing_address.address_line1,
                        'zip':              billing_address.pincode,
                        'town':             billing_address.city,
                        'iso_country_code': billing_address.country
                        },
            'from' :    {'name':            sales_invoice.company,
                        'street':           'receiver_street1', 
                        'zip':              'receiver_zip1',
                        'town':             'receiver_town1',
                        'iso_country_code': 'taccatuccaland'
                        }, 
            'soldTo' :  {'address_id':      'C028Bau WSJ103', 
                        'name':             sales_invoice.customer_name,
                        'street':           'someStreet',
                        'zip':              'receiver_zip1',
                        'town':             'receiver_town1',
                        'iso_country_code': 'taccatuccaland'
                        }, 
            'shipFrom' : {'name':           'receiver_name1', 
                        'street':           'receiver_street1',
                        'zip':              'receiver_zip1',
                        'town':             'receiver_town1',
                        'iso_country_code': 'taccatuccaland'
                        },
            'shipTo' : {'address_id':       'C028Bau WSJ103',
                        'name':             shipping_address.name,
                        'street':           shipping_address.address_line1,
                        'zip':              shipping_address.pincode,
                        'town':             shipping_address.city,
                        'iso_country_code': shipping_address.country
                        }, 
            'receivingBank' : {'swift_id':  'swift_id',
                        'iban_id':          company_details.default_bank_account.split("-")[1].strip().split(" ")[1].strip(),
                        'account_name':     company_details.name, #'account_name',
                        'account_id':       'account_id',
                        'account_type':     'account_type',
                        'branch_name':      'branch_name'
                        }, 
            'extrinsic' : {'buyerVatID':                'TODO: GET VAT Customer - CHE-116.268.023 MWST',
                        'supplierVatID':                sales_invoice.tax_id + 'MWST',
                        'supplierCommercialIdentifier': sales_invoice.tax_id + 'VAT'
                        }, 
            'items' :   itemList, 
            'tax' :     {'amount' :         sales_invoice.as_dict()["taxes"][0]["tax_amount"],
                        'taxable_amount' :  sales_invoice.as_dict()["taxes"][0]["total"],
                        'percent' :         sales_invoice.as_dict()["taxes"][0]["rate"],
                        'taxPointDate' :    sales_invoice.as_dict()["taxes"][0]["creation"].strftime("%Y-%m-%dT%H:%M:%S+01:00"),
                        'description' :     str(sales_invoice.as_dict()["taxes"][0]["rate"]) + '% Swiss VAT'
                        },
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
                        'due_amount' :              sales_invoice.total_billing_amount
                        }
            }
    print("DictXY: " + data2["receivingBank"]["account_name"])
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
    # print(cxml)

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
        
        
