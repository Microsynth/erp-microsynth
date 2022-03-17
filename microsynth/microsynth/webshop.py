# -*- coding: utf-8 -*-
# Copyright (c) 2022, libracore (https://www.libracore.com) and contributors
# For license information, please see license.txt

import frappe
import json
from microsynth.microsynth.migration import update_customer

@frappe.whitelist(allow_guest=True)
def ping():
    return "pong"
    
@frappe.whitelist()
def create_update_customer(customer_data):
    if type(customer_data) == str:
        customer_data = json.loads(customer_data)
    error = update_customer(customer_data)
    if not error:
        return {'status': 'Success'}
    else: 
        return {'status': error}
