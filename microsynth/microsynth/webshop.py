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
from microsynth.microsynth.utils import (
    get_customer,
    create_oligo,
    create_sample,
    get_express_shipping_item,
    get_billing_address,
    configure_new_customer,
    has_webshop_service,
    get_customer_from_company,
    get_supplier_for_product_type,
    get_margin_from_customer,
    to_bool,
    update_address_links_from_contact,
    send_email_from_template,
    get_sql_list
)
from microsynth.microsynth.seqblatt import process_label_status_change
from microsynth.microsynth.taxes import find_dated_tax_template
from microsynth.microsynth.marketing import lock_contact_by_name
from microsynth.microsynth.naming_series import get_naming_series
from microsynth.microsynth.invoicing import set_income_accounts, transmit_sales_invoice
from datetime import date, datetime, timedelta
from erpnextswiss.scripts.crm_tools import get_primary_customer_address
from erpnext.selling.doctype.sales_order.sales_order import make_sales_invoice
import traceback


@frappe.whitelist(allow_guest=True)
def ping():
    """
    Ping is a simple interface test function
    """
    return "pong"


def initialize_webshop_address_doc(webshop_account, shipping_contact, billing_contact):
    """
    Takes three Contact IDs.
    Checks if there exists no Webshop Address for the given webshop_account.
    Creates a new Webshop Address Doc and appends the default shipping and billing contact.

    bench execute microsynth.microsynth.webshop.initialize_webshop_address_doc --kwargs "{'webshop_account': '215856', 'shipping_contact': '215856', 'billing_contact': '71921'}"
    """
    if frappe.db.exists("Webshop Address", webshop_account):
        msg = f"There exists already a Webshop Address '{webshop_account}'. Unable to create a new one."
        frappe.log_error(msg, "webshop.initialize_webshop_address_doc")
        frappe.throw(msg)
    # create a new Webshop Address
    webshop_address_doc = frappe.get_doc({
            'doctype': 'Webshop Address',
            'webshop_account': webshop_account,
        })
    # add default shipping contact
    webshop_address_doc.append('addresses', {
        'contact': shipping_contact,
        'is_default_shipping': 1,
        'is_default_billing': 0,
        'disabled': 0
    })
    # add default billing contact
    webshop_address_doc.append('addresses', {
        'contact': billing_contact,
        'is_default_shipping': 0,
        'is_default_billing': 1,
        'disabled': 0
    })
    webshop_address_doc.insert()


def parse_date(date_str):
    for format_str in ("%Y-%m-%dT%H:%M:%S", "%d.%m.%Y %H:%M:%S", "%d.%m.%Y"):
        try:
            return datetime.strptime(date_str, format_str)
        except (ValueError, TypeError):
            continue
    print(f"failed to parse date: {date_str}")
    return None


def update_child_table(parent, table_fieldname, new_data, match_keys):
    """
    Update a child table with minimal changes.
    The order of the rows in new_data might not be preserved.

    :param parent: The parent document (e.g. Contact)
    :param table_fieldname: Name of the child table field (e.g. 'email_ids')
    :param new_data: List of new dicts to set
    :param match_keys: Keys to match existing rows (e.g. ['email_id', 'is_primary'])
    """
    from copy import deepcopy

    def is_exact_match(row, entry):
        # Check if row matches entry exactly on all match_keys
        return all(row.get(k) == entry.get(k) for k in match_keys)

    def diff_count(row, entry):
        # Count how many fields differ between row and entry (only keys in entry)
        return sum(1 for k in entry if row.get(k) != entry[k])

    existing_rows = list(getattr(parent, table_fieldname))
    # Shallow copy existing rows to track unmatched rows separately,
    # so we can remove matched rows as we process them without
    # altering the original list of child rows.
    existing_rows_unmatched = existing_rows[:]

    new_entries_unmatched = []  # New entries without exact match yet

    # Step 1: Match rows exactly by match_keys
    for entry in new_data:
        match = None
        for row in existing_rows_unmatched:
            if is_exact_match(row, entry):
                match = row
                break
        if match:
            # Update only differing fields to minimize version noise
            for field, value in entry.items():
                if match.get(field) != value:
                    match.set(field, value)
            existing_rows_unmatched.remove(match)
        else:
            new_entries_unmatched.append(entry)

    # Step 2: For unmatched new entries, find the closest existing row by minimal difference
    for entry in new_entries_unmatched:
        best_match = None
        best_score = float('inf')
        for row in existing_rows_unmatched:
            score = diff_count(row, entry)
            if score < best_score:
                best_score = score
                best_match = row

        if best_match:
            # Update the closest existing row in place
            for field, value in entry.items():
                if best_match.get(field) != value:
                    best_match.set(field, value)
            existing_rows_unmatched.remove(best_match)
        else:
            # No suitable existing row; append a new one
            parent.append(table_fieldname, deepcopy(entry))

    # Step 3: Remove any leftover existing rows that were not matched
    for row in existing_rows_unmatched:
        parent.get(table_fieldname).remove(row)


def create_update_contact_doc(contact_data):
    """
    Update or create a contact record. If no first_name is provided, set it to "-".

    Note: Does not initialize the status "Open", in contrast to the update_customer function.
    This, to differentiate between contacts originating from punchout orders and conventional registrations.
    """
    person_id = contact_data.get('name')
    if not person_id:
        return None

    first_name = contact_data.get('first_name') or "-"

    # Check if contact exists
    if not frappe.db.exists("Contact", person_id):
        print(f"Creating contact {person_id}...")
        frappe.db.sql(
            """INSERT INTO `tabContact` (`name`, `first_name`) VALUES (%s, %s)""",
            (person_id, first_name)
        )
    contact = frappe.get_doc("Contact", person_id)

    # Name fields
    contact.first_name = first_name
    contact.last_name = contact_data.get('last_name')
    contact.full_name = f"{contact.first_name}{' ' if contact.last_name else ''}{contact.last_name or ''}"

    # Optional fields
    for field in ['status', 'institute', 'department', 'institute_key', 'group_leader', 'address', 'room', 'has_webshop_account', 'punchout_identifier', 'salutation']:
        if field in contact_data:
            setattr(contact, field, contact_data[field])  # built-in Python function, no import needed

    if 'title' in contact_data:
        contact.designation = contact_data['title']

    if 'source' in contact_data:
        contact.contact_source = contact_data.get('source')

    # Newsletter preferences
    newsletter_state = contact_data.get('newsletter_registration_state', "")
    contact.receive_newsletter = newsletter_state if newsletter_state in ["registered", "unregistered", "pending", "bounced"] else ""

    if 'newsletter_registration_date' in contact_data:
        contact.subscribe_date = parse_date(contact_data['newsletter_registration_date'])

    if 'newsletter_unregistration_date' in contact_data:
        contact.unsubscribe_date = parse_date(contact_data['newsletter_unregistration_date'])

    contact.unsubscribed = 0 if contact_data.get('receive_updates_per_email') == "Mailing" else 1

    # Email
    emails = []
    if contact_data.get("email"):
        emails.append({"email_id": contact_data.get("email"), "is_primary": 1})
    if contact_data.get("email_cc"):
        emails.append({"email_id": contact_data.get("email_cc"), "is_primary": 0})
    update_child_table(contact, "email_ids", emails, match_keys=["email_id", "is_primary"])

    # Phone
    phones = []
    if contact_data.get("phone_number"):
        full_number = f"{contact_data.get('phone_country', '')} {contact_data.get('phone_number')}".strip()
        phones.append({"phone": full_number, "is_primary_phone": 1})
    update_child_table(contact, "phone_nos", phones, match_keys=["phone", "is_primary_phone"])

    # Link to Customer
    links = []
    if contact_data.get("customer_id") or contact_data.get("customer"):
        links.append({
            "link_doctype": "Customer",
            "link_name": contact_data.get("customer_id") or contact_data.get("customer")
        })
    update_child_table(contact, "links", links, match_keys=["link_doctype", "link_name"])

    # Set/Override address if contact_address exists
    contact_address = contact_data.get('contact_address')
    if contact_address and frappe.db.exists("Address", contact_address):
        contact.address = contact_address

    try:
        contact.save(ignore_permissions=True)
        return contact.name
    except Exception as err:
        msg = f"Failed to save contact: {err}"
        print(msg)
        frappe.log_error(msg)
        return None


def robust_get_country(country_name_or_code):
    """
    Robust country finder: accepts country name or ISO code.
    Falls back to system default if not found.
    """
    if frappe.db.exists("Country", country_name_or_code):
        return country_name_or_code

    # Try ISO code lookup (case-insensitive)
    code = (country_name_or_code or "").strip().lower()
    countries = frappe.get_all("Country", filters={'code': code}, fields=['name'], limit=1)

    if countries:
        return countries[0]['name']

    # Fallback to global default
    return frappe.defaults.get_global_default('country')


def create_update_address_doc(address_data, is_deleted=False, customer_id=None):
    """
    Processes data to update an address record.
    """
    address_id = address_data.get('name')
    address_line1 = address_data.get('address_line1')

    if not address_id or not address_line1:
        return None

    # Insert address if not exists
    if not frappe.db.exists("Address", address_id):
        print(f"Creating address {address_id}...")
        frappe.db.sql("""
            INSERT INTO `tabAddress` (`name`, `address_line1`)
            VALUES (%s, %s)
        """, (address_id, address_line1))

    print(f"Updating address {address_id}...")

    address = frappe.get_doc("Address", address_id)

    # Set address title
    customer_name = address_data.get('customer_name')
    if customer_name and address_line1:
        address.address_title = f"{customer_name} - {address_line1}"

    # Set fields
    for field in ['overwrite_company', 'address_line1', 'address_line2', 'pincode', 'city', 'customer_address_id']:
        if field in address_data:
            setattr(address, field, address_data[field])

    if 'source' in address_data:
        address.address_source = address_data.get('source')

    # Set country via helper
    if 'country' in address_data:
        address.country = robust_get_country(address_data['country'])

    # Link to customer
    if customer_id or 'customer_id' in address_data:
        address.links = []
        if not is_deleted:
            address.append("links", {
                'link_doctype': "Customer",
                'link_name': customer_id or address_data['customer_id']
            })

    # Determine address type
    address_type = address_data.get('address_type')
    if address_type in ("INV", "Billing"):
        address.is_primary_address = 1
        address.is_shipping_address = 0
        address.address_type = "Billing"
    else:
        address.is_primary_address = 0
        address.is_shipping_address = 1
        address.address_type = "Shipping"

    # Allow overrides if explicitly provided
    if 'is_primary_address' in address_data:
        address.is_primary_address = address_data['is_primary_address']
    if 'is_shipping_address' in address_data:
        address.is_shipping_address = address_data['is_shipping_address']

    try:
        address.save(ignore_permissions=True)
        return address.name
    except Exception as err:
        msg = f"Failed to save address: {err}"
        print(msg)
        frappe.log_error(msg)
        return None


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
                    VALUES (%s, %s, %s, %s, %s, %s);"""
    frappe.db.sql(customer_query, (
        user_data['customer']['name'],
        user_data['customer']['customer_name'],
        default_company,
        frappe.get_value("Country", country, "default_currency"),
        frappe.get_value("Country", country, "default_pricelist"),
        frappe.get_value("Company", default_company, "payment_terms")
    ))

    customer = frappe.get_doc("Customer", user_data['customer']['name'])

    # Create addresses
    for address in user_data['addresses']:
        address['customer_id'] = customer.name
        create_update_address_doc(address)

    # Create contact
    user_data['contact']['customer_id'] = customer.name
    user_data['contact']['status'] = "Open"
    user_data['contact']['has_webshop_account'] = 1
    contact_name = create_update_contact_doc(user_data['contact'])

    # Create Contact Lock
    lock_contact_by_name(contact_name)

    # Create invoice contact
    user_data['invoice_contact']['customer_id'] = customer.name
    user_data['invoice_contact']['status'] = "Open"
    invoice_contact_name = create_update_contact_doc(user_data['invoice_contact'])

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

    # create a new Webshop Address
    initialize_webshop_address_doc(contact_name, contact_name, invoice_contact_name)

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
def create_update_contact(contact):
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
    contact_name = create_update_contact_doc(contact)
    lock_contact_by_name(contact_name)

    if contact.get('source') == "Registration" or contact.get('contact_source') == "Registration":
        billing_contact = frappe.get_value("Customer", contact.get('customer_id'), "invoice_to")
        if not billing_contact:
            frappe.throw(f"Customer '{contact.get('customer_id')}' has no 'Invoice to' contact.")
        initialize_webshop_address_doc(contact_name, contact_name, billing_contact)

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
    if not 'person_id' in address and not 'name' in address:
        return {'success': False, 'message': "Person ID or Address ID is missing"}
    if not 'address_line1' in address:
        return {'success': False, 'message': "Address line 1 missing"}
    if not 'city' in address:
        return {'success': False, 'message': "City missing"}

    if 'person_id' in address:
        if 'name' in address and address.get('name') is not None:
            if address.get('name') != address.get('person_id'):
                return {'success': False, 'message': f"{address.get('name')=} does not match {address.get('person_id')=}"}
        address['name'] = address.get('person_id')

    address_id = create_update_address_doc(address)
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
              AND `tabDynamic Link`.`link_name` = %s
              AND (`tabAddress`.`is_primary_address` = 1
                   OR `tabAddress`.`name` = %s
                   OR `tabAddress`.`name` = %s)
            ;""", (customer_id, person_id, contact.address), as_dict=True)

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
              AND `tabDynamic Link`.`link_name` = %s
              AND `tabAddress`.`is_primary_address` = 1
            ;""", (customer_id,), as_dict=True)

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
        WHERE `tabContact`.`first_name` = %s"""
    params = [first_name]

    # Note: These statements need the "is not None" term. Simplification to only "contact['...']" will corrupt the API.
    if 'last_name' in contact and contact['last_name'] is not None:
        sql_query += """ AND `tabContact`.`last_name` = %s """
        params.append(contact['last_name'])

    if 'customer_id' in contact and contact['customer_id'] is not None:
        sql_query += """ AND `tabDynamic Link`.`link_name` = %s """
        params.append(contact['customer_id'])

    # TODO check name of email field for interface
    if 'email_id' in contact and contact['email_id'] is not None:
        sql_query += """ AND `tabContact`.`email_id` = %s """
        params.append(contact['email_id'])

    if 'department' in contact and contact['department'] is not None:
        sql_query += """ AND `tabContact`.`department` = %s """
        params.append(contact['department'])

    if 'institute' in contact and contact['institute'] is not None:
        sql_query += """ AND `tabContact`.`institute` = %s """
        params.append(contact['institute'])

    if 'room' in contact and contact['room'] is not None:
        sql_query += """ AND `tabContact`.`room` = %s """
        params.append(contact['room'])

    contacts = frappe.db.sql(sql_query, params, as_dict=True)

    if len(contacts) > 0:
        return {'success': True, 'message': "OK", 'contacts': contacts}
    else:
        return {'success': False, 'message': "Contact not found"}


