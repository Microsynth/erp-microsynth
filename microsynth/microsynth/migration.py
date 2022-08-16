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
from datetime import datetime, date
from microsynth.microsynth.report.pricing_configurator.pricing_configurator import populate_from_reference

PRICE_LIST_NAMES = {
    'CHF': "Sales Prices CHF",
    'EUR': "Sales Prices EUR",
    'USD': "Sales Prices USD",
    'SEK': "Sales Prices SEK",
    'CZK': "Sales Prices CZK"
}

CUSTOMER_HEADER = """person_id\tcustomer_id\tcustomer_name\tfirst_name\tlast_name\temail\taddress_line1\tpincode\tcity\tinstitute\tdepartment\tcountry\tDS_Nr\tadr_type\tvat_nr\tsiret\tcurrency\tis_deleted\tdefault_discount\tis_electronic_invoice\treceive_updates_per_emailis_punchout_user\tpunchout_identifier\tpunchout_shop_id\troom\tsalutation\ttitle\tgroup_leader\temail_cc\tphone_number\tphone_country\tinstitute_key\tnewsletter_registration_state\tnewsletter_registration_date\tnewsletter_unregistration_date\tumr_nr\tinvoicing_method\tsales_manager\n"""
CUSTOMER_HEADER_FIELDS = """{person_id}\t{customer_id}\t{customer_name}\t{first_name}\t{last_name}\t{email}\t{address_line1}\t{pincode}\t{city}\t{institute}\t{department}\t{country}\t{DS_Nr}\t{adr_type}\t{vat_nr}\t{siret}\t{currency}\t{is_deleted}\t{default_discount}\t{is_electronic_invoice}\t{receive_updates_per_emailis_punchout_user}\t{punchout_identifier}\t{punchout_shop_id}\t{room}\t{salutation}\t{title}\t{group_leader}\t{email_cc}\t{phone_number}\t{phone_country}\t{institute_key}\t{newsletter_registration_state}\t{newsletter_registration_date}\t{newsletter_unregistration_date}\t{umr_nr}\t{invoicing_method}\t{sales_manager}\n"""

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
This function will create a customer export file from ERP to Gecko

