# -*- coding: utf-8 -*-
# Copyright (c) 2022, libracore (https://www.libracore.com) and contributors
# For license information, please see license.txt

import frappe


TRACKING_URLS = {
    '1010': "https://www.post.at/sv/sendungssuche?snr=",
    #'1103': "https://www.post.at/sv/sendungssuche?snr=",  # has no tracking anymore
    '1105': "https://www.post.at/sv/sendungssuche?snr=",
    '1108': "https://www.ups.com/track?tracknum=",
    '1114': "https://www.ups.com/track?tracknum=",
    '1117': "https://www.ups.com/track?tracknum=",
    '1119': "https://www.dhl.com/en/express/tracking.html?brand=DHL&AWB=",  # TODO: Check if this is really the correct URL for DHL Economy Select
    '1120': "https://www.dhl.com/en/express/tracking.html?brand=DHL&AWB=",
    '1123': "https://www.dhl.com/ch-en/home/tracking/tracking-express.html?submit=1&tracking-id=",
    '1126': "https://www.fedex.com/fedextrack/?trknbr=",
    '1101': "https://www.post.ch/swisspost-tracking?formattedParcelCodes=",
    '1102': "https://www.post.ch/swisspost-tracking?formattedParcelCodes=",
    '1104': "https://www.post.ch/swisspost-tracking?formattedParcelCodes=",
    '1107': "https://www.post.ch/swisspost-tracking?formattedParcelCodes="
}


def get_shipping_service(item_code, ship_adr, cstm_ID):
    
    SHIPPING_SERVICES = {
        '1100': "P.P.A",
        '1101': "A-plus", 
        '1102': "Express", 
        '1103': "Austria",
        '1104': "Einschreiben",
        '1105': "EMS",    
        '1106': "Germany",
        '1107': "DryIce",
        '1108': "UPS",
        '1110': "Abholung",
        '1112': "Germany",
        '1113': "DryIce",
        '1114': "UPS",
        '1115': "Germany",
        '1117': "UPS",
        '1119': "DHL Economy Select",  # only for EU
        '1120': "DHL CH",  # not for EU
        '1122': "DHL",
        '1123': "DHL/CH", # for countries out of EU
        '1126': "FedEx",
        '1130': "Internal",
        '1133': "Sequencing",
        '1140': "IMP/IMBA"
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

    return (sh_serv)


def get_shipping_item(items):
    for i in reversed(items):
        if i.item_group == "Shipping":
            return i.item_code


def create_receiver_address_lines(customer_name, contact, address):
    '''creates a list of strings that represent the sequence of address lines of the receiver'''

    if contact: contact_doc = frappe.get_doc("Contact", contact)
    if address: address_doc = frappe.get_doc("Address", address)

    rec_adr_lines = []
    if address and address_doc.overwrite_company: 
        rec_adr_lines.append(address_doc.overwrite_company) 
    else: 
        rec_adr_lines.append(customer_name)
    if contact: 
        if contact_doc.institute:   rec_adr_lines.append(contact_doc.institute)
        if contact_doc.designation: rec_adr_lines.append(contact_doc.designation)
        if contact_doc.first_name and contact_doc.first_name != "-": rec_adr_lines.append(contact_doc.first_name)
        if contact_doc.last_name:   rec_adr_lines[-1] += " " + contact_doc.last_name
        if contact_doc.department:  rec_adr_lines.append(contact_doc.department)
        if contact_doc.room:        rec_adr_lines.append(contact_doc.room)

    if address: 
        if address_doc.address_line1: rec_adr_lines.append(address_doc.address_line1)
        if address_doc.address_line2: rec_adr_lines.append(address_doc.address_line2)
    
        if address_doc.city and address_doc.pincode:
            if address_doc.country and address_doc.country in ['United Kingdom']:
                rec_adr_lines.append(address_doc.city + " " + address_doc.pincode)
            else:
                rec_adr_lines.append(address_doc.pincode + " " + address_doc.city)
        elif address_doc.city: rec_adr_lines.append(address_doc.city)
        elif address_doc.pincode: rec_adr_lines.append(address_doc.pincode)
    
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


def update_shipping_item_name(item_codes, dry_run=True):
    """
    Takes a list of item codes.
    Check that each of them has Item Group 'Shipping'.
    Search those Shipping Items with item_name != Item.item_name.
    Set Shipping Item.item_name to Item.item_name.

    bench execute microsynth.microsynth.shipping.update_shipping_item_name --kwargs "{'item_codes': ['1103'], 'dry_run': True}"
    """
    for item_code in item_codes:
        if not frappe.db.exists("Item", item_code):
            print(f"Item '{item_code}' does not exist. Going to continue.")
            continue
        item = frappe.get_doc("Item", item_code)
        if item.item_group != 'Shipping':
            print(f"Item {item_code}: {item.item_name} has Item Group {item.item_group} and is not a Shipping Item. Going to continue.")
            continue
        shipping_items = frappe.db.get_all("Shipping Item",
            filters = [['item', '=', item_code], ['item_name', '!=', item.item_name]],
            fields = ['name', 'item_name', 'parent'])
        for shipping_item in shipping_items:
            if dry_run:
                print(f"Would change Item Name of {item_code} on {shipping_item['parent']} from '{shipping_item['item_name']}' to '{item.item_name}'.")
                continue
            else:
                print(f"Going to change Item Name of {item_code} on {shipping_item['parent']} from '{shipping_item['item_name']}' to '{item.item_name}'.")
                frappe.db.sql(f"""
                    UPDATE `tabShipping Item`
                    SET `item_name` = '{item.item_name}'
                    WHERE `name` = '{shipping_item['name']}';""")
    print("Done")