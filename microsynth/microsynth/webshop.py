# -*- coding: utf-8 -*-
# Copyright (c) 2022, libracore (https://www.libracore.com) and contributors
# For license information, please see license.txt
#
# For more details, refer to https://github.com/Microsynth/erp-microsynth/wiki/Webshop-API
#

import frappe
import json
from microsynth.microsynth.migration import update_customer
from microsynth.microsynth.utils import create_oligo
from datetime import date, timedelta

"""
Ping is a simple interface test function
"""
@frappe.whitelist(allow_guest=True)
def ping():
    return "pong"

"""
This function will create or update a customer
"""
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

"""
Request quote will create a new quote (and open the required oligos, if provided)
"""
@frappe.whitelist(allow_guest=True)
def request_quote(key, content, client="webshop"):
    # check access
    if check_key(key):
        # prepare parameters
        if type(content) == str:
            content = json.loads(content)
        # validate input
        if not frappe.db.exists("Customer", content['customer']):
            return {'success': False, 'message': "Customer not found", 'reference': None}
        if not frappe.db.exists("Address", content['delivery_address']):
            return {'success': False, 'message': "Delivery address not found", 'reference': None}
        if not frappe.db.exists("Address", content['invoice_address']):
            return {'success': False, 'message': "Invoice address not found", 'reference': None}
        if not frappe.db.exists("Contact", content['contact']):
            return {'success': False, 'message': "Contact not found", 'reference': None}
        # create quotation
        qtn_doc = frappe.get_doc({
            'doctype': "Quotation",
            'quotation_to': "Customer",
            'party_name': content['customer'],
            'customer_address': content['invoice_address'],
            'shipping_address': content['delivery_address'],
            'contact_person': content['contact'],
            'customer_request': content['customer_request']
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
            # qtn_doc.submit()          # do not submit - leave on draft for easy edit, sales will process this
            return {'status': True, 'message': 'Quotation created', 
                'reference': qtn_doc.name}
        except Exception as err:
            return {'status': False, 'message': err, 'reference': None}
    else:
        return {'status': False, 'message': 'Authentication failed', 'reference': None}

"""
Returns the quotations for a particular customer
"""
@frappe.whitelist(allow_guest=True)
def get_quotations(key, customer, client="webshop"):
    # check access
    if check_key(key):
        if frappe.db.exists("Customer", customer):
            # return valid quotations
            qtns = frappe.get_all("Quotation", 
                filters={'party_name': customer, 'docstatus': 1},
                fields=['name', 'currency', 'net_total', 'transaction_date', 'customer_request']
            )
            return {'status': True, 'message': "OK", 'quotations': qtns}
        else:
            return {'status': False, 'message': 'Customer not found', 'quotation': None}
    else:
        return {'status': False, 'message': 'Authentication failed', 'quotations': None}

"""
Returns the quotations details
"""
@frappe.whitelist(allow_guest=True)
def get_quotation_detail(key, reference, client="webshop"):
    # check access
    if check_key(key):
        if frappe.db.exists("Quotation", reference):
            # get quotation
            qtn = frappe.get_doc("Quotation", reference)
            return {'status': True, 'message': "OK", 'quotation': qtn.as_dict()}
        else:
            return {'status': False, 'message': 'Quotation not found', 'quotation': None}
    else:
        return {'status': False, 'message': 'Authentication failed', 'quotation': None}

"""
Returns the specific prices for a customer/items
"""
@frappe.whitelist(allow_guest=True)
def get_item_prices(key, content, client="webshop"):
    # check access
    if check_key(key):
        # make sure items are a json object
        if type(content) == str:
            content = json.loads(content)
        if frappe.db.exists("Customer", content['customer']):
            # create virtual sales order to compute prices
            so = frappe.get_doc({
                'doctype': "Sales Order", 
                'customer': content['customer'],
                'currency': content['currency'],
                'delivery_date': date.today()
            })
            for i in content['items']:
                if frappe.db.exists("Item", i['item_code']):
                    so.append('items', {
                        'item_code': i['item_code'],
                        'qty': i['qty']
                    })
                else:
                    return {'status': False, 'message': 'Item {0} not found'.format(i['item_code']), 'quotation': None}
            # temporarily insert
            so.insert(ignore_permissions=True)
            item_prices = []
            for i in so.items:
                item_prices.append({
                    'item_code': i.item_code,
                    'qty': i.qty,
                    'rate': i.rate
                })
            # remove temporary record
            so.delete()
            return {'status': True, 'message': "OK", 'item_prices': item_prices}
        else:
            return {'status': False, 'message': 'Customer not found', 'quotation': None}
    else:
        return {'status': False, 'message': 'Authentication failed', 'quotation': None}

"""
Place an order
"""
@frappe.whitelist(allow_guest=True)
def place_order(key, content, client="webshop"):
    # check access
    if check_key(key):
        # prepare parameters
        if type(content) == str:
            content = json.loads(content)
        # validate input
        if not frappe.db.exists("Customer", content['customer']):
            return {'success': False, 'message': "Customer not found", 'reference': None}
        if not frappe.db.exists("Address", content['delivery_address']):
            return {'success': False, 'message': "Delivery address not found", 'reference': None}
        if not frappe.db.exists("Address", content['invoice_address']):
            return {'success': False, 'message': "Invoice address not found", 'reference': None}
        if not frappe.db.exists("Contact", content['contact']):
            return {'success': False, 'message': "Contact not found", 'reference': None}
        # create quotation
        so_doc = frappe.get_doc({
            'doctype': "Sales Order",
            'customer': content['customer'],
            'customer_address': content['invoice_address'],
            'shipping_address': content['delivery_address'],
            'contact_person': content['contact'],
            'customer_request': content['customer_request'],
            'delivery_date': (date.today() + timedelta(days=3))
        })
        # create oligos
        if 'quotation' in content:
            quotation = content['quotation']
        else:
            quotation = None
        for o in content['oligos']:
            # create or update oligo
            oligo_name = create_oligo(o)
            # insert positions
            for i in o['items']:
                if not frappe.db.exists("Item", i['item_code']):
                    return {'success': False, 'message': "invalid item: {0}".format(i['item_code']), 
                        'reference': None}
                so_doc.append('items', {
                    'item_code': i['item_code'],
                    'qty': i['qty'],
                    'oligo': oligo_name,
                    'prevdoc_docname': quotation
                })
        # append items
        for i in content['items']:
            if not frappe.db.exists("Item", i['item_code']):
                return {'success': False, 'message': "invalid item: {0}".format(i['item_code']), 
                    'reference': None}
            so_doc.append('items', {
                'item_code': i['item_code'],
                'qty': i['qty'],
                'prevdoc_docname': quotation
            })
        try:
            so_doc.insert(ignore_permissions=True)
            so_doc.submit()
            return {'status': True, 'message': 'Sales Order created', 
                'reference': so_doc.name}
        except Exception as err:
            return {'status': False, 'message': err, 'reference': None}
    else:
        return {'status': False, 'message': 'Authentication failed', 'reference': None}
