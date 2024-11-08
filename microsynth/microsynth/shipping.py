# -*- coding: utf-8 -*-
# Copyright (c) 2022, libracore (https://www.libracore.com) and contributors
# For license information, please see license.txt

import frappe
import json


TRACKING_URLS = {
    '1010': "https://www.post.at/sv/sendungssuche?snr=",
    '1101': "https://www.post.ch/swisspost-tracking?formattedParcelCodes=",
    '1102': "https://www.post.ch/swisspost-tracking?formattedParcelCodes=",
    #'1103': "https://www.post.at/sv/sendungssuche?snr=",  # has no tracking anymore
    '1104': "https://www.post.ch/swisspost-tracking?formattedParcelCodes=",
    '1105': "https://www.post.at/sv/sendungssuche?snr=",
    '1107': "https://www.post.ch/swisspost-tracking?formattedParcelCodes=",
    '1108': "https://www.ups.com/track?tracknum=",
    '1114': "https://www.ups.com/track?tracknum=",
    '1117': "https://www.ups.com/track?tracknum=",
    '1119': "https://www.dhl.com/en/express/tracking.html?brand=DHL&AWB=",
    '1120': "https://www.dhl.com/en/express/tracking.html?brand=DHL&AWB=",
    '1123': "https://www.dhl.com/ch-en/home/tracking/tracking-express.html?submit=1&tracking-id=",
    '1126': "https://www.fedex.com/fedextrack/?trknbr=",
    '1160': "https://www.ups.com/track?tracknum=",
    '1161': "https://www.ups.com/track?tracknum=",
    '1162': "https://www.ups.com/track?tracknum=",
    '1165': "https://www.ups.com/track?tracknum=",
    '1166': "https://www.ups.com/track?tracknum=",
    '1167': "https://www.ups.com/track?tracknum="
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
        '1108': "UPS EXP DE",
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
        '1140': "IMP/IMBA",
        '1160': "UPS STD",
        '1161': "UPS STD",
        '1162': "UPS STD",
        '1165': "UPS EXP",
        '1166': "UPS EXP",
        '1167': "UPS EXP"
    }
    # TODO: Move settings to a new DocType (Task #17847)

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
    elif (sh_serv != "UPS" and (ship_adr.pincode == "48309" 
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


def add_shipping_item_to_country(country, item_code, rate, threshold, preferred_express):
    """
    Adds the given Shipping Item with the given rate, threshold and preferred_express flag
    to the given Country if there is no Shipping Item with the given Item Code on the given Country.
    """
    try:
        shipping_items = frappe.db.sql(f"""
            SELECT `tabShipping Item`.`name`
            FROM `tabShipping Item`
            LEFT JOIN `tabItem` ON `tabItem`.`name` = `tabShipping Item`.`item`
            WHERE `tabShipping Item`.`parenttype` = "Country"
                AND `tabShipping Item`.`parent` = '{country}'
                AND `tabItem`.`item_code` = '{item_code}'
            ;""", as_dict=True)
        if len(shipping_items) > 0:
            print(f"Shipping Item {item_code} on Country {country} does already exist, going to skip.")
            return False
        country_doc = frappe.get_doc("Country", country)
        country_doc.append("shipping_items", {
            'item': item_code,
            'qty': 1.0,
            'rate': rate,
            'threshold': threshold,
            'preferred_express': preferred_express
        })
        country_doc.save()
        return True
    except Exception as err:
        print(f"Got the following error when trying to add Shipping Item {item_code} on Country {country}: {err}")
        return False


def replace_shipping_items_on_countries(items_to_replace, country_to_code, code_to_rate, threshold, preferred_express):
    """
    Takes a list of Shipping Item codes to replace and searches them on all Countries.
    Replaces them by the given Item code for the given Country code with the given rate
    if preferred_express matches, the qty was 1.0 and the threshold matches.

    bench execute microsynth.microsynth.shipping.replace_shipping_items_on_countries --kwargs "{'items_to_replace': ['1114', '1117'], 'country_to_code': {'PL': '1165', 'FR': '1165', 'BE': '1166', 'BG': '1166', 'CZ': '1166', 'ES': '1166', 'HU': '1166', 'NL': '1166', 'LV': '1166', 'LT': '1166', 'LU': '1166', 'IE': '1166', 'IT': '1166', 'PT': '1166', 'RO': '1166', 'SK': '1166', 'SI': '1166', 'CY': '1167', 'DK': '1167', 'FI': '1167', 'GR': '1167', 'HR': '1167', 'MT': '1167', 'EE': '1167', 'SE': '1167'}, 'code_to_rate': {'1165': 12.00, '1166': 16.00, '1167': 20.00}, 'threshold': 1000, 'preferred_express': 1}"
    """
    if type(country_to_code) == str:
        country_to_code = json.loads(country_to_code)
    if type(code_to_rate) == str:
        code_to_rate = json.loads(code_to_rate)
    countries_replaced = []

    shipping_items = frappe.db.sql(f"""
        SELECT `tabShipping Item`.`name`,
            `tabShipping Item`.`item`,
            `tabShipping Item`.`item_name`,
            `tabShipping Item`.`parent` AS `country`,
            `tabShipping Item`.`qty`,
            `tabShipping Item`.`rate`,
            `tabShipping Item`.`threshold`,
            `tabShipping Item`.`preferred_express`
        FROM `tabShipping Item`
        LEFT JOIN `tabItem` ON `tabItem`.`name` = `tabShipping Item`.`item`
        WHERE `tabShipping Item`.`parenttype` = "Country"
            AND `tabItem`.`item_code` IN ({','.join(f'"{item_code}"' for item_code in items_to_replace)})
        ORDER BY `tabShipping Item`.`parent` ASC;""", as_dict=True)
    
    for shipping_item in shipping_items:
        if shipping_item['preferred_express'] != preferred_express:
            print(f"Shipping Item {shipping_item['item']}: {shipping_item['item_name']} on Country {shipping_item['country']}  has preferred_express = {shipping_item['preferred_express']}, but got {preferred_express=}, going to skip.")
            continue
        if float(shipping_item['qty']) != 1.0:
            print(f"Shipping Item {shipping_item['item']}: {shipping_item['item_name']} on Country {shipping_item['country']} has not 'qty' 1.0 ({shipping_item['qty']=}), going to skip.")
            continue
        if threshold != shipping_item['threshold']:
            print(f"Shipping Item {shipping_item['item']}: {shipping_item['item_name']} on Country {shipping_item['country']} has threshold {shipping_item['threshold']} but the given threshold is {threshold}, going to skip.")
            continue
        country_code = frappe.get_value("Country", shipping_item['country'], 'code').upper()
        if country_code not in country_to_code:
            print(f"Got no Shipping Item Code for Country {shipping_item['country']} with Country code '{country_code}', going to skip Shipping Item {shipping_item['item']}: {shipping_item['item_name']}.")
            continue
        item_code = country_to_code[country_code]
        if item_code not in code_to_rate:
            print(f"Got no rate for Item code '{item_code}', going to skip Shipping Item {shipping_item['item']}: {shipping_item['item_name']} on Country {shipping_item['country']}.")
            continue
        rate = code_to_rate[item_code]
        added = add_shipping_item_to_country(shipping_item['country'], item_code, rate, threshold, preferred_express)
        if added:
            # delete existing Shipping Item
            shipping_item_doc = frappe.get_doc("Shipping Item", shipping_item['name'])
            shipping_item_doc.delete()
            #frappe.db.commit()
            print(f"Successfully replaced Shipping Item {shipping_item['item']}: {shipping_item['item_name']} with rate {shipping_item['rate']} and threshold {shipping_item['threshold']} with preferred_express = {shipping_item['preferred_express']} on Country {shipping_item['country']} by Shipping Item {item_code} with rate {rate} and threshold {threshold} and {preferred_express=}.")
            countries_replaced.append(country_code)
    for country_code in country_to_code.keys():
        if country_code not in countries_replaced:
            print(f"Country with country code {country_code} had no Shipping Item with an Item code in {items_to_replace} or it was skipped due to an error mentioned above.")


def add_shipping_items_to_countries(country_to_code, code_to_rate, threshold, preferred_express):
    """
    Adds the given Item codes with the given rates and threshold to the given Countries
    if there is not already a Shipping Item with the same Item code on the Country.

    bench execute microsynth.microsynth.shipping.add_shipping_items_to_countries --kwargs "{'country_to_code': {'PL': '1160', 'FR': '1160', 'BE': '1161', 'BG': '1161', 'CZ': '1161', 'ES': '1161', 'HU': '1161', 'NL': '1161', 'LV': '1161', 'LT': '1161', 'LU': '1161', 'IE': '1161', 'IT': '1161', 'PT': '1161', 'RO': '1161', 'SK': '1161', 'SI': '1161', 'CY': '1162', 'DK': '1162', 'FI': '1162', 'GR': '1162', 'HR': '1162', 'MT': '1162', 'EE': '1162', 'SE': '1162'}, 'code_to_rate': {'1160': 7.00, '1161': 9.00, '1162': 14.00}, 'threshold': 1000, 'preferred_express': 0}"
    """
    if type(country_to_code) == str:
        country_to_code = json.loads(country_to_code)
    if type(code_to_rate) == str:
        code_to_rate = json.loads(code_to_rate)
    for country_code, item_code in country_to_code.items():
        countries = frappe.get_all("Country", filters={'code': country_code}, fields=['name'])
        if len(countries) == 0:
            print(f"Unknown country code '{country_code}', going to skip.")
            continue
        elif len(countries) > 1:
            print(f"Found the following {len(countries)} Countries for country code '{country_code}' in the ERP, going to skip: {countries}")
            continue
        else:
            country = countries[0]['name']
        rate = code_to_rate[item_code]
        added = add_shipping_item_to_country(country, item_code, rate, threshold, preferred_express)
        if added:
            print(f"Successfully added Shipping Item {item_code} with rate {rate}, threshold {threshold} and {preferred_express=} to Country {country}.")