@frappe.whitelist()
def address_exists(address):
    """
    Checks if an address record exists
    """
    if type(address) == str:
        address = json.loads(address)
    sql_query = """SELECT
            `tabAddress`.`name` AS `address_id`,
            `tabAddress`.`name` AS `person_id`,
            `tabDynamic Link`.`link_name` AS `customer_id`
        FROM `tabAddress`
        LEFT JOIN `tabDynamic Link` ON
            `tabDynamic Link`.`parent` = `tabAddress`.`name`
            AND `tabDynamic Link`.`parenttype` = "Address"
            AND `tabDynamic Link`.`link_doctype` = "Customer"
        WHERE `address_line1` LIKE %s
            AND `tabAddress`.`disabled` = 0"""
    params = [address['address_line1'] if 'address_line1' in address else "%"]
    # Note: These statements need the "is not None" term. Simplification to only "contact['...']" will corrupt the API.
    if 'address_line2' in address:
        if address['address_line2'] is not None:
            sql_query += """ AND `address_line2` = %s """
            params.append(address['address_line2'])
        else:
            sql_query += """ AND `address_line2` IS NULL """
    if 'customer_id' in address and address['customer_id'] is not None:
        sql_query += """ AND `tabDynamic Link`.`link_name` = %s """
        params.append(address['customer_id'])
    if 'overwrite_company' in address:
        if address['overwrite_company'] is not None:
            sql_query += """ AND `overwrite_company` = %s """
            params.append(address['overwrite_company'])
        else:
            sql_query += """ AND `overwrite_company` IS NULL """
    if 'pincode' in address:
        sql_query += """ AND `pincode` = %s """
        params.append(address['pincode'])
    if 'city' in address:
        sql_query += """ AND `city` = %s """
        params.append(address['city'])
    if 'country' in address:
        sql_query += """ AND `country` = %s """
        params.append(address['country'])
    if 'address_type' in address and address['address_type'] is not None:
        sql_query += """ AND `address_type` = %s """
        params.append(address['address_type'])
    sql_query += """ ORDER BY `tabAddress`.`creation` """
    addresses = frappe.db.sql(sql_query, params, as_dict=True)

    if len(addresses) > 0:
        return {'success': True, 'message': "OK", 'addresses': addresses}
    else:
        return {'success': False, 'message': "Address not found or disabled."}


