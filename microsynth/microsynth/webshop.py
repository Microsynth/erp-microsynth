# -*- coding: utf-8 -*-
# Copyright (c) 2022-2025, libracore (https://www.libracore.com) and contributors
# For license information, please see license.txt
#
# For more details, refer to https://github.com/Microsynth/erp-microsynth/wiki/Webshop-API
#

import frappe
import json
import re
import base64
from frappe.desk.form.linked_with import get_linked_docs
from microsynth.microsynth.migration import update_contact, update_address, robust_get_country
from microsynth.microsynth.utils import get_customer, create_oligo, create_sample, get_express_shipping_item, get_billing_address, configure_new_customer, has_webshop_service, get_customer_from_company, get_supplier_for_product_type, get_margin_from_customer
from microsynth.microsynth.taxes import find_dated_tax_template
from microsynth.microsynth.marketing import lock_contact_by_name
from microsynth.microsynth.naming_series import get_naming_series
from microsynth.microsynth.invoicing import set_income_accounts
from datetime import date, timedelta
from erpnextswiss.scripts.crm_tools import get_primary_customer_address
from erpnext.selling.doctype.sales_order.sales_order import make_sales_invoice
import traceback


@frappe.whitelist(allow_guest=True)
def ping():
    """
    Ping is a simple interface test function
    """
    return "pong"


def validate_registration_data(user_data):
    '''
    Validate the user data provided with the register_user function.
    '''

    if 'customer' not in user_data or not user_data['customer']:
        error = "Customer is missing. "
        return error

    if 'contact' not in user_data or not user_data['contact']:
        error = "Contact is missing. "
        return error

    if 'invoice_contact' not in user_data or not user_data['invoice_contact']:
        error = "Invoice Contact is missing. "
        return error

    if 'addresses' not in user_data or not user_data['addresses']:
        error = "Addresses are missing. "
        return error

    for a in user_data['addresses']:
        if not 'address_line1' in a or not a['address_line1'].strip():
            error = f"Address Line 1 of {a['name']} is missing. "
            return error

    error = []
    if frappe.db.exists("Customer", user_data['customer']['name']):
        error.append("Customer '{0}' already exists.".format(user_data['customer']['name']))

    if frappe.db.exists("Contact", user_data['contact']['name']):
        error.append("Contact '{0}' already exists.".format(user_data['contact']['name']))
    
    for address in user_data['addresses']:
        if frappe.db.exists("Address", address['name']):
            error.append("Address '{0}' already exists.".format(address['name']))

    if len(error) > 0:
        return " ".join(error)
    else:
        return None


@frappe.whitelist()
def register_user(user_data, client="webshop"):
    """
    Register a new webshop user. Do not use for updating user data. 
    This function is derived from migration.update_customer
    """

    # make sure data is a dict or list
    if type(user_data) == str:
        user_data = json.loads(user_data)

    # validate input data
    error = validate_registration_data(user_data)
    if error:
        return {'success': False, 'message': error}

    # country locator
    country = None
    for a in user_data['addresses']:
        # set contry according to the first shipping address
        if 'country' in a and a.get('is_shipping_address', False):
            country = robust_get_country(a['country'])
            if country:
                break

    default_company = frappe.get_value("Country", country, "default_company")

    # Initialize customer
    customer_query = """INSERT INTO `tabCustomer` 
                    (`name`, 
                     `customer_name`, 
                     `default_company`, 
                     `default_currency`, 
                     `default_price_list`, 
                     `payment_terms`) 
                    VALUES ("{0}", "{1}", "{2}", "{3}", "{4}", "{5}");
                    """.format(
                        user_data['customer']['name'],
                        user_data['customer']['customer_name'],
                        default_company,
                        frappe.get_value("Country", country, "default_currency"),
                        frappe.get_value("Country", country, "default_pricelist"),
                        frappe.get_value("Company", default_company, "payment_terms"))

    frappe.db.sql(customer_query)
    
    customer = frappe.get_doc("Customer", user_data['customer']['name'])

    # Create addresses
    for address in user_data['addresses']:
        address['person_id'] = address['name']      # Extend address object to use the legacy update_address function
        address['customer_id'] = customer.name
        address_id = update_address(address)

    # Create contact
    user_data['contact']['person_id'] = user_data['contact']['name']    # Extend contact object to use the legacy update_contact function
    user_data['contact']['customer_id'] = customer.name
    user_data['contact']['status'] = "Open"
    contact_name = update_contact(user_data['contact'])

    # Create Contact Lock
    lock_contact_by_name(contact_name)

    # Create invoice contact
    user_data['invoice_contact']['person_id'] = user_data['invoice_contact']['name']    # Extend invoice_contact object to use the legacy update_contact function
    user_data['invoice_contact']['customer_id'] = customer.name
    user_data['invoice_contact']['status'] = "Open"
    invoice_contact_name = update_contact(user_data['invoice_contact'])

    # Create Contact Lock for invoice contact
    lock_contact_by_name(invoice_contact_name)

    # Update customer data

    if not customer.customer_group:
        customer.customer_group = frappe.get_value("Selling Settings", "Selling Settings", "customer_group")
    if not customer.territory:
        customer.territory = frappe.get_value("Selling Settings", "Selling Settings", "territory")

    if 'tax_id' in user_data['customer']:
        customer.tax_id = user_data['customer']['tax_id']

    if 'siret' in user_data['customer']:
        customer.siret = user_data['customer']['siret']

    if 'invoicing_method' in user_data['customer'] and user_data['customer']['invoicing_method'] == "Post":
        customer.invoicing_method = "Post"
    else:
        customer.invoicing_method = "Email"

    # Set the invoice_to contact. Depends on its creation above.
    if 'invoice_to' in user_data['customer']:
        customer.invoice_to = invoice_contact_name

    if 'punchout_shop' in user_data['customer']:
        customer.punchout_shop = user_data['customer']['punchout_shop']

    if 'punchout_shop_id' in user_data['customer']:
        customer.punchout_buyer = user_data['customer']['punchout_shop_id']

    customer.save()

    # some more administration
    configure_new_customer(customer.name)

    if not error:
        return {'success': True, 'message': "OK"}
    else: 
        return {'success': False, 'message': error}


# @frappe.whitelist()
def create_update_customer(customer_data, client="webshop"):
    """
    This function will create or update a customer and also the given contact and address
    
    Note: This function and endpoint is deprecated and will be removed soon
    
    """
    from microsynth.microsynth.migration import update_customer as migration_update_customer
    if type(customer_data) == str:
        customer_data = json.loads(customer_data)
    error = migration_update_customer(customer_data)
    if not error:
        return {'success': True, 'message': "OK"}
    else: 
        return {'success': False, 'message': error}


