# -*- coding: utf-8 -*-
# Copyright (c) 2022, libracore (https://www.libracore.com) and contributors
# For license information, please see license.txt

import frappe
from frappe import _
import csv
import pandas as pd
import numpy as np
import json
from frappe.utils import cint

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
        reader = pd.read_csv(csvfile, delimiter='\t', quotechar='"', encoding='utf-8')
        headers = None
        print("Reading file...")
        count = 0
        file_length = len(reader.index)
        # replace NaN with None
        reader = reader.replace({np.nan: None})
        # go through rows
        for index, row in reader.iterrows():
            count += 1
            print("...{0}%...".format(int(100 * count / file_length)))
            #print("{0}".format(row))
            update_customer(row)
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
        if not customer_data['customer_name'] or not customer_data['address_line1']:
            error = "Mandatory field missing, skipping ({0})".format(customer_data)
            print(error)
            return
        # check if the customer exists
        if not frappe.db.exists("Customer", str(int(customer_data['customer_id']))):
            # create customer (force mode to achieve target name)
            print("Creating customer {0}...".format(str(int(customer_data['customer_id']))))
            frappe.db.sql("""INSERT INTO `tabCustomer` 
                            (`name`, `customer_name`) 
                            VALUES ("{0}", "{1}");""".format(
                            str(int(customer_data['customer_id'])), str(customer_data['customer_name'])))
                            
            
        # update customer
        customer = frappe.get_doc("Customer", str(int(customer_data['customer_id'])))
        print("Updating customer {0}...".format(customer.name))
        customer.customer_name = customer_data['customer_name']
        if 'adr_type' in customer_data:
            adr_type = customer_data['adr_type']
        else:
            adr_type = None
        if adr_type == "INV":
            customer.invoice_to = customer_data['person_id']
            
        if not customer.customer_group:
            customer.customer_group = frappe.get_value("Selling Settings", "Selling Settings", "customer_group")
        if not customer.territory:
            customer.territory = frappe.get_value("Selling Settings", "Selling Settings", "territory")
        
        if 'vat_nr' in customer_data:
            customer.tax_id = customer_data['vat_nr']
        if 'currency' in customer_data:
            customer.default_currency = customer_data['currency']
        # extend customer bindings here
        customer.flags.ignore_links = True				# ignore links (e.g. invoice to contact that is imported later)
        customer.save(ignore_permissions=True)       
        
        # check if address exists (force insert onto target id)
        if not frappe.db.exists("Address", str(int(customer_data['person_id']))):
            print("Creating address {0}...".format(str(int(customer_data['person_id']))))
            frappe.db.sql("""INSERT INTO `tabAddress` 
                            (`name`, `address_line1`) 
                            VALUES ("{0}", "{1}");""".format(
                            str(int(customer_data['person_id'])), customer_data['address_line1']))
        # update contact
        print("Updating address {0}...".format(str(int(customer_data['person_id']))))
        address = frappe.get_doc("Address", str(int(customer_data['person_id'])))
        address.address_title = "{0} - {1}".format(customer_data['customer_name'], customer_data['address_line1'])
        address.address_line1 = customer_data['address_line1']
        address.pincode = customer_data['pincode']
        address.city = customer_data['city']
        if frappe.db.exists("Country", customer_data['country']):
            address.country = customer_data['country']
        else:
            # check if this is an ISO code match
            countries = frappe.get_all("Country", filters={'code': (customer_data['country'] or "NA").lower()}, fields=['name'])
            if countries and len(countries) > 0:
                address.country = countries[0]['name']
            else: 
                address.country = "Schweiz"
                print("Country fallback from {0} in {1}".format(customer_data['country'], customer_data['customer_id']))
        address.links = []
        address.append("links", {
            'link_doctype': "Customer",
            'link_name': str(int(customer_data['customer_id']))
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
        
        
        # check mandatory fields for contact
        if not customer_data['first_name']:
            error = "Mandatory contact field missing, skipping ({0})".format(customer_data)
            print(error)
        else:
            # check if contact exists (force insert onto target id)
            if not frappe.db.exists("Contact", str(int(customer_data['person_id']))):
                print("Creating contact {0}...".format(str(int(customer_data['person_id']))))
                frappe.db.sql("""INSERT INTO `tabContact` 
                                (`name`, `first_name`) 
                                VALUES ("{0}", "{1}");""".format(
                                str(int(customer_data['person_id'])), customer_data['first_name']))
            # update contact
            print("Updating contact {0}...".format(str(int(customer_data['person_id']))))
            contact = frappe.get_doc("Contact", str(int(customer_data['person_id'])))
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
            contact.phone_nos = []
            if customer_data['phone_number']:
                contact.append("phone_nos", {
                    'phone': "{0} {1}".format(customer_data['phone_country'] or "", customer_data['phone_number']),
                    'is_primary_phone': 1
                })
            contact.links = []
            contact.append("links", {
                'link_doctype': "Customer",
                'link_name': str(int(customer_data['customer_id']))
            })
            contact.institute_key = customer_data['institute_key']
            contact.address = address.name
            if 'salutation' in customer_data['salutation']:
                if not frappe.db.exists("Salutation"):
                    frappe.get_doc({
                        'doctype': 'Salutation',
                        'salutation': customer_data['salutation']
                    }).insert()
                contact.salutation = customer_data['salutation']
            contact.designation = customer_data['title']
            # extend contact bindings here
            contact.save(ignore_permissions=True)
        
        frappe.db.commit()
    
    return error


"""
This function imports/updates the item price data from a CSV file

Run from bench like
 $ bench execute microsynth.microsynth.migration.import_prices --kwargs "{'filename': '/home/libracore/frappe-bench/apps/microsynth/microsynth/docs/articleExport_with_Header.txt'}"
"""
def import_prices(filename):
    # load csv file
    with open(filename) as csvfile:
        # create reader
        reader = csv.reader(csvfile, delimiter='\t', quotechar='"')
        headers = None
        print("Reading file...")
        # go through rows
        for row in reader:
            # if headers are not ready, get them (field_name: id)
            if not headers:
                headers = {}
                for i in range(0, len(row)):
                    headers[row[i]] = i
                print("Headers loaded... {0}".format(headers))
            else:
                if len(row) == len(headers):
                    # prepare customer data from rows
                    price_data = {}
                    for k, v in headers.items():
                        price_data[k] = row[v]
                    update_prices(price_data)
                else:
                    frappe.throw("Data length mismatch on {0} (header:{1}/row:{2}".format(row, len(headers), len(row)))
    return

"""
This function will update item prices
"""
def update_prices(price_data):
    # check if this item is available
    if frappe.db.exists("Item", price_data['item_code']) and cint(frappe.get_value("Item", price_data['item_code'], "disabled")) == 0:
        update_pricelist(item_code=price_data['item_code'], 
            price_list="Sales Prices CHF",
            price_list_rate=price_data['price_chf'], 
            min_qty=price_data['minimum_quantity'], 
            currency="CHF")
        update_pricelist(item_code=price_data['item_code'], 
            price_list="Sales Prices EUR",
            price_list_rate=price_data['price_eur'], 
            min_qty=price_data['minimum_quantity'], 
            currency="EUR")
        update_pricelist(item_code=price_data['item_code'], 
            price_list="Sales Prices USD",
            price_list_rate=price_data['price_usd'], 
            min_qty=price_data['minimum_quantity'], 
            currency="USD")
    else:
        print("Item {0} not found.".format(price_data['item_code']))
    return
    
def update_pricelist(item_code, price_list, price_list_rate, min_qty, currency):
    # check if this item price already exists
    matching_item_prices = frappe.get_all("Item Price", 
        filters={'item_code': item_code, 'price_list': price_list, 'min_qty': min_qty},
        fields=['name'])
    if matching_item_prices and len(matching_item_prices) > 0:
        item_price = frappe.get_doc("Item Price", matching_item_prices[0]['name'])
        item_price.price_list_rate = price_list_rate
        item_price.save()
    else:
        item_price = frappe.get_doc({
            'doctype': "Item Price",
            'item_code': item_code,
            'min_qty': min_qty,
            'price_list': price_list,
            'buying': 0,
            'selling': 1,
            'currency': currency,
            'price_list_rate': price_list_rate
        })
        item_price.insert()
    frappe.db.commit()
    return

"""
This function imports/updates the discount conditions from a CSV file

Columns are customer_id\titem_code\tdiscount_percent
Run from bench like
 $ bench execute microsynth.microsynth.migration.import_discounts --kwargs "{'filename': '/home/libracore/frappe-bench/apps/microsynth/microsynth/docs/discountExport.tab'}"
"""
def import_discounts(filename):
    # load csv file
    with open(filename) as csvfile:
        # create reader
        reader = csv.reader(csvfile, delimiter='\t', quotechar='"')
        print("Reading file...")
        last_customer = None
        # go through rows
        for row in reader:
            # prepare discount data from rows
            if row[0]:
                last_customer = row[0]
            if row[2]:  # only perform in case there is a percentage
                discount_data = {
                    'customer': last_customer,
                    'item_code': row[1],
                    'discount_percent': float(row[2])
                }
                update_pricing_rule(discount_data)
                print("Imported {0}".format(discount_data))
    return

"""
This function will update pricing rules
"""
def update_pricing_rule(price_data):
    # check if customer exists
    if frappe.db.exists("Customer", price_data['customer']):
        # check if this pricing rule already exists
        matching_pricing_rule = frappe.get_all("Pricing Rule", 
            filters={'item_code': price_data['item_code'], 'customer': price_data['customer']},
            fields=['name'])
        if matching_pricing_rule and len(matching_pricing_rule) > 0:
            pricing_rule = frappe.get_doc("Pricing Rule", matching_pricing_rule[0]['name'])
            pricing_rule.discount_percentage = price_data['discount_percent']
            pricing_rule.save()
        else:
            pricing_rule = frappe.get_doc({
                'doctype': "Pricing Rule",
                'title': "{0} - {1} - {2}p".format(price_data['customer'], price_data['item_code'], price_data['discount_percent']),
                'apply_on': "Item Code",
                'price_or_product_discount': "Price",
                'items': [{
                    'item_code': price_data['item_code']
                }],
                'buying': 0,
                'selling': 1,
                'applicable_for': "Customer",
                'customer': price_data['customer'],
                'rate_or_discount': "Discount Percentage",
                'discount_percentage': price_data['discount_percent'],
                'priority': "1"
            })
            pricing_rule.insert()
        frappe.db.commit()
    else:
        print("Customer {0} not found.".format(price_data['customer']))
    return
