# -*- coding: utf-8 -*-
# Copyright (c) 2022, libracore (https://www.libracore.com) and contributors
# For license information, please see license.txt

import frappe
import socket
import sys
from datetime import datetime


def get_shipping_service(item_code, ship_adr,cstm_ID):
    
    SHIPPING_SERVICES = {
        '1100': "P.P.A",
        '1101': "A-plus", 
        '1102': "Express", 
        '1103': "Austria",
        '1104': "Einschreiben",
        '1105': "EMS",    
        '1106': "Germany",
        '1107': "DryIce",
        '1108': "DHL",
        '1110': "Abholung",
        '1112': "Germany",
        '1113': "DryIce",
        '1114': "DHL",
        '1115': "Germany",
        '1117': "DHL",
        '1120': "DHL CH",  # not for EU
        '1122': "DHL",
        '1123': "DHL/CH", # for countries out of EU
        '1126': "FedEx",
    }

    try: 
        sh_serv = SHIPPING_SERVICES[item_code]
    except: 
        sh_serv = ""

    # special cases: Dr. Bohr Gasse 9 and Leberstrasse 20, 
    if sh_serv in ["Austria", "EMS"] and (("Bohr" in ship_adr.address_line1 
                                                and "Dr" in ship_adr.address_line1 
                                                and "Gasse" in ship_adr.address_line1
                                                and ("7" in ship_adr.address_line1
                                                    or "9" in ship_adr.address_line1)) 
                                            or ("Leberstrasse" in ship_adr.address_line1 
                                                and "20" in ship_adr.address_line1)): 
        sh_serv = "MFPL"
    # special cases: Tartu, Össu and Jögeva
    elif (sh_serv != "DHL" and (ship_adr.pincode == "48309" 
                                or "Tartu" in ship_adr.city
                                or "Õssu" in ship_adr.city
                                or "Össu" in ship_adr.city
                                or "Jõgeva" in ship_adr.city
                                or "Jögeva" in ship_adr.city
                                or "Ülenu" in ship_adr.city)
                                ):
        sh_serv = "Tartu"
    # Receivers IMP und IMBA are special cases   
    elif (cstm_ID == "57022" or cstm_ID == "57023" or cstm_ID == "57023"): 
        sh_serv = "IMP"

    return (sh_serv)


def get_shipping_item(items):
    for i in reversed(items):
        if i.item_group == "Shipping":
            return i.item_code


def create_receiver_address_lines(customer_id=None, contact_id=None, address_id=None):
    '''creates a list of strings that represent the sequence of address lines of the receiver'''

    if contact_id: contact_doc = frappe.get_doc("Contact", contact_id)
    if address_id: address_doc = frappe.get_doc("Address", address_id)
    if customer_id:  customer_doc = frappe.get_doc("Customer", customer_id)

    rec_adr_lines = []
    if address_id and address_doc.overwrite_company: 
        rec_adr_lines.append(address_doc.overwrite_company) 
    else: 
        rec_adr_lines.append(customer_doc.customer_name)
    if contact_id: 
        if contact_doc.institute:   rec_adr_lines.append(contact_doc.institute)
        if contact_doc.designation: rec_adr_lines.append(contact_doc.designation)
        if contact_doc.first_name and contact_doc.first_name != "-": rec_adr_lines.append(contact_doc.first_name)
        if contact_doc.last_name:   rec_adr_lines[-1] += " " + contact_doc.last_name
        if contact_doc.department:  rec_adr_lines.append(contact_doc.department)
        if contact_doc.room:        rec_adr_lines.append(contact_doc.room)

    if address_id: 
        if address_doc.address_line1: rec_adr_lines.append(address_doc.address_line1)
        if address_doc.address_line2: rec_adr_lines.append(address_doc.address_line2)
    
        if address_doc.country in ['United Kingdom']: 
            if address_doc.city and address_doc.pincode: rec_adr_lines.append(address_doc.city + " " + address_doc.pincode)
        else: 
            if address_doc.pincode and address_doc.city: rec_adr_lines.append(address_doc.pincode + " " + address_doc.city)
    
        if address_doc.country: rec_adr_lines.append(address_doc.country)

    return rec_adr_lines