"""
def export_customers(filename, from_date):
    # create file
    f = open(filename, "w")
    # write header
    f.write(CUSTOMER_HEADER)
    # get applicable records changed since from_date
    sql_query = """SELECT 
           `tabAddress`.`name` AS `person_id`,
           `tabCustomer`.`name` AS `customer_id`,
           `tabCustomer`.`customer_name` AS `customer_name`,
           `tabContact`.`first_name` AS `first_name`,
           `tabContact`.`last_name` AS `last_name`,
           `tabContact`.`email_id` AS `email`,
           `tabAddress`.`address_line1` AS `address_line1`,
           `tabAddress`.`pincode` AS `pincode`,
           `tabAddress`.`city` AS `city`,
           `tabContact`.`institute` AS `institute`,
           `tabContact`.`department` AS `department`,
           `tabCountry`.`code` AS `country`,
           "" AS `ds_nr`,
           `tabAddress`.`address_type` AS `adr_type`,
           `tabCustomer`.`tax_id` AS `vat_nr`,
           `tabCustomer`.`siret` AS `siret`,
           `tabCustomer`.`default_currency` AS `currency`,
           `tabCustomer`.`disabled` AS `is_deleted`,
           `tabPrice List`.`general_discount` AS `default_discount`,
           0 AS `is_electronic_invoice`,
           0 AS `receive_updates_per_emailis_punchout_user`,
           `tabCustomer`.`punchout_identifier` AS `punchout_identifier`,
           `tabCustomer`.`punchout_shop` AS `punchout_shop_id`,
           `tabContact`.`room` AS `room`,
           `tabContact`.`salutation` AS `salutation`,
           `tabContact`.`designation` AS `title`,
           `tabContact`.`group_leader` AS `group_leader`,
           NULL AS `email_cc`,
           `tabContact`.`phone` AS `phone_number`,
           `tabCountry`.`code` AS `phone_country`,
           `tabContact`.`institute_key` AS `institute_key`,
           `tabContact`.`receive_newsletter` AS `newsletter_registration_state`,
           `tabContact`.`subscribe_date` AS `newsletter_registration_date`,
           `tabContact`.`unsubscribe_Date` AS `newsletter_unregistration_date`,
           NULL AS `umr_nr`,
           `tabCustomer`.`invoicing_method` AS `invoicing_method`,
           `tabUser`.`username` AS `sales_manager`
        FROM `tabAddress`
        LEFT JOIN `tabDynamic Link` AS `tDLA` ON `tDLA`.`parent` = `tabAddress`.`name` 
                                              AND `tDLA`.`parenttype`  = "Address" 
                                              AND `tDLA`.`link_doctype` = "Customer"
        LEFT JOIN `tabCustomer` ON `tabCustomer`.`name` = `tDLA`.`link_name` 
        LEFT JOIN `tabContact` ON `tabContact`.`address` = `tabAddress`.`name`
        LEFT JOIN `tabPrice List` ON `tabPrice List`.`name` = `tabCustomer`.`default_price_list`
        LEFT JOIN `tabUser` ON `tabCustomer`.`account_manager` = `tabUser`.`name`
        LEFT JOIN `tabCountry` ON `tabCountry`.`name` = `tabAddress`.`country`
        WHERE `tabCustomer`.`modified` >= "{from_date}"
           OR `tabAddress`.`modified` >= "{from_date}"
           OR `tabContact`.`modified` >= "{from_date}"
    """.format(from_date=from_date)
    data = frappe.db.sql(sql_query, as_dict=True)
    for d in data:
        row = CUSTOMER_HEADER_FIELDS.format(
            person_id=d['person_id'],
            customer_id=d['customer_id'],
            customer_name=d['customer_name'],
            first_name=d['first_name'],
            last_name=d['last_name'],
            email=d['email'],
            address_line1=d['address_line1'],
            pincode=d['pincode'],
            city=d['city'],
            institute=d['institute'],
            department=d['department'],
            country=d['country'],
            DS_Nr=d['ds_nr'],
            adr_type=d['adr_type'],
            vat_nr=d['vat_nr'],
            siret=d['siret'],
            currency=d['currency'],
            is_deleted=d['is_deleted'],
            default_discount=d['default_discount'],
            is_electronic_invoice=d['is_electronic_invoice'],
            receive_updates_per_emailis_punchout_user=d['receive_updates_per_emailis_punchout_user'],
            punchout_identifier=d['punchout_identifier'],
            punchout_shop_id=d['punchout_shop_id'],
            room=d['room'],
            salutation=d['salutation'],
            title=d['title'],
            group_leader=d['group_leader'],
            email_cc=d['email_cc'],
            phone_number=d['phone_number'],
            phone_country=d['phone_country'],
            institute_key=d['institute_key'],
            newsletter_registration_state=d['newsletter_registration_state'],
            newsletter_registration_date=d['newsletter_registration_date'],
            newsletter_unregistration_date=d['newsletter_unregistration_date'],
            umr_nr=d['umr_nr'],
            invoicing_method=d['invoicing_method'],
            sales_manager=d['sales_manager']
        )
        f.write(row)
    # close file
    f.close()
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
        if not customer_data['customer_id']:
            error = "No ID record, skipping ({0})".format(customer_data)
            print(error)
            return
        if not 'addresses' in customer_data and not 'person_id' in customer_data:
            error = "No ID record, skipping ({0})".format(customer_data)
            print(error)
            return
        # check mandatory fields
        if not customer_data['customer_name']: # or not customer_data['address_line1']:
            error = "Mandatory field customer_name missing, skipping ({0})".format(customer_data)
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
        
        if 'is_deleted' in customer_data:
            if customer_data['is_deleted'] == "Ja" or str(customer_data['is_deleted']) == "1":
                is_deleted = 1
            else:
                is_deleted = 0
        else:
            is_deleted = 0
            
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
            customer.disabled = is_deleted                              # in case is_deleted (can be 1 or 0) is on the INV record
            
        if not customer.customer_group:
            customer.customer_group = frappe.get_value("Selling Settings", "Selling Settings", "customer_group")
        if not customer.territory:
            customer.territory = frappe.get_value("Selling Settings", "Selling Settings", "territory")
        
        if 'vat_nr' in customer_data:
            customer.tax_id = customer_data['vat_nr']
        if 'tax_id' in customer_data:
            customer.tax_id = customer_data['tax_id']
        if 'siret' in customer_data:
            customer.siret = customer_data['siret']
        if 'currency' in customer_data:
            customer.default_currency = customer_data['currency']
        if 'invoicing_method' in customer_data and customer_data['invoicing_method']:
            if customer_data['invoicing_method'] in ["Post", "Paynet", "Email", "ARIBA", "Carlo ERBA", "GEP", "Corus", "X-Rechnung", "Scientist"]:
                customer.invoicing_method = customer_data['invoicing_method']
            elif customer_data['invoicing_method'] == "PDF":
                customer.invoicing_method = "Email"
            else:
                customer.invoicing_method = "Email"
        else:
            customer.invoicing_method = "Email"
        if 'electronic_invoice' in customer_data:
            if cint(customer_data['electronic_invoice']) == 1: 
                customer.invoicing_method = "Email"
            else:
                customer.invoicing_method = "Post"
        if 'sales_manager' in customer_data:
            users = frappe.db.sql("""SELECT `name` FROM `tabUser` WHERE `username` LIKE "{0}";""".format(customer_data['sales_manager']), as_dict=True)
            if len(users) > 0:
                customer.account_manager = users[0]['name']
        if 'invoice_email' in customer_data:
            customer.invoice_email = customer_data['invoice_email']
        if 'default_company' in customer_data:
            companies = frappe.get_all("Company", filters={'abbr': customer_data['default_company']}, fields=['name'])
            if len(companies) > 0:
                customer.default_company = companies[0]['name']
            
        # extend customer bindings here
        customer.flags.ignore_links = True				# ignore links (e.g. invoice to contact that is imported later)
        customer.save(ignore_permissions=True)       
        
        # update address
        address_name = update_address(customer_data, is_deleted=is_deleted)     # base address
        if 'addresses' in customer_data:
            # multiple addresses:
            for adr in customer_data['addresses']:
                update_address(adr, is_deleted=is_deleted, customer_id=customer_data['customer_id'])
                
        # update contact
        
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
            if 'email' in customer_data and customer_data['email']:
                contact.append("email_ids", {
                    'email_id': customer_data['email'],
                    'is_primary': 1
                })
            if 'email_cc' in customer_data and customer_data['email_cc']:
                contact.append("email_ids", {
                    'email_id': customer_data['email_cc'],
                    'is_primary': 0
                })
            contact.phone_nos = []
            if 'phone_number' in customer_data and customer_data['phone_number']:
                if 'phone_country' in customer_data:
                    number = "{0} {1}".format(customer_data['phone_country'] or "", 
                        customer_data['phone_number'])
                else:
                    number = "{0}".format(customer_data['phone_number'])
                contact.append("phone_nos", {
                    'phone': number,
                    'is_primary_phone': 1
                })
            contact.links = []
            if not is_deleted:
                contact.append("links", {
                    'link_doctype': "Customer",
                    'link_name': str(int(customer_data['customer_id']))
                })
            if 'institute_key' in customer_data:
                contact.institute_key = customer_data['institute_key']
            if 'group_leader' in customer_data:
                contact.group_leader = customer_data['group_leader']
            if address_name:
                contact.address = address_name
            if 'salutation' in customer_data and customer_data['salutation']:
                if not frappe.db.exists("Salutation", customer_data['salutation']):
                    frappe.get_doc({
                        'doctype': 'Salutation',
                        'salutation': customer_data['salutation']
                    }).insert()
                contact.salutation = customer_data['salutation']
            if 'title' in customer_data:
                contact.designation = customer_data['title']
            if 'receive_updates_per_email' in customer_data and customer_data['receive_updates_per_email'] == "Mailing":
                contact.unsubscribed = 0
            else:
                contact.unsubscribed = 1
            if 'room' in customer_data:
                contact.room = customer_data['room']
            if 'punchout_shop_id' in customer_data:
                contact.punchout_buyer = customer_data['punchout_shop_id']
            if 'punchout_buyer' in customer_data:
                contact.punchout_buyer = customer_data['punchout_buyer']
            if 'punchout_identifier' in customer_data:
                contact.punchout_identifier = customer_data['punchout_identifier']
            if 'newsletter_registration_state' in customer_data:
                if customer_data['newsletter_registration_state'] == "registered":
                    contact.receive_newsletter = "registered"
                elif customer_data['newsletter_registration_state'] == "unregistered":
                    contact.receive_newsletter = "unregistered"
                elif customer_data['newsletter_registration_state'] == "pending":
                    contact.receive_newsletter = "pending"
                elif customer_data['newsletter_registration_state'] == "bounced":
                    contact.receive_newsletter = "bounced"
                else:
                    contact.receive_newsletter = ""
            if 'newsletter_registration_date' in customer_data:
                try:
                    contact.subscribe_date = datetime.strptime(customer_data['newsletter_registration_date'], "%d.%m.%Y %H:%M:%S")
                except:
                    # fallback date only 
                    try:
                        contact.subscribe_date = datetime.strptime(customer_data['newsletter_registration_date'], "%d.%m.%Y")
                    except:
                        print("failed to parse subscription date: {0}".format(customer_data['newsletter_registration_date']))
            if 'newsletter_unregistration_date' in customer_data:
                try:
                    contact.unsubscribe_date = datetime.strptime(customer_data['newsletter_unregistration_date'], "%d.%m.%Y %H:%M:%S")
                except:
                    # fallback date only 
                    try:
                        contact.unsubscribe_date = datetime.strptime(customer_data['newsletter_unregistration_date'], "%d.%m.%Y")
                    except:
                        print("failed to parse unsubscription date: {0}".format(customer_data['newsletter_unregistration_date']))
            # extend contact bindings here
            contact.save(ignore_permissions=True)
        
        frappe.db.commit()
    
    return error

"""
Processes data to update an address record
"""
def update_address(customer_data, is_deleted=False, customer_id=None):
    frappe.log_error(customer_data)
    if not 'person_id' in customer_data:
        return None
    if not 'address_line1' in customer_data:
        return None
        
    print("Updating address {0}...".format(str(int(customer_data['person_id']))))
    # check if address exists (force insert onto target id)
    if not frappe.db.exists("Address", str(int(customer_data['person_id']))):
        print("Creating address {0}...".format(str(int(customer_data['person_id']))))
        frappe.db.sql("""INSERT INTO `tabAddress` 
                        (`name`, `address_line1`) 
                        VALUES ("{0}", "{1}");""".format(
                        str(int(customer_data['person_id'])), 
                        customer_data['address_line1'] if 'address_lin1' in customer_data else "-"))
    
    # update record
    if 'adr_type' in customer_data:
        adr_type = customer_data['adr_type']
    else:
        adr_type = None
    address = frappe.get_doc("Address", str(int(customer_data['person_id'])))
    if 'customer_name' in customer_data and 'address_line1' in customer_data:
        address.address_title = "{0} - {1}".format(customer_data['customer_name'], customer_data['address_line1'])
    if 'address_line1' in customer_data:
        address.address_line1 = customer_data['address_line1']
    if 'address_line2' in customer_data:
        address.address_line2 = customer_data['address_line2']
    if 'pincode' in customer_data:
        address.pincode = customer_data['pincode']
    if 'city' in customer_data:
        address.city = customer_data['city']
    if 'country' in customer_data:
        address.country = robust_get_country(customer_data['country'])
    if customer_id or 'customer_id' in customer_data:
        address.links = []
        if not is_deleted:
            address.append("links", {
                'link_doctype': "Customer",
                'link_name': str(int(customer_id or customer_data['customer_id']))
            })
    # get type of address
    if adr_type == "INV":
        address.is_primary_address = 1
        address.email_id = customer_data['email']        # invoice address: pull email also into address record
        address.address_type = "Billing"
    else:
        address.is_shipping_address = 1
        address.address_type = "Shipping"
    if 'customer_address_id' in customer_data:
        address.customer_address_id = customer_data['customer_address_id']
        
    # extend address bindings here
    frappe.log_error("saving")
    try:
        address.save(ignore_permissions=True)
        return address.name
    except Exception as err:
        print("Failed to save address: {0}".format(err))
        frappe.log_error("Failed to save address: {0}".format(err))
        return None

"""
Robust country find function: accepts country name or code
"""
def robust_get_country(country_name_or_code):
    if frappe.db.exists("Country", country_name_or_code):
        return country_name_or_code
    else:
        # check if this is an ISO code match
        countries = frappe.get_all("Country", filters={'code': (country_name_or_code or "NA").lower()}, fields=['name'])
        if countries and len(countries) > 0:
            return countries[0]['name']
        else:
            return frappe.defaults.get_global_default('country')
            
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
            price_list=PRICE_LIST_NAMES['CHF'],
            price_list_rate=price_data['price_chf'], 
            min_qty=price_data['minimum_quantity'], 
            currency="CHF")
        update_pricelist(item_code=price_data['item_code'], 
            price_list=PRICE_LIST_NAMES['EUR'],
            price_list_rate=price_data['price_eur'], 
            min_qty=price_data['minimum_quantity'], 
            currency="EUR")
        update_pricelist(item_code=price_data['item_code'], 
            price_list=PRICE_LIST_NAMES['USD'],
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

"""
Import customer price list

