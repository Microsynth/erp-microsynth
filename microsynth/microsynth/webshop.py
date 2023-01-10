# -*- coding: utf-8 -*-
# Copyright (c) 2022, libracore (https://www.libracore.com) and contributors
# For license information, please see license.txt
#
# For more details, refer to https://github.com/Microsynth/erp-microsynth/wiki/Webshop-API
#

import frappe
import json
from microsynth.microsynth.migration import update_customer, update_contact, update_address, robust_get_country
from microsynth.microsynth.utils import create_oligo, create_sample, find_tax_template, get_express_shipping_item
from microsynth.microsynth.naming_series import get_naming_series
from datetime import date, timedelta
from erpnextswiss.scripts.crm_tools import get_primary_customer_address
from erpnext.selling.doctype.sales_order.sales_order import make_sales_invoice

@frappe.whitelist(allow_guest=True)
def ping():
    """
    Ping is a simple interface test function
    """
    return "pong"

@frappe.whitelist()
def create_update_customer(customer_data, client="webshop"):
    """
    This function will create or update a customer and also the given contact and address
    """
    if type(customer_data) == str:
        customer_data = json.loads(customer_data)
    error = update_customer(customer_data)
    if not error:
        return {'success': True, 'message': "OK"}
    else: 
        return {'success': False, 'message': error}

@frappe.whitelist()
def create_update_contact(contact, client="webshop"):
    """
    This function will create or update a contact
    """
    if not contact:
        return {'success': False, 'message': "Contact missing"}
    if type(contact) == str:
        contact = json.loads(contact)
    if not 'person_id' in contact:
        return {'success': False, 'message': "Person ID missing"}
    if not 'first_name' in contact:
        return{'success': False, 'message': "First Name missing"}    
    contact_name = update_contact(contact)
    if contact_name:
        return {'success': True, 'message': "OK"}
    else: 
        return {'success': False, 'message': "An error occured while creating/updating the contact record"}

@frappe.whitelist()
def create_update_address(address=None, client="webshop"):
    """
    This function will create or update an address
    """
    if not address:
        return {'success': False, 'message': "Address missing"}
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
        
@frappe.whitelist()
def get_user_details(person_id, client="webshop"):
    """
    From a user (AspNetUser), get customer data 
    """
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
                `tabAddress`.`overwrite_company`,
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

@frappe.whitelist()
def get_customer_details(customer_id, client="webshop"):
    """
    Get customer data (addresses: only invoice addresses)
    """
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

@frappe.whitelist()
def contact_exists(contact, client="webshop"):
    """
    Checks if a contact record exists and returns a list with contact IDs .
    """
    if type(contact) == str:
        contact = json.loads(contact)
    
    if 'first_name' in contact and contact['first_name'] and contact['first_name'] != "":
        first_name = contact['first_name']
    else:
        first_name = "-"
    
    sql_query = """SELECT
            `tabContact`.`name` AS `contact_id`,
            `tabDynamic Link`.`link_name` AS `customer_id`
        FROM `tabContact`
        LEFT JOIN `tabDynamic Link` ON 
            `tabDynamic Link`.`parent` = `tabContact`.`name`
            AND `tabDynamic Link`.`parenttype` = "Contact"
            AND `tabDynamic Link`.`link_doctype` = "Customer"
        WHERE `tabContact`.`first_name` = "{0}" """.format(first_name)
    
    if 'last_name' in contact and contact['last_name']:
        sql_query += """ AND `tabContact`.`last_name` = "{}" """.format(contact['last_name'])

    if 'customer_id' in contact and contact['customer_id']:
        sql_query += """ AND `tabDynamic Link`.`link_name` = "{0}" """.format(contact['customer_id'])

    # TODO check name of email field for interface
    if 'email_id' in contact and contact['email_id']:
        sql_query += """ AND `tabContact`.`email_id` = "{}" """.format(contact['email_id'])

    if 'department' in contact and contact['department']:
        sql_query += """ AND `tabContact`.`department` = "{}" """.format(contact['department'])

    if 'institute' in contact and contact['institute']:
        sql_query += """ AND `tabContact`.`institute` = "{}" """.format(contact['institute'])

    if 'room' in contact and contact['room']:
        sql_query += """ AND `tabContact`.`room` = "{}" """.format(contact['room'])

    contacts = frappe.db.sql(sql_query, as_dict=True)

    if len(contacts) > 0:
        return {'success': True, 'message': "OK", 'contacts': contacts}
    else: 
        return {'success': False, 'message': "Contact not found"}

