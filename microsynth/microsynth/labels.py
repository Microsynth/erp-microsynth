# -*- coding: utf-8 -*-
# Copyright (c) 2022, libracore (https://www.libracore.com) and contributors
# For license information, please see license.txt

import frappe
import socket

def print_raw(ip, port, content):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect((ip, port))
    s.send(content.encode())
    s.close()
    return
    
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
;T 1,140,0,3,pt 10;[DATE]-[TIME]-ERPtest
A 1
'''
    print_raw('192.0.1.71', 9100, content )

def print_test_label_novexx():
    content = '''#!A1
#IMS105/148
#N13
#ER

#T19#J28.6#YG/3///C:\Logos\Microsynth_black_140x27.bmp#G

#T4#J130#YN101/0U/45///Schützenstrasse 15, 9436 Balgach#G
#T4#J127#YL0/0/0.5/95

#T60#J105#YN101/3U/45///first line#G
#T55#J105#YN101/3U/45///2nd line#G
#T50#J105#YN101/3U/45///3rd line#G
#T45#J105#YN101/3U/45///4. line#G
#T40#J105#YN101/3U/45///5. line#G
#T35#J105#YN101/3U/45///6. line#G
#T30#J105#YN101/3U/45///Balgach#G
#T25#J105#YN101/3U/45///Switzerland#G

#T78#J54#YN101/3U/85///P.P. A#G
#T75#J54#YN101/3U/45///CH-9436 Balgach#G
#T71#J54#YN101/3U/45///POST CH AG#G
#T69#J22#YR0/0/0.5/15/33

#T4#J105#YN101/3U/45///hardcoded from print_test_label_novexx#G
#Q1/
#!P1
'''
    print_raw('192.0.1.72', 9100, content )

def print_test_address_template_brady():
    content = frappe.render_template("microsynth/templates/includes/address_label_brady.html", 
        {'lines': create_receiver_address_lines(customer_id='8003', contact_id='215856', address_id='215856'), 
        'sender_address': return_sender_address("Balgach"),
        'postal_list': ['FEDEX']}
        )
    print(content)
    print_raw('192.0.1.70', 9100, content )

def print_test_address_template_novexx():
    content = frappe.render_template("microsynth/templates/includes/address_label_novexx.html", 
        {'lines': create_receiver_address_lines(customer_id='8003', contact_id='215856', address_id='215856'), 
        'sender_address': return_sender_address("Balgach"),
        'postal_list': ['P.P. A.', '', '']}
        )
    print(content)
    print_raw('192.0.1.72', 9100, content )

def create_receiver_address_lines(customer_id=None, contact_id=None, address_id=None):
    '''
    creates a list of strings that represent the sequence of address lines of the receiver
    '''

    if contact_id: contact_doc = frappe.get_doc("Contact", contact_id)
    if address_id: address_doc = frappe.get_doc("Address", address_id)
    if customer_id:  customer_doc = frappe.get_doc("Customer", customer_id)

    rec_adr_lines = []
    if address_doc.overwrite_company: 
        rec_adr_lines.append(address_doc.overwrite_company) 
    else: 
        rec_adr_lines.append(customer_doc.customer_name)
    if contact_doc: 
        if contact_doc.institute:   rec_adr_lines.append(contact_doc.institute)
        if contact_doc.designation: rec_adr_lines.append(contact_doc.designation)
        if contact_doc.first_name and contact_doc.first_name != "-": rec_adr_lines.append(contact_doc.first_name)
        if contact_doc.last_name:   rec_adr_lines[-1] += " " + contact_doc.last_name
        if contact_doc.department:  rec_adr_lines.append(contact_doc.department)
        if contact_doc.room:        rec_adr_lines.append(contact_doc.room)

    if address_doc: 
        if address_doc.address_line1: rec_adr_lines.append(address_doc.address_line1)
        if address_doc.address_line2: rec_adr_lines.append(address_doc.address_line2)
    
        if address_doc.country in ['United Kingdom']: 
            if address_doc.city and address_doc.pincode: rec_adr_lines.append(address_doc.city + " " + address_doc.pincode)
        else: 
            if address_doc.pincode and address_doc.city: rec_adr_lines.append(address_doc.pincode + " " + address_doc.city)
    
        if address_doc.country: rec_adr_lines.append(address_doc.country)

    return rec_adr_lines

def return_sender_address(company):
    '''
    returns a string representing the sender address based on logical decission
    '''

    if company == "Balgach": 
        sender_adr = 'Schützenstrasse 15, CH-9436 Balgach'
    elif company == "Lindau": 
        sender_adr = 'Postfach 3351, DE-88115 Lindau'
    elif company == "Wolfurt": 
        sender_adr = 'Postlagernd, Senderstrasse 10, AT-696 Wolfurt'
    else: 
        sender_adr = 'Schützenstrasse 15, CH-9436 Balgach'
    return sender_adr


### the following code might be deleted completely if string builder variant is obsolete ###


def print_microsynth_address_label():
    
    printer_IP = "192.0.1.70"
    #printer_IP = "192.0.1.71"
    label = ""
    label = label_string_builder('8003', '215856', '215856')
    print(label)
    print_raw(printer_IP, 9100, label)


def return_company_label_string(company): 

    if company == "Microsynth AG": 
        company_label_string = '''; ###Microsynth swiss address, rotated 180 dregree, address bottom line with company logo ### OK
