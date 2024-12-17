# -*- coding: utf-8 -*-
# Copyright (c) 2022-2024, libracore (https://www.libracore.com) and contributors
# For license information, please see license.txt

import frappe
from microsynth.microsynth.report.pricing_configurator.pricing_configurator import get_rate
from frappe.utils import cint
import unicodedata

"""
Jinja endpoint to get pricelist rate and reference rate for an item
"""
def get_price_list_rate(item_code, price_list, qty=1):
    data = {
        'rate': get_rate(item_code, price_list, qty),
        'reference_rate': get_rate(item_code, 
            frappe.get_value("Price List", price_list, "reference_price_list"),
            qty)
    }
    return data

"""
Jinja endpoint to find destination region classification
"""
def get_destination_classification(so=None, dn=None, si=None):
    # check if one of the reference documents are provided
    if not so and not dn and not si:
        frappe.throw("Please provide one reference document")
    
    # find shipping (or fallback to invoice) address
    if so:
        shipping_address = frappe.get_value("Sales Order", so, "shipping_address_name") or frappe.get_value("Sales Order", so, "customer_address")
    elif dn:
        shipping_address = frappe.get_value("Delivery Note", dn, "shipping_address_name") or frappe.get_value("Delivery Note", dn, "customer_address")
    else:
        shipping_address = frappe.get_value("Sales Invoice", si, "shipping_address_name") or frappe.get_value("Sales Invoice", si, "customer_address")
    # error if there is no address
    if not shipping_address:
        frappe.throw("No address found for {0}".format(so or dn or si))
    
    country = frappe.get_value("Address", shipping_address, "country")
    
    if country == "Switzerland":
        return "CH"
    else:
        eu_code = frappe.get_value("Country", country, "eu")
        if cint(eu_code) == 1:
            return "EU"
        else:
            return "ROW"

"""
XML-encoding and clean up
"""
def xml_normalize(s, length):
    translation_table = {
        #'ä': 'a', 
        #'ö': 'o', 
        #'ü': 'u', 
        'ß': 'ss', 
        'é': 'e',       # utf-8 0xC3 or 0xA9
        'è': 'e', 
        'á': 'a',
        'à': 'a',
        'í': 'i', 
        'ó': 'o', 
        'ú': 'u', 
        'ñ': 'n', 
        'ç': 'c', 
        'â': 'a', 
        'ê': 'e', 
        'ô': 'o',
        'î': 'i', 
        'û': 'u', 
        'é': 'e',       # utf-8 0xA9 or 0xC3
        'è': 'e', 
        'œ': 'oe', 
        'ø': 'o', 
        'å': 'a', 
        'æ': 'ae',
        '&': '+'
    }
    
    normalized_string = ''.join(translation_table.get(char, char) for char in s) # if ord(char) < 128 or char in translation_table)
    
    normalized_s = unicodedata.normalize('NFKD', normalized_string)
    
    return normalized_s[:length]
