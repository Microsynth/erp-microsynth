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
    content = """m m
J
H 100
S 0,-2.5,10,12,25
O R
B 1,3.5,0,DATAMATRIX,0.3;Pl00002877
T 6,3.5,0,3,pt 4;MGo
T 9,3.5,0,3,pt 4;2022-09-20, 13:05:26
T 1,9.5,0,3,pt 4;NGS02065
T 6,7.5,0,3,pt 4;Pool
T 6,5.5,0,3,pt 6;Pl00002877
T 11,9.5,0,3,pt 4;Pool-3 NGS01965
A 1
"""    
    print_raw('192.0.1.71', 9100, content )

def show_test_address_template():
    content = frappe.render_template("microsynth/templates/includes/address_label_brady.html", {'contact':'215856','address':'215856', 'customer':'8003'})
    print(content)

def print_test_address_template():
    content = frappe.render_template("microsynth/templates/includes/address_label_brady.html", {'contact':'215856','address':'215856', 'customer':'8003'})
    print("will print following: %s" %content)
    print_raw('192.0.1.71', 9100, content )

def joergs_print():
    
    #printer_IP = "192.0.1.70"
    printer_IP = "192.0.1.71"
    label = ""
    if printer_IP == "192.0.1.70":
        label_header = """m m
J
H 100
S 0,0,145,150,105
O R
"""
    else: 
        label_header = """m m
J
H 100
S 0,-2.5,10,12,25
O R
"""
    label_footer = """
A 1
"""
    
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

    label += label_header
    

    font_size = 10 if printer_IP == "192.0.1.70" else 6
    
    start_coord = 3
    for address_line in lines: 
        print(address_line)
        label += "T 0, %s, 0, 3, pt %s; %s\n" % (start_coord, font_size, address_line)
        start_coord += 3
    if printer_IP == "192.0.1.70":
        label += "B 10, 48, 0, CODE128, 8, 0.15;  grosse Buchstaben - grosse Wirkung"

    label += label_footer
    print_raw(printer_IP, 9100, label )


'''
def joergs_print_minimal():

    label = ""
    label_header = """m m
J
H 100
S 0,-2.5,10,12,25
O R
"""
    label_footer = """
A 1
"""
    
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

    label += label_header

    
    start_coord = 3
    for address_line in lines: 
        label += "T 0, %s, 0, 3, pt 6; %s\n" % (start_coord, address_line)
        start_coord += 3

    label += label_footer
    print_raw('192.0.1.70', 9100, label )
'''