@frappe.whitelist(allow_guest=False)
def request_quote(content, client="webshop"):
    """
    Request quote will create a new Oligo quote (and open the required oligos, if provided)
    """
    # prepare parameters
    if isinstance(content, str):
        content = json.loads(content)
    # validate input
    required_keys = ['customer', 'delivery_address', 'invoice_address', 'contact']
    missing = [k for k in required_keys if not content.get(k)]
    if missing:
        return {'success': False, 'message': f"Missing required fields: {', '.join(missing)}"}

    if not frappe.db.exists("Customer", content['customer']):
        return {'success': False, 'message': "Customer not found", 'reference': None}
    customer_doc = frappe.get_doc("Customer", content['customer'])

    if "company" in content:
        if has_webshop_service(content['customer'], "InvoiceByDefaultCompany"):
            if not customer_doc.default_company:
                return {'success': False, 'message': f"The provided customer {content['customer']} has InvoiceByDefaultCompany but no default_company.", 'reference': None}
            if content["company"] != customer_doc.default_company:
                return {'success': False, 'message': f"The given company {content['company']} does not match the determined company {customer_doc.default_company}.", 'reference': None}
        else:
            if content['company'] != 'Microsynth AG':
                return {'success': False,
                        'message': f"The provided customer {content['customer']} has not InvoiceByDefaultCompany but the provided company {content['company']} differs from 'Microsynth AG'.",
                        'reference': None}
        company = content['company']
    else:
        if has_webshop_service(content['customer'], "InvoiceByDefaultCompany"):
            if not customer_doc.default_company:
                return {'success': False, 'message': f"The provided customer {content['customer']} has InvoiceByDefaultCompany but no default_company.", 'reference': None}
            company = customer_doc.default_company
        else:
            company = "Microsynth AG"

    # create quotation
    transaction_date = date.today()
    qtn_doc = frappe.get_doc({
        'doctype': "Quotation",
        'quotation_to': "Customer",
        'company': company,
        'party_name': content['customer'],
        'product_type': "Oligos" if content.get('oligos') else None,
        'customer_address': content['invoice_address'],
        'shipping_address_name': content['delivery_address'],
        'contact_person': content['contact'],
        'contact_display': frappe.get_value("Contact", content['contact'], "full_name"),
        'territory': customer_doc.territory,
        'customer_request': content['customer_request'],
        'currency': customer_doc.default_currency,
        'selling_price_list': customer_doc.default_price_list,
        'transaction_date': transaction_date,
        'valid_till': transaction_date + timedelta(days=90),
        'sales_manager': customer_doc.account_manager
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
    if not express_shipping:
        frappe.log_error(f"Found no express shipping item for Customer {content['customer']} and Country {shipping_address.country} in currency {customer_doc.default_currency}.", "webshop.request_quote")
        shipping_items = get_contact_shipping_items(content['shipping_contact'] or content['contact'])
        for item in shipping_items:
            if item.get('preferred_express'):
                express_shipping = item
                break
    #     if shipping_items and not express_shipping:
    #         express_shipping = shipping_items[0]
    #     elif not express_shipping:
    #         frappe.throw("Unable to fetch an express_shipping item.")
    # if express_shipping:
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
        qtn_doc.insert()
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
        msg = f"Failed to create quotation for account {content['contact']}: {err}. Check ERP Error Log for details."
        frappe.log_error(f"{msg}\n\n\n{traceback.format_exc()}", "webshop.request_quote")
        return {'success': False, 'message': msg, 'reference': None}


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
            WHERE (`tabQuotation`.`contact_person` = %s
            OR (`tabQuotation`.`party_name` = %s and `tabQuotation`.`customer_web_access` = 1 ) )
            AND `tabQuotation`.`docstatus` = 1
            AND `tabQuotation`.`status` <> 'Lost'
            AND (`tabQuotation`.`valid_till` >= CURDATE() OR `tabQuotation`.`valid_till` IS NULL)
            ORDER BY `tabQuotation`.`name` DESC, `tabQuotation Item`.`idx` ASC;"""
        qtns = frappe.db.sql(query, (contact, customer_name), as_dict=True)

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
            msg = f"Error getting item prices for customer {content['customer']}: {err}. Check ERP Error Log for details."
            frappe.log_error(f"{msg}\n\n\n{traceback.format_exc()}", "webshop.get_item_prices")
            return {'success': False, 'message': msg, 'quotation': None}
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

    invoice_to = content['invoice_contact'] if 'invoice_contact' in content else None
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
                invoice_to = customer.invoice_to

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
        'invoice_to': invoice_to,
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
        'hold_order': True if 'comment' in content and content['comment'] != None and content['comment'] != "" else None,
        'hold_invoice': True if (not content.get('po_no') and 'Pasteur' in customer.customer_name) else None
        })
    if 'product_type' in content:
        so_doc.product_type = content['product_type']
    if 'credit_accounts' in content:
        for ca in content['credit_accounts']:
            ca_doc = frappe.get_doc("Credit Account", ca)
            if ca_doc.expiry_date and ca_doc.expiry_date < date.today():
                return {'success': False, 'message': f"Credit Account '{ca_doc.name}' is expired.", 'reference': None}
            if ca_doc.status != "Active":
                return {'success': False, 'message': f"Credit Account '{ca_doc.name}' is not Active.", 'reference': None}
            so_doc.append('credit_accounts', {
                'credit_account': ca_doc.name
            })
            # set has_transaction on Credit Account
            if not ca_doc.has_transactions:
                ca_doc.has_transactions = 1
                ca_doc.save()
    else:
        # check for Legacy Credit Accounts with matching Customer, Company and Product Type != Project
        legacy_credit_accounts = frappe.get_all('Credit Account',
            filters={
                'customer': customer.name,
                'company': company,
                'account_type': 'Legacy',
                'status': 'Active'
            },
            fields=['name']
        )
        applicable_legacy_credit_accounts = []
        for account in legacy_credit_accounts:
            # Fetch product types from child table "Product Type Link"
            product_type_rows = frappe.get_all(
                'Product Type Link',
                filters={
                    'parent': account.name,
                    'parenttype': 'Credit Account',
                    'parentfield': 'product_types'
                },
                fields=['product_type']
            )
            product_types = [r['product_type'] for r in product_type_rows]

            # If Legacy Credit Account has no product types, consider it as applicable to all Sales Orders
            if not product_types:
                applicable_legacy_credit_accounts.append(account.name)
                continue

            if so_doc.product_type == 'Project':
                if 'Project' in product_types:
                    applicable_legacy_credit_accounts.append(account.name)
            else:
                if 'Project' not in product_types:
                    applicable_legacy_credit_accounts.append(account.name)

        if len(applicable_legacy_credit_accounts) > 1:
            frappe.log_error(f"WARNING: Found {len(applicable_legacy_credit_accounts)} applicable legacy credit accounts "
                             f"for Customer {customer.name}, Company {company} and product type {so_doc.product_type}, "
                             f"going to add them all on Sales Order {so_doc.name}: {applicable_legacy_credit_accounts}",
                             "webshop.place_order")
        for alca in applicable_legacy_credit_accounts:
            so_doc.append('credit_accounts', {
                'credit_account': alca
            })
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
    if taxes and taxes != so_doc.taxes_and_charges:
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
        msg = f"Error placing order {content['web_order_id'] if 'web_order_id' in content else None} for account {contact.name}: {err}. Check ERP Error Log for details."
        frappe.log_error(f"{msg}\n\n\n{traceback.format_exc()}", "webshop.place_order")
        return {'success': False, 'message': msg, 'reference': None}

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
        msg = f"Error placing order {content['web_order_id'] if 'web_order_id' in content else None} for account {contact.name}: {err}. Check ERP Error Log for details."
        frappe.log_error(f"{msg}\n\n\n{traceback.format_exc()}", "webshop.place_order")
        return {'success': False, 'message': msg, 'reference': None}


def place_dropship_order(sales_order, intercompany_customer_name, supplier_company):
    """
    Create a dropship order for the given sales order.

    bench execute "microsynth.microsynth.webshop.place_dropship_order" --kwargs "{'sales_order': 'SO-LYO-25001085', 'intercompany_customer_name': '37595596', 'supplier_company': 'Microsynth AG'}"
    """
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
        frappe.log_error(f"{err}\n\n{customer}\n{supplier_company}\n{sales_order}\n\n{traceback.format_exc()}", "webshop.place_dropship_order")

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
        msg = f"Error creating Sales Order for Quotation {quotation_id}: {err}. Check ERP Error Log for details."
        frappe.log_error(f"{msg}\n\n\n{traceback.format_exc()}", "webshop.order_quote")
        return {'success': False, 'message': msg, 'reference': None}
    else:
        return {'success': True, 'message': None, 'reference': sales_order.name}


@frappe.whitelist()
def get_countries(client="webshop"):
    """
    Returns all available countries

    bench execute microsynth.microsynth.webshop.get_countries
    """
    top_country_names = ['Switzerland', 'Germany', 'Austria', 'France']
    countries = frappe.db.sql(
        """SELECT `country_name`, `code`, `export_code`, `default_currency`
           FROM `tabCountry`
           WHERE `disabled` = 0
           ORDER BY `country_name` ASC;""", as_dict=True)
    filtered_countries = []
    top_countries = []
    for top_country in top_country_names:
        for country in countries:
            if top_country == country.get('country_name'):
                top_countries.append(country)

    for country in countries:
        if country.get('country_name') not in top_country_names:
            filtered_countries.append(country)

    countries = top_countries + filtered_countries

    for i, c in enumerate(countries):
        c['sort_order'] = i + 1

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
                `tabShipping Item`.`currency`,
                `tabShipping Item`.`preferred_express`
            FROM `tabShipping Item`
            LEFT JOIN `tabItem` ON `tabItem`.`name` = `tabShipping Item`.`item`
            WHERE `tabShipping Item`.`parent` = %s
                AND `tabShipping Item`.`parenttype` = "Customer"
                AND `tabItem`.`disabled` = 0
            ORDER BY `tabShipping Item`.`idx` ASC;""", (str(customer_id),), as_dict=True)
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
                `tabShipping Item`.`currency`,
                `tabShipping Item`.`preferred_express`
        FROM `tabShipping Item`
        LEFT JOIN `tabItem` ON `tabItem`.`item_code` = `tabShipping Item`.`item`
        WHERE `tabShipping Item`.`parent` = %s
            AND `tabShipping Item`.`parenttype` = "Country"
            AND `tabItem`.`disabled` = 0
        ORDER BY `tabShipping Item`.`idx` ASC;""", (country,), as_dict=True)

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
    customer_currency = frappe.get_value("Customer", customer_id, 'default_currency')
    # find by customer id
    if customer_id:
        shipping_items = frappe.db.sql("""
            SELECT `tabShipping Item`.`item`,
                `tabItem`.`item_name`,
                `tabShipping Item`.`qty`,
                `tabShipping Item`.`rate`,
                `tabShipping Item`.`threshold`,
                `tabShipping Item`.`currency`,
                `tabShipping Item`.`preferred_express`
            FROM `tabShipping Item`
            LEFT JOIN `tabItem` ON `tabItem`.`name` = `tabShipping Item`.`item`
            WHERE `tabShipping Item`.`parent` = %s
                AND `tabShipping Item`.`parenttype` = "Customer"
                AND `tabItem`.`disabled` = 0
            ORDER BY `tabShipping Item`.`idx` ASC;""", (customer_id,), as_dict=True)
        if len(shipping_items) > 0:
            return {'success': True, 'message': "OK", 'currency': customer_currency, 'shipping_items': shipping_items}
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
        """SELECT `tabShipping Item`.`item`,
                `tabItem`.`item_name`,
                `tabShipping Item`.`qty`,
                `tabShipping Item`.`rate`,
                `tabShipping Item`.`threshold`,
                `tabShipping Item`.`currency`,
                `tabShipping Item`.`preferred_express`
            FROM `tabShipping Item`
            LEFT JOIN `tabItem` ON `tabItem`.`item_code` = `tabShipping Item`.`item`
            WHERE `tabShipping Item`.`parent` = %s
                AND `tabShipping Item`.`parenttype` = "Country"
                AND `tabItem`.`disabled` = 0
                AND (`tabShipping Item`.`currency` = %s OR `tabShipping Item`.`currency` IS NULL)
            ORDER BY `tabShipping Item`.`idx` ASC;""", (country, customer_currency), as_dict=True)
    if len(shipping_items) > 0:
        return {'success': True, 'message': "OK", 'currency': customer_currency, 'shipping_items': shipping_items}
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
            msg = f"Error updating newsletter state for {person_id}: {err}. Check ERP Error Log for details."
            frappe.log_error(f"{msg}\n\n\n{traceback.format_exc()}", "webshop.update_newsletter_state")
            return {'success': False, 'message': msg}
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
            msg = f"Error updating punchout details for {person_id}: {err}. Check ERP Error Log for details."
            frappe.log_error(f"{msg}\n\n\n{traceback.format_exc()}", "webshop.update_punchout_details")
            return {'success': False, 'message': msg}
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
            msg = f"Error updating GPS data for {person_id}: {err}. Check ERP Error Log for details."
            frappe.log_error(f"{msg}\n\n\n{traceback.format_exc()}", "webshop.update_address_gps")
            return {'success': False, 'message': msg}
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
        msg = f"Error creating Sales Invoice for Sales Order {sales_order}: {err}. Check ERP Error Log."
        frappe.log_error(f"{msg}\n\n\n{traceback.format_exc()}", "webshop.create_payment")
        return {'success': False, 'message': msg}
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
        msg = f"Error creating Payment Entry for Sales Invoice {sinv.name} of Sales Order {sales_order}: {err}. Check ERP Error Log for details."
        frappe.log_error(f"{msg}\n\n\n{traceback.format_exc()}", "webshop.create_payment")
        return {'success': False, 'message': msg}
    frappe.db.commit()

    # remove hold flag
    so_doc = frappe.get_doc("Sales Order", sales_order)
    so_doc.hold_order = 0
    try:
        so_doc.save()
    except Exception as err:
        msg = f"Error updating Sales Order {sales_order} after payment: {err}. Check ERP Error Log for details."
        frappe.log_error(f"{msg}\n\n\n{traceback.format_exc()}", "webshop.create_payment")
        return {'success': False, 'message': msg}
    frappe.db.commit()

    return {'success': True, 'message': "OK", 'reference': sinv.name}


### Label API


def get_sql_list(raw_list):
    if raw_list:
        return (','.join('"{0}"'.format(e) for e in raw_list))
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
        sql_query = """
            SELECT `item`,
                `label_id` AS `barcode`,
                `status`,
                `registered`,
                `contact`,
                `registered_to`
            FROM `tabSequencing Label`
            WHERE `status` = 'unused'
                AND `item` IN ({})
                AND `registered_to` IN ({})
            ;""".format(','.join(['%s'] * len(items)), ','.join(['%s'] * len(contacts)))
        labels = frappe.db.sql(sql_query, items + contacts, as_dict=True)
        return {'success': True, 'message': 'OK', 'labels': labels}
    except Exception as err:
        msg = f"Error fetching unused labels for contacts {contacts} and items {items}: {err}. Check ERP Error Log for details."
        frappe.log_error(f"{msg}\n\n\n{traceback.format_exc()}", "webshop.get_unused_labels")
        return {'success': False, 'message': msg, 'labels': None}


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
            for r in ranges:
                parts = r.split('-')
                start = int(parts[0].strip())
                end = int(parts[1].strip())
                ranges_to_return.append({
                    "item": label_range['item_code'],
                    "prefix": label_range['prefix'],
                    "barcode_start_range": start,
                    "barcode_end_range": end
                })
    except Exception as err:
        msg = f"Error fetching label ranges: {err}. Check ERP Error Log for details."
        frappe.log_error(f"{msg}\n\n\n{traceback.format_exc()}", "webshop.get_label_ranges")
        return {'success': False, 'message': msg, 'ranges': None}
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
    barcode_range = {
        'registered_to': sequencing_labels[0]['registered_to'],
        'item': sequencing_labels[0]['item'],
        'barcode_start_range': current_range_barcode,
        'barcode_end_range': current_range_barcode
    }
    for i, label in enumerate(sequencing_labels):
        if i == 0:
            continue  # do not consider the first label a second time
        if label['registered_to'] != barcode_range['registered_to'] or label['item'] != barcode_range['item'] or not is_next_barcode(current_range_barcode, label['barcode']):
            # finish current barcode_range
            barcode_range['barcode_end_range'] = current_range_barcode
            ranges.append(barcode_range)
            # start a new barcode_range
            barcode_range = {
                'registered_to': label['registered_to'],
                'item': label['item'],
                'barcode_start_range': label['barcode'],
                'barcode_end_range': label['barcode']
            }
        current_range_barcode = label['barcode']
    # finish last barcode_range
    barcode_range['barcode_end_range'] = current_range_barcode
    if not barcode_range in ranges:
        # add last barcode_range
        ranges.append(barcode_range)
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
        sql_query = """
            SELECT `item`,
                `label_id` AS `barcode`,
                `registered_to`
            FROM `tabSequencing Label`
            WHERE `status` = 'unused'
                AND `registered_to` IN ({})
            ORDER BY `label_id` ASC
            ;""".format(','.join(['%s'] * len(contacts)))
        sequencing_labels = frappe.db.sql(sql_query, contacts, as_dict=True)
        if len(sequencing_labels) == 0:
            return {'success': True, 'message': 'OK', 'ranges': []}
        ranges = partition_into_ranges(sequencing_labels)
        return {'success': True, 'message': 'OK', 'ranges': ranges}
    except Exception as err:
        msg = f"Error fetching registered label ranges for contacts {contacts}: {err}. Check ERP Error Log for details."
        frappe.log_error(f"{msg}\n\n\n{traceback.format_exc()}", "webshop.get_registered_label_ranges")
        return {'success': False, 'message': msg, 'ranges': None}


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
    for r in ranges:
        parts = r.split('-')
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
        item_condition = f"AND `item` = %s"
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
        WHERE `label_id` IN ({','.join(['%s'] * len(barcodes))})
            {item_condition}
        ;"""
    return frappe.db.sql(sql_query, barcodes + ([item] if item else []), as_dict=True)


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
        msg = f"Error registering labels for registered_to {registered_to}, item {item}, barcode_start_range {barcode_start_range}, barcode_end_range {barcode_end_range}: {err}. Check ERP Error Log for details."
        frappe.log_error(f"{msg}\n\n\n{traceback.format_exc()}", "webshop.register_labels")
        return {'success': False, 'message': msg, 'ranges': None}


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
        msg = f"Error unregistering labels for registered_to {registered_to}, item {item}, barcode_start_range {barcode_start_range}, barcode_end_range {barcode_end_range}: {err}. Check ERP Error Log for details."
        frappe.log_error(f"{msg}\n\n\n{traceback.format_exc()}", "webshop.unregister_labels")
        return {'success': False, 'message': msg}


@frappe.whitelist()
def set_label_submitted(labels):
    """
    Set the Status of the given Labels to submitted if they are unused and pass further tests.
    Try to submit as many labels as possible, return False if at least one given label could not be submitted

    bench execute microsynth.microsynth.webshop.set_label_submitted --kwargs "{'labels': [{'item': '6030', 'barcode': 'MY004450', 'status': 'unused'}, {'item': '6030', 'barcode': 'MY004449', 'status': 'unused'}]}"
    """
    return process_label_status_change(
        labels=labels,
        target_status="submitted",
        required_current_statuses=["unused"]
    )


@frappe.whitelist()
def set_label_unused(labels):
    """
    Set the Status of the given Labels to unused if they are all submitted and pass further tests.

    bench execute microsynth.microsynth.webshop.set_label_unused --kwargs "{'labels': [{'item': '6030', 'barcode': 'MY004450', 'status': 'submitted'}, {'item': '6030', 'barcode': 'MY004449', 'status': 'submitted'}]}"
    """
    return process_label_status_change(
        labels=labels,
        target_status="unused",
        required_current_statuses=["submitted"],
        check_not_used=True,
        stop_on_first_failure=True
    )


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
        msg = f"Error cancelling Sales Order '{sales_order}' with Web Order ID '{web_order_id}': {err}. Check ERP Error Log for details."
        frappe.log_error(f"{msg}\n\n\n{traceback.format_exc()}", "webshop.cancel_order")
        return {
            'success': False,
            'message': msg,
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
        msg = f"Error creating PDF for Quotation '{quotation_id}': {err}. Check ERP Error Log for details."
        frappe.log_error(f"{msg}\n\n\n{traceback.format_exc()}", "webshop.get_quotation_pdf")
        return {'success': False, 'message': msg, 'base64string': None}


def get_customer_dto(customer):
    customer_dto = {
        'name': customer.name,
        'customer_name': customer.customer_name,
        'tax_id': customer.tax_id,
        'disabled': customer.disabled
    }
    return customer_dto


def get_contact_dto(contact):
    #from microsynth.microsynth.utils import get_customer  # already imported

    # find the first non-primary if available
    cc_email = None
    if hasattr(contact, 'email_ids'):
        non_primary_emails = [e.email_id for e in contact.email_ids if not e.is_primary]
        cc_email = non_primary_emails[0] if non_primary_emails else None

    contact_dto = {
        'name': contact.name,
        'first_name': contact.first_name,
        'last_name': contact.last_name,
        'salutation': contact.salutation,
        'title': contact.designation,
        'institute': contact.institute,
        'department': contact.department,
        'room': contact.room,
        # 'group_leader': contact.group_leader,
        'email': contact.email_id,
        'email_cc': cc_email,
        'phone': contact.phone,
        'status': contact.status,
        'source': contact.contact_source,
        'address': contact.address,
        'customer': get_customer(contact.name)
    }
    return contact_dto


def get_address_dto(address):
    if not address:
        return None
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
        'geo_lat': address.geo_lat if address.geo_lat is not None else None,
        'geo_long': address.geo_long if address.geo_long != 0 else None
    }
    return address_dto


def get_webshop_address_objects(webshop_address_doc):
    webshop_addresses = []
    for a in webshop_address_doc.addresses:
        if a.disabled:
            continue

        contact = frappe.get_doc("Contact", a.contact)
        address = frappe.get_doc("Address", contact.address) if contact.address else None              #TODO handle Contacts without address. Check current implementation
        customer = frappe.get_doc("Customer", get_customer(contact.name))

        webshop_address = {
            'customer': customer,
            'contact': contact,
            'address': address,
            'is_default_shipping': to_bool(a.is_default_shipping),
            'is_default_billing': to_bool(a.is_default_billing)
        }
        webshop_addresses.append(webshop_address)
    return webshop_addresses


def get_webshop_address_dtos(webshop_addresses):
    webshop_address_dtos = []

    for a in webshop_addresses:
        webshop_address_dto = {
            'customer': get_customer_dto(a["customer"]),
            'contact': get_contact_dto(a["contact"]),
            'address': get_address_dto(a["address"]),
            'is_default_shipping': a["is_default_shipping"],
            'is_default_billing': a["is_default_billing"]
        }
        webshop_address_dtos.append(webshop_address_dto)
    return webshop_address_dtos


def get_webshop_address_dtos_from_doc(webshop_address_doc):
    webshop_address_objects = get_webshop_address_objects(webshop_address_doc)
    return get_webshop_address_dtos(webshop_address_objects)


@frappe.whitelist()
def get_webshop_addresses(webshop_account):
    """
    bench execute microsynth.microsynth.webshop.get_webshop_addresses --kwargs "{'webshop_account':'215856'}"
    """
    try:
        webshop_address_doc = frappe.get_doc("Webshop Address", webshop_account)

        return {
            'success': True,
            'message': "OK",
            'webshop_account': webshop_address_doc.name,
            'webshop_addresses': get_webshop_address_dtos_from_doc(webshop_address_doc),
        }
    except Exception as err:
        msg = f"Error getting webshop addresses for webshop_account '{webshop_account}': {err}. Check ERP Error Log for details."
        frappe.log_error(f"{msg}\n\n\n{traceback.format_exc()}", "webshop.get_webshop_addresses")
        return {
            'success': False,
            'message': msg,
            'webshop_account': webshop_account,
            'webshop_addresses': [],
        }


def validate_webshop_address(webshop_address):
    """
    Check webshop_address object for consistency.
    Throw an error in case of ID mismatch.
    """
    customer = webshop_address.get('customer')
    contact = webshop_address.get('contact')
    address = webshop_address.get('address')

    if customer.get('name') != contact.get('customer'):
        frappe.throw(f"Customer.name = '{customer.get('name')}', but Contact.customer = '{contact.get('customer')}'.")

    if address is not None and contact.get('address') != address.get('name'):
        frappe.throw(f"Contact.address = '{contact.get('address')}', but Address.name = '{address.get('name')}'.")

    if address is None and contact.get('address') is not None:
        frappe.throw(f"Contact.address = '{contact.get('address')}', but Address is NULL")

    if (webshop_address.get('is_default_shipping') or webshop_address.get('is_default_billing')) and address is None:
        frappe.throw(f"Cannot set missing address to default.")


def validate_contact_in_webshop_address_doc(webshop_address_doc, contact_id):
    """
    Ensure that the webshop addresses contain the given contact and that the contact is active (not disabled).
    """
    found = False
    for a in webshop_address_doc.addresses:
        if a.contact == contact_id:
            if a.disabled:
                frappe.throw(f"The given {contact_id=} is disabled for the webshop addresses of the webshop account '{webshop_address_doc.name}'.")
            found = True
            break
    if not found:
        frappe.throw(f"The given {contact_id=} is not part of the given webshop account '{webshop_address_doc.name}'.")


# def create_customer(webshop_address):
#     user_data = {
#         'customer': webshop_address['customer'],
#         'contact': webshop_address['contact'],
#         'addresses': [webshop_address['address']]
#     }
#     register_user(user_data)  # customer, contact, invoice_contact, shipping and billing address needed
    # consider usage of get_first_shipping_address regarding Customers without a Shipping Address:
    # It is assumed in utils.check_new_customers_taxid (executed daily), that every enabled Customer has a Shipping Address
    # Several functions called in configure_new_customer use utils.get_first_shipping_address
    # Enabled Customers without a Shipping Address are disabled every night


def create_contact(webshop_address):
    """
    Use a webshop address to create a contact with the create_update_contact_doc function.
    """

    validate_webshop_address(webshop_address)

    contact = webshop_address['contact']
    contact['customer_id'] = webshop_address.get('customer').get('name')
    contact['address'] = webshop_address.get('address').get('name') if webshop_address.get('address') else None
    contact['status'] = "Passive"
    contact['phone_number'] = contact.get('phone')
    contact_id = create_update_contact_doc(contact)
    # create Contact Lock
    lock_contact_by_name(contact_id)
    return contact_id


def create_address(webshop_address):
    """
    Use a webshop address to create an address with the create_update_address_doc function. Returns None if the Webshop Address does not contain an address.
    """
    address = webshop_address['address']
    if frappe.db.exists('Address', address['name']):
        frappe.throw(f"There exists already an Address with the given name '{address['name']}'. Not going to create a new one.")
    address['customer_id'] = webshop_address.get('customer').get('name')
    address_id = create_update_address_doc(address)

    if not address_id:
        frappe.throw(f'Unable to create an Address with the given {webshop_address=}')
    # check if address_id matches the one in webshop_address
    if address_id != webshop_address.get('address').get('name'):
        frappe.throw(f"Created Address '{address_id}', but different from Address.name = '{webshop_address.get('address').get('name')}' of the given webshop_address.")
    return address_id


@frappe.whitelist()
def create_webshop_address(webshop_account, webshop_address):
    try:
        if type(webshop_address) == str:
            webshop_address = json.loads(webshop_address)

        validate_webshop_address(webshop_address)
        webshop_address_doc = frappe.get_doc("Webshop Address", webshop_account)

        if webshop_address['address']['address_type'] == 'Shipping':
            webshop_account_customer = get_customer(webshop_account)
            if webshop_account_customer != webshop_address['customer']['name']:
                frappe.throw(f"Customer of Contact {webshop_account} ('{webshop_account_customer}'), but Customer.name = '{webshop_address['customer']['name']}'.")

        elif webshop_address['address']['address_type'] == 'Billing':
            raise NotImplementedError("No implementation for Address Type Billing so far.")
        else:
            raise NotImplementedError(f"No implementation for Address Type '{webshop_address['address']['address_type']}'.")

        # create a new customer if it is different from the customer of webshop_account and the new webshop_address is a billing address
        # if webshop_address['customer']['name'] != webshop_account_customer and webshop_address['address']['address_type'] == 'Billing':
        #     create_customer(webshop_address)

        # Create an Address if it does not yet exist for the Customer
        webshop_address['address']['customer_id'] = webshop_address['customer'].get('name')
        address_exists_response = address_exists(webshop_address['address'])

        if address_exists_response.get('success'):
            address_id = address_exists_response.get('addresses')[0].get('address_id')
            webshop_address['contact']['address'] = address_id
            webshop_address['address']['name'] = address_id
            frappe.log_error(f"Webshop account {webshop_account}: Link existing Address: {address_id}\n{webshop_address['contact']['address']=}\n{webshop_address['address']['name']=}", "webshop.create_webshop_address")
        else:
            address_id = create_address(webshop_address)

        # create a Contact
        contact_id = create_contact(webshop_address)
        if not contact_id:
            frappe.throw(f'Unable to create a Contact with the given {webshop_address=}')
        # append a webshop_address entry with above contact id to webshop_addresses.addresses
        webshop_address_doc.append('addresses', {
            'contact': contact_id,
            'is_default_shipping': 0,
            'is_default_billing': 0,
            'disabled': 0
        })
        webshop_address_doc.save()
        webshop_address_dtos = get_webshop_address_dtos_from_doc(webshop_address_doc)

        return {
            'success': True,
            'message': "OK",
            'webshop_account': webshop_address_doc.name,
            'webshop_addresses': webshop_address_dtos,
        }
    except Exception as err:
        msg = f"Error creating webshop address with contact_id '{webshop_address['contact']['name']}' for webshop_account '{webshop_account}': {err}. Check ERP Error Log for details."
        frappe.log_error(f"{msg}\n\n\n{traceback.format_exc()}", "webshop.create_webshop_address")
        return {
            'success': False,
            'message': msg,
            'webshop_account': webshop_account,
            'webshop_addresses': [],
        }


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
    #print(linked_docs)
    return len(linked_docs) > 0


def is_contact_used(contact_id):
    """
    Check if the given Contact is used on one of the below DocTypes

    bench execute microsynth.microsynth.webshop.is_contact_used --kwargs "{'contact_id': '243482'}"
    """
    # linked_doctypes = {
    #     # 'Supplier Quotation': {'fieldname': ['contact_person']},
    #     'Quotation': {'fieldname': ['contact_person', 'shipping_contact']},
    #     'Customer': {'fieldname': ['customer_primary_contact', 'invoice_to', 'reminder_to']},
    #     'Sales Order': {'fieldname': ['contact_person', 'shipping_contact', 'invoice_to']},
    #     # 'Purchase Receipt': {'fieldname': ['contact_person']},
    #     # 'Delivery Note': {'fieldname': ['contact_person', 'shipping_contact', 'invoice_to']},
    #     # 'Purchase Invoice': {'fieldname': ['contact_person']},
    #     # 'Purchase Order': {'fieldname': ['contact_person', 'customer_contact_person']},
    #     'Sales Invoice': {'fieldname': ['contact_person', 'invoice_to', 'shipping_contact']},
    #     # 'Payment Entry': {'fieldname': ['contact_person']},
    #     # 'Product Idea': {'fieldname': ['contact_person']},
    #     # 'Benchmark': {'fieldname': ['contact_person']},
    #     # 'Standing Quotation': {'fieldname': ['contact']},
    #     # 'Contact Note': {'fieldname': ['contact_person']},
    #     # 'Sequencing Label': {'fieldname': ['contact', 'registered_to']},
    #     # 'Punchout Shop': {'fieldname': ['billing_contact']},
    #     # 'Analysis Report': {'fieldname': ['contact_person']},
    #     # 'Label Log': {'fieldname': ['contact', 'registered_to']}
    # }
    # linked_docs = get_linked_docs('Contact', contact_id, linked_doctypes)
    doctypes = {
        "Quotation": ["contact_person", "shipping_contact"],
        "Customer": ["customer_primary_contact", "invoice_to", "reminder_to"],
        "Sales Order": ["contact_person", "shipping_contact", "invoice_to"],
        "Sales Invoice": ["contact_person", "invoice_to", "shipping_contact"]
    }
    unions = []
    params = []

    for doctype, fields in doctypes.items():
        conditions = " OR ".join([f"`tab{doctype}`.`{field}` = %s" for field in fields])
        unions.append(f"""
            SELECT '{doctype}' AS doctype, `tab{doctype}`.`name`
            FROM `tab{doctype}`
            WHERE {conditions}
        """)
        params.extend([contact_id] * len(fields))

    sql_query = "\nUNION\n".join(unions)

    linked_docs = frappe.db.sql(sql_query, params, as_dict=True)
    return len(linked_docs) > 0


def is_address_used(address_id):
    """
    Check if the given Address is used on one of the below DocTypes

    bench execute microsynth.microsynth.webshop.is_address_used --kwargs "{'address_id': '215856'}"
    """
    # linked_doctypes = {
    #     # 'Supplier Quotation': {'fieldname': ['supplier_address']},
    #     'Quotation': {'fieldname': ['customer_address', 'shipping_address_name']},
    #     # 'Customer': {'fieldname': ['customer_primary_address']},
    #     'Sales Order': {'fieldname': ['customer_address', 'shipping_address_name', 'company_address']},
    #     # 'Purchase Receipt': {'fieldname': ['shipping_address', 'supplier_address']},
    #     # 'Delivery Note': {'fieldname': ['customer_address', 'company_address', 'shipping_address_name']},
    #     # 'Purchase Invoice': {'fieldname': ['shipping_address', 'supplier_address']},
    #     # 'Purchase Order': {'fieldname': ['shipping_address', 'supplier_address']},
    #     'Sales Invoice': {'fieldname': ['customer_address', 'company_address', 'shipping_address_name']},
    #     # 'Standing Quotation': {'fieldname': ['address']},
    #     # 'Punchout Shop': {'fieldname': ['billing_address']},
    #     # 'Analysis Report': {'fieldname': ['address']},
    #     # 'Customs Declaration': {'child_doctype': 'Customs Declaration Delivery Note', 'fieldname': ['shipping_address']}
    # }
    # linked_docs = get_linked_docs('Address', address_id, linked_doctypes)
    doctypes = {
        "Quotation": ["customer_address", "shipping_address_name"],
        "Sales Order": ["customer_address", "shipping_address_name", "company_address"],
        "Sales Invoice": ["customer_address", "shipping_address_name", "company_address"]
    }
    unions = []
    params = []

    for doctype, fields in doctypes.items():
        conditions = " OR ".join([f"`tab{doctype}`.`{field}` = %s" for field in fields])
        unions.append(f"""
            SELECT '{doctype}' AS doctype, `tab{doctype}`.`name`
            FROM `tab{doctype}`
            WHERE {conditions}
        """)
        params.extend([address_id] * len(fields))

    sql_query = "\nUNION\n".join(unions)

    linked_docs = frappe.db.sql(sql_query, params, as_dict=True)
    return len(linked_docs) > 0


def increase_version(name):
    """
    Takes an ID and increases the version assuming that name ends with -n if it already has version n+1.

    bench execute microsynth.microsynth.webshop.increase_version --kwargs "{'name': '215856'}"
    """
    if not '-' in name:
        return name + "-1"
    else:
        parts = name.split('-')
        if len(parts) != 2:
            msg = f"Unable to increase version of ID '{name}'. Most likely it contains more than one dash ('-')."
            frappe.log_error(msg, 'webshop.increase_version')
            frappe.throw(msg)
        try:
            version = int(parts[-1])
        except Exception as err:
            msg = f"Unable to increase version of ID '{name}'. The part after the last dash is not convertible to an integer ({err})."
            frappe.log_error(msg, 'webshop.increase_version')
            frappe.throw(msg)
        else:
            return parts[0] + '-' + str(version + 1)


def webshop_print_addresses_differ(webshop_address_1, webshop_address_2):
    """
    Check if two webshop addresses differ in their printed fields. Requires that both webshop_address_1 and webshop_address_2 belong to the same customer otherwhise throws an error.

    :param webshop_address_1: First webshop address to compare.
    :param webshop_address_2: Second webshop address to compare.
    :return: bool
        -------------
    Returns True if they differ, False otherwise.
    """
    if get_customer(webshop_address_1.get('contact').get('name')) != get_customer(webshop_address_2.get('contact').get('name')):
        frappe.throw(f"Contacts {webshop_address_1.get('contact').get('name')} and {webshop_address_2.get('contact').get('name')} do not belong to the same Customer.")
    if webshop_address_1 and not webshop_address_2:
        return True
    if not webshop_address_1 and webshop_address_2:
        return True
    contact_fields_to_check = [
        'first_name', 'last_name', 'salutation', 'designation', 'institute', 'department', 'room'
    ]
    for field in contact_fields_to_check:
        if webshop_address_1.get('contact').get(field) != webshop_address_2.get('contact').get(field):
            return True

    address_fields_to_check = [
        'overwrite_company', 'address_line1', 'address_line2',
        'pincode', 'city', 'country',
    ]
    for field in address_fields_to_check:
        if webshop_address_1.get('address').get(field) != webshop_address_2.get('address').get(field):
            return True

    return False


@frappe.whitelist()
def update_webshop_address(webshop_account, webshop_address):
    """
    bench execute microsynth.microsynth.webshop.update_webshop_address --kwargs "{'webshop_account': '215856', 'webshop_address': ''}"
    """
    try:
        if type(webshop_address) == str:
            webshop_address = json.loads(webshop_address)
        validate_webshop_address(webshop_address)

        webshop_address_doc = frappe.get_doc("Webshop Address", webshop_account)
        contact_id = webshop_address.get('contact').get('name')
        address_id = webshop_address.get('address').get('name') if webshop_address.get('address') is not None else None

        validate_contact_in_webshop_address_doc(webshop_address_doc, contact_id)

        if webshop_address.get('address') and webshop_address.get('address').get('address_type') == 'Billing':
            raise NotImplementedError("No implementation for Address Type Billing so far.")

        # check if the print fields of the webshop_address differ from the existing webshop_address in the webshop_address_doc
        for a in webshop_address_doc.addresses:
            if a.contact == contact_id:
                existing_contact = frappe.get_doc("Contact", contact_id)
                existing_address = frappe.get_doc("Address", existing_contact.address) if existing_contact.address else None

        if existing_contact is None:
            frappe.throw(f"Contact with ID '{contact_id}' not found in the ERP. Cannot update webshop address.")

        # Find out if we can update the existing Contact and Address or create a new one.
        update_existing_contact_address = False

        if existing_address is None:
            if existing_contact.has_webshop_account and existing_contact.punchout_identifier:
                if not is_contact_used(contact_id):
                    update_existing_contact_address = True
                else:
                    update_existing_contact_address = False
            else:
                # it's not a punchout webshop account
                if not webshop_address['address']:
                    frappe.throw(f"Contact '{contact_id}' has no Address and no address data was provided. Cannot update webshop address.")
                update_existing_contact_address = False
        else:
            existing_print_address = {
                'contact': get_contact_dto(existing_contact),
                'address': get_address_dto(existing_address)
            }
            if not webshop_print_addresses_differ(webshop_address, existing_print_address):
                # The new webshop_address resembles the existing webshop_address when printed.
                # So we can update the existing Contact and Address without creating a new one.
                update_existing_contact_address = True

            else:
                # The new webshop_address differs from the existing webshop_address when printed.
                if is_contact_used(contact_id) or (address_id is not None and is_address_used(address_id)):  # this will take very long  # TODO if we consolidate the addresses, the second condition might cause an issue
                    # The existing Contact or Address is used on other documents (Quotations, Sales Orders, Delivery Notes, Sales Invoices).
                    # So we need to create a new Contact and Address to maintain data integrity.
                    update_existing_contact_address = False
                else:
                    update_existing_contact_address = True

        # Update the webshop address.
        if update_existing_contact_address:
            # The new webshop_address does not differ from the existing webshop_address when printed or
            # the existing contact and address are not yet used on other documents (Quotations, Sales Orders, Delivery Notes, Sales Invoices).

            # Update the contact/address without creating a new one.
            if address_id:
                address = webshop_address['address']
                address_id = create_update_address_doc(address)
            contact = webshop_address['contact']
            contact['phone_number'] = contact.get('phone')
            contact['customer_id'] = contact.get('customer')
            contact_id = create_update_contact_doc(contact)
        else:
            # Contact and Address differ in their printed fields and were used previously, so we need to create a new Contact and Address.

            # Update the existing Contact for the non-printable fields (email, phone, etc.) as well.
            # This is in most cases the Contact of the webshop account but might change in the future.
            # The group leader is not updated here, because it is not part of the webshop_address['contact'] object
            updated_existing_contact = get_contact_dto(existing_contact)
            updated_existing_contact['phone'] = webshop_address['contact'].get('phone')
            updated_existing_contact['email'] = webshop_address['contact'].get('email')
            updated_existing_contact['email_cc'] = webshop_address['contact'].get('email_cc')

            create_update_contact_doc(updated_existing_contact)

            # create new contact/address if used to maintain data integrity on existing Sales Orders, Delivery Notes, Sales Invoices, etc.
            from copy import deepcopy
            new_contact_id = increase_version(webshop_address['contact']['name'])
            if address_id:
                new_address_id = increase_version(webshop_address['address']['name'])  # TODO do not create new a new address if there is already one
            else:
                new_address_id = None

            new_webshop_address = deepcopy(webshop_address)
            if new_address_id:
                new_webshop_address['address']['name'] = new_address_id
            new_webshop_address['contact']['name'] = new_contact_id
            new_webshop_address['contact']['address'] = new_address_id
            new_webshop_address['contact'].pop('group_leader', None)  # remove group leader, because it is not part of the webshop_address['contact'] object according to the specification
            # Do not remove phone, email, email_cc because they might be used on the new Contact (e.g. for the mail address of an invoice contact)
            validate_webshop_address(new_webshop_address)

            if new_webshop_address['address'] is not None:
                create_address(new_webshop_address)

            returned_contact_id = create_contact(new_webshop_address)
            if not returned_contact_id:
                frappe.throw(f'Unable to create a Contact with the given {webshop_address=}')

            for a in webshop_address_doc.addresses:
                if a.contact == contact_id:
                    # append the newly created webshop_address entry with the contact id to webshop_addresses.addresses
                    webshop_address_doc.append('addresses', {
                        'contact': returned_contact_id,
                        'is_default_shipping': a.is_default_shipping,
                        'is_default_billing': a.is_default_billing,
                        'disabled': 0
                    })
                    a.disabled = 1
                    a.is_default_shipping = 0
                    a.is_default_billing = 0

        webshop_address_doc.save()

        return {
            'success': True,
            'message': "OK",
            'webshop_account': webshop_address_doc.name,
            'webshop_addresses': get_webshop_address_dtos_from_doc(webshop_address_doc)
        }
    except Exception as err:
        msg = f"Error updating webshop address with contact_id '{webshop_address['contact']['name']}' for webshop_account '{webshop_account}': {err}. Check ERP Error Log for details."
        frappe.log_error(f"{msg}\n\n\n{traceback.format_exc()}", "webshop.update_webshop_address")
        return {
            'success': False,
            'message': msg,
            'webshop_account': webshop_account,
            'webshop_addresses': []
        }


def delete_if_unused(contact_id):
    """
    Delete the given Contact and its Address if both are unused.
    If both are unused, delete the Customer of the given Contact if it is unused too.
    """
    address_id = frappe.get_value('Contact', contact_id, 'address')
    customer_id = get_customer(contact_id)
    if not is_address_used(address_id) and not is_contact_used(contact_id):
        # TODO: Delete link of Contact in Webshop Address (otherwise Contact cannot be deleted)
        # remove Contact Lock
        frappe.db.sql("""DELETE FROM `tabContact Lock` WHERE `contact` = %s; """, (contact_id,))
        frappe.db.commit()
        contact_doc = frappe.get_doc('Contact', contact_id)
        contact_doc.delete()
        address_doc = frappe.get_doc('Address', address_id)
        address_doc.delete()  # TODO: Ensure that the Webshop has the permission to delete an Address
        frappe.db.commit()
    else:
        return
    if not is_customer_used(customer_id):
        customer_doc = frappe.get_doc('Customer', customer_id)
        customer_doc.delete()


@frappe.whitelist()
def delete_webshop_address(webshop_account, contact_id):
    """
    bench execute microsynth.microsynth.webshop.delete_webshop_address --kwargs "{'webshop_account':'215856', 'contact_id':'234007'}"
    """
    try:
        webshop_address_doc = frappe.get_doc("Webshop Address", webshop_account)

        validate_contact_in_webshop_address_doc(webshop_address_doc, contact_id)

        for a in webshop_address_doc.addresses:
            if a.contact == contact_id:
                if a.is_default_shipping:
                    frappe.throw(f"Cannot disable webshop address '{contact_id}' because it default shipping address.")
                if a.is_default_billing:
                    frappe.throw(f"Cannot disable webshop address '{contact_id}' because it default billing address.")
                a.disabled = True
                #a.delete()  # necessary in order to be able to delete the Contact

        webshop_address_doc.save()

        # trigger an async background job that checks if the Customer/Contact/Address was used on Quotations/Sales Orders/Delivery Notes/Sales Invoices before. if not, delete it.
        frappe.enqueue(method=delete_if_unused, queue='long', timeout=600, is_async=True, contact_id=contact_id)

        return {
            'success': True,
            'message': "OK",
            'webshop_account': webshop_address_doc.name,
            'webshop_addresses': get_webshop_address_dtos_from_doc(webshop_address_doc),
        }
    except Exception as err:
        msg = f"Error deleting webshop address with contact_id '{contact_id}' for webshop_account '{webshop_account}': {err}. Check ERP Error Log for details."
        frappe.log_error(f"{msg}\n\n\n{traceback.format_exc()}", "webshop.delete_webshop_address")
        return {
            'success': False,
            'message': msg,
            'webshop_account': webshop_account,
            'webshop_addresses': [],
        }


@frappe.whitelist()
def set_default_webshop_address(webshop_account, address_type, contact_id):
    try:
        webshop_address_doc = frappe.get_doc("Webshop Address", webshop_account)

        validate_contact_in_webshop_address_doc(webshop_address_doc, contact_id)

        if address_type == "Shipping":
            for a in webshop_address_doc.addresses:
                if a.contact == contact_id:
                    a.is_default_shipping = True
                else:
                    a.is_default_shipping = False

        elif address_type == "Billing":
            for a in webshop_address_doc.addresses:
                if a.contact == contact_id:
                    a.is_default_billing = True
                else:
                    a.is_default_billing = False

        else:
            frappe.throw(f"Invalid address_type '{address_type}'. Allowed is 'Shipping' and 'Billing'")

        webshop_address_doc.save()

        return {
            'success': True,
            'message': "OK",
            'webshop_account': webshop_address_doc.name,
            'webshop_addresses': get_webshop_address_dtos_from_doc(webshop_address_doc)
        }
    except Exception as err:
        msg = f"Error setting default webshop address for webshop_account '{webshop_account}' with contact_id '{contact_id}': {err}. Check ERP Error Log for details."
        frappe.log_error(f"{msg}\n\n\n{traceback.format_exc()}", "webshop.set_default_webshop_address")
        return {
            'success': False,
            'message': msg,
            'webshop_account': webshop_account,
            'webshop_addresses': [],
        }


def get_account_settings_dto(webshop_address):
    customer = webshop_address.get('customer')
    account_settings_dto = {
        'group_leader': webshop_address.get('contact').group_leader,
        'institute_key': webshop_address.get('contact').institute_key,
        'default_company': customer.default_company,
        'sales_manager': customer.account_manager,
        'invoicing_method': customer.invoicing_method,
        'po_required': to_bool(customer.po_required),
        'billing_address_readonly': to_bool(customer.webshop_address_readonly)
    }
    return account_settings_dto


@frappe.whitelist()
def get_account_details(webshop_account):
    """
    bench execute microsynth.microsynth.webshop.get_account_details --kwargs "{'webshop_account': '241884'}"
    """
    try:
        webshop_address_doc = frappe.get_doc("Webshop Address", webshop_account)
        webshop_addresses = get_webshop_address_objects(webshop_address_doc)
        webshop_address_dtos = get_webshop_address_dtos(webshop_addresses)

        for a in webshop_addresses:
            if a.get('contact').get('name').split('-')[0] == webshop_account:
                main_contact = a
                break

        if main_contact and main_contact.get('contact').get('status') == 'Disabled':
            msg = f"The Contact {main_contact.get('contact').get('name')} of the webshop account '{webshop_account}' is disabled."
            return {
                'success': False,
                'message': msg,
                'webshop_account': webshop_account,
                'currency': None,
                'shipping_items': [],
                'webshop_addresses': [],
                'webshop_services': []
            }
        if main_contact and main_contact.get('customer').disabled:
            msg = f"The Customer {main_contact.get('customer').get('name')} of the webshop account '{webshop_account}' is disabled."
            return {
                'success': False,
                'message': msg,
                'webshop_account': webshop_account,
                'currency': None,
                'shipping_items': [],
                'webshop_addresses': [],
                'webshop_services': []
            }

        services = []
        for s in main_contact.get('customer').webshop_service:
            services.append(s.webshop_service)

        shipping_items_response = get_contact_shipping_items(main_contact.get('contact').get('name'))
        if shipping_items_response.get('currency') != main_contact.get('customer').default_currency:
            if not shipping_items_response.get('currency'):
                msg = (
                    f"Found no Shipping Item with Currency {main_contact.get('customer').default_currency} "
                    f"for the Country of Contact <strong>{main_contact.get('contact').get('name')}</strong> "
                    f"of the Customer {main_contact.get('customer').get('name')}.<br> "
                    f"Please consider adding Shipping Items in Currency {main_contact.get('customer').default_currency} "
                    f"to the Country of Contact <strong>{main_contact.get('contact').get('name')}</strong>."
                )
            else:
                msg = (
                    f"The Currency of the Shipping Items ({shipping_items_response.get('currency')}) "
                    f"of the Country of Contact <strong>{main_contact.get('contact').get('name')}</strong> "
                    f"does not match the Billing Currency ({main_contact.get('customer').default_currency}) "
                    f"of the Customer {main_contact.get('customer').get('name')}.<br>"
                    f"Please consider to add Shipping Items to the Customer in the Customers Billing Currency."
                )
            email_template = frappe.get_doc("Email Template", "Shipping Items Currency Mismatch with Customers Billing Currency")
            rendered_content = frappe.render_template(email_template.response, {'details': msg})
            send_email_from_template(email_template, rendered_content)
            frappe.throw(msg)

        return {
            'success': True,
            'message': "OK",
            'webshop_account': webshop_address_doc.get('name'),
            'account_settings': get_account_settings_dto(main_contact),
            'currency': main_contact.get('customer').default_currency,
            'shipping_items': shipping_items_response.get('shipping_items'),
            'webshop_addresses': webshop_address_dtos,
            'webshop_services': services
        }
    except Exception as err:
        msg = f"Error getting account details for webshop_account '{webshop_account}': {err}. Check ERP Error Log for details."
        frappe.log_error(f"{msg}\n\n\n{traceback.format_exc()}", "webshop.get_account_details")
        return {
            'success': False,
            'message': msg,
            'webshop_account': webshop_account,
            'currency': None,
            'shipping_items': [],
            'webshop_addresses': [],
            'webshop_services': []
        }


@frappe.whitelist()
def update_account_settings(webshop_account, account_settings):
    """
    Webshop endpoint to update webshop account settings. Some fields are not allowed to be changed from the webshop. See code...

    bench execute microsynth.microsynth.webshop.update_account_settings --kwargs "{'webshop_account': '243755', 'account_settings': {'group_leader': 'me', 'institute_key': 'de_göt_06_05', 'invoicing_method': 'Post'}}"
    """
    try:
        if type(account_settings) == str:
            account_settings = json.loads(account_settings)

        contact_doc = frappe.get_doc("Contact", webshop_account)

        # prevent changes of Contact.institute_key
        if account_settings.get('institute_key') is not None and account_settings.get('institute_key') != contact_doc.institute_key:
            frappe.throw(f"Not allowed to change Institute Key of Contact {contact_doc.name} from '{contact_doc.institute_key}' to '{account_settings.get('institute_key')}'.")

        customer_id = get_customer(webshop_account)
        customer_doc = frappe.get_doc("Customer", customer_id)

        # Allow to change Customer.invoicing method only from Email to Post and back.
        # TODO Fix webshop to not try to save the invoicing method if it is not Email or Post (Task #20829)
        # TODO Remove hotfix line below
        if customer_doc.invoicing_method in ['Email', 'Post']:      # Hotfix: ignore all changes of the invoicing method if the customer has an invoicing method other than Email or Post.
            if customer_doc.invoicing_method != account_settings.get('invoicing_method'):
                if customer_doc.invoicing_method not in ['Email', 'Post']:
                    frappe.throw(f"Contact {webshop_account} belongs to Customer {customer_id} that has Invoicing Method {customer_doc.invoicing_method}.")
                if account_settings.get('invoicing_method') not in ['Email', 'Post']:
                    frappe.throw(f"Not allowed to change to Invoicing Method '{customer_doc.invoicing_method}'.")
                customer_doc.invoicing_method = account_settings.get('invoicing_method')
                customer_doc.save()

        # Allow changing Contact.group_leader
        if contact_doc.group_leader != account_settings.get('group_leader'):
            contact_doc.group_leader = account_settings.get('group_leader')
            contact_doc.save()

        return {
            'success': True,
            'message': "OK",
            'webshop_account': contact_doc.name,
            'account_settings': {
                'group_leader': contact_doc.group_leader,
                'institute_key': contact_doc.institute_key,
                'invoicing_method': customer_doc.invoicing_method
            }
        }
    except Exception as err:
        msg = f"Error updating account details for webshop_account '{webshop_account}': {err}. Check ERP Error Log for details."
        frappe.log_error(f"Unable to update account details for webshop_account '{webshop_account}'\n\n{traceback.format_exc()}", "webshop.update_account_settings")
        return {
            'success': False,
            'message': msg,
            'webshop_account': webshop_account,
            'account_settings': account_settings
        }


def change_default_billing_address(webshop_account_id, new_invoice_to_contact_id):
    """
    bench execute microsynth.microsynth.webshop.change_default_billing_address --kwargs "{'webshop_account_id': '243755', 'new_invoice_to_contact': '812881'}"
    """
    webshop_address_doc = frappe.get_doc("Webshop Address", webshop_account_id)

    found = False
    for row in webshop_address_doc.addresses:
        if row.is_default_billing:
            if found:
                msg = f"Webshop Address {webshop_address_doc.name} has more than one default billing Contact. Please contact IT App."
                frappe.log_error(msg, 'webshop.change_default_billing_address')
                frappe.throw(msg)
            row.contact = new_invoice_to_contact_id
            found = True
    if not found:
        msg = f"Webshop Address {webshop_address_doc.name} has no default billing Contact. Please contact IT App."
        frappe.log_error(msg, 'webshop.change_default_billing_address')
        frappe.throw(msg)

    webshop_address_doc.save()


@frappe.whitelist()
def change_contact_customer(contact_id, new_customer_id):
    """
    bench execute microsynth.microsynth.webshop.change_contact_customer --kwargs "{'contact_id': '243755', 'new_customer_id': '8003'}"
    """
    contact_doc = frappe.get_doc("Contact", contact_id)

    if len(contact_doc.links) != 1:
        frappe.throw("This action is only allowed when there is exactly one link. Please contact IT App.")

    link = contact_doc.links[0]

    if link.link_doctype != "Customer":
        frappe.throw(f"The only link links to '{link.link_doctype}', but expected a link to a Customer. Please contact IT App.")

    customer_doc = frappe.get_doc("Customer", new_customer_id)

    if not customer_doc.invoice_to:
        frappe.throw(f"The new Customer '{new_customer_id}' has no Invoice to Contact. Unable to link.")

    # update the Default Billing Contact of the corresponding Webshop Address
    if contact_doc.has_webshop_account:
        change_default_billing_address(contact_id, customer_doc.invoice_to)

    link.link_name = new_customer_id
    link.link_title = customer_doc.customer_name
    contact_doc.save(ignore_permissions=True)
    update_address_links_from_contact(contact_doc.address, contact_doc.links)
    frappe.db.commit()
    return {"status": "success"}


def create_webshop_addresses():
    """
    Create a Webshop Address for all enabled Contacts that have a Webshop Account and not yet a Webshop Address

    bench execute microsynth.microsynth.webshop.create_webshop_addresses
    """
    sql_query = """
        SELECT `tabContact`.`name`,
            `tabCustomer`.`name` AS `customer_id`,
            `tabCustomer`.`invoice_to`
        FROM `tabContact`
        LEFT JOIN `tabWebshop Address` ON `tabWebshop Address`.`webshop_account` = `tabContact`.`name`
        LEFT JOIN `tabDynamic Link` AS `tDLA` ON `tDLA`.`parent` = `tabContact`.`name`
                                              AND `tDLA`.`parenttype`  = "Contact"
                                              AND `tDLA`.`link_doctype` = "Customer"
        LEFT JOIN `tabCustomer` ON `tabCustomer`.`name` = `tDLA`.`link_name`
        WHERE `tabContact`.`status` != 'Disabled'
            AND `tabContact`.`has_webshop_account` = 1
            AND `tabWebshop Address`.`webshop_account` IS NULL
        ;"""
    contacts = frappe.db.sql(sql_query, as_dict=True)
    print(f"There are {len(contacts)} non-Disabled Contacts with a Webshop Account, but without a Webshop Address.")
    for i, contact in enumerate(contacts):
        if i % 200 == 0:
            print(f"Already processed {i}/{len(contacts)} Contacts.")
            frappe.db.commit()
        contact_id = contact.get('name')
        if not contact.get('customer_id'):
            print(f"Contact '{contact_id}' has no Customer.")
            continue
        if not contact.get('invoice_to'):
            print(f"Customer '{contact.get('customer_id')}' of Contact '{contact_id}' has no Invoice To Contact.")
            continue
        initialize_webshop_address_doc(contact_id, contact_id, contact.get('invoice_to'))


def get_price_list_pdf(contact_id):
    """
    Generate a PDF representation of the price list for the given Contact ID.
    Returns the raw PDF content as bytes.
    """
    from frappe.utils.pdf import get_pdf
    from microsynth.microsynth.utils import get_customer
    from microsynth.microsynth.report.pricing_configurator.pricing_configurator import get_item_prices as get_item_prices_from_price_list

    customer_id = get_customer(contact_id)
    if not customer_id:
        frappe.throw(f"Contact {contact_id} does not belong to any Customer. Unable to get Price List PDF.")
    customer_doc = frappe.get_doc('Customer', customer_id)
    language = customer_doc.language
    price_list = customer_doc.default_price_list
    item_prices = get_item_prices_from_price_list(price_list)
    item_price_dict = {}

    for item_price in item_prices:
        item_price_dict[(item_price.get('item_code'), item_price.get('min_qty'))] = item_price.get('rate')

    data = get_contact_shipping_items(contact_id)
    shipping_items = data.get('shipping_items')

    for item in shipping_items:
        item_price_dict[(item.get('item'), item.get('qty'))] = item.get('rate')

    css = frappe.get_value('Print Format', 'Price List Print Template', 'css')
    raw_html = frappe.get_value('Print Format', 'Price List Print Template', 'html')
    # create html
    css_html = f"<style>{css}</style>{raw_html}"
    rendered_html = frappe.render_template(
        css_html,
        {
            'doc': frappe.get_doc('Price List Print Template', 'Price List Print Template'),
            'contact_id': contact_id,
            'customer_doc': customer_doc,
            'language': 'en' or language,
            'item_prices': item_price_dict,
            'shipping_items': shipping_items
        }
    )
    # need to load the styles and tags
    content = frappe.render_template(
        'microsynth/templates/pages/print.html',
        {'html': rendered_html}
    )
    options = {
        'disable-smart-shrinking': ''
    }
    pdf = get_pdf(content, options)
    return pdf


@frappe.whitelist()
def prepare_price_list_pdf_download(contact):
    """
    Generates the price list PDF for a given Contact and sends it as a file download.

    Side Effects:
        Sets `frappe.local.response` to return a downloadable PDF file.
    """
    pdf = get_price_list_pdf(contact)
    # Use contact name in filename, replace spaces to avoid invalid characters
    frappe.local.response.filename = f"Price_List_PersID_{contact.replace(' ', '_')}.pdf"
    frappe.local.response.filecontent = pdf
    frappe.local.response.type = "download"


@frappe.whitelist()
def get_price_list_doc(contact):
    """
    Return a base64-encoded PDF and a file name of the Price List for the Customer of the given contact.

    bench execute microsynth.microsynth.webshop.get_price_list_doc --kwargs "{'contact': '215856'}"
    """
    try:
        pdf = get_price_list_pdf(contact)
        encoded_pdf = base64.b64encode(pdf).decode("utf-8")
        file_name = f"Price_List_{contact.replace(' ', '_')}.pdf"
        return {
            "success": True,
            "file": {
                "file_name": file_name,
                "content_base64": encoded_pdf,
                "mime_type": "application/pdf"
            },
            "message": "OK"
        }
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "webshop.get_price_list_doc")
        return {
            "success": False,
            "file": None,
            "message": f"Failed to generate PDF: {str(e)}"
        }