@frappe.whitelist()
def update_customer(customer, client="webshop"):
    """
    Update a customer.
    """

    if not customer:
        return {'success': False, 'message': "Customer missing"}
    if not 'customer_id' in customer:
        return {'success': False, 'message': "Customer ID missing"}

    if not frappe.db.exists("Customer", customer['customer_id']):
        return {'success': False, 'message': f"Customer '{ customer['customer_id'] }' not found."}

    doc = frappe.get_doc("Customer", customer['customer_id'])

    if doc.disabled:
        return {'success': False, 'message': f"Customer '{ customer['customer_id'] }' is disabled."}

    if doc.webshop_address_readonly:
        return {'success': False, 'message': f"Customer '{ customer['customer_id'] }' is readonly."}

    if 'customer_name' in customer:
        doc.customer_name = customer['customer_name']

    if 'tax_id' in customer:
        doc.tax_id = customer['tax_id']

    if 'siret' in customer:
        doc.siret = customer['siret']

    if 'invoicing_method' in customer:
        doc.invoicing_method = customer['invoicing_method']

    doc.save()

    return {'success': True, 'message': f"Updated customer '{ customer['customer_id'] }'" }


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
    lock_contact_by_name(contact_name)
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
    if contact.status == "Disabled":
        return {'success': False, 'message': "Contact '{}' is disabled".format(contact.name)}
    # fetch customer
    # TODO: replace by utils.get_customer to get the customer_id
    customer_id = None
    for l in contact.links:
        if l.link_doctype == "Customer":
            customer_id = l.link_name
    if not customer_id:
        return {'success': False, 'message': "No customer linked"}
    customer = frappe.get_doc("Customer", customer_id)
    if customer.disabled == 1:
        return {'success': False, 'message': 'Customer disabled'}
    
    if customer.invoice_to:
        invoice_contact = frappe.get_doc("Contact", customer.invoice_to)
    else:
        invoice_contact = None
    
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
                   OR `tabAddress`.`name` = "{person_id}"
                   OR `tabAddress`.`name` = "{contact_address_id}")
            ;""".format(customer_id=customer_id, person_id=person_id, contact_address_id=contact.address), as_dict=True)
        
    # return structure
    return {
        'success': True, 
        'message': "OK", 
        'details': {
            'contact': contact,
            'customer': customer,
            'addresses': addresses,
            'invoice_contact': invoice_contact
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
    # fetch invoice contact
    invoice_contact = frappe.get_doc("Contact", customer.invoice_to)
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
            'invoice_contact': invoice_contact,
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
    
    # Note: These statements need the "is not None" term. Simplification to only "contact['...']" will corrupt the API.
    if 'last_name' in contact and contact['last_name'] is not None:
        sql_query += """ AND `tabContact`.`last_name` = "{}" """.format(contact['last_name'])

    if 'customer_id' in contact and contact['customer_id'] is not None:
        sql_query += """ AND `tabDynamic Link`.`link_name` = "{0}" """.format(contact['customer_id'])

    # TODO check name of email field for interface
    if 'email_id' in contact and contact['email_id'] is not None:
        sql_query += """ AND `tabContact`.`email_id` = "{}" """.format(contact['email_id'])

    if 'department' in contact and contact['department'] is not None:
        sql_query += """ AND `tabContact`.`department` = "{}" """.format(contact['department'])

    if 'institute' in contact and contact['institute'] is not None:
        sql_query += """ AND `tabContact`.`institute` = "{}" """.format(contact['institute'])

    if 'room' in contact and contact['room'] is not None:
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
    # Note: These statements need the "is not None" term. Simplification to only "contact['...']" will corrupt the API.
    if 'address_line2' in address:
        if address['address_line2'] is not None:
            sql_query += """ AND `address_line2` = "{0}" """.format(address['address_line2'])
        else: 
            sql_query += """ AND `address_line2` is null """
    if 'customer_id' in address and address['customer_id'] is not None:
        sql_query += """ AND `tabDynamic Link`.`link_name` = "{0}" """.format(address['customer_id'])
    if 'overwrite_company' in address:
        if address['overwrite_company'] is not None:
            sql_query += """ AND `overwrite_company` = "{0}" """.format(address['overwrite_company'])
        else: 
            sql_query += """ AND `overwrite_company` is null """
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
    transaction_date = date.today()
    qtn_doc = frappe.get_doc({
        'doctype': "Quotation",
        'quotation_to': "Customer",
        'company': company,
        'party_name': content['customer'],
        'customer_address': content['invoice_address'],
        'shipping_address_name': content['delivery_address'],
        'contact_person': content['contact'],
        'contact_display': frappe.get_value("Contact", content['contact'], "full_name"),
        'territory': frappe.get_value("Customer", content['customer'], "territory"),
        'customer_request': content['customer_request'],
        'currency': frappe.get_value("Customer", content['customer'], "default_currency"),
        'selling_price_list': frappe.get_value("Customer", content['customer'], "default_price_list"),
        'transaction_date': transaction_date,
        'valid_till': transaction_date + timedelta(days=90),
        'sales_manager': frappe.get_value("Customer", content['customer'], "account_manager")
    })
    oligo_items_consolidated = dict()
    # create oligos
    for o in content['oligos']:
        o['status'] = 'Offered'
        # create or update oligo
        oligo_name = create_oligo(o)
        # insert positions
        for i in o['items']:
            if not frappe.db.exists("Item", i['item_code']):
                return {'success': False, 'message': "invalid item: {0}".format(i['item_code']), 
                    'reference': None}
            if not i['item_code'] in oligo_items_consolidated:
                oligo_items_consolidated[i['item_code']] = i['qty']
            else:
                oligo_items_consolidated[i['item_code']] += i['qty']
        # Append oligo to quotation
        qtn_doc.append('oligos', {
            'oligo': oligo_name
        })
    # append items
    for item_code, qty in oligo_items_consolidated.items():
        qtn_doc.append('items', {
            'item_code': item_code,
            'qty': qty
        })
    for i in content['items']:
        if not frappe.db.exists("Item", i['item_code']):
            return {'success': False, 'message': "invalid item: {0}".format(i['item_code']), 
                'reference': None}
        qtn_doc.append('items', {
            'item_code': i['item_code'],
            'qty': i['qty']
        })
    # insert shipping item
    shipping_address = frappe.get_doc("Address", content['delivery_address'])
    express_shipping = get_express_shipping_item(content['customer'], shipping_address.country)
    qtn_doc.append('items', {
        'item_code': express_shipping.item,
        'item_name': express_shipping.item_name,
        'qty': 1,
        'rate': express_shipping.rate
    })
    # append taxes
    category = "Service"
    if 'oligos' in content and len(content['oligos']) > 0:
        category = "Material" 
    taxes = find_dated_tax_template(company, content['customer'], content['delivery_address'], category, transaction_date)
    if taxes:
        qtn_doc.taxes_and_charges = taxes
        taxes_template = frappe.get_doc("Sales Taxes and Charges Template", taxes)
        for t in taxes_template.taxes:
            qtn_doc.append("taxes", t)
    # check for service specifications
    service_specifications = []
    for i in qtn_doc.items:
        item_service_specification = frappe.get_value("Item", i.item_code, "service_specification")
        if item_service_specification and item_service_specification not in service_specifications:
            service_specifications.append(item_service_specification)
    if len(service_specifications) > 0:
        qtn_doc.service_specification = "<h3>Service Description</h3>" + "".join(service_specifications)
    # insert new quotation
    try:
        qtn_doc.insert(ignore_permissions=True)
        if 'warnings' in content and content['warnings']:
            new_comment = frappe.get_doc({
                'doctype': 'Comment',
                'comment_type': 'Comment',
                'subject': 'Warnings from the Webshop',
                'content': content['warnings'],
                'reference_doctype': 'Quotation',
                'status': 'Linked',
                'reference_name': qtn_doc.name
            })
            new_comment.insert(ignore_permissions=True)
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
    Returns the quotation items for a particular contact. 
    """
    
    customer_name = get_customer(contact)

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
                `tabQuotation Item`.`item_name`, 
                `tabQuotation Item`.`qty`, 
                `tabQuotation Item`.`rate`
            FROM `tabQuotation`
            LEFT JOIN `tabQuotation Item` ON `tabQuotation Item`.`parent` = `tabQuotation`.`name`
            WHERE (`tabQuotation`.`contact_person` = '{0}'
            OR (`tabQuotation`.`party_name` = '{1}' and `tabQuotation`.`customer_web_access` = 1 ) )
            AND `tabQuotation`.`docstatus` = 1
            AND `tabQuotation`.`status` <> 'Lost'
            AND (`tabQuotation`.`valid_till` >= CURDATE() OR `tabQuotation`.`valid_till` IS NULL)
            ORDER BY `tabQuotation`.`name` DESC, `tabQuotation Item`.`idx` ASC;""".format(contact, customer_name) 

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
        # extend values
        so.company = frappe.get_value("Customer", content['customer'], 'default_company') or frappe.defaults.get_global_default('company')
        try:
            so.set_missing_values()
            so.validate()
        except Exception as err:
            return {'success': False, 'message': err, 'quotation': None}
        # pick prices
        item_prices = []
        for i in so.items:
            item_prices.append({
                'item_code': i.item_code,
                'qty': i.qty,
                'rate': i.rate,
                'description': i.item_name
            })
        return {'success': True, 'message': "OK", 'item_prices': item_prices, 'meta': meta }
    else:
        return {'success': False, 'message': 'Customer not found', 'quotation': None}


def apply_discount(quotation, sales_order):
    if not quotation:
        return sales_order
    if quotation.additional_discount_percentage > 0:
        sales_order.additional_discount_percentage = quotation.additional_discount_percentage
    elif sales_order.total == quotation.total:
        sales_order.discount_amount = quotation.discount_amount
    else:
        frappe.log_error(f"Unable to apply discount on {sales_order.name}. Mismatch between quotation and sales order: {sales_order.total=} != {quotation.total=}", "webshop.apply_discount")
    return sales_order


@frappe.whitelist()
def place_order(content, client="webshop"):
    """
    Place an order
    """
    # prepare parameters
    if type(content) == str:
        content = json.loads(content)
    is_drop_shipment = False
    # validate input
    if not frappe.db.exists("Customer", content['customer']):
        return {'success': False, 'message': f"Customer '{content['customer']}' not found", 'reference': None}
    if not frappe.db.exists("Address", content['delivery_address']):
        return {'success': False, 'message': f"Delivery address '{content['delivery_address']}' not found", 'reference': None}
    if not frappe.db.exists("Address", content['invoice_address']):
        return {'success': False, 'message': f"Invoice address '{content['invoice_address']}' not found", 'reference': None}
    if not frappe.db.exists("Contact", content['contact']):
        return {'success': False, 'message': f"Contact '{content['contact']}' not found", 'reference': None}
    company = None
    if "company" in content:
        if frappe.db.exists("Company", content['company']):
            company = content['company']
        else:
            return {'success': False, 'message': f"Invalid company '{content['company']}'", 'reference': None}
    else:
        company = frappe.get_value("Customer", content['customer'], 'default_company')
    if not company:
        company = frappe.defaults.get_global_default('company')
    
    customer = frappe.get_doc("Customer", content['customer'])
    contact = frappe.get_doc("Contact", content['contact'])  # cache contact values (Frappe bug in binding)
    billing_address = content['invoice_address']

    order_customer = None

    if not 'product_type' in content or not content['product_type']:
        return {'success': False, 'message': "Product Type is mandatory but not given.", 'reference': None}

    if has_webshop_service(customer.name, "InvoiceByDefaultCompany"):
        # identify dropshipment/intracompany order
        intercompany_supplier = get_supplier_for_product_type(customer.default_company, content.get('product_type'))
        if intercompany_supplier \
            and customer.default_company != intercompany_supplier['manufacturing_company']:
            # this is a dropshipment case
            drop_shipment_manufacturer = intercompany_supplier['manufacturing_company']        # keep original manufacturer
            company = customer.default_company          # selling company
            is_drop_shipment = True

    # Distributor workflow
    if 'product_type' in content:
        for distributor in customer.distributors:
            if distributor.product_type == content['product_type']:
                # swap customer and replace billing address
                if is_drop_shipment:
                    err = "Not implemented: dropshipment conflicts with distributor workflow"
                    frappe.log_error(err, "webshop.place_order")
                    return {'success': False, 'message': err, 'reference': None}
                order_customer = customer
                customer = frappe.get_doc("Customer", distributor.distributor)

                billing_address = get_billing_address(customer.name).name

    # check that the webshop does not send prices / take prices from distributor price list
    #   consider product type

    # select naming series
    naming_series = get_naming_series("Sales Order", company)

    # create sales order
    transaction_date = date.today()
    delivery_date = transaction_date + timedelta(days=3)
    so_doc = frappe.get_doc({
        'doctype': "Sales Order",
        'company': company,
        'naming_series': naming_series,
        'customer': customer.name,
        'tax_id': customer.tax_id,
        'invoice_to': content['invoice_contact'] if 'invoice_contact' in content else None,
        'customer_address': billing_address,
        'shipping_contact': content['shipping_contact'] if 'shipping_contact' in content else None,
        'shipping_address_name': content['delivery_address'],
        'order_customer': order_customer.name if order_customer else None,
        'contact_person': contact.name,
        'contact_display': contact.full_name,
        'contact_phone': contact.phone,
        'contact_email': contact.email_id,
        'territory': order_customer.territory if order_customer else customer.territory,
        'customer_request': content['customer_request'] if 'customer_request' in content else None,
        'transaction_date': transaction_date,
        'delivery_date': delivery_date,
        'web_order_id': content['web_order_id'] if 'web_order_id' in content else None,
        'is_punchout': content['is_punchout'] if 'is_punchout' in content else None,
        'po_no': content['po_no'] if 'po_no' in content else None,
        'po_date': content['po_date'] if 'po_date' in content else None,
        'punchout_shop': content['punchout_shop'] if 'punchout_shop' in content else None,
        'register_labels': content['register_labels'] if 'register_labels' in content else None,
        'selling_price_list': frappe.get_value("Customer", customer.name, "default_price_list"),
        'currency': frappe.get_value("Customer", customer.name, "default_currency"),
        'comment': content['comment'] if 'comment' in content else None,
        'hold_order': True if 'comment' in content and content['comment'] != None and content['comment'] != "" else None
        })
    if 'product_type' in content:
        so_doc.product_type = content['product_type']
    # quotation reference (NOTE: ignores same item at different qtys (staged pricing) )
    if 'quotation' in content and frappe.db.exists("Quotation", content['quotation']):
        quotation = content['quotation']
        quotation_rate = {}
        qtn_doc = frappe.get_doc("Quotation", content['quotation'])
        for item in qtn_doc.items:
            if item.item_code not in quotation_rate:
                quotation_rate[item.item_code] = item.rate
    else:
        quotation = None
        qtn_doc = None

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
            so_doc.append('items', _item)

    # create samples
    if 'samples' in content:
        consolidated_item_qtys = {}
        for s in content['samples']:
            # create or update sample
            sample_name = create_sample(s)
            # create sample record
            so_doc.append('samples', {
                'sample': sample_name
            })
            # insert positions (add to consolidated)
            for i in s['items']:
                if not frappe.db.exists("Item", i['item_code']):
                    return {'success': False, 'message': "invalid item: {0}".format(i['item_code']), 
                        'reference': None}
                if i['item_code'] in consolidated_item_qtys:
                    consolidated_item_qtys[i['item_code']] += i['qty']
                else:
                    consolidated_item_qtys[i['item_code']] = i['qty']

        # apply consolidated items
        for item, qty in consolidated_item_qtys.items():
            _item = {
                'item_code': item,
                'qty': qty,
                'prevdoc_docname': quotation
            }
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
        if 'rate' in i and i['rate'] is not None:
            # this item is overriding the normal rate (e.g. shipping item)
            item_detail['rate'] = i['rate']
            item_detail['price_list_rate'] = i['rate']
        so_doc.append('items', item_detail)

    # append taxes
    if so_doc.product_type == "Oligos" or so_doc.product_type == "Material":
        category = "Material"
    else:
        category = "Service"
    if 'oligos' in content and len(content['oligos']) > 0:
        category = "Material"
    taxes = find_dated_tax_template(company, content['customer'], content['delivery_address'], category, delivery_date)
    if taxes:
        so_doc.taxes_and_charges = taxes
        taxes_template = frappe.get_doc("Sales Taxes and Charges Template", taxes)
        for t in taxes_template.taxes:
            so_doc.append("taxes", t)
    # in case of drop-shipment, mark item positions for drop shipment (prevent actual delivery)
    if is_drop_shipment and intercompany_supplier:
        supplier = intercompany_supplier['supplier']
        if not supplier:
            err = f"No supplier found for {so_doc.product_type}."
            return {'success': False, 'message': err, 'reference': None}
        for i in so_doc.items:
            i.delivered_by_supplier = 1
            i.supplier = supplier
            
    # save
    try:
        so_doc.insert(ignore_permissions=True)

    except Exception as err:
        return {'success': False, 'message': err, 'reference': None}

    # set shipping item for oligo orders to express shipping if the order total exceeds the threshold
    shipping_address = frappe.get_doc("Address", content['delivery_address'])
    express_shipping = get_express_shipping_item(content['customer'], shipping_address.country)   # use original customer for the shipping items also in the distributor workflow
    
    if (so_doc.product_type == "Oligos" and express_shipping and 
        (so_doc.total > express_shipping.threshold or 
        (shipping_address.country == "Switzerland" and so_doc.total > 1000))):
        for item in so_doc.items:
            if item.item_group == "Shipping":
                item.item_code = express_shipping.item
                item.item_name = express_shipping.item_name
                item.description = "express shipping" 

    # prepayment: hold order if there are any costs
    if "Prepayment" in (customer.invoicing_method or "") and so_doc.grand_total != 0:
        so_doc.hold_order = 1

    # quotation rate override: if an item has a rate in the quotation, always take this 
    #    (note: has to be post insert, otherwise frappe will override 0 rates)
    if quotation:
        for item in so_doc.items:                                   # loop through all items in sales order
            if item.item_code in quotation_rate:                    # check if this item had a quotation rate
                item.rate = quotation_rate[item.item_code]
                item.price_list_rate = quotation_rate[item.item_code]
        so_doc.save()
        so_doc = apply_discount(qtn_doc, so_doc)

    so_doc.save()
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
            
        """
        
        # if drop shipment: create intra-company sales order for manufacturing company
        if is_drop_shipment:
            place_dropship_order(so_doc.name,
                intercompany_customer_name=get_customer_from_company(so_doc.company), 
                supplier_company=drop_shipment_manufacturer)
            
        return {
            'success': True, 
            'message': 'Sales Order created', 
            'reference': so_doc.name,
            'currency': so_doc.currency,
            'net_amount': so_doc.net_total,
            'tax_amount': so_doc.total_taxes_and_charges,
            'gross_amount': so_doc.grand_total
        }
    except Exception as err:
        return {'success': False, 'message': err, 'reference': None}


