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
    sales_invoice.insert()
    sales_invoice.submit()
    transmit_sales_invoice(sales_invoice.name)
    frappe.db.commit()
    return

"""
This function will check a transfer moe and transmit the invoice
"""
def transmit_sales_invoice(sales_invoice_name):
    sales_invoice = frappe.get_doc("Sales Invoice", sales_invoice_name)
    customer = frappe.get_doc("Customer", sales_invoice.customer)
    if customer.invoicing_method == "Email":
        # send by mail
        target_email = customer.get("invoice_email") or sales_invoice.get("contact_email")
        if not target_email:
            frappe.log_error( "Unable to send {0}: no email address found.".format(sales_invoice__name), "Sending invoice email failed")
            return
        
        # TODO: send email with content & attachment
        
    elif customer.invoicing_method == "Post":
        # create and attach pdf
        execute(
            'doctype': 'Sales Invoice',
            'name': sales_invoice_name,
            'title': sales_invoice.title,
            'lang': sales_invoice.language,
            'print_format': "Sales Invoice",             # TODO: from configuration
            'is_private': 1
        )
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
        # create ARIBA cXML
        data = sales_invoice.as_dict()
        data['customer_record'] = customer.as_dict()
        cxml = frappe.render_template("microsynth/templates/includes/ariba_cxml.html", data)
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

        # transmit to target
        # TODO
        
    return
        
        