# Credit Account API


def get_credit_account_balance(account_id):
    """
    Fetch the current balance of the given Credit Account.
    """
    from microsynth.microsynth.report.customer_credits.customer_credits import get_data
    try:
        credit_account = frappe.get_doc('Credit Account', account_id)
        filters = {
            'credit_account': account_id,
            'company': credit_account.company,
            'customer': credit_account.customer,
            'exclude_unpaid_deposits': True
        }
        customer_credits = get_data(filters)
        balance = 0.0
        for transaction in customer_credits:
            if transaction.get('status') in ['Paid', 'Return', 'Credit Note Issued']:
                balance += transaction.get('net_amount', 0.0)
    except Exception as err:
        msg = f"Error getting balance for Credit Account '{account_id}': {err}. Check ERP Error Log for details."
        frappe.log_error(f"{msg}\n\n{traceback.format_exc()}", "webshop.get_credit_account_balance")
        frappe.throw(msg)
    return balance


def get_product_types(account_id):
    """
    Get the product types linked to the given Credit Account.

    bench execute microsynth.microsynth.webshop.get_product_types --kwargs "{'account_id': 'CA-000002'}"
    """
    product_types = frappe.get_all(
        "Product Type Link",
        filters={
            "parent": account_id,
            "parentfield": "product_types",
            "parenttype": "Credit Account"
        },
        fields=["product_type"]
    )
    return [pt["product_type"] for pt in product_types]