def get_sender_address_line(sales_order, shipping_address_country):

    letter_head_name = ""
    letter_head = ""

    if sales_order.company == "Microsynth AG" and shipping_address_country.name == "Austria":
        letter_head_name = "Microsynth AG Wolfurt"    
    elif sales_order.company == "Microsynth AG" and shipping_address_country.eu:
        letter_head_name = "Microsynth AG Lindau"        
    else:
        letter_head_name = sales_order.company

    letter_head = frappe.get_doc("Letter Head", letter_head_name)

    if not letter_head.sender_address_line:   
        # frappe.throw("Letter head '{0}' does not have a 'sender_address_line' specified.".format(letter_head_name))
        return ""

    return letter_head.sender_address_line


def decide_brady_printer_ip(company):
    """
    printers have to be set in Sequencing Settings based on company name
    printer IPs have to be set in an object of DocType Brady Printer
    """
    
    if not company: 
        frappe.throw("Company missing for deciding on printer IP")

    settings = frappe.get_doc("Sequencing Settings", "Sequencing Settings")
    for printer in settings.label_printers:
        if printer.company == company:
            printer = frappe.get_doc("Brady Printer", printer.brady_printer)
            return printer.ip


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

    shipping_item = get_shipping_item(sales_order.items)

    address_id = sales_order.shipping_address_name
    shipping_address = frappe.get_doc("Address", address_id)
    destination_country = frappe.get_doc("Country", shipping_address.country)

    data = {
        'lines': create_receiver_address_lines(customer_id = sales_order.customer, contact_id = sales_order.contact_person, address_id = address_id), 
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
def print_address_template(sales_order_id=None, printer_ip=None):
    """function calls respective template for creating a transport label"""

    # test data - during development
    if not sales_order_id: 
        sales_order_id = 'SO-BAL-22009917'
        sales_order_id = 'SO-GOE-22000704'
        sales_order_id = 'SO-BAL-22009934'
        sales_order_id = 'SO-LYO-22000071'
        sales_order_id = "SO-BAL-22009681"
        sales_order_id = "SO-BAL-22009354"
        sales_order_id = "SO-BAL-22008255"
        sales_order_id = "SO-BAL-22000012"
        sales_order_id = "SO-BAL-22000004"
    customers = frappe.get_all("Customer", fields=["name", "customer_name"])

    sales_order = frappe.get_doc("Sales Order", sales_order_id)    
    
    # this is Brady
    # printer_ip = "192.0.1.70"
    # this is Novexx    
    # printer_ip = "192.0.1.72"
    
    # if ip (use case "Novexx")
    if not printer_ip:
        printer_ip = decide_brady_printer_ip(sales_order.company)

    if printer_ip in ['192.0.1.70', '192.0.1.71', '192.168.101.26','172.16.0.40']: 
        printer_template = "microsynth/templates/includes/address_label_brady.html"
    elif printer_ip in ['192.0.1.72']: 
        printer_template = "microsynth/templates/includes/address_label_novexx.html"
    else: 
        frappe.throw("invalid IP, no printer set")

    content = frappe.render_template(printer_template, get_label_data(sales_order))

    # print(content)
    print_raw(printer_ip, 9100, content )


@frappe.whitelist()
def print_oligo_order_labels(sales_orders):
    """
    Prints the shipping labels from a list of sales order names.

    Run
    bench execute "microsynth.microsynth.labels.print_oligo_order_labels" --kwargs "{'sales_orders': ['SO-BAL-22011340']}"
    """    
    settings = frappe.get_doc("Flushbox Settings", "Flushbox Settings")

    for o in sales_orders:
        sales_order = frappe.get_doc("Sales Order", o)
        label_data = get_label_data(sales_order)
        content = frappe.render_template(NOVEXX_PRINTER_TEMPLATE, label_data)
        
        print_raw(settings.label_printer_ip, settings.label_printer_port, content)        
        sales_order.label_printed_on = datetime.now()
        sales_order.save()
    
    frappe.db.commit()
    return