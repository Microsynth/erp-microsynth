# -*- coding: utf-8 -*-
# Copyright (c) 2022, libracore (https://www.libracore.com) and contributors
# For license information, please see license.txt

import frappe
import socket
import sys

# TODO: dict is not complete
SHIPPING_SERVICES = {
    '1100': "A-Post",
    '1123': "DHL"
}


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
    for del_item in items[::-1]:
        if del_item.item_group == "Shipping":
            return del_item.item_code


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


# TODO: Ths function might be obsolete as it can be implied by destination_country
def return_sender_address(company):
    '''
    returns a string representing the sender address based on logical decission 
    is a workaround during development to mock sender address
    indicator might be the destination_country, logic can be transfered to jinja template
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


def print_address_template(sales_order_id='SO-BAL-22000001', printer_ip='192.0.1.70'):
    """function calls respective template for creating a transport label
    default printer is IP 192.0.1.70 (Brady Sanger)"""
        
    if printer_ip in ['192.0.1.70', '192.0.1.71']: 
        printer_template = "microsynth/templates/includes/address_label_brady.html"
    elif printer_ip in ['192.0.1.72']: 
        printer_template = "microsynth/templates/includes/address_label_novexx.html"
    else: 
        frappe.throw("invalid IP, no printer set")
    
    sales_order = frappe.get_doc("Sales Order", sales_order_id)    
    shipping_item = get_shipping_item(sales_order.items)

    if not sales_order.shipping_address_name:
        frappe.throw("address missing")
    elif not sales_order.customer: 
        frappe.throw("customer missing")
    elif not sales_order.contact_person: 
        frappe.throw("contact missing")
        
    adr_id = sales_order.shipping_address_name
    address = frappe.get_doc("Address", adr_id)
    cst_id = sales_order.customer
    cntct_id = sales_order.contact_person
    country = frappe.get_doc("Country", address.country)   

    # sender_address
    sender_address_discriminator = "eu" if country.eu else address.country

    content = frappe.render_template(printer_template, 
        {'lines': create_receiver_address_lines(customer_id=cst_id, contact_id=cntct_id, address_id=adr_id), 
        'sender_address_discriminator': sender_address_discriminator,
        'destination_country': address.country,
        'shipping_service': SHIPPING_SERVICES[shipping_item]}
        )

    print(content) # must we trigger a log entry for what is printed?
    #print_raw(printer_ip, 9100, content )
