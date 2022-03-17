# -*- coding: utf-8 -*-
# Copyright (c) 2022, libracore (https://www.libracore.com) and contributors
# For license information, please see license.txt

import frappe
import json
from microsynth.microsynth.migration import update_customer

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
            return {'status': 'Success'}
        else: 
            return {'status': error}
    else:
        return {'status': 'Authentication failed'}

def check_key(key):
    server_key = frappe.get_value("Microsynth Webshop Settings", "Microsynth Webshop Settings", "preshared_key")
    if server_key == key:
        return True
    else:
        return False
