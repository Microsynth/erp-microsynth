# -*- coding: utf-8 -*-
# Copyright (c) 2022, libracore (https://www.libracore.com) and contributors
# For license information, please see license.txt

import frappe
from frappe import _
import csv
import json

"""
This function imports/updates the customer master data from a CSV file

Columns should follow the customer_data structure, see https://github.com/Microsynth/erp-microsynth/wiki/customer_data-object

Run from bench like
 $ bench execute microsynth.microsynth.migration.import_customers --kwargs "{'filename': '/home/libracore/frappe-bench/apps/microsynth/microsynth/docs/customer_import_sample.csv'}"
"""
def import_customers(filename):
    # load csv file
    with open(filename) as csvfile:
        # create reader
        reader = csv.reader(csvfile, delimiter='\t', quotechar='"')
        headers = None
        print("Reading file...")
        # go through rows
        for row in reader:
            #fields = row.split("\t")
            # if headers are not ready, get them (field_name: id)
            if not headers:
                headers = {}
                for i in range(0, len(row)):
                    headers[row[i]] = i
                print("Headers loaded... {0}".format(headers))
            else:
                if len(row) == len(headers):
                    # prepare customer data from rows
                    customer_data = {}
                    for k, v in headers.items():
                        customer_data[k] = row[v]
                    update_customer(customer_data)
                else:
                    frappe.throw("Data length mismatch on {0} (header:{1}/row:{2}".format(row, len(headers), len(row)))
    return

"""
This function will update a customer master (including contact & address)

The function will either accept one customer_data record or a list of the same
"""
def update_customer(customer_data):
    error = None
    # make sure data is a dict or list
    if type(customer_data) == str:
        customer_data = json.loads(customer_data)
    # if customer_data is a list, iterate each entry
    if type(customer_data) == list:
        for c in customer_data:
            update_customer(c)
    else:
        # if person_id and/or customer_id are missing, skip
        if not customer_data['person_id'] or not customer_data['customer_id']:
            error = "No ID record, skipping ({0})".format(customer_data)
            print(error)
            return
        # check mandatory fields
        if not customer_data['customer_name'] or not customer_data['first_name']:
            error = "Mandatory field missing, skipping ({0})".format(customer_data)
            print(error)
            return
        # check if the customer exists
        if not frappe.db.exists("Customer", customer_data['customer_id']):
            # create customer (force mode to achieve target name)
            print("Creating customer {0}...".format(customer_data['customer_id']))
            frappe.db.sql("""INSERT INTO `tabCustomer` 
                            (`name`, `customer_name`) 
                            VALUES ("{0}", "{1}");""".format(
                            customer_data['customer_id'], customer_data['customer_name']))
                            
            
        # update customer
        customer = frappe.get_doc("Customer", customer_data['customer_id'])
        print("Updating customer {0}...".format(customer.name))
        customer.customer_name = customer_data['customer_name']
        if 'adr_type' in customer_data:
            adr_type = customer_data['adr_type']
        else:
            adr_type = None
        if adr_type == "INV" and customer_data['email']:
            customer.invoice_to = customer_data['email']
            
        if not customer.customer_group:
            customer.customer_group = frappe.get_value("Selling Settings", "Selling Settings", "customer_group")
        if not customer.territory:
            customer.territory = frappe.get_value("Selling Settings", "Selling Settings", "territory")
        
        if 'tax_id' in customer_data:
            customer.tax_id = customer_data['tax_id']
        # extend customer bindings here
        
        customer.save(ignore_permissions=True)       
        
        # check if address exists (force insert onto target id)
        if not frappe.db.exists("Address", customer_data['person_id']):
            print("Creating address {0}...".format(customer_data['person_id']))
            frappe.db.sql("""INSERT INTO `tabAddress` 
                            (`name`, `address_line1`) 
                            VALUES ("{0}", "{1}");""".format(
                            customer_data['person_id'], customer_data['address_line1']))
        # update contact
        print("Updating address {0}...".format(customer_data['person_id']))
        address = frappe.get_doc("Address", customer_data['person_id'])
        address.address_title = "{0} - {1}".format(customer_data['customer_name'], customer_data['address_line1'])
        address.address_line1 = customer_data['address_line1']
        address.pincode = customer_data['pincode']
        address.city = customer_data['city']
        if frappe.db.exists("Country", customer_data['country']):
            address.country = customer_data['country']
        else:
            # check if this is an ISO code match
            countries = frappe.get_all("Country", filters={'code': customer_data['country'].lower()}, fields=['name'])
            if countries and len(countries) > 0:
                address.country = countries[0]['name']
            else: 
                address.country = "Schweiz"
                print("Country fallback from {0} in {1}".format(customer_data['country'], customer_data['customer_id']))
        address.links = []
        address.append("links", {
            'link_doctype': "Customer",
            'link_name': customer_data['customer_id']
        })
        # get type of address
        if adr_type == "INV":
            address.is_primary_address = 1
            address.email_id = customer_data['email']        # invoice address: pull email also into address record
            address.address_type = "Billing"
        else:
            address.is_shipping_address = 1
            address.address_type = "Shipping"
        # extend address bindings here
        
        try:
            address.save(ignore_permissions=True)
        except Exception as err:
            print("Failed to save address: {0}".format(err))
        
        # check if contact exists (force insert onto target id)
        if not frappe.db.exists("Contact", customer_data['person_id']):
            print("Creating contact {0}...".format(customer_data['person_id']))
            frappe.db.sql("""INSERT INTO `tabContact` 
                            (`name`, `first_name`) 
                            VALUES ("{0}", "{1}");""".format(
                            customer_data['person_id'], customer_data['first_name']))
        # update contact
        print("Updating contact {0}...".format(customer_data['person_id']))
        contact = frappe.get_doc("Contact", customer_data['person_id'])
        contact.first_name = customer_data['first_name']
        contact.last_name = customer_data['last_name']
        contact.full_name = "{first_name} {last_name}".format(first_name=contact.first_name, last_name=contact.last_name)
        contact.institute = customer_data['institute']
        contact.department = customer_data['department']
        contact.email_ids = []
        if customer_data['email']:
            contact.append("email_ids", {
                'email_id': customer_data['email'],
                'is_primary': 1
            })
        contact.links = []
        contact.append("links", {
            'link_doctype': "Customer",
            'link_name': customer_data['customer_id']
        })
        contact.address = address.name
        # extend contact bindings here
        contact.save(ignore_permissions=True)
        
        frappe.db.commit()
    
    return error