Headers (\t): PriceList ["1234"], BasisPriceList ["CHF"], GeneralDiscount ["0"], ArticleCode, Discount

Run from bench like
 $ bench execute microsynth.microsynth.migration.import_customer_price_lists --kwargs "{'filename': '/home/libracore/customerPrices.tab'}"
"""
def import_customer_price_lists(filename):
    # load csv file
    with open(filename) as csvfile:
        # create reader
        reader = pd.read_csv(csvfile, delimiter='\t', quotechar='"', 
            encoding='utf-8', dtype={'ArticleCode': object})
        print("Reading file...")
        count = 0
        file_length = len(reader.index)
        # replace NaN with None
        reader = reader.replace({np.nan: None})
        # go through rows
        for index, row in reader.iterrows():
            count += 1
            print("...{0}%...".format(int(100 * count / file_length)))
            print("{0}".format(row))
            create_update_customer_price_list(
                pricelist_code = row['PriceList'], 
                currency = row['BasisPriceList'], 
                general_discount = float(row['GeneralDiscount']), 
                item_code = row['ArticleCode'], 
                discount = float(row['Discount'])
            )
    frappe.db.commit()
    return

def get_long_price_list_name(price_list_code):
    return "Pricelist {0}".format(price_list_code)
        
def create_update_customer_price_list(pricelist_code, currency, 
        general_discount, item_code, discount, qty=1):
    pl_long_name = get_long_price_list_name(pricelist_code)
    # check if it exists
    if not frappe.db.exists("Price List", pl_long_name):
        # create new price list
        pl = frappe.get_doc({
            'doctype': "Price List",
            'price_list_name': pl_long_name,
            'selling': 1,
            'currency': currency
        })
        pl.insert()
    else:
        # load existing price list
        pl = frappe.get_doc("Price List", pl_long_name)
        pl.currency = currency
        pl.save()
    # update values
    pl.reference_price_list = PRICE_LIST_NAMES[currency]
    pl.general_discount = general_discount
    pl.save()
    # find reference prices
    reference_item_prices = frappe.get_all("Item Price",
        filters={
            'price_list': PRICE_LIST_NAMES[currency],
            'item_code': item_code,
            'min_qty': qty
        },
        fields=['name', 'valid_from', 'price_list_rate']
    )
    for ref_price in reference_item_prices:
        # find item prices
        item_prices = frappe.get_all("Item Price", 
            filters={
                'price_list': pl_long_name,
                'item_code': item_code,
                'min_qty': qty,
                'valid_from': ref_price['valid_from']
            },
            fields=['name']
        )
        price_list_rate = ((100 - discount) / 100) * ref_price['price_list_rate']
        if len(item_prices) > 0:
            # update records
            for p in item_prices:
                price_doc = frappe.get_doc("Item Price", p['name'])
                price_doc.discount = discount
                price_doc.price_list_rate = price_list_rate
                price_doc.currency = currency
                price_doc.save()
                print("updated customer item price {0}".format(price_doc.name))
        else:
            # create customer price record
            price_doc = frappe.get_doc({
                'doctype': "Item Price",
                'item_code': item_code,
                'min_qty': qty,
                'price_list': pl_long_name,
                'valid_from': ref_price['valid_from'],
                'discount': discount,
                'price_list_rate': price_list_rate,
                'currency': currency
            })
            price_doc.insert()
            print("created customer item price {0}".format(price_doc.name))
    return

"""
Map customer price lists to customers