def place_dropship_order(sales_order, intercompany_customer_name, supplier_company):
    original_order = frappe.get_doc("Sales Order", sales_order)
    
    customer = frappe.get_doc("Customer", intercompany_customer_name)
    
    # shipping address: company override (2025-02-20: obsolete - we use order_customer instead
    #shipping_address = frappe.get_doc("Address", original_order.shipping_address_name)
    #if not shipping_address.overwrite_company:
    #    # note: do not overwrite: if there is a custom-selected overwrite target, leave as is (can come from webshop)
    #    shipping_address.overwrite_company = original_order.customer_name
    #    shipping_address.save()
    
    dropship_order = frappe.get_doc({
        'doctype': "Sales Order",
        'company': supplier_company,
        'naming_series': get_naming_series("Sales Order", supplier_company),
        'customer': customer.name,
        'tax_id': customer.tax_id,
        'invoice_to': customer.invoice_to,
        'customer_address': frappe.get_value("Contact", customer.invoice_to, "address"),
        'shipping_contact': original_order.shipping_contact,
        'shipping_address_name': original_order.shipping_address_name,
        'order_customer': original_order.customer,
        'order_customer_display': original_order.customer_name,
        'contact_person': original_order.contact_person,
        'contact_display': original_order.contact_display,
        'contact_phone': original_order.contact_phone,
        'contact_email': original_order.contact_email,
        'product_type': original_order.product_type,
        #'order_type': 'Intercompany',
        'is_intercompany': 1,
        'territory': original_order.territory,
        #'customer_request': original_order.customer_request,       # this field is currently not available
        'transaction_date': original_order.transaction_date,
        'delivery_date': original_order.delivery_date,
        'web_order_id': original_order.web_order_id,
        'is_punchout': original_order.is_punchout,
        'po_no': original_order.name,
        'po_date': original_order.transaction_date,
        'punchout_shop': original_order.punchout_shop,
        'register_labels': original_order.register_labels,
        'selling_price_list': original_order.selling_price_list,
        'currency': original_order.currency,
        'comment': original_order.comment,
        'hold_order': original_order.hold_order,
        'additional_discount_percentage': get_margin_from_customer(intercompany_customer_name)  # apply intercompany conditions
    })
    
    # items
    for i in original_order.items:
        dropship_order.append("items", {
            'item_code': i.item_code,
            'item_name': i.item_name,
            'qty': i.qty,
            'rate': i.rate
        })
        
    # oligos
    for o in original_order.oligos:
        dropship_order.append("oligos", {
            'oligo': o.oligo
        })
    
    # samples
    for s in original_order.samples:
        dropship_order.append("samples", {
            'sample': s.sample
        })
    
    # ToDo: plates
    
    # append taxes
    if dropship_order.product_type == "Oligos" or dropship_order.product_type == "Material":
        category = "Material"
    else:
        category = "Service"

    taxes = find_dated_tax_template(dropship_order.company, dropship_order.customer, dropship_order.customer_address, category, dropship_order.delivery_date)
    if taxes:
        dropship_order.taxes_and_charges = taxes
        taxes_template = frappe.get_doc("Sales Taxes and Charges Template", taxes)
        for t in taxes_template.taxes:
            dropship_order.append("taxes", t)
    
    # insert
    try:
        dropship_order.insert(ignore_permissions=True)

        dropship_order.submit()
        
        return dropship_order.name
        
    except Exception as err:
        frappe.log_error(f"{customer}\n{supplier_company}\n{sales_order}\n\n{traceback.format_exc()}", "webshop.place_dropship_order")
    
        return None