@frappe.whitelist()
def address_exists(address, client="webshop"):
    """
    Checks if an address record exists
    """
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
        if address['address_line2']:
            sql_query += """ AND `address_line2` = "{0}" """.format(address['address_line2'])
        else: 
            sql_query += """ AND `address_line2` is null """
    if 'customer_id' in address and address['customer_id']:
        sql_query += """ AND `tabDynamic Link`.`link_name` = "{0}" """.format(address['customer_id'])
    if 'overwrite_company' in address and address['overwrite_company']:
        sql_query += """ AND `overwrite_company` = "{0}" """.format(address['overwrite_company'])
    if 'pincode' in address:
        sql_query += """ AND `pincode` = "{0}" """.format(address['pincode'])
    if 'city' in address:
        sql_query += """ AND `city` = "{0}" """.format(address['city'])

    addresses = frappe.db.sql(sql_query, as_dict=True)
    
    if len(addresses) > 0:
        return {'success': True, 'message': "OK", 'addresses': addresses}
    else: 
        return {'success': False, 'message': "Address not found"}


@frappe.whitelist()
def request_quote(content, client="webshop"):
    """
    Request quote will create a new quote (and open the required oligos, if provided)
    """
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
    company = "Microsynth AG"       # TODO send company with webshop request. Currently request_quote is only used for oligo orders.
    # create quotation
    qtn_doc = frappe.get_doc({
        'doctype': "Quotation",
        'quotation_to': "Customer",
        'company': company,
        'party_name': content['customer'],
        'customer_address': content['invoice_address'],
        'shipping_address_name': content['delivery_address'],
        'contact_person': content['contact'],
        'customer_request': content['customer_request'],
        'currency': frappe.get_value("Customer", content['customer'], "default_currency"),
        'selling_price_list': frappe.get_value("Customer", content['customer'], "default_price_list")
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
        # Append oligo to quotation
        qtn_doc.append('oligos', {
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
    # append taxes
    category = "Service"
    if 'oligos' in content and len(content['oligos']) > 0:
        category = "Material" 
    taxes = find_tax_template(company, content['customer'], content['invoice_address'], category)
    if taxes:
        qtn_doc.taxes_and_charges = taxes
        taxes_template = frappe.get_doc("Sales Taxes and Charges Template", taxes)
        for t in taxes_template.taxes:
            qtn_doc.append("taxes", t)
    try:
        qtn_doc.insert(ignore_permissions=True)
        # qtn_doc.submit()          # do not submit - leave on draft for easy edit, sales will process this
        return {'success': True, 'message': 'Quotation created', 
            'reference': qtn_doc.name}
    except Exception as err:
        return {'success': False, 'message': err, 'reference': None}

@frappe.whitelist()
def get_quotations(customer, client="webshop"):
    """
    Returns the quotations for a particular customer
    """
    if frappe.db.exists("Customer", customer):
        # return valid quotations
        qtns = frappe.get_all("Quotation", 
            filters={'party_name': customer, 'docstatus': 1},
            fields=['name', 'quotation_type', 'currency', 'net_total', 'transaction_date', 'customer_request']
        )
        return {'success': True, 'message': "OK", 'quotations': qtns}
    else:
        return {'success': False, 'message': 'Customer not found', 'quotation': None}

@frappe.whitelist()
def get_contact_quotations(contact, client="webshop"):
    """
    Returns the quotations for a particular customer
    """
    if frappe.db.exists("Contact", contact):
        # return valid quotations
        query = """SELECT 
                `tabQuotation`.`name`, 
                `tabQuotation`.`quotation_type`, 
                `tabQuotation`.`currency`, 
                `tabQuotation`.`net_total`, 
                `tabQuotation`.`transaction_date`, 
                `tabQuotation`.`customer_request`, 
                `tabQuotation Item`.`item_code`, 
                `tabQuotation Item`.`description`, 
                `tabQuotation Item`.`qty`, 
                `tabQuotation Item`.`rate`
            FROM `tabQuotation`
            LEFT JOIN `tabQuotation Item` ON `tabQuotation Item`.`parent` = `tabQuotation`.`name`
            WHERE `tabQuotation`.`contact_person` = '{0}' 
            AND `tabQuotation`.`docstatus` = 1 
            ORDER BY `tabQuotation`.`name` """.format(contact) 

        qtns = frappe.db.sql(query, as_dict=True)

        return {'success': True, 'message': "OK", 'quotations': qtns}
    else:
        return {'success': False, 'message': 'Customer not found', 'quotation': None}

@frappe.whitelist()
def get_quotation_detail(reference, client="webshop"):
    """
    Returns the quotations details
    """
    if frappe.db.exists("Quotation", reference):
        # get quotation
        qtn = frappe.get_doc("Quotation", reference)
        return {'success': True, 'message': "OK", 'quotation': qtn.as_dict()}
    else:
        return {'success': False, 'message': 'Quotation not found', 'quotation': None}

@frappe.whitelist()
def get_item_prices(content, client="webshop"):
    """
    Returns the specific prices for a customer/items
    """
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
            'delivery_date': date.today(),
            'selling_price_list': frappe.get_value("Customer", content['customer'], "default_price_list")
        })
        meta = { 
            "price_list": so.selling_price_list,
            "currency": so.currency
        } 
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
        return {'success': True, 'message': "OK", 'item_prices': item_prices, 'meta': meta }
    else:
        return {'success': False, 'message': 'Customer not found', 'quotation': None}

@frappe.whitelist()
def place_order(content, client="webshop"):
    """
    Place an order
    """
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
    
    # TODO check if distributor requires replacement of the customer
    # check that the webshop does not send prices
    # shipping item?
    
    # cache contact values (Frappe bug in binding)
    contact = frappe.get_doc("Contact", content['contact'])
    # create sales order
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
        'po_no': content['po_no'] if 'po_no' in content else None,
        'po_date': content['po_date'] if 'po_date' in content else None,
        'punchout_shop': content['punchout_shop'] if 'punchout_shop' in content else None,
        'selling_price_list': frappe.get_value("Customer", content['customer'], "default_price_list"),
        'currency': frappe.get_value("Customer", content['customer'], "default_currency"),
        'comment': content['comment'] if 'comment' in content else None
        })
    if 'product_type' in content:
        so_doc.product_type = content['product_type']
    # quotation reference
    if 'quotation' in content and frappe.db.exists("Quotation", content['quotation']):
        quotation = content['quotation']
        quotation_rate = {}
        qtn_doc = frappe.get_doc("Quotation", content['quotation'])
        for item in qtn_doc.items:
            if item.item_code not in quotation_rate:
                quotation_rate[item.item_code] = item.rate
    else:
        quotation = None
    # create oligos
    if 'oligos' in content:
        consolidated_item_qtys = {}
        for o in content['oligos']:
            if not 'web_id' in o:
                return {'success': False, 'message': "web_id missing: {0}".format(o), 'reference': None}
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
            _item = {
                'item_code': item,
                'qty': qty,
                'prevdoc_docname': quotation
            }
            if quotation and item in quotation_rate:
                _item['rate'] = quotation_rate[item]
            so_doc.append('items', _item)
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
                _item = {
                    'item_code': i['item_code'],
                    'qty': i['qty'],
                    'prevdoc_docname': quotation
                }
                if quotation and item in quotation_rate:
                    _item['rate'] = quotation_rate[item]
                so_doc.append('items', _item)
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
        if quotation and i['item_code'] in quotation_rate:
            item_detail['rate'] = quotation_rate[i['item_code']]
        elif 'rate' in i and i['rate'] is not None:
            # this item is overriding the normal rate (e.g. shipping item)
            item_detail['rate'] = i['rate']
            item_detail['price_list_rate'] = i['rate']
        so_doc.append('items', item_detail)
    # append taxes
    category = "Service"
    if 'oligos' in content and len(content['oligos']) > 0:
        category = "Material" 
    taxes = find_tax_template(company, content['customer'], content['invoice_address'], category)
    if taxes:
        so_doc.taxes_and_charges = taxes
        taxes_template = frappe.get_doc("Sales Taxes and Charges Template", taxes)
        for t in taxes_template.taxes:
            so_doc.append("taxes", t)
    # save
    try:
        so_doc.insert(ignore_permissions=True)

    except Exception as err:
        return {'success': False, 'message': err, 'reference': None}

    # set shipping item for oligo orders to express shipping if the order total exceeds the threshold
    shipping_address = frappe.get_doc("Address", content['delivery_address'])
    express_shipping = get_express_shipping_item(shipping_address.country)
    
    if (so_doc.product_type == "Oligos" and express_shipping and 
        (so_doc.total > express_shipping.threshold or 
        (shipping_address.country == "Switzerland" and so_doc.total > 1000))):
        for item in so_doc.items:
            if item.item_group == "Shipping":
                item.item_code = express_shipping.item
                item.item_name = express_shipping.item_name
                item.description = "express shipping" 

    try:        
        so_doc.submit()
        
        # check if this customer is approved
        """if not frappe.get_value("Customer", so_doc.customer, "customer_approved"):
            # this customer is not approved: create invoice and payment link
            ## create delivery note (leave on draft: submitted by flushbox after processing)
            si_content = make_sales_invoice(so_doc.name)
            sinv = frappe.get_doc(si_content)
            sinv.flags.ignore_missing = True
            sinv.insert(ignore_permissions=True)
            sinv.submit()
            frappe.db.commit()
            
            # create stripe payment line
            # ToDo
        """
        
        return {'success': True, 'message': 'Sales Order created', 
            'reference': so_doc.name}
    except Exception as err:
        return {'success': False, 'message': err, 'reference': None}