Headers (\t): PriceList ["1234"], Customer ["1234"]

Run from bench like
 $ bench execute microsynth.microsynth.migration.map_customer_price_list --kwargs "{'filename': '/home/libracore/customerPrices.tab'}"
"""
def map_customer_price_list(filename):
    # load csv file
    with open(filename) as csvfile:
        # create reader
        reader = pd.read_csv(csvfile, delimiter='\t', quotechar='"', encoding='utf-8')
        print("Reading file...")
        count = 0
        file_length = len(reader.index)
        # replace NaN with None
        reader = reader.replace({np.nan: None})
        # go through rows
        for index, row in reader.iterrows():
            count += 1
            # get and update customer
            if frappe.db.exists("Customer", str(row['Customer'])):
                customer = frappe.get_doc("Customer", str(row['Customer']))
                customer.default_price_list = get_long_price_list_name(row['PriceList'])
                customer.flags.ignore_links = True                      # ignore links (e.g. invoice to contact that is imported later)
                customer.save()
                print("...{0}%... Linked {1}".format(int(100 * count / file_length), str(row['Customer'])))
            else:
                print("Customer {0} not found!".format(str(row['Customer'])))
    frappe.db.commit()
    return

"""
Go through all price lists and populate missing prices

Run from bench like
 $ bench execute microsynth.microsynth.migration.populate_price_lists
