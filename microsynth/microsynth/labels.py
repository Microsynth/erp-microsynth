# -*- coding: utf-8 -*-
# Copyright (c) 2022, libracore (https://www.libracore.com) and contributors
# For license information, please see license.txt

import frappe
import socket
import sys
from datetime import datetime
from microsynth.microsynth.shipping import get_shipping_service, get_shipping_item, create_receiver_address_lines, get_sender_address_line

NOVEXX_PRINTER_TEMPLATE = "microsynth/templates/includes/address_label_novexx.html"
BRADY_PRINTER_TEMPLATE = "microsynth/templates/includes/address_label_brady.html"

def print_raw(ip, port, content):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect((ip, port))
    s.send(content.encode())
    s.close()
    return


def print_test_label_brady():
    """Test functions are hardcoded to specific printer IPs and are useful only during initial development - delete after finishing development"""
    
    content = ''';###load Microsynth logo###
M l IMG;01_MIC_Logo_Swiss_black

m m
J
H 100
S 0,-2.5,145,150,105
O R

; ###Microsynth logo, rotated 90 degree###
I 100,137,180,2,2;01_MIC_Logo_Swiss_black

;###print date and time during development###

;T 1,140,0,3,pt 10;[DATE]-[TIME]-function: print_test_label_brady
A 1
'''
    print_raw('192.0.1.71', 9100, content )


def print_test_label_novexx():
    """Test functions are hardcoded to specific printer IPs and are useful only during initial development - delete after finishing development"""
    
    content = '''#!A1
#IMS105/148
#N13
#ER

#T19#J28.6#YG/3///C:\Logos\Microsynth_black_140x27.bmp#G

#T4#J130#YN101/0U/45///Schützenstrasse 15, 9436 Balgach#G
#T4#J127#YL0/0/0.5/95

#T60#J105#YN101/3U/45///first address line#G

#T78#J54#YN101/3U/85///some country#G
#T75#J54#YN101/3U/45///postal service#G
#T69#J22#YR0/0/0.5/15/33

#T4#J105#YN101/3U/45///hardcoded from print_test_label_novexx#G
#Q1/
#!P1
'''
    print_raw('192.0.1.72', 9100, content )

def choose_brady_printer(company):
    """
    Returns the Brady printer specified for the user with the 'User Printer' DocType
    or alternatively the one defined in 'Sequencing Settings'.

    Printers have to be set in Sequencing Settings based on company name. The IP and port 
    of the printer are specified on the 'Brady Printer' DocType. 
    """
    
    # check if there is a user-specific printer
    user = frappe.get_user()
    if frappe.db.exists("User Printer", user.name):
        printer_name = frappe.get_value("User Printer", user.name, "label_printer")
        printer = frappe.get_doc("Brady Printer", printer_name)

        return printer

    # Austria labels will be handled in by Microsynth AG
    if company == "Microsynth Austria GmbH": 
        company = "Microsynth AG"
    
    if not company: 
        frappe.throw("Company missing for deciding on printer IP")

    settings = frappe.get_doc("Sequencing Settings", "Sequencing Settings")
    for printer in settings.label_printers:
        if printer.company == company:
            printer = frappe.get_doc("Brady Printer", printer.brady_printer)
            return printer


def get_label_data(sales_order):
    """
    Returns the data for printing a shipping label from a sales order document.
    """
    
    if not sales_order.shipping_address_name:
        frappe.throw("Sales Order '{0}': Address missing".format(sales_order.name))
    elif not sales_order.customer: 
        frappe.throw("Sales Order '{0}': Customer missing".format(sales_order.name))
    elif not sales_order.contact_person: 
        frappe.throw("Sales Order '{0}': Contact missing".format(sales_order.name))

    if sales_order.shipping_contact:
        contact_id = sales_order.shipping_contact
    else:
        contact_id = sales_order.contact_person

    shipping_item = get_shipping_item(sales_order.items)

    address_id = sales_order.shipping_address_name
    shipping_address = frappe.get_doc("Address", address_id)
    destination_country = frappe.get_doc("Country", shipping_address.country)

    data = {
        'lines': create_receiver_address_lines(customer_id = sales_order.customer, contact_id = contact_id, address_id = address_id), 
        'sender_header': get_sender_address_line(sales_order, destination_country),
        'destination_country': shipping_address.country,
        'shipping_service': get_shipping_service(shipping_item, shipping_address, sales_order.customer),
        'po_no': sales_order.po_no,
        'web_id': sales_order.web_order_id,
        'cstm_id': sales_order.customer,
        'oligo_count': len(sales_order.oligos)
    }
    return data


@frappe.whitelist()
def print_shipping_label(sales_order_id):
    """
    function calls respective template for creating a transport label
    """

    sales_order = frappe.get_doc("Sales Order", sales_order_id)    
    label_data = get_label_data(sales_order)
    content = frappe.render_template(BRADY_PRINTER_TEMPLATE, label_data)   

    printer = choose_brady_printer(sales_order.company)

    #print(content)
    print_raw(printer.ip, printer.port, content)
    sales_order.label_printed_on = datetime.now()
    sales_order.save()
    frappe.db.commit()


@frappe.whitelist()
def print_oligo_order_labels(sales_orders):
    """
    Prints the shipping labels from a list of sales order names.

    Run
    bench execute "microsynth.microsynth.labels.print_oligo_order_labels" --kwargs "{'sales_orders': ['SO-BAL-22011340']}"
    """    
    settings = frappe.get_doc("Flushbox Settings", "Flushbox Settings")

    for o in sales_orders:
        try:
            sales_order = frappe.get_doc("Sales Order", o)
            label_data = get_label_data(sales_order)
            content = frappe.render_template(NOVEXX_PRINTER_TEMPLATE, label_data)
            
            print_raw(settings.label_printer_ip, settings.label_printer_port, content)
            sales_order.label_printed_on = datetime.now()
            sales_order.save()    
            frappe.db.commit()
        except Exception as err:
            frappe.log_error("Error printing label for '{0}':\n{1}".format(sales_order.name, err), "print_oligo_order_labels")
    return