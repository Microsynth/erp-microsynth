# -*- coding: utf-8 -*-
# Copyright (c) 2022, libracore (https://www.libracore.com) and contributors
# For license information, please see license.txt
#
# For more details, refer to https://github.com/Microsynth/erp-microsynth/
#

import requests
from requests.auth import HTTPBasicAuth
import frappe
from frappe import _
from frappe.utils import cint
from frappe.utils.password import get_decrypted_password
import json

# check a person ID in SLIMS
def get_customer(person_id):
    # get configuration
    config = frappe.get_doc("SLIMS Settings", "SLIMS Settings")
    # endpoint
    endpoint = "{host}/slimsrest/rest/Customer?cstm_cf_personId={person_id}".format(host=config.endpoint, person_id=person_id)
    # get customer data
    res = requests.get(
        endpoint, 
        verify=cint(config.verify_ssl), 
        auth=HTTPBasicAuth(
            config.username, 
            get_decrypted_password("SLIMS Settings", "SLIMS Settings", "password")
        )
    )
    # parse feedback
    if res.status_code == 200:
        content = res.json()
        print("{0}".format(content))
        if len(content['entities']) == 0:
            return None
        elif len(content['entities']) > 1:
            frappe.log_error( _("Requested SLIMS customer for person_id {0} returned multiple results").format(person_id), _("SLIMS") )
        # return the first hit
        return content['entities'][0]['pk']
    else:
        frappe.log_error( _("SLIMS error {0} - {1} on get customer {2}").format(res.status_code, res.text, person_id), _("SLIMS") )
        return None
        
def create_update_customer(person_id):
    # get configuration
    config = frappe.get_doc("SLIMS Settings", "SLIMS Settings")
    # check if customer exists
    primary_key = get_customer(person_id)
    # fetch customer record
    if not frappe.db.exists("Contact", person_id):
        frappe.throw( _("Contact {0} not found.").format(person_id) )
    contact = frappe.get_doc("Contact", person_id)
    customer = None
    for r in contact.links:
        if r.link_doctype == "Customer":
            customer = frappe.get_doc("Customer", r.link_name)
            break
    if not customer:
        frappe.throw( _("No customer found for contact {0}.").format(person_id) )
    if not contact.address and not frappe.db.exists("Address", person_id):
        frappe.throw( _("No address found for contact {0}.").format(person_id) )
    address = frappe.get_doc("Address", contact.address or person_id)
    
    customer_data = {
        "cstm_name": "{lastname}_{person_id}".format(lastname=contact.last_name, person_id=person_id),
        "cstm_cf_personId": "{person_id}".format(person_id=person_id),
        #"cstm_cf_userName": "{user}".format(user=contact.webshop_user),    # will not work - variable not implemente
        "cstm_cf_salutation": "{salutation}".format(salutation=contact.salutation),
        "cstm_cf_title": "{title}".format(title=contact.designation),
        "cstm_cf_firstName": "{firstname}".format(firstname=contact.first_name),
        "cstm_cf_lastName": "{lastname}".format(lastname=contact.last_name),
        "cstm_cf_institute": "{institute}".format(institute=contact.institute),
        "cstm_cf_department": "{department}".format(department=contact.department),
        "cstm_cf_houseRoom": "{room}".format(room=contact.room),
        "cstm_cf_groupLeader": "{groupleader}".format(groupleader=contact.group_leader),
        "cstm_cf_universityCompany": "{customer_name}".format(customer_name=customer.customer_name),
        "cstm_cf_street": "{street}".format(street=address.address_line1),
        "cstm_cf_zipCode": "{zipcode}".format(zipcode=address.pincode),
        "cstm_cf_town": "{town}".format(town=address.city),
        "cstm_cf_country": "{country}".format(country=address.country),
        "cstm_cf_email": "{email}".format(email=contact.email_id),
        #"cstm_cf_secondEmail": "mySecondAddress@mail.com",
        #"cstm_cf_phoneCountry": "0041",
        "cstm_cf_phone": "{phone}".format(phone=contact.phone)
    }
    # send customer record
    headers = {'content-type': 'application/json'}
    if primary_key:
        # update
        endpoint = "{host}/slimsrest/rest/Customer/{primary_key}".format(host=config.endpoint, primary_key=primary_key)
        res = requests.post(
            endpoint, 
            data=json.dumps(customer_data),
            verify=cint(config.verify_ssl), 
            auth=HTTPBasicAuth(
                config.username, 
                get_decrypted_password("SLIMS Settings", "SLIMS Settings", "password")
            ),
            headers=headers
        )
        print("updating")
    else:
        # create
        endpoint = "{host}/slimsrest/rest/Customer".format(host=config.endpoint)
        res = requests.put(
            endpoint, 
            data=json.dumps(customer_data),
            verify=cint(config.verify_ssl), 
            auth=HTTPBasicAuth(
                config.username, 
                get_decrypted_password("SLIMS Settings", "SLIMS Settings", "password")
            ),
            headers=headers
        )
        
    # parse feedback
    if res.status_code != 200:
        frappe.log_error( _("SLIMS error {0} - {1} on create/update customer with person_id {2}").format(res.status_code, res.text, person_id), _("SLIMS") )
    return 