def get_open_sales_orders(credit_account_id):
    """
    Get all Sales Orders that are associated with the given Credit Account and are not yet fully billed.

    bench execute microsynth.microsynth.webshop.get_open_sales_orders --kwargs "{'credit_account_id': 'CA-000002'}"
    """
    sql_query = """
        SELECT
            `tabSales Order`.`name`,
            `tabSales Order`.`grand_total`,
            `tabSales Order`.`per_billed`,
            `tabSales Order`.`grand_total` * (1 - `tabSales Order`.`per_billed` / 100) AS `unbilled_amount`,
            `tabSales Order`.`transaction_date`,
            `tabSales Order`.`contact_display`,
            `tabSales Order`.`status`,
            `tabSales Order`.`web_order_id`,
            `tabSales Order`.`currency`,
            `tabSales Order`.`product_type`,
            `tabSales Order`.`po_no`
        FROM
            `tabSales Order`
        JOIN
            `tabCredit Account Link`
            ON `tabCredit Account Link`.`parent` = `tabSales Order`.`name`
        WHERE
            `tabCredit Account Link`.`credit_account` = %s
            AND `tabSales Order`.`docstatus` = 1
            AND `tabSales Order`.`per_billed` < 100
        ORDER BY `tabSales Order`.`transaction_date` DESC, `tabSales Order`.`creation` DESC
        """
    sales_orders = frappe.db.sql(sql_query, (credit_account_id,), as_dict=True)
    return sales_orders


