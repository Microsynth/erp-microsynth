# -*- coding: utf-8 -*-
# Copyright (c) 2022, libracore (https://www.libracore.com) and contributors
# For license information, please see license.txt

import frappe
import socket
import sys


def get_shipping_service(item_code, ship_adr,cstm_ID):
    
    # TODO: dict is not complete
    SHIPPING_SERVICES = {
        '1100': "P.P.A",
        '1101': "A-plus", 
        '1102': "Express", 
        '1103': "Austria", # Empfänger IMP und IMBA benötigen wir einen speziellen Barcode und den Vermerk IMP 
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
        '1120': "DHL CH",  # für nicht EU Europastaaten
        '1122': "DHL",
        '1123': "DHL/CH", # für Staaten ausserhalb Europas
        '1126': "FedEx",
    }

    try: 
        sh_serv = SHIPPING_SERVICES[item_code]
    except: 
        sh_serv = ""

    # Ausnahme Adresse Dr. Bohr Gasse 9 und Leberstrasse 20, 
        # da brauchen wir wegen Sammelversand den Vermerk MFPL
    if sh_serv in ["Austria", "EMS"] and (("Bohr" in ship_adr.address_line1 
                                                and "Dr" in ship_adr.address_line1 
                                                and "Gasse" in ship_adr.address_line1
                                                and ("7" in ship_adr.address_line1
                                                    or "9" in ship_adr.address_line1)) 
                                            or ("Leberstrasse" in ship_adr.address_line1 
                                                and "20" in ship_adr.address_line1)): 
        sh_serv = "MFPL"
    # Ausnahme Tartu, Össu und Jögeva – da benötigen wir den Vermerk Tartu
    elif (sh_serv != "DHL" and (ship_adr.pincode == "48309" 
                                or "Tartu" in ship_adr.city
                                or "Õssu" in ship_adr.city
                                or "Össu" in ship_adr.city
                                or "Jõgeva" in ship_adr.city
                                or "Jögeva" in ship_adr.city
                                or "Ülenu" in ship_adr.city)
                                ):
        sh_serv = "Tartu"
    # Empfänger IMP und IMBA benötigen den Vermerk   
    elif (cstm_ID == "57022" or cstm_ID == "57023" or cstm_ID == "57023"): 
        sh_serv = "IMP"

    return (sh_serv)


def print_raw(ip, port, content):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect((ip, port))
    s.send(content.encode())
    s.close()
    return


# TODO obsolete: Test functions are hardcoded to specific printer IPs and are useful only during initial development - delete after finishing development
def print_test_label_brady():
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


# TODO obsolete: Test functions are hardcoded to specific printer IPs and are useful only during initial development - delete after finishing development
def print_test_label_novexx():
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


def get_shipping_item(items):
    for i in reversed(items):
        if i.item_group == "Shipping":
            return i.item_code


def create_receiver_address_lines(customer_id=None, contact_id=None, address_id=None):
    '''
    creates a list of strings that represent the sequence of address lines of the receiver
    '''

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
    if sales_order.company == "Microsynth AG" and shipping_address_country.eu == "EU":
            letter_head_name = "Microsynth AG Wolfurt"
    else:
        letter_head_name = sales_order.company

    # robustness: use try/except to catch frappe.exceptions.DoesNotExistError
    try: 
        letter_head = frappe.get_doc("Letter Head", letter_head_name)
    except:
        letter_head = frappe.throw("Letter head {0} not found. Please define the letter head under print settings.".format(letter_head_name))


    if letter_head and letter_head.content:
        # before
        #sender_header = letter_head.content
        
        sender_address_line = letter_head.sender_address_line
        #sender_address_line = letter_head.footer
    else:
        frappe.throw("Letter head {0} empty. Please define the letter head under print settings.".format(letter_head_name))

    return sender_address_line 


def decide_brady_printer_ip(company):
    """printers have to be set in Sequencing Settings based on company name
    printer ips have to be set in an object of DocType Brady Printer
    """
    
    if not company: 
        frappe.throw("Company missing for deciding on printer IP")

    settings = frappe.get_doc("Sequencing Settings", "Sequencing Settings")
    for printer in settings.label_printers:
        if printer.company == company:
            printer = frappe.get_doc("Brady Printer", printer.brady_printer)
            return printer.ip

@frappe.whitelist()
def print_address_template(sales_order_id=None, printer_ip=None):
    #@RSu: without default argument sales_order_id, I cannot test via console
    #@RSu: printer_ip is useful to overload function, if set --> use case Novexx, else decide on company name
    #TODO: wrapper or Novexx must be developed or just call this function with SO, IP 192.0.1.72
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
    customers = frappe.get_all("Customer", fields=["name", "customer_name"])

    sales_order = frappe.get_doc("Sales Order", sales_order_id)    
    shipping_item = get_shipping_item(sales_order.items)

    
    # this is brady
    # printer_ip = "192.0.1.70"
    # if ip (use case "Novexx")
    # printer_ip = "192.0.1.72"
    if not printer_ip:
        printer_ip = decide_brady_printer_ip(sales_order.company)
        print(printer_ip)    

    if not sales_order.shipping_address_name:
        frappe.throw("print delivery note: address missing")
    elif not sales_order.customer: 
        frappe.throw("print delivery note: customer missing")
    elif not sales_order.contact_person: 
        frappe.throw("print delivery note: contact missing")
        
    adr_id = sales_order.shipping_address_name
    shipping_address = frappe.get_doc("Address", adr_id)
    cstm_id = sales_order.customer
    cntct_id = sales_order.contact_person
    shipping_address_country = frappe.get_doc("Country", shipping_address.country)   
    po_no = sales_order.po_no
    print(po_no)
    web_id = sales_order.web_order_id


    if printer_ip in ['192.0.1.70', '192.0.1.71', '192.168.101.26','172.16.0.40']: 
        printer_template = "microsynth/templates/includes/address_label_brady.html"
    elif printer_ip in ['192.0.1.72']: 
        printer_template = "microsynth/templates/includes/address_label_novexx.html"
    else: 
        frappe.throw("invalid IP, no printer set")

    content = frappe.render_template(printer_template, 
        {'lines': create_receiver_address_lines(customer_id=cstm_id, contact_id=cntct_id, address_id=adr_id), 
        'sender_header': get_sender_address_line(sales_order, shipping_address_country),
        'destination_country': shipping_address.country,
        'shipping_service': get_shipping_service(shipping_item, shipping_address, cstm_id),
        'po_no': po_no,
        'web_id': web_id,
        'cstm_id': cstm_id
        }
        )

    print(content) # must we trigger a log entry for what is printed?
    print_raw(printer_ip, 9100, content )
