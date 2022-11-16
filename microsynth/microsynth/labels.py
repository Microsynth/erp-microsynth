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
    
def print_test_label():
    content = ''';###load Microsynth logo###
M l IMG;01_MIC_Logo_Swiss_black
;M l IMG;00_MIC_Logo_black

m m
J
H 100
S 0,-2.5,145,150,105
O R
;###just for dev###
T 10,10,0,3,pt 24;#x5

; ###Microsynth logo, rotated 90 degree###
I 100,137,180,2,2;01_MIC_Logo_Swiss_black

; ###Microsynth address, rotated 180 dregree ###
T 50,130,180,3,pt 10;Schützenstrasse 15
T 50,125,180,3,pt 10;CH-9436 Balgach
; ### bar to seperate sender ###
G 5,122,0;L:90,0.5,r,r

;### postal stuff ###
G 20,50,90;R:30,10,0.3,0.3
T 29,47,90,3,pt 20;A-PLUS
T 35,47,90,3,pt 10;Auftragsnummer

;### barcode ###
B 80,50,180,CODE128,4,0.2;irgendwas12

; ### customer address###
T 45,120,90,3,pt 10;Hans-Wurst Ltd Customer
T 50,120,90,3,pt 10;Herr Hans Wurst
T 55,120,90,3,pt 10;Sonstwo Avenue
T 60,120,90,3,pt 10;0123 Nirgendwo
T 65,120,90,3,pt 10;Honigkuchenland

;###print date and time during development###
;T 1,140,0,3,pt 10;[DATE]-[TIME]-NPP
A 1
'''

    print_raw('192.0.1.71', 9100, content )

def show_test_address_template():
    content = frappe.render_template("microsynth/templates/includes/address_label_brady.html", {'contact':'215856','address':'215856', 'customer':'8003'})
    print(content)

def print_test_address_template():
    content = frappe.render_template("microsynth/templates/includes/address_label_brady.html", {'contact':'215856','address':'215856', 'customer':'8003'})
    print("will print following: %s" %content)
    print_raw('192.0.1.71', 9100, content )

def print_microsynth_address_label():
    
    printer_IP = "192.0.1.70"
    #printer_IP = "192.0.1.71"
    label = ""
    label = label_string_builder('8003', '215856', '215856')
    print(label)
    #print_raw(printer_IP, 9100, label)

def label_string_builder(customer_id, contact_id, address_id):
    '''function to build the raw string of an addres label
    input: customer_id, contact_id, address_id
    output: string digestable by brady printer
    '''

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

    label_string = ''';### load section ###
M l IMG;01_MIC_Logo_Swiss_black
;M l IMG;00_MIC_Logo_black

;### printer config ###
m m
J
H 100
S 0,-2.5,145,150,105
O R

; ### Microsynth logo, rotated 90 degrees###
I 100,137,180,2,2;01_MIC_Logo_Swiss_black

; ### Microsynth address, rotated 180 degrees ###
T 50,130,180,3,pt 10;Schützenstrasse 15
T 50,125,180,3,pt 10;CH-9436 Balgach
; ### bar to seperate sender ###
G 5,122,0;L:90,0.5,r,r

;### postal stuff - TODO: Placeholder ###
G 20,50,90;R:30,10,0.3,0.3
T 29,47,90,3,pt 20;A-PLUS
T 35,47,90,3,pt 10;Auftragsnummer

;### barcode - TODo: Placeholder ###
B 80,50,180,CODE128,4,0.2;something

; ### customer address ###
'''

    start_coord = 45
    for address_line in receiver_address_lines: 
        label_string += "T %s, 110, 90, 3, pt 10; %s\n" % (start_coord, address_line)
        start_coord += 5

    label_string += ''';### print date and time during development ###
T 10,10,0,3,pt 10;[DATE]-[TIME]-NPP
A 1
    '''
    return label_string

    '''
    contact_doc = frappe.get_doc("Contact", "215856")
    address_doc = frappe.get_doc("Address", "215856")
    customer_doc = frappe.get_doc("Customer", "8003")
    
    lines = []
    if address_doc.overwrite_company: 
        lines.append(address_doc.overwrite_company) 
    else: 
        lines.append(customer_doc.customer_name)
    if contact_doc: 
        if contact_doc.institute: lines.append(contact_doc.institute)
        if contact_doc.designation: lines.append(contact_doc.designation)
        if contact_doc.first_name and contact_doc.first_name != "-": lines.append(contact_doc.first_name)
        if contact_doc.last_name: lines[-1] += " " + contact_doc.last_name
        if contact_doc.department: lines.append(contact_doc.department)
        if contact_doc.room: lines.append(contact_doc.room)

    if address_doc: 
        if address_doc.address_line1: lines.append(address_doc.address_line1)
        if address_doc.address_line2: lines.append(address_doc.address_line2)
    
        if address_doc.country in ['United Kingdom']: 
            if address_doc.city and address_doc.pincode: lines.append(address_doc.city + " " + address_doc.pincode)
        else: 
            if address_doc.pincode and address_doc.city: lines.append(address_doc.pincode + " " + address_doc.city)
    
        if address_doc.country: lines.append(address_doc.country)

    
    start_coord = 3
    for address_line in lines: 
        print(address_line)
        label += "T 0, %s, 0, 3, pt %s; %s\n" % (start_coord, font_size, address_line)
        start_coord += 5
'''