@frappe.whitelist()
def order_quote(quotation_id, client="webshop"):
    """
    Create a Sales Order based on the given Quotation ID.

    bench execute "microsynth.microsynth.webshop.order_quote" --kwargs "{'quotation_id': 'QTN-2401003'}"
    """
    from erpnext.selling.doctype.quotation.quotation import make_sales_order
    if not quotation_id or not frappe.db.exists("Quotation", quotation_id):
        return {'success': False, 'message': f"There is no Quotation with ID '{quotation_id}' in the ERP.", 'reference': None}
    quotation = frappe.get_doc("Quotation", quotation_id)
    if quotation.has_sales_order():
        return {'success': False, 'message': f"There is already a submitted Sales Order against {quotation_id}.", 'reference': None}
    try:
        quotation = frappe.get_doc("Quotation", quotation_id)
        sales_order = make_sales_order(quotation_id)
        sales_order.delivery_date = date.today() + timedelta(days=3)
        sales_order.insert()
        sales_order.delivery_date = date.today() + timedelta(days=3)
        sales_order.product_type = quotation.product_type
        sales_order.save()
        #sales_order.submit()
    except Exception as err:
        frappe.log_error(f"Unable to create a Sales Order for Quotation {quotation_id}:\n{err}", "webshop.order_quote")
        return {'success': False, 'message': err, 'reference': None}
    else:
        return {'success': True, 'message': None, 'reference': sales_order.name}


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
        shipping_items = frappe.db.sql("""
            SELECT `tabShipping Item`.`item`,
                `tabShipping Item`.`item_name`,
                `tabShipping Item`.`qty`,
                `tabShipping Item`.`rate`,
                `tabShipping Item`.`threshold`,
                `tabShipping Item`.`preferred_express`
            FROM `tabShipping Item`
            LEFT JOIN `tabItem` ON `tabItem`.`name` = `tabShipping Item`.`item`
            WHERE `tabShipping Item`.`parent` = "{0}"
                AND `tabShipping Item`.`parenttype` = "Customer"
                AND `tabItem`.`disabled` = 0
            ORDER BY `tabShipping Item`.`idx` ASC;""".format(str(customer_id)), as_dict=True)
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
    shipping_items = frappe.db.sql("""
        SELECT `tabShipping Item`.`item`,
                `tabShipping Item`.`item_name`,
                `tabShipping Item`.`qty`,
                `tabShipping Item`.`rate`,
                `tabShipping Item`.`threshold`,
                `tabShipping Item`.`preferred_express`
        FROM `tabShipping Item`
        LEFT JOIN `tabItem` ON `tabItem`.`item_code` = `tabShipping Item`.`item`
        WHERE `tabShipping Item`.`parent` = "{0}" 
            AND `tabShipping Item`.`parenttype` = "Country"
            AND `tabItem`.`disabled` = 0
        ORDER BY `tabShipping Item`.`idx` ASC;""".format(country), as_dict=True)
           
    return {'success': True, 'message': "OK", 'currency': frappe.get_value("Country", country, 'default_currency'), 'shipping_items': shipping_items}


@frappe.whitelist()
def get_contact_shipping_items(contact, client="webshop"):
    """
    Return all available shipping items for a contact specified by its Contact ID (Person ID)

    bench execute "microsynth.microsynth.webshop.get_contact_shipping_items" --kwargs "{'contact': 243079}"
    """
    if not contact or not frappe.db.exists("Contact", contact):
        return {'success': False, 'message': 'A valid and existing contact is required', 'shipping_items': []}
    customer_id = get_customer(contact)
    # find by customer id
    if customer_id:
        shipping_items = frappe.db.sql(f"""
            SELECT `tabShipping Item`.`item`,
                `tabItem`.`item_name`,
                `tabShipping Item`.`qty`,
                `tabShipping Item`.`rate`,
                `tabShipping Item`.`threshold`,
                `tabShipping Item`.`preferred_express`
            FROM `tabShipping Item`
            LEFT JOIN `tabItem` ON `tabItem`.`name` = `tabShipping Item`.`item`
            WHERE `tabShipping Item`.`parent` = "{customer_id}"
                AND `tabShipping Item`.`parenttype` = "Customer"
                AND `tabItem`.`disabled` = 0
            ORDER BY `tabShipping Item`.`idx` ASC;""", as_dict=True)
        if len(shipping_items) > 0:
            return {'success': True, 'message': "OK", 'currency': frappe.get_value("Customer", customer_id, 'default_currency'), 'shipping_items': shipping_items}
        else:
            country = None
            # check if customer has a punchout_shop
            punchout_shop = frappe.get_value("Customer", customer_id, "punchout_shop")
            if punchout_shop:
                punchout_shop_country = frappe.get_value("Punchout Shop", punchout_shop, "shipping_country")
                if punchout_shop_country:
                    country = punchout_shop_country
            if not country:
                # find country for fallback
                address = frappe.get_value("Contact", contact, "address")
                if address:
                    country = frappe.get_value("Address", address, "country")
                else:
                    return {'success': False, 'message': f'Contact {contact} has no address', 'shipping_items': []}

    # find by country (fallback from the customer)
    if not country:
        country = frappe.defaults.get_global_default('country')
    country = robust_get_country(country)
    shipping_items = frappe.db.sql(
        f"""SELECT `tabShipping Item`.`item`,
                `tabItem`.`item_name`,
                `tabShipping Item`.`qty`,
                `tabShipping Item`.`rate`,
                `tabShipping Item`.`threshold`,
                `tabShipping Item`.`preferred_express`
            FROM `tabShipping Item`
            LEFT JOIN `tabItem` ON `tabItem`.`item_code` = `tabShipping Item`.`item`
            WHERE `tabShipping Item`.`parent` = "{country}" 
                AND `tabShipping Item`.`parenttype` = "Country"
                AND `tabItem`.`disabled` = 0
            ORDER BY `tabShipping Item`.`idx` ASC;""", as_dict=True)
    if len(shipping_items) > 0:
        return {'success': True, 'message': "OK", 'currency': frappe.get_value("Country", country, 'default_currency'), 'shipping_items': shipping_items}
    else:
        return {'success': False, 'message': 'No data', 'shipping_items': []}


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
def update_punchout_details(person_id, punchout_shop, punchout_buyer, punchout_identifier, client="webshop"):
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
        customer.punchout_shop = punchout_shop
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


@frappe.whitelist()
def create_payment(sales_order, stripe_reference, client="webshop"):
    """
    Create sales invoice and payment record
    
    Test with
    bench execute microsynth.microsynth.webshop.create_payment --kwargs "{'sales_order': 'SO-BAL-23058405', 'stripe_reference': 'ABCD1236'}"
    """

    # check configuration
    if not frappe.db.exists("Mode of Payment", "stripe"):
        return {'success': False, 'message': "Mode of Payment stripe missing. Please correct ERP configuration."}

    # fetch sales order
    if not frappe.db.exists("Sales Order", sales_order):
        return {'success': False, 'message': "Sales Order not found"}
    so_doc = frappe.get_doc("Sales Order", sales_order)

    # create sales invoice
    si_content = make_sales_invoice(so_doc.name)
    sinv = frappe.get_doc(si_content)
    sinv.flags.ignore_missing = True
    try:
        sinv.insert(ignore_permissions=True)
        # update income accounts
        set_income_accounts(sinv)           # this function will save the updated doc
        frappe.db.commit()                  # make sure the latest version is loaded
        sinv = frappe.get_doc("Sales Invoice", sinv.name)   
        sinv.submit()
    except Exception as err:
        return {'success': False, 'message': "Failed to create invoice: {0}".format(err)}
    frappe.db.commit()

    # create the payment record
    mode_of_payment = frappe.get_doc("Mode of Payment", "stripe")
    stripe_account = None
    for m in mode_of_payment.accounts:
        if m.company == sinv.company:
            stripe_account = m.default_account
            break
    from erpnext.accounts.doctype.payment_entry.payment_entry import get_payment_entry
    pe = get_payment_entry("Sales Invoice", sinv.name, bank_account=stripe_account)
    pe.reference_no = stripe_reference
    pe.reference_date = date.today()
    try:
        pe.insert(ignore_permissions=True)
        pe.remarks = "Stripe payment ({client})\n{others}".format(client=client, others=pe.remarks)
        pe.save()
        pe.submit()
    except Exception as err:
        return {'success': False, 'message': "Failed to create payment: {0}".format(err)}
    frappe.db.commit()

    # remove hold flag
    so_doc = frappe.get_doc("Sales Order", sales_order)
    so_doc.hold_order = 0
    try:
        so_doc.save()
    except Exception as err:
        return {'success': False, 'message': "Failed to update sales order {0}: {1}".format(sales_order, err)}
    frappe.db.commit()

    return {'success': True, 'message': "OK", 'reference': sinv.name}


### Label API


def get_sql_list(list):
    if list:
        return (','.join('"{0}"'.format(e) for e in list))
    else:
        return '""'


@frappe.whitelist()
def get_unused_labels(contacts, items):
    """
    Return unused Sequencing Labels that are registered to a given contact.

    bench execute microsynth.microsynth.webshop.get_unused_labels --kwargs "{'contacts': ['215856', '237365'], 'items': ['6030', '6031'] }"
    """
    # Check parameters
    if not contacts or len(contacts) == 0:
        return {'success': False, 'message': "Please provide at least one Contact", 'labels': None}
    if not items or len(items) == 0:
        return {'success': False, 'message': "Please provide at least one Item", 'labels': None}
    for contact in contacts:
        if not frappe.db.exists("Contact", contact):
            return {'success': False, 'message': f"The given Contact '{contact}' does not exist in the ERP.", 'labels': None}
    for item in items:
        if not frappe.db.exists("Item", item):
            return {'success': False, 'message': f"The given Item '{item}' does not exist in the ERP.", 'labels': None}
    try:
        sql_query = f"""
            SELECT `item`,
                `label_id` AS `barcode`,
                `status`,
                `registered`,
                `contact`,
                `registered_to`
            FROM `tabSequencing Label`
            WHERE `status` = 'unused'
                AND `item` IN ({get_sql_list(items)})
                AND `registered_to` IN ({get_sql_list(contacts)})
            ;"""
        labels = frappe.db.sql(sql_query, as_dict=True)
        return {'success': True, 'message': 'OK', 'labels': labels}
    except Exception as err:
        return {'success': False, 'message': err, 'labels': None}


