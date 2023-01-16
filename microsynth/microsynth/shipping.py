# -*- coding: utf-8 -*-
# Copyright (c) 2022, libracore (https://www.libracore.com) and contributors
# For license information, please see license.txt

import frappe
import socket
import sys
from datetime import datetime

TRACKING_URLS = {
    '1010': "https://www.post.at/sv/sendungssuche?snr=",
    '1103': "https://www.post.at/sv/sendungssuche?snr=",
    '1105': "https://www.post.at/sv/sendungssuche?snr=",
    '1108': "https://www.dhl.com/en/express/tracking.html?brand=DHL&AWB=",
    '1114': "https://www.dhl.com/en/express/tracking.html?brand=DHL&AWB=",
    '1117': "https://www.dhl.com/en/express/tracking.html?brand=DHL&AWB=",
    '1120': "https://www.dhl.com/en/express/tracking.html?brand=DHL&AWB=",
    '1123': "https://www.dhl.com/ch-en/home/tracking/tracking-express.html?submit=1&tracking-id=",
    '1126': "https://www.fedex.com/fedextrack/?trknbr=",
    '1101': "https://www.post.ch/swisspost-tracking?formattedParcelCodes=",
    '1102': "https://www.post.ch/swisspost-tracking?formattedParcelCodes=",
    '1104': "https://www.post.ch/swisspost-tracking?formattedParcelCodes=",
    '1107': "https://www.post.ch/swisspost-tracking?formattedParcelCodes="
}


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
        '1130': "Internal",
        '1133': "Sequencing"
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