# -*- coding: utf-8 -*-
# Copyright (c) 2022, libracore (https://www.libracore.com) and contributors
# For license information, please see license.txt
#
# For more details, refer to https://github.com/Microsynth/erp-microsynth/wiki/Webshop-API
#

import frappe
import json
from microsynth.microsynth.migration import update_customer, update_address, robust_get_country
from microsynth.microsynth.utils import create_oligo, create_sample, find_tax_template
from microsynth.microsynth.naming_series import get_naming_series
from datetime import date, timedelta
from erpnextswiss.scripts.crm_tools import get_primary_customer_address

"""
Ping is a simple interface test function
"""
@frappe.whitelist(allow_guest=True)
def ping():
    return "pong"

"""
This function will create or update a customer
"""
@frappe.whitelist()
def create_update_customer(customer_data, client="webshop"):
    if type(customer_data) == str:
        customer_data = json.loads(customer_data)
    error = update_customer(customer_data)
    if not error:
        return {'success': True, 'message': "OK"}
    else: 
        return {'success': False, 'message': error}

"""
This function will create or update an address
"""
@frappe.whitelist()
def create_update_address(address, client="webshop"):
    if type(address) == str:
        address = json.loads(address)
    if not 'person_id' in address:
        return {'success': False, 'message': "Person ID missing"}
    if not 'address_line1' in address:
        return {'success': False, 'message': "Address line 1 missing"}
    if not 'city' in address:
        return {'success': False, 'message': "City missing"}
    address_id = update_address(address)
    if address_id:
        return {'success': True, 'message': "OK"}
    else: 
        return {'success': False, 'message': "An error occured while creating/updating the address record"}
        
"""
From a user (AspNetUser), get customer data 
"""
@frappe.whitelist()
def get_user_details(person_id, client="webshop"):
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
    if customer.disabled == 1:
        return {'success': False, 'message': 'Customer disabled'}
    # fetch addresses
    addresses = frappe.db.sql(
        """ SELECT 
                `tabAddress`.`name`,
                `tabAddress`.`address_type`,
                `tabAddress`.`address_line1`,
                `tabAddress`.`address_line2`,
                `tabAddress`.`pincode`,
                `tabAddress`.`city`,
                `tabAddress`.`country`,
                `tabAddress`.`is_shipping_address`,
                `tabAddress`.`is_primary_address`,
                `tabAddress`.`geo_lat`,
                `tabAddress`.`geo_long`,
                `tabAddress`.`customer_address_id`
            FROM `tabDynamic Link`
            LEFT JOIN `tabAddress` ON `tabAddress`.`name` = `tabDynamic Link`.`parent`
            WHERE `tabDynamic Link`.`parenttype` = "Address"
              AND `tabDynamic Link`.`link_doctype` = "Customer"
              AND `tabDynamic Link`.`link_name` = "{customer_id}"
              AND (`tabAddress`.`is_primary_address` = 1 
                   OR `tabAddress`.`name` = "{person_id}")
            ;""".format(customer_id=customer_id, person_id=person_id), as_dict=True)
        
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

"""
Get customer data (addresses: only invoice addresses)
"""
@frappe.whitelist()
def get_customer_details(customer_id, client="webshop"):
    # fetch customer
    customer = frappe.get_doc("Customer", customer_id)
    if customer.disabled == 1:
        return {'success': False, 'message': 'Customer disabled'}
    # fetch addresses
    addresses = frappe.db.sql(
        """ SELECT 
                `tabAddress`.`name`,
                `tabAddress`.`address_type`,
                `tabAddress`.`address_line1`,
                `tabAddress`.`address_line2`,
                `tabAddress`.`pincode`,
                `tabAddress`.`city`,
                `tabAddress`.`country`,
                `tabAddress`.`is_shipping_address`,
                `tabAddress`.`is_primary_address`,
                `tabAddress`.`geo_lat`,
                `tabAddress`.`geo_long`,
                `tabAddress`.`customer_address_id`
            FROM `tabDynamic Link`
            LEFT JOIN `tabAddress` ON `tabAddress`.`name` = `tabDynamic Link`.`parent`
            WHERE `tabDynamic Link`.`parenttype` = "Address"
              AND `tabDynamic Link`.`link_doctype` = "Customer"
              AND `tabDynamic Link`.`link_name` = "{customer_id}"
              AND `tabAddress`.`is_primary_address` = 1 
            ;""".format(customer_id=customer_id), as_dict=True)
        
    # return structure
    return {
        'success': True, 
        'message': "OK", 
        'details': {
            'customer': customer,
            'addresses': addresses
        }
    }