@frappe.whitelist()
def get_label_status(labels):
    """
    Check uniqueness of label: throw an error if multiple Labels with the barcode are found

    bench execute microsynth.microsynth.webshop.get_label_status --kwargs "{'labels': [{'item': '6030', 'barcode': 'MY00043'}, {'item': '6030', 'barcode': 'MY00047'}]}"
    """
    # Check parameter
    if not labels or len(labels) == 0:
        return {'success': True, 'messages': []}
    try:
        messages_to_return = []
        for label in labels:
            if not 'item' in label or not label['item'] or not 'barcode' in label or not label['barcode']:
                messages_to_return.append({
                    'query': label,
                    'label': None,
                    'message': f"Label '{label['barcode']}' does not exist."  # Item and Barcode are both mandatory.
                })
                continue
            if not frappe.db.exists("Item", label['item']):
                messages_to_return.append({
                    'query': label,
                    'label': None,
                    'message': f"Label '{label['barcode']}' does not exist."  # f"The given Item '{label['item']}' does not exist in the ERP."
                })
                continue
            item_condition = f"AND `item` = {label['item']}"
            item_string = f" and Item Code {label['item']}"
            sql_query = f"""
                SELECT `item`,
                    `label_id` AS `barcode`,
                    `status`,
                    `registered`,
                    `contact`,
                    `registered_to`
                FROM `tabSequencing Label`
                WHERE `label_id` = '{label['barcode']}'
                    {item_condition}
                ;"""
            sequencing_labels = frappe.db.sql(sql_query, as_dict=True)
            if len(sequencing_labels) > 1:
                frappe.log_error(f"Found {len(sequencing_labels)} labels for the given barcode {label['barcode']}{item_string}.", "webshop.get_label_status")
                messages_to_return.append({
                    'query': label,
                    'label': None,
                    'message': f"Label '{label['barcode']}' is not valid. Please contact the Microsynth support."
                })
                continue
            elif len(sequencing_labels) == 0:
                #frappe.log_error(f"Found no label for the given barcode {label['barcode']}{item_string}.", "webshop.get_label_status")
                messages_to_return.append({
                    'query': label,
                    'label': None,
                    'message': f"Label '{label['barcode']}' does not exist."
                })
                continue
            else:
                messages_to_return.append({
                    'query': label,
                    'label': sequencing_labels[0],
                    'message': "OK"
                })
        return {'success': True, 'messages': messages_to_return}
    except Exception as err:
        frappe.log_error(f"{labels=}\n{err}", "webshop.get_label_status")
        return {'success': False, 'messages': [{'query': None, 'label': None, 'message': err}]}
        #return {'success': False, 'message': err, 'labels': None}


@frappe.whitelist()
def get_label_ranges():
    """
    Documented at https://github.com/Microsynth/erp-microsynth/wiki/Webshop-Label-API#get-label-ranges

    bench execute microsynth.microsynth.webshop.get_label_ranges
    """
    ranges_to_return = []
    try:  # range is also a SQL key word and needs therefore to be surrounded by backticks:
        label_ranges = frappe.get_all("Label Range", fields=['item_code', 'prefix', '`range`'])
        for label_range in label_ranges:
            ranges = label_range['range'].split(',')
            for range in ranges:
                parts = range.split('-')
                start = int(parts[0].strip())
                end = int(parts[1].strip())
                ranges_to_return.append({
                    "item": label_range['item_code'],
                    "prefix": label_range['prefix'],
                    "barcode_start_range": start,
                    "barcode_end_range": end
                })
    except Exception as err:
        return {'success': False, 'message': err, 'ranges': None}
    return {'success': True, 'message': 'OK', 'ranges': ranges_to_return}


def is_next_barcode(first_barcode, second_barcode):
    """
    Check if second_barcode follows immediatly after first_barcode
    """
    try:
        first_int = int(first_barcode)
        second_int = int(second_barcode)
        return first_int + 1 == second_int
    except Exception:
        try:
            # compile a regex
            cre = re.compile("([a-zA-Z]+)([0-9]+)")
            # match it to group text and numbers separately into a tuple
            first_split = cre.match(first_barcode).groups()
            second_split = cre.match(second_barcode).groups()
            # check if label prefixes are identical
            if first_split[0] == second_split[0]:
                return int(first_split[1]) + 1 == int(second_split[1])
            else:
                return False
        except Exception:
            return False


def partition_into_ranges(sequencing_labels):
    """
    Takes a list of dictionaries of labels sorted by barcode ascending and returns a list of dictionary of barcode ranges.
    """
    ranges = []
    if len(sequencing_labels) < 1:
        return ranges
    current_range_barcode = sequencing_labels[0]['barcode']
    range = {
        'registered_to': sequencing_labels[0]['registered_to'],
        'item': sequencing_labels[0]['item'],
        'barcode_start_range': current_range_barcode,
        'barcode_end_range': current_range_barcode
    }
    for i, label in enumerate(sequencing_labels):
        if i == 0:
            continue  # do not consider the first label a second time
        if label['registered_to'] != range['registered_to'] or label['item'] != range['item'] or not is_next_barcode(current_range_barcode, label['barcode']):
            # finish current range
            range['barcode_end_range'] = current_range_barcode
            ranges.append(range)
            # start a new range
            range = {
                'registered_to': label['registered_to'],
                'item': label['item'],
                'barcode_start_range': label['barcode'],
                'barcode_end_range': label['barcode']
            }
        current_range_barcode = label['barcode']
    # finish last range
    range['barcode_end_range'] = current_range_barcode
    if not range in ranges:
        # add last range
        ranges.append(range)
    return ranges


@frappe.whitelist()
def get_registered_label_ranges(contacts):
    """
    bench execute microsynth.microsynth.webshop.get_registered_label_ranges --kwargs "{'contacts': ['215856', '237365']}"
    """
    # Check parameter
    if not contacts or len(contacts) == 0:
        return {'success': False, 'message': "Please provide at least one Contact", 'ranges': None}
    for contact in contacts:
        if not frappe.db.exists("Contact", contact):
            return {'success': False, 'message': f"The given Contact '{contact}' does not exist in the ERP.", 'ranges': None}
    try:
        sql_query = f"""
            SELECT `item`,
                `label_id` AS `barcode`,
                `registered_to`
            FROM `tabSequencing Label`
            WHERE `status` = 'unused'
                AND `registered_to` IN ({get_sql_list(contacts)})
            ORDER BY `label_id` ASC
            ;"""
        sequencing_labels = frappe.db.sql(sql_query, as_dict=True)
        if len(sequencing_labels) == 0:
            return {'success': True, 'message': 'OK', 'ranges': []}
        ranges = partition_into_ranges(sequencing_labels)
        return {'success': True, 'message': 'OK', 'ranges': ranges}
    except Exception as err:
        return {'success': False, 'message': err, 'ranges': None}


def check_label_range(item, prefix, first_int, second_int):
    """
    Check if the given integers are both in the range of the Label Range of the given Item.
    """
    if not frappe.db.exists("Label Range", item):
        frappe.throw(f"There is no Label Range in the ERP for the given Item Code '{item}'.")
    label_range = frappe.get_doc("Label Range", item)
    if label_range.prefix and label_range.prefix != prefix:
        frappe.throw(f"The Label Range of the given Item Code '{item}' has prefix '{label_range.prefix}' "
                     f"but the given barcode_start_range and barcode_end_range have prefix '{prefix}'.")
    start_is_in_range = False
    end_is_in_range = False
    ranges = label_range.range.split(',')
    for range in ranges:
        parts = range.split('-')
        start = int(parts[0].strip())
        end = int(parts[1].strip())
        if start <= first_int <= end:
            start_is_in_range = True
        if start <= second_int <= end:
            end_is_in_range = True
    if not (start_is_in_range and end_is_in_range):
        frappe.throw(f"Either {first_int} or {second_int} or both are out of range for the Label Range of the given Item '{item}'.")


def check_and_unfold_label_range(barcode_start_range, barcode_end_range, item):
    """
    Returns a list of all barcode labels from barcode_start_range to barcode_end_range (including both)

    bench execute microsynth.microsynth.webshop.check_and_unfold_label_range --kwargs "{'barcode_start_range': 'MY00001', 'barcode_end_range': 'MY00011', 'item': None}"
    """
    try:
        number_length = len(barcode_start_range)
        first_int = int(barcode_start_range)
        second_int = int(barcode_end_range)
        prefix = ""
    except Exception:
        # compile a regex
        cre = re.compile("([a-zA-Z]+)([0-9]+)")
        # match it to group text and numbers separately into a tuple
        first_split = cre.match(barcode_start_range).groups()
        second_split = cre.match(barcode_end_range).groups()
        # check if label prefixes are identical
        if first_split[0] != second_split[0]:
            frappe.throw(f"The given barcodes have different prefixes ({first_split[0]} != {second_split[0]})")
        prefix = first_split[0]
        number_length = len(first_split[1])
        first_int = int(first_split[1])
        second_int = int(second_split[1])
    if first_int > second_int:
        frappe.throw(f"The given barcode_start_range must be smaller or equal than the given barcode_end_range.")
    if item:
        check_label_range(item, prefix, first_int, second_int)
    barcodes = []
    for n in range(first_int, second_int + 1):
        barcodes.append(f"{prefix}{n:0{number_length}d}" if prefix else f"{n:0{number_length}d}")
    return barcodes


