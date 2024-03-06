# -*- coding: utf-8 -*-
# Copyright (c) 2022-2024, libracore (https://www.libracore.com) and contributors
# For license information, please see license.txt
#
# For more details, refer to https://github.com/Microsynth/erp-microsynth/wiki/Webshop-API
#

import frappe
import json
from microsynth.microsynth.migration import update_contact, update_address, robust_get_country
from microsynth.microsynth.utils import get_customer, create_oligo, create_sample, get_express_shipping_item, get_billing_address, configure_new_customer
from microsynth.microsynth.taxes import find_dated_tax_template
from microsynth.microsynth.marketing import lock_contact_by_name
from microsynth.microsynth.naming_series import get_naming_series
from microsynth.microsynth.invoicing import set_income_accounts
from datetime import date, timedelta
from erpnextswiss.scripts.crm_tools import get_primary_customer_address
from erpnext.selling.doctype.sales_order.sales_order import make_sales_invoice


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
    if 'overwrite_company' in address and address['overwrite_company'] is not None:
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
        # temporarily insert
        so.insert(ignore_permissions=True)
        item_prices = []
        for i in so.items:
            item_prices.append({
                'item_code': i.item_code,
                'qty': i.qty,
                'rate': i.rate,
                'description': i.item_name
            })
        # remove temporary record
        so.delete()
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
    # select naming series
    naming_series = get_naming_series("Sales Order", company)

    customer = frappe.get_doc("Customer", content['customer'])
    contact = frappe.get_doc("Contact", content['contact'])  # cache contact values (Frappe bug in binding)
    billing_address = content['invoice_address']

    order_customer = None

    # Distributor workflow
    if 'product_type' in content:
        for distributor in customer.distributors:
            if distributor.product_type == content['product_type']:
                # swap customer and replace billing address
                order_customer = customer
                customer = frappe.get_doc("Customer", distributor.distributor)

                billing_address = get_billing_address(customer.name).name

    # check that the webshop does not send prices / take prices from distributor price list
    #   consider product type

    # create sales order
    transaction_date = date.today()
    delivery_date = transaction_date + timedelta(days=3)
    so_doc = frappe.get_doc({
        'doctype': "Sales Order",
        'company': company,
        'naming_series': naming_series,
        'customer': customer.name,
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
    # quotation rate override: if an item has a rate in the quotation, always take this 
    #    (note: has to be post insert, otherwise frappe will override 0 rates)
    if quotation:
        for item in so_doc.items:                                   # loop through all items in sales order
            if item.item_code in quotation_rate:                    # check if this item had a quotation rate
                item.rate = quotation_rate[item.item_code]
                item.price_list_rate = quotation_rate[item.item_code]

        so_doc = apply_discount(qtn_doc, so_doc)

    # prepayment: hold order
    if "Prepayment" in (customer.invoicing_method or ""):
        so_doc.hold_order = 1
    
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
        """SELECT `item`, `item_name`, `qty`, `rate`, `threshold`, `preferred_express`
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
    """SELECT `item`, `item_name`, `qty`, `rate`, `threshold`, `preferred_express`
       FROM `tabShipping Item`
       WHERE `parent` = "{0}" 
         AND `parenttype` = "Country"
       ORDER BY `idx` ASC;""".format(country), as_dict=True)
           
    return {'success': True, 'message': "OK", 'currency': frappe.get_value("Country", country, 'default_currency'), 'shipping_items': shipping_items}


@frappe.whitelist()
def get_contact_shipping_items(person_id):
    """
    Return all available shipping items for a contact

    bench execute "microsynth.microsynth.webshop.get_contact_shipping_items" --kwargs "{'person_id': 221845}"
    """
    if not person_id or not frappe.db.exists("Contact", person_id):
        return {'success': False, 'message': 'A valid and existing person_id is required', 'shipping_items': []}
    customer_id = get_customer(person_id)
    # find by customer id
    if customer_id:
        shipping_items = frappe.db.sql(
            f"""SELECT `item`, `item_name`, `qty`, `rate`, `threshold`, `preferred_express`
                FROM `tabShipping Item`
                WHERE `parent` = "{customer_id}" 
                    AND `parenttype` = "Customer"
                ORDER BY `idx` ASC;""", as_dict=True)
        if len(shipping_items) > 0:
            return {'success': True, 'message': "OK", 'currency': frappe.get_value("Customer", customer_id, 'default_currency'), 'shipping_items': shipping_items}
        else:
            # find country for fallback
            address = frappe.get_value("Contact", person_id, "address")
            if address:
                country = frappe.get_value("Address", address, "country")
            else:
                return {'success': False, 'message': f'Contact {person_id} has no address', 'shipping_items': []}

    # find by country (fallback from the customer)
    if not country:
        country = frappe.defaults.get_global_default('country')
    country = robust_get_country(country)
    shipping_items = frappe.db.sql(
        f"""SELECT `item`, `item_name`, `qty`, `rate`, `threshold`, `preferred_express`
            FROM `tabShipping Item`
            WHERE `parent` = "{country}" 
                AND `parenttype` = "Country"
            ORDER BY `idx` ASC;""", as_dict=True)
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
    """
    
    # check configuration
    if not frappe.db.exists("Mode of Payment", "stripe"):
        return {'success': False, 'message': "Mode of Payment stripe missing. Please correct ERP configuration."}
        
    # fetch sales order
    if not frappe.db.exists("Sales Order", sales_order):
        return {'success': False, 'message': "Sales Order not found"}
    so_doc = frappe.get_doc("Sales Order", sales_order)
    
    # assure this sales order is against default company (no longer required with mode of payment)
    #if so_doc.company != frappe.defaults.get_global_default("company"):
    #    return {'success': False, 'message': "Only company {0} is allowed to process stripe".format(frappe.defaults.get_global_default("company"))}
    
    # create sales invoice
    si_content = make_sales_invoice(so_doc.name)
    sinv = frappe.get_doc(si_content)
    sinv.flags.ignore_missing = True
    sinv.is_pos = 1                     # enable included payment
    sinv.append("payments", {
        'default': 1,
        'mode_of_payment': "stripe",
        'amount': sinv.rounded_total or sinv.grand_total
    })
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
    
    # remove hold flag
    so_doc = frappe.get_doc("Sales Order", sales_order)
    so_doc.hold_order = 0
    try:
        so_doc.save()
    except Exception as err:
        return {'success': False, 'message': "Failed to update sales order {0}: {1}".format(sales_order, err)}
    frappe.db.commit()
    
    return {'success': True, 'message': "OK", 'reference': sinv.name}