"""
Checks if an address record exists
"""
@frappe.whitelist()
def address_exists(address, client="webshop"):
    if type(address) == str:
        address = json.loads(address)
    sql_query = """SELECT 
            `tabAddress`.`name` AS `person_id`,
            `tabDynamic Link`.`link_name` AS `customer_id`
        FROM `tabAddress`
        LEFT JOIN `tabDynamic Link` ON 
            `tabDynamic Link`.`parent` = `tabAddress`.`name`
            AND `tabDynamic Link`.`parenttype` = "Address"
            AND `tabDynamic Link`.`link_doctype` = "Customer"
        WHERE `address_line1` LIKE "{0}" """.format(
            address['address_line1'] if 'address_line1' in address else "%")
    if 'address_line2' in address:
        sql_query += """ AND `address_line2` = "{0}" """.format(address['address_line2'])
    if 'pincode' in address:
        sql_query += """ AND `pincode` = "{0}" """.format(address['pincode'])
    if 'city' in address:
        sql_query += """ AND `city` = "{0}" """.format(address['city'])
    addresses = frappe.db.sql(sql_query, as_dict=True)
    
    if len(addresses) > 0:

        return {'success': True, 'message': "OK", 'addresses': addresses}
    else: 
        return {'success': False, 'message': "Address not found"}
    

"""
Request quote will create a new quote (and open the required oligos, if provided)
"""
@frappe.whitelist()
def request_quote(content, client="webshop"):
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
    if "company" not in content:
        company = frappe.get_value("Customer", content['customer'], 'default_company')
        if not company:
            company = frappe.defaults.get_default('company')
    # create quotation
    qtn_doc = frappe.get_doc({
        'doctype': "Quotation",
        'quotation_to': "Customer",
        'company': company,
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

"""
Returns the quotations for a particular customer
"""
@frappe.whitelist()
def get_quotations(customer, client="webshop"):
    if frappe.db.exists("Customer", customer):
        # return valid quotations
        qtns = frappe.get_all("Quotation", 
            filters={'party_name': customer, 'docstatus': 1},
            fields=['name', 'currency', 'net_total', 'transaction_date', 'customer_request']
        )
        return {'success': True, 'message': "OK", 'quotations': qtns}
    else:
        return {'success': False, 'message': 'Customer not found', 'quotation': None}

"""
Returns the quotations details
"""
@frappe.whitelist()
def get_quotation_detail(reference, client="webshop"):
    if frappe.db.exists("Quotation", reference):
        # get quotation
        qtn = frappe.get_doc("Quotation", reference)
        return {'success': True, 'message': "OK", 'quotation': qtn.as_dict()}
    else:
        return {'success': False, 'message': 'Quotation not found', 'quotation': None}

"""
Returns the specific prices for a customer/items
"""
@frappe.whitelist()
def get_item_prices(content, client="webshop"):
    # make sure items are a json object
    if type(content) == str:
        content = json.loads(content)
    if not 'customer' in content:
        return {'success': False, 'message': 'Customer parameter missing', 'quotation': None}
    if not 'items' in content:
        return {'success': False, 'message': 'Items missing', 'quotation': None}
    if frappe.db.exists("Customer", content['customer']):
        if not 'currency' in content:
            content['currency'] = frappe.get_value("Customer", content['customer'], "default_currency")
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
                'rate': i.rate,
                'description': i.description
            })
        # remove temporary record
        so.delete()
        return {'success': True, 'message': "OK", 'item_prices': item_prices}
    else:
        return {'success': False, 'message': 'Customer not found', 'quotation': None}