def check_and_get_sequencing_labels(registered_to, item, barcode_start_range, barcode_end_range):
    """
    Check the given parameters, check and unfold the given label range, return the Sequencing Labels as a list of dictionaries

    bench execute microsynth.microsynth.webshop.check_and_get_sequencing_labels --kwargs "{'registered_to': '215856', 'item': '3000', 'barcode_start_range': '96858440', 'barcode_end_range': '96858444'}"
    """
    if not (registered_to and barcode_start_range and barcode_end_range):
        return {'success': False, 'message': "registered_to, barcode_start_range and barcode_end_range are mandatory parameters. Please provide all of them.", 'ranges': None}
    if item:
        if not frappe.db.exists("Item", item):
            return {'success': False, 'message': f"The given Item '{item}' does not exist in the ERP.", 'ranges': None}
        item_condition = f"AND `item` = {item}"
    else:
        item_condition = ""
    # check given label range
    barcodes = check_and_unfold_label_range(barcode_start_range, barcode_end_range, item)

    sql_query = f"""
        SELECT `name`,
            `item`,
            `label_id` AS `barcode`,
            `status`,
            `registered`,
            `contact`,
            `registered_to`
        FROM `tabSequencing Label`
        WHERE `label_id` IN ({get_sql_list(barcodes)})
            {item_condition}
        ;"""
    return frappe.db.sql(sql_query, as_dict=True)


@frappe.whitelist()
def register_labels(registered_to, item, barcode_start_range, barcode_end_range):
    """
    Register the given label range to the given Contact after doing several checks.

    bench execute microsynth.microsynth.webshop.register_labels --kwargs "{'registered_to': '215856', 'item': '3000', 'barcode_start_range': '96858440', 'barcode_end_range': '96858444'}"
    """
    try:
        sequencing_labels = check_and_get_sequencing_labels(registered_to, item, barcode_start_range, barcode_end_range)
        registered_labels = []
        messages = ''
        for label in sequencing_labels:
            # check label
            if label['status'] != 'unused':
                message = 'Some labels were not registered because they were already used. '
                if not message in messages:
                    messages += message
                # do not change the affected Sequencing Label
                continue
            if label['registered'] or label['registered_to']:
                message = 'Some labels were not registered because they were already registered. '
                if not message in messages:
                    messages += message
                # do not change the affected Sequencing Label
                continue
            seq_label = frappe.get_doc("Sequencing Label", label['name'])
            # register label
            seq_label.registered = 1
            seq_label.registered_to = registered_to
            seq_label.save()
            label['registered_to'] = registered_to
            registered_labels.append(label)
        if len(registered_labels) > 0:
            return {'success': True, 'message': messages if messages else 'OK', 'ranges': partition_into_ranges(registered_labels)}
        else:
            return {'success': False, 'message': 'Unable to register any labels. ' + messages, 'ranges': partition_into_ranges(registered_labels)}
    except Exception as err:
        return {'success': False, 'message': err, 'ranges': None}


@frappe.whitelist()
def unregister_labels(registered_to, item, barcode_start_range, barcode_end_range):
    """
    Unregister the given label range if it is registered to the given Contact

    bench execute microsynth.microsynth.webshop.unregister_labels --kwargs "{'registered_to': '215856', 'item': '3000', 'barcode_start_range': '96858440', 'barcode_end_range': '96858444'}"
    """
    try:
        sequencing_labels = check_and_get_sequencing_labels(registered_to, item, barcode_start_range, barcode_end_range)
        for label in sequencing_labels:
            # check label
            if label['registered_to'] != registered_to:
                return {'success': False, 'message': f"Barcode {label['barcode']} is not registered to {registered_to}. Did not unregister any labels."}
        for label in sequencing_labels:
            # unregister label
            seq_label = frappe.get_doc("Sequencing Label", label['name'])
            seq_label.registered = 0
            seq_label.registered_to = None
            seq_label.save()
        return {'success': True, 'message': 'OK'}
    except Exception as err:
        return {'success': False, 'message': err}


def check_and_get_label(label):
    """
    Take a label dictionary (item, barcode, status), search it in the ERP and return it if it is unique or an error message otherwise.

    bench execute microsynth.microsynth.webshop.check_and_get_label --kwargs "{'label': {'item': '6030', 'barcode': 'MY00042', 'status': 'submitted'}}"
    """
    sql_query = f"""
        SELECT `name`,
            `item`,
            `label_id` AS `barcode`,
            `status`,
            `registered`,
            `contact`,
            `registered_to`,
            `sales_order`
        FROM `tabSequencing Label`
        WHERE `label_id` = '{label['barcode']}'
            AND `item` = '{label['item']}'
        ;"""
    sequencing_labels = frappe.db.sql(sql_query, as_dict=True)
    if len(sequencing_labels) == 0:
        return {'success': False, 'message': f"Found no label with barcode {label['barcode']} and Item {label['item']} in the ERP.", 'label': None}
    elif len(sequencing_labels) > 1:
        return {'success': False, 'message': f"Found multiple labels with barcode {label['barcode']} and Item {label['item']} in the ERP.", 'label': None}
    else:
        return {'success': True, 'message': "OK", 'label': sequencing_labels[0]}


@frappe.whitelist()
def set_label_submitted(labels):
    """
    Set the Status of the given Labels to submitted if they are unused and pass further tests.
    Try to submit as many labels as possible, return False if at least one given label could not be submitted

    bench execute microsynth.microsynth.webshop.set_label_submitted --kwargs "{'labels': [{'item': '6030', 'barcode': 'MY00042', 'status': 'submitted'}, {'item': '6030', 'barcode': 'MY00043', 'status': 'submitted'}]}"
    """
    if not labels or len(labels) == 0:
        return {'success': False, 'message': "Please provide at least one Label", 'labels': None}
    try:
        success = True
        labels_to_return = []
        for label in labels:
            response = check_and_get_label(label)
            if not response['success']:
                label['message'] = response['message']
                labels_to_return.append(label)
                success = False
                continue
            if not response['label']:  # should not happen here, but just for safety
                label['message'] = response['message'] or "Did not found exactly one label in the ERP."
                labels_to_return.append(label)
                success = False
                continue
            erp_label = response['label']
            if response['label']['status'] != 'unused':
                erp_label['message'] = "The label has not status unused in the ERP."
                labels_to_return.append(erp_label)
                success = False
                continue
            seq_label = frappe.get_doc("Sequencing Label", erp_label['name'])
            # set label sumitted
            seq_label.status = "submitted"
            seq_label.save()
            erp_label['status'] = seq_label.status
            erp_label['message'] = "OK"
            labels_to_return.append(erp_label)
        if success:
            return {'success': success, 'message': 'OK', 'labels': labels_to_return}
        else:
            return {'success': success, 'message': 'There was at least one label that could not be set to status submitted. Please check the label messages.', 'labels': labels_to_return}
    except Exception as err:
        return {'success': False, 'message': err, 'labels': None}


@frappe.whitelist()
def set_label_unused(labels):
    """
    Set the Status of the given Labels to unused if they are all submitted and pass further tests.

    bench execute microsynth.microsynth.webshop.set_label_unused --kwargs "{'labels': [{'item': '6030', 'barcode': 'MY00042', 'status': 'submitted'}, {'item': '6030', 'barcode': 'MY00043', 'status': 'submitted'}]}"
    """
    if not labels or len(labels) == 0:
        return {'success': False, 'message': "Please provide at least one Label", 'labels': None}
    try:
        labels_to_set_unused = []
        for label_to_check in labels:
            response = check_and_get_label(label_to_check)
            if not response['success']:
                return {'success': False, 'message': response['message'], 'labels': None}
            if not response['label']:  # should not happen here, but just for safety
                return {'success': False, 'message': response['message'] or "Did not found exactly one label in the ERP.", 'labels': None}
            erp_label = response['label']
            if erp_label['status'] != 'submitted':
                return {'success': False, 'message': f"The label with barcode '{erp_label['barcode']}' and Item '{erp_label['item']}' has not status submitted in the ERP.", 'labels': None}
            labels_to_set_unused.append(erp_label)
        # Check that the Sequencing Labels are NOT used on Sales Order.samples of Sales Orders with DocStatus <= 1
        # The Sequencing Label.sales_order is the order from ordering the labels. Do not consider this entry
        for label in labels_to_set_unused:
            sql_query = f"""
                SELECT 
                    `tabSample`.`name` AS `sample`,
                    `tabSample`.`sequencing_label` AS `barcode`,
                    `tabSales Order`.`name` AS `sales_order`
                FROM `tabSample Link`
                LEFT JOIN `tabSample` ON `tabSample Link`.`sample` = `tabSample`.`name`
                LEFT JOIN `tabSales Order` ON `tabSales Order`.`name` = `tabSample Link`.`parent`
                WHERE
                    `tabSample`.`sequencing_label` = '{label['barcode']}'
                    AND `tabSample Link`.`parent` != '{label['sales_order']}'
                    AND `tabSample Link`.`parenttype` = "Sales Order"
                    AND `tabSales Order`.`docstatus` <= 1
                ;"""
            samples = frappe.db.sql(sql_query, as_dict=True)
            if len(samples) > 0:
                return {
                    'success': False,
                    'message': f"The label '{label['barcode']}' occurs on {len(samples)} Sample(s) that are on a non-Cancelled Sales Order unequals the Sales Order {label['sales_order']} on the Sequencing Label.",
                    'labels': None
                }
        labels_set_unused = []
        for label in labels_to_set_unused:
            seq_label = frappe.get_doc("Sequencing Label", label['name'])
            # set label unused
            seq_label.status = "unused"
            seq_label.save()
            labels_set_unused.append({
                "item": seq_label.item,
                "barcode": seq_label.label_id,
                "status": seq_label.status
            })
        return {'success': True, 'message': 'OK', 'labels': labels_set_unused}
    except Exception as err:
        return {'success': False, 'message': err, 'labels': None}