@frappe.whitelist()
def get_countries(client="webshop"):
    """
    Returns all available countries
    """
    countries = frappe.db.sql(
        """SELECT `country_name`, `code`, `export_code`, `default_currency`, `has_night_service`
           FROM `tabCountry`
           WHERE `disabled` = 0;""", as_dict=True)
           
    return {'success': True, 'message': None, 'countries': countries}

@frappe.whitelist()
def get_shipping_items(customer_id=None, country=None, client="webshop"):
    """
    Return all available shipping items for a customer or country
    """
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

@frappe.whitelist()
def update_newsletter_state(person_id, newsletter_state, client="webshop"):
    """
    Update newsletter state
    """
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

@frappe.whitelist()
def update_punchout_details(person_id, punchout_buyer, punchout_identifier, client="webshop"):
    """
    Update punchout details
    """
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
        contact.punchout_identifier = punchout_identifier
        try:
            customer.save(ignore_permissions=True)
            contact.save(ignore_permissions=True)
            return {'success': True, 'message': None}
        except Exception as err:
            return {'success': False, 'message': err}
    else: 
        return {'success': False, 'message': "Person ID not found"}

@frappe.whitelist()
def update_address_gps(person_id, gps_lat, gps_long, client="webshop"):
    """
    Update address GPS data
    """
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
        
def notify_customer_change(customer):
    """
    Inform webshop about customer master change
    """
    ## TODO
    return

@frappe.whitelist()
def get_companies(client="webshop"):
    """
    Return all companies
    """
    companies = frappe.get_all("Company", fields=['name', 'abbr', 'country'])
    
    default_company = frappe.get_value("Global Defaults", "Global Defaults", "default_company")
    for c in companies:
        if c['name'] == default_company:
            c['default'] = 1
        else:
            c['default'] = 0
            
    return {'success': True, 'message': "OK", 'companies': companies}