def get_ca_forecast_balance(credit_account_doc, balance):
    """
    Calculate the forecast balance of the given Credit Account by considering unbilled Sales Orders.

    bench execute microsynth.microsynth.webshop.get_ca_forecast_balance --kwargs "{'credit_account_doc': 'CA-000002', 'balance': 1000.0}"
    """
    if isinstance(credit_account_doc, str):
        credit_account_doc = frappe.get_doc("Credit Account", credit_account_doc)
    unbilled_sales_orders = get_open_sales_orders(credit_account_doc.name)
    if len(unbilled_sales_orders) > 0:
        total_unbilled_amount = sum(so.get('unbilled_amount', 0.0) for so in unbilled_sales_orders)
        forecast_balance = balance - total_unbilled_amount
    else:
        forecast_balance = balance
    return round(forecast_balance, 2)


def get_credit_account_dto(credit_account):
    """
    Takes a Credit Account DocType or dict and returns a data transfer object (DTO) suitable for the webshop.

    bench execute microsynth.microsynth.webshop.get_credit_account_dto --kwargs "{'credit_account': 'CA-000002'}"
    """
    if isinstance(credit_account, str):
        credit_account = frappe.get_doc("Credit Account", credit_account)
    balance = get_credit_account_balance(credit_account.name)

    return {
        "account_id": credit_account.name,
        "type": credit_account.account_type,
        "name": credit_account.account_name,
        "description": credit_account.description,
        "webshop_account": credit_account.contact_person,
        "status": credit_account.status,
        "company": credit_account.company,
        "customer": credit_account.customer,
        "currency": credit_account.currency,
        "expiry_date": credit_account.expiry_date,
        "balance": round(balance, 2),
        "forecast_balance": get_ca_forecast_balance(credit_account, balance),
        "product_types": get_product_types(credit_account.name),
        "product_types_locked": credit_account.product_types_locked
    }