@frappe.whitelist()
def cancel_order(sales_order, web_order_id):
    """
    Cancel the given Sales Order and return the labels of its samples.

    bench execute microsynth.microsynth.webshop.cancel_order --kwargs "{'sales_order': 'SO-BAL-24032361', 'web_order_id': '4128337'}"
    """
    try:
        sales_order_doc = frappe.get_doc("Sales Order", sales_order)
        if not sales_order_doc or sales_order_doc.docstatus != 1:
            sales_orders = frappe.get_all("Sales Order", filters=[['web_order_id', '=', web_order_id], ['docstatus', '=', 1]], fields=['name'])
            if len(sales_orders) == 0:
                return {
                    'success': False,
                    'message': 'Found no valid Sales Order with the given Sales Order ID or Web Order ID in the ERP.',
                    "sales_order": None,
                    "web_order_id": None,
                    'labels': None
                }
            if len(sales_orders) > 1:
                return {
                    'success': False,
                    'message': 'Found no valid Sales Order with the given Sales Order ID and multiple valid Sales Orders with the given Web Order ID in the ERP.',
                    "sales_order": None,
                    "web_order_id": None,
                    'labels': None
                }
            else:
                # found exactly one valid Sales Order with the given Web Order ID
                sales_order_doc = frappe.get_doc("Sales Order", sales_orders[0]['name'])
        elif sales_order_doc.web_order_id != web_order_id:
            return {
                'success': False,
                'message': f"The given Sales Order '{sales_order}' has not the given Web Order ID '{web_order_id}'.",
                "sales_order": None,
                "web_order_id": None,
                'labels': None
            }
        labels = []
        for sample in sales_order_doc.samples:
            sequencing_label = frappe.get_value("Sample", sample.sample, "sequencing_label")
            if not sequencing_label:
                return {
                    'success': False,
                    'message': f"Sample {sample.sample} has no Barcode Label.",
                    "sales_order": sales_order_doc.name,
                    "web_order_id": sales_order_doc.web_order_id,
                    'labels': None
                }
            label_doc = frappe.get_doc("Sequencing Label", sequencing_label)
            # Check that the Sequencing Label is in status "submitted"
            if label_doc.status != "submitted":
                return {
                    'success': False,
                    'message': f"Sample {sample.sample} has the Barcode Label {label_doc.name} with status {label_doc.status} (not status 'submitted').",
                    "sales_order": sales_order_doc.name,
                    "web_order_id": sales_order_doc.web_order_id,
                    'labels': None
                }
            # Set label unused
            label_doc.status = "unused"
            label_doc.save()
            labels.append({
                "item": label_doc.item,
                "barcode": label_doc.label_id,
                "status": label_doc.status
            })
        # Cancel & comment
        sales_order_doc.cancel()
        new_comment = frappe.get_doc({
            'doctype': "Comment",
            'comment_type': "Comment",
            'subject': sales_order_doc.name,
            'content': "Cancelled by the Webshop (webshop.cancel_order)",
            'reference_doctype': "Sales Order",
            'status': "Linked",
            'reference_name': sales_order_doc.name
        })
        new_comment.insert(ignore_permissions=True)
        return {
            'success': True,
            'message': 'OK',
            "sales_order": sales_order_doc.name,
            "web_order_id": sales_order_doc.web_order_id,
            'labels': labels
        }
    except Exception as err:
        return {
            'success': False,
            'message': err,
            "sales_order": None,
            "web_order_id": None,
            'labels': None
        }


@frappe.whitelist()
def get_quotation_pdf(quotation_id):
    """
    Creates the Quotation PDF and returns it as base64-encoded file

    bench execute microsynth.microsynth.webshop.get_quotation_pdf --kwargs "{'quotation_id': 'QTN-2500123'}"
    """
    from erpnextswiss.erpnextswiss.attach_pdf import get_pdf_data
    if not frappe.db.exists("Quotation", quotation_id):
        return {'success': False, 'message': f"Quotation '{quotation_id}' not found.", 'base64string': None}
    try:
        pdf = get_pdf_data(doctype='Quotation', name=quotation_id, print_format='Quotation')
        encoded_string = base64.b64encode(pdf)
        return {'success': True, 'message': 'OK', 'base64string': encoded_string}
    except Exception as err:
        return {'success': False, 'message': err, 'base64string': None}


def get_customer_dto(customer):
    customer_dto = {
        'name': customer.name,
        'customer_name': customer.customer_name,
        'tax_id': customer.tax_id
    }
    return customer_dto


def get_contact_dto(contact):
    from microsynth.microsynth.utils import get_customer

    contact_dto = {
        'name': contact.name,
        'first_name': contact.first_name,
        'last_name': contact.last_name,
        'salutation': contact.salutation,
        'title': contact.designation,
        'institute': contact.institute,
        'department': contact.department,
        'room': contact.room,
        'status': contact.status,
        'source': contact.source,
        'email': contact.email_id,
        'address': contact.address,
        'customer': get_customer(contact.name)
    }
    return contact_dto


def get_address_dto(address):
    address_dto = {
        'name': address.name,
        'address_type': address.address_type,
        'overwrite_company': address.overwrite_company,
        'address_line1': address.address_line1,
        'address_line2': address.address_line2,
        'pincode': address.pincode,
        'city': address.city,
        'country': address.country,
        # 'is_shipping_address': address.is_shipping_address,
        # 'is_primary_address': address.is_primary_address,
        'geo_lat': address.geo_lat,
        'geo_long': address.geo_long
    }
    return address_dto


def get_webshop_address_dtos(webshop_addresses):
    addresses = []
    
    for a in webshop_addresses.addresses:
        if a.disabled:
            continue

        contact = frappe.get_doc("Contact", a.contact)
        contact_dto = get_contact_dto(contact)

        address = frappe.get_doc("Address", contact.address)        
        customer = frappe.get_doc("Customer", contact_dto['customer'])

        webshop_address = {
            'customer': get_customer_dto(customer),
            'contact': contact_dto,
            'address': get_address_dto(address),
            'is_default_shipping': a.is_default_shipping,
            'is_default_billing': a.is_default_billing
        }
        addresses.append(webshop_address)
    return addresses


@frappe.whitelist()
def get_webshop_addresses(webshop_account):
    """
    bench execute microsynth.microsynth.webshop.get_webshop_addresses --kwargs "{'webshop_account':'215856'}"
    """
    try:
        webshop_addresses = frappe.get_doc("Webshop Address", webshop_account)

        return {
            'success': True, 
            'message': "OK", 
            'webshop_account': webshop_addresses.name,
            'webshop_addresses': get_webshop_address_dtos(webshop_addresses),
        }
    except Exception as err:
        return {
            'success': False,
            'message': err,
            'webshop_account': webshop_account,
            'webshop_addresses': [],
        }


def create_customer(webshop_address):
    user_data = {
        'customer': webshop_address['customer'],
        'contact': webshop_address['contact'],
        'addresses': [webshop_address['address']]
    }
    register_user(user_data)  # TODO: customer, contact, invoice_contact, shipping and billing address needed
    # TODO: consider usage of get_first_shipping_address regarding Customers without a Shipping Address


def create_contact(webshop_address, customer):
    contact = webshop_address['contact']
    contact['person_id'] = contact['name']    # Extend contact object to use the legacy update_contact function
    contact['customer_id'] = customer
    contact['status'] = "Passive"  # TODO?
    contact_id = update_contact(contact)
    # create Contact Lock
    lock_contact_by_name(contact_id)
    return contact_id


def create_address(webshop_address, customer):
    address = webshop_address['address']
    address['person_id'] = address['name']      # Extend address object to use the legacy update_address function
    address['customer_id'] = customer
    address_id = update_address(address)
    return address_id


@frappe.whitelist()
def create_webshop_address(webshop_account, webshop_address):
    try:
        if type(webshop_address) == str:
            webshop_address = json.loads(webshop_address)
        webshop_addresses = frappe.get_doc("Webshop Address", webshop_account)
        
        webshop_account_customer = get_customer(webshop_account)

        # create a new customer if it is different from the customer of webshop_account and the new webshop_address is a billing address
        if webshop_address['customer']['name'] != webshop_account_customer and webshop_address['address']['address_type'] == 'Billing':
            create_customer(webshop_address)            

        # create an Address if it does not yet exist for the Customer
        address_id = create_address(webshop_address, webshop_account_customer)
        # create a Contact
        contact_id = create_contact(webshop_address, webshop_account_customer)

        # append a webshop_address entry with above contact id to webshop_addresses.addresses
        webshop_addresses.append('addresses', {
            'contact': contact_id,
            'is_default_shipping': 0,
            'is_default_billing': 0,
            'disabled': 0
        })
        webshop_address_dtos = get_webshop_address_dtos(webshop_addresses)

        return {
            'success': True, 
            'message': "OK", 
            'webshop_account': webshop_addresses.name,
            'webshop_addresses': webshop_address_dtos,
        }
    except Exception as err:
        return {
            'success': False,
            'message': err,
            'webshop_account': webshop_account,
            'webshop_addresses': [],
        }