"""
Place an order
"""
@frappe.whitelist()
def place_order(content, client="webshop"):
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
    company = None
    if "company" in content:
        if frappe.db.exists("Company", content['company']):
            company = content['company']
        else:
            return {'success': False, 'message': "Invalid company", 'reference': None}
    else:
        company = frappe.get_value("Customer", content['customer'], 'default_company')
    if not company:
        company = frappe.defaults.get_global_default('company')
    # select naming series
    naming_series = get_naming_series("Sales Order", company)
    # cache contact values (Frappe bug in binding)
    contact = frappe.get_doc("Contact", content['contact'])
    # create quotation
    so_doc = frappe.get_doc({
        'doctype': "Sales Order",
        'company': company,
        'naming_series': naming_series,
        'customer': content['customer'],
        'customer_address': content['invoice_address'],
        'shipping_address_name': content['delivery_address'],
        'contact_person': content['contact'],
        'contact_display': contact.full_name,
        'contact_phone': contact.phone,
        'contact_email': contact.email_id,
        'customer_request': content['customer_request'] if 'customer_request' in content else None,
        'delivery_date': (date.today() + timedelta(days=3)),
        'web_order_id': content['web_order_id'] if 'web_order_id' in content else None,
        'is_punchout': content['is_punchout'] if 'is_punchout' in content else None,
        'po_no': content['po_no'] if 'po_no' in content else None
    })
    if 'product_type' in content:
        so_doc.product_type = content['product_type']
    # quotation reference
    if 'quotation' in content:
        quotation = content['quotation']
    else:
        quotation = None
    # create oligos
    if 'oligos' in content:
        consolidated_item_qtys = {}
        for o in content['oligos']:
            if not 'oligo_web_id' in o:
                return {'success': False, 'message': "oligo_web_id missing: {0}".format(o), 'reference': None}
            # create or update oligo
            oligo_name = create_oligo(o)
            so_doc.append('oligos', {
                'oligo': oligo_name
            })
            # insert positions (add to consolidated)
            for i in o['items']:
                if not frappe.db.exists("Item", i['item_code']):
                    return {'success': False, 'message': "invalid item: {0}".format(i['item_code']), 
                        'reference': None}
                if i['item_code'] in consolidated_item_qtys:
                    consolidated_item_qtys[i['item_code']] = consolidated_item_qtys[i['item_code']] + i['qty']
                else:
                    consolidated_item_qtys[i['item_code']] = i['qty']
        
        # apply consolidated items
        for item, qty in consolidated_item_qtys.items():
            so_doc.append('items', {
                'item_code': item,
                'qty': qty,
                'prevdoc_docname': quotation
            })
    # create samples
    if 'samples' in content:
        for s in content['samples']:
            # create or update sample
            sample_name = create_sample(s)
            # create sample record
            so_doc.append('samples', {
                'sample': sample_name
            })
            # insert positions
            for i in s['items']:
                if not frappe.db.exists("Item", i['item_code']):
                    return {'success': False, 'message': "invalid item: {0}".format(i['item_code']), 
                        'reference': None}
                so_doc.append('items', {
                    'item_code': i['item_code'],
                    'qty': i['qty'],
                    'prevdoc_docname': quotation
                })
    # append items
    for i in content['items']:
        if not frappe.db.exists("Item", i['item_code']):
            return {'success': False, 'message': "invalid item: {0}".format(i['item_code']), 
                'reference': None}
        item_detail = {
            'item_code': i['item_code'],
            'qty': i['qty'],
            'prevdoc_docname': quotation
        }
        if 'rate' in i and i['rate']:
            # this item is overriding the normal rate (e.g. shipping item)
            item_detail['rate'] = i['rate']
            item_detail['price_list_rate'] = i['rate']
        so_doc.append('items', item_detail)
    # append taxes
    category = "Service"
    if 'oligos' in content:
        category = "Material" 
    taxes = find_tax_template(company, content['invoice_address'], category)
    if taxes:
        so_doc.taxes_and_charges = taxes
        taxes_template = frappe.get_doc("Sales Taxes and Charges Template", taxes)
        for t in taxes_template.taxes:
            so_doc.append("taxes", t)
    try:
        so_doc.insert(ignore_permissions=True)
        so_doc.submit()
        return {'success': True, 'message': 'Sales Order created', 
            'reference': so_doc.name}
    except Exception as err:
        return {'success': False, 'message': err, 'reference': None}

"""
Returns all available countries
"""
@frappe.whitelist()
def get_countries(client="webshop"):
    countries = frappe.db.sql(
        """SELECT `country_name`, `code`, `export_code`, `default_currency`, `has_night_service`
           FROM `tabCountry`
           WHERE `disabled` = 0;""", as_dict=True)
           
    return {'success': True, 'message': None, 'countries': countries}