"""
def populate_price_lists():
    price_lists = frappe.db.sql("""
        SELECT `name`
        FROM `tabPrice List`
        WHERE `reference_price_list` IS NOT NULL;""", as_dict=True)
    count = 0
    start_ts = None
    for p in price_lists:
        count += 1
        start_ts = datetime.now()
        print("Updating {0}... ({1}%)".format(p['name'], int(100 * count / len(price_lists))))
        populate_from_reference(price_list=p['name'])
        print("... {0} sec".format((datetime.now() - start_ts).total_seconds()))
    return

"""
Move item price from staggered item to base item

Run from bench like
 $ bench execute microsynth.microsynth.migration.move_staggered_item_price --kwargs "{'filename': '/home/libracore/staggered_prices.tab'}"
"""
def move_staggered_item_price(filename):
    with open(filename) as csvfile:
        # create reader
        reader = pd.read_csv(csvfile, delimiter='\t', quotechar='"', encoding='utf-8')
        print("Reading file...")
        count = 0
        file_length = len(reader.index)
        # replace NaN with None
        reader = reader.replace({np.nan: None})
        # go through rows
        for index, row in reader.iterrows():
            count += 1
            print("...{0}%...".format(int(100 * count / file_length)))
            staggered_item_code = row['ArticleCode']
            base_item_code = row['BaseArticleCode']
            min_qty = row['Quantity']
            matching_item_prices = frappe.get_all("Item Price", filters={'item_code': staggered_item_code}, fields=['name'])
            print("{0} with {1} records...".format(staggered_item_code, len(matching_item_prices)))
            for item_price in matching_item_prices:
                item_price_doc = frappe.get_doc("Item Price", item_price['name'])
                item_price_doc.item_code = base_item_code
                item_price_doc.min_qty = min_qty
                item_price_doc.save()
        frappe.db.commit()
    return

""" 
Sets the "webshop_address_readonly" from the contacts
This is used that users cannot change a jointly used customer/address