@frappe.whitelist()
def get_credit_accounts(webshop_account, workgroup_members):
    """
    Takes a webshop_account (Contact ID) and a list of workgroup_members (Contact IDs)
    and returns all Credit Accounts linked to any of these Contacts.

    Also includes all Credit Accounts with account_type='Legacy' of the Customer
    of the webshop_account (if not already included).

    bench execute microsynth.microsynth.webshop.get_credit_accounts --kwargs "{'webshop_account': '215856', 'workgroup_members': '["215856", "243755"]'}"
    """
    try:
        # Parse workgroup_members
        if isinstance(workgroup_members, str):
            workgroup_members = json.loads(workgroup_members)
        if webshop_account not in workgroup_members:
            workgroup_members.append(webshop_account)
        workgroup_members = [str(member) for member in workgroup_members]

        # Get the Customer linked to the webshop_account
        customer_id = get_customer(webshop_account)

        # Use a single SQL query to fetch both:
        #   1. Credit Accounts linked to any workgroup member contact
        #   2. Legacy Credit Accounts of the same Customer
        #   (avoid duplicates via DISTINCT)
        contacts = ', '.join(['%s'] * len(workgroup_members))
        params = workgroup_members.copy()

        sql = f"""
            SELECT DISTINCT
                name,
                account_name,
                description,
                status,
                company,
                currency,
                expiry_date,
                account_type,
                customer
            FROM `tabCredit Account`
            WHERE
                contact_person IN ({contacts})
                AND status != 'Disabled'
        """

        if customer_id:
            sql += " OR (customer = %s AND account_type = 'Legacy' AND status != 'Disabled')"
            params.append(customer_id)

        credit_accounts = frappe.db.sql(sql, params, as_dict=True)

        if not credit_accounts:
            return {
                "success": True,
                "message": f"No Credit Account found for Contact '{webshop_account}'",
                "credit_accounts": []
            }
        # Build DTO list
        credit_accounts_to_return = [
            get_credit_account_dto(ca.get('name')) for ca in credit_accounts
        ]
        return {
            "success": True,
            "message": "OK",
            "credit_accounts": credit_accounts_to_return
        }
    except Exception as err:
        msg = f"Error getting Credit Accounts for webshop_account '{webshop_account}': {err}. Check ERP Error Log for details."
        frappe.log_error(f"{msg}\n\n{traceback.format_exc()}", "webshop.get_credit_accounts")
        return {
            "success": False,
            "message": msg,
            "credit_accounts": []
        }


@frappe.whitelist()
def create_credit_account(webshop_account, name, description, company, product_types):
    """
    Create a new Credit Account for the given webshop_account (Contact ID) with the given name, description, company and product types.

    bench execute microsynth.microsynth.webshop.create_credit_account --kwargs "{'webshop_account': '215856', 'name': 'Test', 'description': 'some description', 'company': 'Microsynth AG', 'product_types': ['Oligos', 'Sequencing']}"
    """
    try:
        if isinstance(product_types, str):
            product_types = json.loads(product_types)

        customer_id = get_customer(webshop_account)

        credit_account = frappe.get_doc({
            'doctype': 'Credit Account',
            'contact_person': webshop_account,
            'customer': customer_id,
            'account_name': name,
            'description': description,
            'company': company,
            'currency': frappe.db.get_value('Customer', customer_id, 'default_currency'),
            'status': 'Active'
        })
        # Add product types
        for pt in product_types:
            credit_account.append("product_types", {
                "product_type": pt
            })
        credit_account.insert()
        return {
            "success": True,
            "message": "OK",
            "credit_account": get_credit_account_dto(credit_account)
        }
    except Exception as err:
        msg = f"Error creating Credit Account for webshop_account '{webshop_account}': {err}. Check ERP Error Log for details."
        frappe.log_error(f"{msg}\n\n{traceback.format_exc()}", "webshop.create_credit_account")
        return {
            "success": False,
            "message": msg,
            "credit_accounts": []
        }


