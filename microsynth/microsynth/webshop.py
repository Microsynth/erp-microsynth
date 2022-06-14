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
def create_update_customer(key, customer_data, client="webshop"):
    if check_key(key):
        if type(customer_data) == str:
            customer_data = json.loads(customer_data)
        error = update_customer(customer_data)
        if not error:
            return {'success': True, 'message': "OK"}
        else: 
            return {'success': False, 'message': error}
    else:
        return {'success': False, 'message': 'Authentication failed'}

"""
From a user (AspNetUser), get customer data 
"""
@frappe.whitelist(allow_guest=True)
def get_user_details(key, person_id, client="webshop"):
    if check_key(key):
        # get contact
        contact = frappe.get_doc("Contact", person_id)
        if not contact:
            return {'success': False, 'message': "Person not found"}
        # fetch customer
        customer_id = None
        for l in contact.links:
            if l.link_doctype == "Customer":
                customer_id = l.link_name
        if not customer_id:
            return {'success': False, 'message': "No customer linked"}
        customer = frappe.get_doc("Customer", customer_id)
        # fetch addresses
        addresses = frappe.db.sql(
            """ SELECT 
                    `tabAddress`.`name`,
                    `tabAddress`.`address_type`,
                    `tabAddress`.`address_line1`,
                    `tabAddress`.`pincode`,
                    `tabAddress`.`city`,
                    `tabAddress`.`country`,
                    `tabAddress`.`is_shipping_address`,
                    `tabAddress`.`is_primary_address`
                FROM `tabDynamic Link`
                LEFT JOIN `tabAddress` ON `tabAddress`.`name` = `tabDynamic Link`.`parent`
                WHERE `tabDynamic Link`.`parenttype` = "Address"
                  AND `tabDynamic Link`.`link_doctype` = "Customer"
                  AND `tabDynamic Link`.`link_name` = "35276856"
                ;""".format(customer_id=customer_id), as_dict=True)
            
        # return structure
        return {
            'success': True, 
            'message': "OK", 
            'details': {
                'contact': contact,
                'customer': customer,
                'addresses': addresses
            }
        }
    else:
        return {'success': False, 'message': 'Authentication failed'}
        
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
            return {'success': True, 'message': 'Quotation created', 
                'reference': qtn_doc.name}
        except Exception as err:
            return {'success': False, 'message': err, 'reference': None}
    else:
        return {'success': False, 'message': 'Authentication failed', 'reference': None}

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
            return {'success': True, 'message': "OK", 'quotations': qtns}
        else:
            return {'success': False, 'message': 'Customer not found', 'quotation': None}
    else:
        return {'success': False, 'message': 'Authentication failed', 'quotations': None}

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
            return {'success': True, 'message': "OK", 'quotation': qtn.as_dict()}
        else:
            return {'success': False, 'message': 'Quotation not found', 'quotation': None}
    else:
        return {'success': False, 'message': 'Authentication failed', 'quotation': None}

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
                    return {'success': False, 'message': 'Item {0} not found'.format(i['item_code']), 'quotation': None}
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
            return {'success': True, 'message': "OK", 'item_prices': item_prices}
        else:
            return {'success': False, 'message': 'Customer not found', 'quotation': None}
    else:
        return {'success': False, 'message': 'Authentication failed', 'quotation': None}

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
            'customer_request': content['customer_request'] if 'customer_request' in content else None,
            'delivery_date': (date.today() + timedelta(days=3)),
            'web_order_id': content['web_order_id'] if 'web_order_id' in content else None,
            'is_punchout': content['is_punchout'] if 'is_punchout' in content else None,
            'po_no': content['po_no'] if 'po_no' in content else None
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
            return {'success': True, 'message': 'Sales Order created', 
                'reference': so_doc.name}
        except Exception as err:
            return {'success': False, 'message': err, 'reference': None}
    else:
        return {'success': False, 'message': 'Authentication failed', 'reference': None}

"""
Inform webshop about customer master change
"""
def notify_customer_change(customer):
    ## TODO
    return