Run from
 $ bench execute microsynth.microsynth.migration.set_webshop_address_readonly
"""
def set_webshop_address_readonly():
    customers = frappe.get_all("Customer", filters={'disabled': 0}, fields=['name'])
    count = 0
    for c in customers:
        count += 1
        # find number of linked contacts
        linked_contacts = frappe.db.sql("""
            SELECT `name`
            FROM `tabDynamic Link`
            WHERE `tabDynamic Link`.`parenttype` = "Contact"
                AND `tabDynamic Link`.`link_doctype` = "Customer"
                AND `tabDynamic Link`.`link_name` = "{customer_id}"
        """.format(customer_id=c['name']), as_dict=True)
        if len(linked_contacts) > 2:
            readonly = 1
        else:
            readonly = 0
        if readonly != frappe.get_value("Customer", c['name'], "webshop_address_readonly"):
            customer = frappe.get_doc("Customer", c['name'])
            customer.webshop_address_readonly = readonly
            try:
                customer.save()
                print("{1}%... Updated {0}".format(c['name'], int(100 * count / len(customers))))
            except Exception as err:
                print("{2}%... Failed updating {0} ({1})".format(c['name'], err, int(100 * count / len(customers))))
        else:
            print("{1}%... Skipped {0}".format(c['name'], int(100 * count / len(customers))))
    return
