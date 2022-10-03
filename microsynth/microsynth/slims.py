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
from datetime import datetime

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
        if len(content['entities']) == 0:
            return None
        elif len(content['entities']) > 1:
            frappe.log_error( _("Requested SLIMS customer for person_id {0} returned multiple results").format(person_id), _("SLIMS") )
        # return the first hit
        return content['entities'][0]['pk']
    else:
        frappe.log_error( _("SLIMS error {0} - {1} on get customer {2}").format(res.status_code, res.text, person_id), _("SLIMS") )
        return None
        
def create_update_slims_customer(person_id):
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
    
    if contact.address and frappe.db.exists("Address", person_id):

        address = frappe.get_doc("Address", contact.address or person_id)
        
        if address.address_type == "Shipping":
            customer_data = {
                "cstm_name": "{lastname}_{person_id}".format(lastname=contact.last_name, person_id=person_id),
                "cstm_cf_personId": "{person_id}".format(person_id=person_id),
                #"cstm_cf_userName": "{user}".format(user=contact.webshop_user),    # will not work - variable not implemente
                "cstm_cf_salutation": "{salutation}".format(salutation=contact.salutation or ""),
                "cstm_cf_title": "{title}".format(title=contact.designation or ""),
                "cstm_cf_firstName": "{firstname}".format(firstname=contact.first_name or ""),
                "cstm_cf_lastName": "{lastname}".format(lastname=contact.last_name or ""),
                "cstm_cf_institute": "{institute}".format(institute=contact.institute or ""),
                "cstm_cf_department": "{department}".format(department=contact.department or ""),
                "cstm_cf_houseRoom": "{room}".format(room=contact.room or ""),
                "cstm_cf_groupLeader": "{groupleader}".format(groupleader=contact.group_leader or ""),
                "cstm_cf_universityCompany": "{customer_name}".format(customer_name=customer.customer_name or "") if customer else "",
                "cstm_cf_street": "{street}".format(street=address.address_line1 or ""),
                "cstm_cf_zipCode": "{zipcode}".format(zipcode=address.pincode or ""),
                "cstm_cf_town": "{town}".format(town=address.city or ""),
                "cstm_cf_country": "{country}".format(country=address.country or ""),
                "cstm_cf_email": "{email}".format(email=contact.email_id or ""),
                #"cstm_cf_secondEmail": "mySecondAddress@mail.com",
                #"cstm_cf_phoneCountry": "0041",
                "cstm_cf_phone": "{phone}".format(phone=contact.phone or ""),
                "cstm_active": (not customer.disabled) if customer else 0
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
                print("creating")
                
            # parse feedback
            if res.status_code != 200:
                frappe.log_error( _("SLIMS error {0} - {1} on create/update customer with person_id {2}").format(res.status_code, res.text, person_id), _("SLIMS") )
        else:
            print("is billing contact")
    return 

def sync(debug=False):
    # get configuration
    config = frappe.get_doc("SLIMS Settings", "SLIMS Settings")
    if cint(config.enabled) == 1:
        # prepare timestamps
        start_sync = datetime.now()
        last_sync = config.last_sync or "2020-01-01 00:00:00"
        # get changed records
        changed_records = get_modified_records(last_sync)
        count = 0
        for record in changed_records:
            if debug:
                count += 1
                print("Sending {0} to SLIMS... ({1}%)".format(record, int(100*count/len(changed_records))))
            create_update_slims_customer(record)
        # update last sync timestamp
        config.last_sync = start_sync
        config.save(ignore_permissions=True)
        frappe.db.commit()
    else:
        if debug:
            print("SLIMS scheduler disabled. Go to SLIMS Settings > Enabled and set to 1")
    return
        
def get_modified_records(change_datetime):
    if type(change_datetime) == datetime:
        change_datetime = change_datetime.strftime("%Y-%m-%d %H:%M:%S")
        
    changed_records = frappe.db.sql("""
            SELECT 
            `tabContact`.`name` AS `contact`
        FROM `tabContact`
        LEFT JOIN `tabAddress` ON 
            (`tabAddress`.`name` = IFNULL(`tabContact`.`address`, `tabContact`.`name`))
        LEFT JOIN `tabDynamic Link` ON 
            (`tabDynamic Link`.`parent` = `tabContact`.`name`
            AND `tabDynamic Link`.`parenttype` = "Contact"
            AND `tabDynamic Link`.`link_doctype` = "Customer")
        LEFT JOIN `tabCustomer` ON
            (`tabCustomer`.`name` = `tabDynamic Link`.`link_name`)
        WHERE 
            `tabContact`.`modified` >= "{dt}"
            OR `tabAddress`.`modified` >= "{dt}"
            OR `tabCustomer`.`modified` >= "{dt}"; 
    """.format(dt=change_datetime), as_dict=True)
    contacts = []
    for r in changed_records:
        contacts.append(r['contact'])
    return contacts