@frappe.whitelist()
def update_credit_account(credit_account):
    """
    Update the Credit Account with the given account_id (Credit Account name) with the given fields.
    Only the fields name, description, status, webshop_account (Contact ID) and product_types can be changed.

    "credit_account": {
        "account_id": "Account-000003",
        "name": "MyChangedName",
        "description": "some changed description",
        "status": "Disabled",
        "webshop_account": "215856" # to change the owner (ERP validates if it is the same customer),
        "product_types": ["Oligos", "Sequencing"] # not implemented yet
    }

    bench execute microsynth.microsynth.webshop.update_credit_account --kwargs "{'credit_account': {'account_id': 'CA-000003', 'name': 'Changed Name', 'description': 'Changed Description', 'product_types': ['Oligos', 'Sequencing', 'NGS']}}"
    """
    try:
        credit_account_doc = frappe.get_doc('Credit Account', credit_account.get('account_id'))
        if 'name' in credit_account and credit_account.get('name') != credit_account_doc.account_name:
            credit_account_doc.account_name = credit_account.get('name')
        if 'description' in credit_account and credit_account.get('description') != credit_account_doc.description:
            credit_account_doc.description = credit_account.get('description')
        if 'status' in credit_account and credit_account.get('status') != credit_account_doc.status:
            if credit_account_doc.status == 'Disabled':
                frappe.throw(f"Not allowed to change status of Credit Account '{credit_account.get('account_id')}' because it is Disabled.")
            if credit_account.get('status') not in ['Active', 'Frozen', 'Disabled']:
                frappe.throw(f"Not allowed to change status of Credit Account '{credit_account.get('account_id')}' to '{credit_account.get('status')}'. Allowed values are 'Active', 'Frozen' and 'Disabled'.")
            if credit_account.get('status') == 'Disabled':
                # Only allow to disable a Credit Account if its balance is zero
                balance = get_credit_account_balance(credit_account.get('account_id'))
                if balance >= 0.01 or balance <= -0.01:
                    frappe.throw(f"Not allowed to change status of Credit Account '{credit_account.get('account_id')}' to 'Disabled' because its balance is not zero (balance: {balance}).")
            credit_account_doc.status = credit_account.get('status')
        if 'webshop_account' in credit_account and credit_account.get('webshop_account') != credit_account_doc.contact_person:
            # Change the owner of the credit account
            new_contact = credit_account.get('webshop_account')
            if not new_contact:
                frappe.throw(f"Not allowed to change owner of Credit Account '{credit_account.get('account_id')}' to empty value.")
            if not frappe.db.exists('Contact', new_contact):
                frappe.throw(f"Not allowed to change owner of Credit Account '{credit_account.get('account_id')}' to Contact '{new_contact}' that does not exist.")
            old_customer = get_customer(credit_account_doc.contact_person)
            new_customer = get_customer(new_contact)
            if old_customer != new_customer:
                frappe.throw(f"Not allowed to change owner of Credit Account '{credit_account.get('account_id')}' from Contact '{credit_account_doc.contact_person}' (Customer '{old_customer}') to Contact '{new_contact}' (Customer '{new_customer}') because they belong to different Customers.")
            credit_account_doc.contact_person = new_contact
        if 'product_types' in credit_account:
            if not isinstance(credit_account.get('product_types'), list):
                new_product_types = json.loads(credit_account.get('product_types'))
            else:
                new_product_types = credit_account.get('product_types')
            if set(new_product_types) != set(get_product_types(credit_account.get('account_id'))):
                if credit_account_doc.product_types_locked:
                    frappe.throw(f"Not allowed to change product types of Credit Account '{credit_account.get('account_id')}' because it is locked for editing by the webshop.")
                # Remove all existing product types
                credit_account_doc.product_types = []
                # Add new product types
                for pt in new_product_types:
                    credit_account_doc.append("product_types", {
                        "product_type": pt
                    })
        if 'company' in credit_account and (credit_account.get('company') != credit_account_doc.company or credit_account_doc.has_transactions):
            frappe.throw(f"Not allowed to change company of Credit Account '{credit_account.get('account_id')}'.")
        if 'customer' in credit_account and (credit_account.get('customer') != get_customer(credit_account_doc.contact_person) or credit_account_doc.has_transactions):
            frappe.throw(f"Not allowed to change customer of Credit Account '{credit_account.get('account_id')}'.")
        if 'currency' in credit_account and (credit_account.get('currency') != credit_account_doc.currency or credit_account_doc.has_transactions):
            frappe.throw(f"Not allowed to change currency of Credit Account '{credit_account.get('account_id')}'.")
        credit_account_doc.save()
        return {
            "success": True,
            "message": "OK",
            "credit_account": get_credit_account_dto(credit_account_doc)
        }
    except Exception as err:
        msg = f"Error updating Credit Account '{credit_account.get('account_id')}': {err}. Check ERP Error Log for details."
        frappe.log_error(f"{msg}\n\n{traceback.format_exc()}", "webshop.update_credit_account")
        return {
            "success": False,
            "message": msg,
            "credit_accounts": []
        }


def get_default_shipping_address(webshop_address_id):
    """
    Get the default shipping address of the given Webshop Address.

    bench execute microsynth.microsynth.webshop.get_default_shipping_address --kwargs "{'webshop_address_id': '215856'}"
    """
    webshop_address_doc = frappe.get_doc("Webshop Address", webshop_address_id)
    for a in webshop_address_doc.addresses:
        if a.is_default_shipping and not a.disabled:
            return frappe.get_value("Contact", a.contact, "address")
    return None


@frappe.whitelist()
def create_deposit_invoice(webshop_account, account_id, amount, currency, description, company, customer, customer_order_number, ignore_permissions=False, transmit_invoice=True):
    """
    Create a Sales Invoice to deposit customer credits.

    Request:
    {
        "webshop_account": "215856",
        "account_id": "CA-000003",
        "amount": "1000.00",
        "currency": "CHF",
        "description": "Cloning Primers",
        "company": "Microsynth AG",
        "customer": "801234",
        "customer_order_number": "PO-12345"
    }
    * Company, Currency and Customer are pulled from the Credit Account and transmitted over the API for validation
    * Credits will be available as soon as the payment of the Sales Invoice is received
    * ERP validates that the company, customer and currency matches the account currency
    * The description will be used to name the item. if not set (null) the standard text "Primers and Sequencing" will be shown on the Sales Invoice

    bench execute microsynth.microsynth.webshop.create_deposit_invoice --kwargs "{'webshop_account': '215856', 'account_id': 'CA-000003', 'amount': 1000.00, 'currency': 'CHF', 'description': 'Primers', 'company': 'Microsynth AG', 'customer': '8003', 'customer_order_number': 'PO-12345'}"
    """
    try:
        if ignore_permissions and frappe.get_user().name == 'webshop@microsynth.ch':
            frappe.throw("Not allowed to use ignore_permissions.")
        credit_account_doc = frappe.get_doc('Credit Account', account_id)
        # Validate that the company, customer and currency matches the account currency
        if credit_account_doc.company != company:
            frappe.throw(f"The given Company '{company}' does not match the company '{credit_account_doc.company}' of Credit Account '{account_id}'.")
        if credit_account_doc.customer != customer:
            frappe.throw(f"The given Customer '{customer}' does not match the customer '{credit_account_doc.customer}' of Credit Account '{account_id}'.")
        if credit_account_doc.currency != currency:
            frappe.throw(f"The given Currency '{currency}' does not match the currency '{credit_account_doc.currency}' of Credit Account '{account_id}'.")
        if credit_account_doc.has_transactions and credit_account_doc.account_type in ['Enforced Credit', 'Legacy']:
            frappe.throw(f"Not allowed to create a deposit invoice for a Credit Account of type 'Legacy' or 'Enforced Credit' that already has transactions.")

        # Fetch credit item from Microsynth Settings
        credit_item_code = frappe.get_value("Microsynth Settings", "Microsynth Settings", "credit_item")
        credit_item = frappe.get_doc("Item", credit_item_code)

        # Fetch shipping address of the webshop account
        shipping_address = get_default_shipping_address(webshop_account)
        if not shipping_address:
            frappe.throw(f"Webshop Address '{webshop_account}' has no default shipping address. Unable to create deposit invoice.")
        tax_template = find_dated_tax_template(company, customer, shipping_address, "Service", datetime.now().date())
        customer_doc = frappe.get_doc("Customer", customer)
        # Create the Sales Invoice
        invoice = frappe.get_doc({
            "doctype": "Sales Invoice",
            "company": company,
            "customer": customer,
            "contact_person": webshop_account,
            "contact_display": frappe.get_value("Contact", webshop_account, "full_name"),
            "po_no": customer_order_number,
            "product_type": "Service",
            "contact_person": webshop_account,
            "territory": customer_doc.territory or "All Territories",
            "currency": currency,
            "selling_price_list": customer_doc.default_price_list or f"Sales Prices {currency}",
            "items": [{
                "item_code": credit_item.item_code,
                "qty": 1,
                "rate": amount,
                "item_name": description if description else credit_item.item_name,
                "cost_center": credit_item.get("selling_cost_center") or frappe.get_value("Company", company, "cost_center")
            }],
            "taxes_and_charges": tax_template,
            "credit_account": account_id,
            "remarks": f"Webshop deposit for Credit Account {account_id}"
        })
        invoice.naming_series = get_naming_series("Sales Invoice", company)
        invoice.insert(ignore_permissions=ignore_permissions)
        invoice.submit()
        # Transmit the Sales Invoice
        if isinstance(transmit_invoice, str):
            transmit_invoice = transmit_invoice.strip().lower() in ("true", "1", "yes")
        if transmit_invoice:
            transmit_sales_invoice(invoice.name)
        # Set has_transaction on the Credit Account
        account_doc = frappe.get_doc("Credit Account", account_id)
        if not account_doc.has_transactions:
            account_doc.has_transactions = True
            account_doc.save()
        return {
            "success": True,
            "message": "OK",
            "reference": invoice.name
        }
    except Exception as err:
        msg = f"Error creating deposit invoice for Credit Account '{account_id}'. Details have been recorded."
        frappe.log_error(f"{msg}\n\n{traceback.format_exc()}", "webshop.create_deposit_invoice")
        return {
            "success": False,
            "message": msg,
            "reference": None
        }


def get_reservations(account_id, current_balance):
    open_sales_orders = get_open_sales_orders(account_id)
    running_balance = current_balance
    reservations = []
    for i, order in enumerate(open_sales_orders):
        unbilled_amount = order.get('unbilled_amount') or 0.0
        running_balance -= unbilled_amount
        reservations.append({
            "date": order.get('transaction_date'),
            "type": "Charge",
            "reference": order.get('name'),
            "contact_name": order.get('contact_display'),
            "status": order.get('status'),
            "web_order_id": order.get('web_order_id'),
            "currency": order.get('currency'),
            "amount": round((-1) * unbilled_amount, 2),
            "balance": round(running_balance, 2),
            "product_type": order.get('product_type'),
            "po_no": order.get('po_no'),
            "idx": i    # index for webshop api to maintain the order of transactions
        })
    return reservations


@frappe.whitelist()
def get_transactions(account_id):
    """
    Get all transactions for the given Credit Account.

    bench execute microsynth.microsynth.webshop.get_transactions --kwargs "{'account_id': 'CA-000020'}"
    """
    from microsynth.microsynth.report.customer_credits.customer_credits import build_transactions_with_running_balance
    type_mapping = {
        'Allocation': 'Charge',
        'Credit': 'Deposit'
    }
    try:
        credit_account = frappe.get_doc('Credit Account', account_id)
        filters = {
            'credit_account': account_id,
            'company': credit_account.company,
            'customer': credit_account.customer
        }
        transactions = build_transactions_with_running_balance(filters, type_mapping=type_mapping)

        # reverse to display the most recent transaction first
        transactions.reverse()
        current_balance = transactions[0].get('balance') if len(transactions) > 0 else 0.0

        return {
            "success": True,
            "message": "OK",
            "credit_account": get_credit_account_dto(credit_account),
            "transactions": transactions,
            "reservations": get_reservations(account_id, current_balance)
        }
    except Exception as err:
        msg = f"Error fetching Credit Account '{account_id}': {err}. Check ERP Error Log for details."
        frappe.log_error(f"{msg}\n\n\n{traceback.format_exc()}", "webshop.get_transactions")
        return {
            "success": False,
            "message": msg,
            "credit_account": None,
            "transactions": [],
            "reservations": None
        }


@frappe.whitelist()
def get_balance_sheet_pdf(account_id):
    """
    stub (actual PDF generation not yet implemented)

    bench execute microsynth.microsynth.webshop.get_balance_sheet_pdf --kwargs "{'account_id': 'CA-000002'}"
    """
    from erpnextswiss.erpnextswiss.attach_pdf import get_pdf_data
    try:
        pdf = get_pdf_data(doctype='Credit Account', name=account_id, print_format='Credit Account')
        encoded_pdf = base64.b64encode(pdf)
        file_name = f"Balance_Sheet_{account_id.replace(' ', '_')}.pdf"
        return {
            "success": True,
            "file": {
                "file_name": file_name,
                "content_base64": encoded_pdf,
                "mime_type": "application/pdf"
            },
            "message": "Print Format will be changed"
        }
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "webshop.get_balance_sheet_pdf")
        return {
            "success": False,
            "file": None,
            "message": f"Failed to generate PDF: {str(e)}"
        }