@frappe.whitelist()
def update_webshop_address(webshop_account, webshop_address):
    """
    bench execute microsynth.microsynth.webshop.update_webshop_address --kwargs "{'webshop_account': '215856', 'webshop_address': ''}"
    """
    try:
        if type(webshop_address) == str:
            webshop_address = json.loads(webshop_address)
        webshop_addresses = frappe.get_doc("Webshop Address", webshop_account)
        customer_id = webshop_address.get('customer').get('name')
        contact_id = webshop_address.get('contact').get('name')
        address_id = webshop_address.get('address').get('name')

        # check if the provided webshop_address is part of the webshop_addresses (by contact.name). Send an error if it is not present.
        found = False
        for a in webshop_addresses.addresses:
            if a.contact == contact_id:
                found = True
                break
        if not found:
            return {
                'success': False,
                'message': f"The given Contact '{contact_id}' is not part of the given {webshop_account=}.",
                'webshop_account': webshop_account,
                'webshop_addresses': [],
            }
        # check if the customer, contact or address of the webshop_address are used on Quotations, Sales Orders, Delivery Notes, Sales Invoices
        if not is_customer_used(customer_id) and not is_contact_used(contact_id) and not is_address_used(address_id):  # this will take very long
            # update customer/contact/address if not used
            customer = webshop_address['contact']
            customer['customer_id'] = customer['name']
            update_customer(customer)
            contact = webshop_address['contact']
            contact['person_id'] = contact['name']  # Extend contact object to use the legacy update_contact function
            contact_id = update_contact(contact)
            address = webshop_address['address']
            address['person_id'] = address['name']  # Extend address object to use the legacy update_address function
            address_id = update_address(address)
        else:
            # create new customer/contact/address if used
            customer_id = None  # TODO: Create Customer
            address_id = create_address(webshop_address, customer_id)
            contact_id = create_contact(webshop_address, customer_id)
            # if a new customer/contact/address was created, append a webshop_address entry with the contact id to webshop_addresses.addresses
            webshop_addresses.append('addresses', {
                'contact': contact_id,
                'is_default_shipping': 0,
                'is_default_billing': 0,
                'disabled': 0
            })

        return {
            'success': True, 
            'message': "OK", 
            'webshop_account': webshop_addresses.name,
            'webshop_addresses': get_webshop_address_dtos(webshop_addresses),
        }
    except Exception as err:
        return {
            'success': False,
            'message': err,
            'webshop_account': webshop_account,
            'webshop_addresses': [],
        }


@frappe.whitelist()
def delete_webshop_address(webshop_account, contact_id):
    """
    bench execute microsynth.microsynth.webshop.delete_webshop_address --kwargs "{'webshop_account':'215856', 'contact_id':'234007'}"
    """
    try:
        webshop_addresses = frappe.get_doc("Webshop Address", webshop_account)

        # check if the provided contact_id is part of the webshop_addresses. send an error if not.
        found = False
        for a in webshop_addresses.addresses:
            if a.contact == contact_id:
                found = True
                break
        if not found:
            return {
                'success': False,
                'message': f"The given {contact_id=} is not part of the given {webshop_account=}.",
                'webshop_account': webshop_account,
                'webshop_addresses': [],
            }

        for a in webshop_addresses.addresses:
            if a.contact == contact_id:
                a.disabled = True

        webshop_addresses.save()

        # trigger an async background job that checks if the Customer/Contact/Address was used on Quotations/Sales Orders/Delivery Notes/Sales Invoices before. if not, delete it.
        frappe.enqueue(method=delete_if_unused, queue='long', timeout=600, is_async=True, contact_id=contact_id)

        return {
            'success': True, 
            'message': "OK", 
            'webshop_account': webshop_addresses.name,
            'webshop_addresses': get_webshop_address_dtos(webshop_addresses),
        }
    except Exception as err:
        return {
            'success': False,
            'message': err,
            'webshop_account': webshop_account,
            'webshop_addresses': [],
        }


def delete_if_unused(contact_id):
    """
    Delete the given Contact and its Address if both are unused.
    If both are unused, delete the Customer of the given Contact if it is unused too.
    """
    address_id = frappe.get_value('Contact', contact_id, 'address')
    customer_id = get_customer(contact_id)
    if not is_address_used(address_id) and not is_contact_used(contact_id):
        address_doc = frappe.get_doc('Address', address_id)
        address_doc.delete()
        contact_doc = frappe.get_doc('Contact', contact_id)
        contact_doc.delete()
        frappe.db.commit()
    else:
        return
    if not is_customer_used(customer_id):
        customer_doc = frappe.get_doc('Customer', customer_id)
        customer_doc.delete()


def is_customer_used(customer_id):
    """
    Check if the given Customer is used on one of the below DocTypes

    bench execute microsynth.microsynth.webshop.is_customer_used --kwargs "{'customer_id': '839115'}"
    """
    linked_doctypes = {
        'Sales Order': {'fieldname': ['customer', 'order_customer']},
        'Delivery Note': {'fieldname': ['customer', 'order_customer']},
        'Purchase Order': {'fieldname': ['customer']},
        'Sales Invoice': {'fieldname': ['customer', 'order_customer']},
        'Payment Reminder': {'fieldname': ['customer']},
        'ERPNextSwiss Settings': {'fieldname': ['default_customer']},
        'Standing Quotation': {'fieldname': ['customer']},
        'Sequencing Label': {'fieldname': ['customer']},
        'Oligo': {'fieldname': ['customer']},
        'Sample': {'fieldname': ['customer']},
        'Analysis Report': {'fieldname': ['customer']},
        'Label Log': {'fieldname': ['customer']},
        'Intercompany Settings': {'child_doctype': 'Intercompany Settings Account', 'fieldname': ['party'], 'doctype_fieldname': 'party_type'},
        'Customs Declaration': {'child_doctype': 'Customs Declaration Delivery Note', 'fieldname': ['customer']},
        'QM Change': {'child_doctype': 'QM Change Customer', 'fieldname': ['customer']},
        'QM Document': {'child_doctype': 'QM Document Customer', 'fieldname': ['customer']},
        'QM Nonconformity': {'child_doctype': 'QM Nonconformity Customer', 'fieldname': ['customer']},
        'QM Analytical Procedure': {'child_doctype': 'Customer Link', 'fieldname': ['customer']},
        'Contact': {'child_doctype': 'Dynamic Link', 'fieldname': ['link_name'], 'doctype_fieldname': 'link_doctype'},
        'Address': {'child_doctype': 'Dynamic Link', 'fieldname': ['link_name'], 'doctype_fieldname': 'link_doctype'},
        'Journal Entry': {'child_doctype': 'Journal Entry Account', 'fieldname': ['party'], 'doctype_fieldname': 'party_type'},
        'Quotation': {'fieldname': ['party_name'], 'doctype_fieldname': 'quotation_to'},
        'Payment Entry': {'fieldname': ['party'], 'doctype_fieldname': 'party_type'}
    }
    linked_docs = get_linked_docs('Customer', customer_id, linked_doctypes)
    print(linked_docs)
    return len(linked_docs) > 0


def is_contact_used(contact_id):
    """
    Check if the given Contact is used on one of the below DocTypes

    bench execute microsynth.microsynth.webshop.is_contact_used --kwargs "{'contact_id': '243482'}"
    """
    linked_doctypes = {
        'Supplier Quotation': {'fieldname': ['contact_person']},
        'Quotation': {'fieldname': ['contact_person', 'shipping_contact']},
        'Customer': {'fieldname': ['customer_primary_contact', 'invoice_to', 'reminder_to']},
        'Sales Order': {'fieldname': ['contact_person', 'shipping_contact', 'invoice_to']},
        'Purchase Receipt': {'fieldname': ['contact_person']},
        'Delivery Note': {'fieldname': ['contact_person', 'shipping_contact', 'invoice_to']},
        'Purchase Invoice': {'fieldname': ['contact_person']},
        'Purchase Order': {'fieldname': ['contact_person', 'customer_contact_person']},
        'Sales Invoice': {'fieldname': ['contact_person', 'invoice_to', 'shipping_contact']},
        'Payment Entry': {'fieldname': ['contact_person']},
        'Product Idea': {'fieldname': ['contact_person']},
        'Benchmark': {'fieldname': ['contact_person']},
        'Standing Quotation': {'fieldname': ['contact']},
        'Contact Note': {'fieldname': ['contact_person']},
        'Sequencing Label': {'fieldname': ['contact', 'registered_to']},
        'Punchout Shop': {'fieldname': ['billing_contact']},
        'Analysis Report': {'fieldname': ['contact_person']},
        'Label Log': {'fieldname': ['contact', 'registered_to']}
    }
    linked_docs = get_linked_docs('Contact', contact_id, linked_doctypes)
    #print(linked_docs)
    return len(linked_docs) > 0


def is_address_used(address_id):
    """
    Check if the given Address is used on one of the below DocTypes

    bench execute microsynth.microsynth.webshop.is_address_used --kwargs "{'address_id': '215856'}"
    """
    linked_doctypes = {
        'Supplier Quotation': {'fieldname': ['supplier_address']},
        'Quotation': {'fieldname': ['customer_address', 'shipping_address_name']},
        'Customer': {'fieldname': ['customer_primary_address']},
        'Sales Order': {'fieldname': ['customer_address', 'shipping_address_name', 'company_address']},
        'Purchase Receipt': {'fieldname': ['shipping_address', 'supplier_address']},
        'Delivery Note': {'fieldname': ['customer_address', 'company_address', 'shipping_address_name']},
        'Purchase Invoice': {'fieldname': ['shipping_address', 'supplier_address']},
        'Purchase Order': {'fieldname': ['shipping_address', 'supplier_address']},
        'Sales Invoice': {'fieldname': ['customer_address', 'company_address', 'shipping_address_name']},
        'Standing Quotation': {'fieldname': ['address']},
        'Punchout Shop': {'fieldname': ['billing_address']},
        'Analysis Report': {'fieldname': ['address']},
        'Customs Declaration': {'child_doctype': 'Customs Declaration Delivery Note', 'fieldname': ['shipping_address']}
    }
    linked_docs = get_linked_docs('Address', address_id, linked_doctypes)
    return len(linked_docs) > 0
