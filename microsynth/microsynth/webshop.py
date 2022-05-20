# -*- coding: utf-8 -*-
# Copyright (c) 2022, libracore (https://www.libracore.com) and contributors
# For license information, please see license.txt

import frappe
import json
from microsynth.microsynth.migration import update_customer
from microsynth.microsynth.utils import create_oligo

@frappe.whitelist(allow_guest=True)
def ping():
    return "pong"
    
@frappe.whitelist(allow_guest=True)
def create_update_customer(key, customer_data):
    if check_key(key):
        if type(customer_data) == str:
            customer_data = json.loads(customer_data)
        error = update_customer(customer_data)
        if not error:
            return {'status': True, 'message': "Success"}
        else: 
            return {'status': False, 'message': error}
    else:
        return {'status': False, 'message': 'Authentication failed'}

def check_key(key):
    server_key = frappe.get_value("Microsynth Webshop Settings", "Microsynth Webshop Settings", "preshared_key")
    if server_key == key:
        return True
    else:
        return False

@frappe.whitelist(allow_guest=True)
def request_quote(key, customer, content, customer_request, contact, 
        delivery_address, invoice_address, client="webshop"):
    # check access
    if check_key(key):
        # prepare parameters
        if type(content) == str:
            content = json.loads(content)
        # validate input
        if not frappe.db.exists("Customer", customer):
            return {'success': False, 'message': "Customer not found", 'reference': None}
        if not frappe.db.exists("Address", delivery_address):
            return {'success': False, 'message': "Delivery address not found", 'reference': None}
        if not frappe.db.exists("Address", invoice_address):
            return {'success': False, 'message': "Invoice address not found", 'reference': None}
        if not frappe.db.exists("Contact", contact):
            return {'success': False, 'message': "Contact not found", 'reference': None}
        # create quotation
        qtn_doc = frappe.get_doc({
            'doctype': "Quotation",
            'quotation_to': "Customer",
            'party_name': customer,
            'customer_address': invoice_address,
            'shipping_address': delivery_address,
            'contact_person': contact,
            'customer_request': customer_request
        })
        # create oligos
        for o in content['oligos']:
            # create or update oligo
            oligo_name = create_oligo(o)
            # insert positions
            for i in o['items']:
                if not frappe.db.exists("Item", i['item_code']):
                    return {'success': False, 'message': "invalid item: {0}".format(i['item_code']), 
                        'reference': None}
                qtn_doc.append('items', {
                    'item_code': i['item_code'],
                    'qty': i['qty'],
                    'oligo': oligo_name
                })
        # append items
        for i in content['items']:
            if not frappe.db.exists("Item", i['item_code']):
                return {'success': False, 'message': "invalid item: {0}".format(i['item_code']), 
                    'reference': None}
            qtn_doc.append('items', {
                'item_code': i['item_code'],
                'qty': i['qty']
            })
        try:
            qtn_doc.insert(ignore_permissions=True)
            return {'status': True, 'message': 'Quotation created', 
                'reference': qtn_doc.name}
        except Exception as err:
            return {'status': False, 'message': err, 'reference': None}
    else:
        return {'status': False, 'message': 'Authentication failed', 'reference': None}
