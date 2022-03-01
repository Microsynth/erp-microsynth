# -*- coding: utf-8 -*-
# Copyright (c) 2022, libracore (https://www.libracore.com) and contributors
# For license information, please see license.txt

import frappe
from frappe import _
import csv

"""
This function imports/updates the customer master data from a CSV file

Import file column headers
  person_id         Person ID
  customer_id       Customer number
  customer_name     Customer name
  first_name
  last_name
  email
  address_line1
  pincode
  city
  country
  institute
  department

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
                    update_customer(headers, row)
                else:
                    frappe.throw("Data length mismatch on {0} (header:{1}/row:{2}".format(row, len(headers), len(row)))
    return
    
"""
This function will update a customer master (including contact & address)
"""
def update_customer(headers, fields):
    # if person_id and/or customer_id are missing, skip
    if not fields[headers['person_id']] or not fields[headers['customer_id']]:
        print("No ID record, skipping ({0})".format(fields))
        return
    # check mandatory fields
    if not fields[headers['customer_name']] or not fields[headers['first_name']]:
        print("Mandatory field missing, skipping ({0})".format(fields))
        return
    # check if the customer exists
    if not frappe.db.exists("Customer", fields[headers['customer_id']]):
        # create customer (force mode to achieve target name)
        print("Creating customer {0}...".format(fields[headers['customer_id']]))
        frappe.db.sql("""INSERT INTO `tabCustomer` 
                        (`name`, `customer_name`) 
                        VALUES ("{0}", "{1}");""".format(
                        fields[headers['customer_id']], fields[headers['customer_name']]))
                        
        
    # update customer
    customer = frappe.get_doc("Customer", fields[headers['customer_id']])
    print("Updating customer {0}...".format(customer.name))
    customer.customer_name = fields[headers['customer_name']]
    if fields[headers['adr_type']] == "INV" and fields[headers['email']]:
        customer.invoice_to = fields[headers['email']]
        
    if not customer.customer_group:
        customer.customer_group = frappe.get_value("Selling Settings", "Selling Settings", "customer_group")
    if not customer.territory:
        customer.territory = frappe.get_value("Selling Settings", "Selling Settings", "territory")
    
    customer.save()       
    
    # check if address exists (force insert onto target id)
    if not frappe.db.exists("Address", fields[headers['person_id']]):
        print("Creating address {0}...".format(fields[headers['person_id']]))
        frappe.db.sql("""INSERT INTO `tabAddress` 
                        (`name`, `address_line1`) 
                        VALUES ("{0}", "{1}");""".format(
                        fields[headers['person_id']], fields[headers['address_line1']]))
    # update contact
    print("Updating address {0}...".format(fields[headers['person_id']]))
    address = frappe.get_doc("Address", fields[headers['person_id']])
    address.address_type = "Billing"
    address.address_title = "{0} - {1}".format(fields[headers['customer_name']], fields[headers['address_line1']])
    address.address_line1 = fields[headers['address_line1']]
    address.pincode = fields[headers['pincode']]
    address.city = fields[headers['city']]
    if frappe.db.exists("Country", fields[headers['country']]):
        address.country = fields[headers['country']]
    else:
        # check if this is an ISO code match
        countries = frappe.get_all("Country", filters={'code': fields[headers['country']].lower()}, fields=['name'])
        if countries and len(countries) > 0:
            address.country = countries[0]['name']
        else: 
            address.country = "Schweiz"
            print("Country fallback from {0} in {1}".format(fields[headers['country']], fields[headers['customer_id']]))
    address.links = []
    address.append("links", {
        'link_doctype': "Customer",
        'link_name': fields[headers['customer_id']]
    })
    # get type of address
    if fields[headers['adr_type']] == "INV":
        address.is_primary_address = 1
        address.email_id = fields[headers['email']]         # invoice address: pull email also into address record
        address.address_type = "Billing"
    else:
        address.is_shipping_address = 1
        address.address_type = "Shipping"
        
    try:
        address.save()
    except Exception as err:
        print("Failed to save address: {0}".format(err))
    
    # check if contact exists (force insert onto target id)
    if not frappe.db.exists("Contact", fields[headers['person_id']]):
        print("Creating contact {0}...".format(fields[headers['person_id']]))
        frappe.db.sql("""INSERT INTO `tabContact` 
                        (`name`, `first_name`) 
                        VALUES ("{0}", "{1}");""".format(
                        fields[headers['person_id']], fields[headers['first_name']]))
    # update contact
    print("Updating contact {0}...".format(fields[headers['person_id']]))
    contact = frappe.get_doc("Contact", fields[headers['person_id']])
    contact.first_name = fields[headers['first_name']]
    contact.last_name = fields[headers['last_name']]
    contact.full_name = "{first_name} {last_name}".format(first_name=contact.first_name, last_name=contact.last_name)
    contact.institute = fields[headers['institute']]
    contact.department = fields[headers['department']]
    contact.email_ids = []
    if fields[headers['email']]:
        contact.append("email_ids", {
            'email_id': fields[headers['email']],
            'is_primary': 1
        })
    contact.links = []
    contact.append("links", {
        'link_doctype': "Customer",
        'link_name': fields[headers['customer_id']]
    })
    contact.address = address.name
    contact.save()
    
    frappe.db.commit()
    
    return