T 50,130,180,3,pt 10;Schützenstrasse 15
T 50,125,180,3,pt 10;CH-9436 Balgach
'''
    elif company == "Lindau": 
        company_label_string = '''; ###Microsynth Lindau address, rotated 180 dregree, address bottom line with company logo ### OK
T 50,130,180,3,pt 10;Postfach 3351
T 50,125,180,3,pt 10;DE-88115 Lindau
'''
    elif company == "Wolfurt": 
        company_label_string = '''; ###Microsynth Wolfurt address, rotated 180 dregree, address bottom line with company logo ### OK
T 50,133,180,3,pt 10;Postlagernd
T 50,129,180,3,pt 10;Senderstrasse 10
T 50,125,180,3,pt 10;AT-696 Wolfurt
'''
    else: 
        company_label_string = ""
    
    return company_label_string


def return_delivery_address(receiver_address_lines): 

    start_coord = 45
    delivery_address_string = '''; ### customer address ###
'''
    for address_line in receiver_address_lines: 
        delivery_address_string += "T %s, 100, 90, 3, pt 10; %s\n" % (start_coord, address_line)
        start_coord += 5
    return delivery_address_string



def label_string_builder(customer_id, contact_id, address_id):

    contact_doc = frappe.get_doc("Contact", contact_id)
    address_doc = frappe.get_doc("Address", address_id)
    customer_doc = frappe.get_doc("Customer", customer_id)

    receiver_address_lines = []
    if address_doc.overwrite_company: 
        receiver_address_lines.append(address_doc.overwrite_company) 
    else: 
        receiver_address_lines.append(customer_doc.customer_name)
    if contact_doc: 
        if contact_doc.institute:   receiver_address_lines.append(contact_doc.institute)
        if contact_doc.designation: receiver_address_lines.append(contact_doc.designation)
        if contact_doc.first_name and contact_doc.first_name != "-": receiver_address_lines.append(contact_doc.first_name)
        if contact_doc.last_name:   receiver_address_lines[-1] += " " + contact_doc.last_name
        if contact_doc.department:  receiver_address_lines.append(contact_doc.department)
        if contact_doc.room:        receiver_address_lines.append(contact_doc.room)

    if address_doc: 
        if address_doc.address_line1: receiver_address_lines.append(address_doc.address_line1)
        if address_doc.address_line2: receiver_address_lines.append(address_doc.address_line2)
    
        if address_doc.country in ['United Kingdom']: 
            if address_doc.city and address_doc.pincode: receiver_address_lines.append(address_doc.city + " " + address_doc.pincode)
        else: 
            if address_doc.pincode and address_doc.city: receiver_address_lines.append(address_doc.pincode + " " + address_doc.city)
    
        if address_doc.country: receiver_address_lines.append(address_doc.country)

    company = "Microsynth AG" # can be "Microsynth AG", "SeqLab", "Wolfurt", "Lindau"
    postal = "PPA" # can be "PPA", "DHL Germany", "Germany", "MPFL Austria", "IMP Austria", "EXPRESS", "A-PLUS", "Fedex"

    label_string = ''';###load Microsynth logo###
M l IMG;01_MIC_Logo_Swiss_black
M l IMG;00_MIC_Logo_black

; ### Setup printer ###
m m
J
H 100
S 0,-2.5,145,150,105
O R

; ###Microsynth logo, rotated 90 degree###
I 100,137,180,2,2;01_MIC_Logo_Swiss_black

; ### bar to seperate sender ### OK
G 5,122,0;L:90,0.5,r,r
'''

    label_string += return_company_label_string(company)
    label_string += create_postal_brady(postal)
    label_string += return_delivery_address(receiver_address_lines)

    label_string += '''
; ### Auftragsnummer ###
;T 35,47,90,3,pt 10;Auftragsnummer?

;### barcode - TODO: Placeholder - is it needed? ###
B 80,50,180,CODE128,10,0.2;something

;### print date and time during development ###
T 10,10,0,3,pt 10;[DATE]-[TIME]-ERP
T 60,10,0,3,pt 24;ERP#1
A 1
    '''
    return label_string