"""
Return all available shipping items for a customer or country
"""
@frappe.whitelist()
def get_shipping_items(customer_id=None, country=None, client="webshop"):
    if not customer_id and not country:
        return {'success': False, 'message': 'Either customer_id or country is required', 'shipping_items': []}
    if customer_id:
        # find by customer id
        shipping_items = frappe.db.sql(
        """SELECT `item`, `item_name`, `qty`, `rate`, `threshold`
           FROM `tabShipping Item`
           WHERE `parent` = "{0}" 
             AND `parenttype` = "Customer"
           ORDER BY `idx` ASC;""".format(str(customer_id)), as_dict=True)
        if len(shipping_items) > 0:
            return {'success': True, 'message': "OK", 'currency': frappe.get_value("Customer", customer_id, 'default_currency'), 'shipping_items': shipping_items}
        else:
            # find country for fallback
            primary_address = get_primary_customer_address(str(customer_id))
            if primary_address:
                country = frappe.get_value("Address", primary_address.get('name'), "country")
            else:
                return {'success': False, 'message': 'No data found', 'shipping_items': []}
    
    # find by country (this is also the fallback from the customer)
    if not country:
        country = frappe.defaults.get_global_default('country')
    else:
        country = robust_get_country(country)
    shipping_items = frappe.db.sql(
    """SELECT `item`, `item_name`, `qty`, `rate`, `threshold`
       FROM `tabShipping Item`
       WHERE `parent` = "{0}" 
         AND `parenttype` = "Country"
       ORDER BY `idx` ASC;""".format(country), as_dict=True)
           
    return {'success': True, 'message': "OK", 'currency': frappe.get_value("Country", country, 'default_currency'), 'shipping_items': shipping_items}

"""
Update newsletter state
"""
@frappe.whitelist()
def update_newsletter_state(person_id, newsletter_state, client="webshop"):
    if frappe.db.exists("Contact", person_id):
        contact = frappe.get_doc("Contact", person_id)
        contact.receive_newsletter = newsletter_state
        try:
            contact.save(ignore_permissions=True)
            return {'success': True, 'message': None}
        except Exception as err:
            return {'success': False, 'message': err}
    else: 
        return {'success': False, 'message': "Person ID not found"}

"""
Update punchout details
"""
@frappe.whitelist()
def update_punchout_details(person_id, punchout_buyer, punchout_identifier, client="webshop"):
    if frappe.db.exists("Contact", person_id):
        contact = frappe.get_doc("Contact", person_id)
        # fetch customer
        customer_id = None
        for l in contact.links:
            if l.link_doctype == "Customer":
                customer_id = l.link_name
        if not customer_id:
            return {'success': False, 'message': "No customer linked"}
        customer = frappe.get_doc("Customer", customer_id)
        customer.punchout_buyer = punchout_buyer
        customer.punchout_identifier = punchout_identifier
        try:
            customer.save(ignore_permissions=True)
            return {'success': True, 'message': None}
        except Exception as err:
            return {'success': False, 'message': err}
    else: 
        return {'success': False, 'message': "Person ID not found"}

"""
Update address GPS data
"""
@frappe.whitelist()
def update_address_gps(person_id, gps_lat, gps_long, client="webshop"):
    if frappe.db.exists("Address", person_id):
        address = frappe.get_doc("Address", person_id)
        address.geo_lat = float(gps_lat)
        address.geo_long = float(gps_long)
        try:
            address.save(ignore_permissions=True)
            return {'success': True, 'message': None}
        except Exception as err:
            return {'success': False, 'message': err}
    else: 
        return {'success': False, 'message': "Person ID not found"}
        
"""
Inform webshop about customer master change
"""
def notify_customer_change(customer):
    ## TODO
    return

"""
Return all companies
"""
@frappe.whitelist()
def get_companies(client="webshop"):
    companies = frappe.get_all("Company", fields=['name', 'abbr', 'country'])
    
    default_company = frappe.get_value("Global Defaults", "Global Defaults", "default_company")
    for c in companies:
        if c['name'] == default_company:
            c['default'] = 1
        else:
            c['default'] = 0
            
    return {'success': True, 'message': "OK", 'companies': companies}
