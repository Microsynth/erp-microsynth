# -*- coding: utf-8 -*-
# Copyright (c) 2022, libracore (https://www.libracore.com) and contributors
# For license information, please see license.txt

from email.policy import default
import os
import frappe
from frappe import _
import csv
import pandas as pd
import numpy as np
import json
from frappe.utils import cint, flt
from datetime import datetime, date
from microsynth.microsynth.report.pricing_configurator.pricing_configurator import populate_from_reference
from microsynth.microsynth.naming_series import get_naming_series
from microsynth.microsynth.utils import find_label, set_default_language, set_debtor_accounts, tag_linked_documents, replace_none, configure_customer
from microsynth.microsynth.invoicing import get_income_accounts

PRICE_LIST_NAMES = {
    'CHF': "Sales Prices CHF",
    'EUR': "Sales Prices EUR",
    'USD': "Sales Prices USD",
    'SEK': "Sales Prices SEK",
    'CZK': "Sales Prices CZK"
}

CUSTOMER_HEADER = """person_id\tcustomer_id\tcompany\tfirst_name\tlast_name\temail\taddress_line1\tpincode\tcity\tinstitute\tdepartment\tcountry\tDS_Nr\taddress_type\tvat_nr\tsiret\tcurrency\tis_deleted\tdefault_discount\tis_electronic_invoice\treceive_updates_per_email\tis_punchout_user\tpunchout_identifier\tpunchout_shop_id\troom\tsalutation\ttitle\tgroup_leader\temail_cc\tphone_number\tphone_country\tinstitute_key\tnewsletter_registration_state\tnewsletter_registration_date\tnewsletter_unregistration_date\tumr_nr\tinvoicing_method\tsales_manager\text_debitor_number\tinvoice_email\tphone\tdefault_company\n"""
CUSTOMER_HEADER_FIELDS = """{person_id}\t{customer_id}\t{company}\t{first_name}\t{last_name}\t{email}\t{address_line1}\t{pincode}\t{city}\t{institute}\t{department}\t{country}\t{DS_Nr}\t{address_type}\t{vat_nr}\t{siret}\t{currency}\t{is_deleted}\t{default_discount}\t{is_electronic_invoice}\t{receive_updates_per_email}\t{is_punchout_user}\t{punchout_identifier}\t{punchout_shop_id}\t{room}\t{salutation}\t{title}\t{group_leader}\t{email_cc}\t{phone_number}\t{phone_country}\t{institute_key}\t{newsletter_registration_state}\t{newsletter_registration_date}\t{newsletter_unregistration_date}\t{umr_nr}\t{invoicing_method}\t{sales_manager}\t{ext_debitor_number}\t{invoice_email}\t{phone}\t{default_company}\n"""

def import_customers(filename):
    """
    This function imports/updates the customer master data from a CSV file

    Columns should follow the customer_data structure, see https://github.com/Microsynth/erp-microsynth/wiki/customer_data-object

    Run from bench like
    $ bench execute microsynth.microsynth.migration.import_customers --kwargs "{'filename': '/home/libracore/frappe-bench/apps/microsynth/microsynth/docs/customer_import_sample.csv'}"
    """
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


def export_customers(filename, from_date):
    """
    This function will create a customer export file from ERP to Gecko

    run
    bench execute microsynth.microsynth.migration.export_customers --kwargs "{'filename': '/home/libracore/Desktop/customer_data.txt', 'from_date': '2023-04-24'}"
    """
    # create file
    f = open(filename, "w")
    # write header
    f.write(CUSTOMER_HEADER)
    # get applicable records changed since from_date
    sql_query = """SELECT 
           `tabContact`.`name` AS `person_id`,
           `tabCustomer`.`name` AS `customer_id`,
           `tabCustomer`.`customer_name` AS `customer_name`,
           `tabContact`.`first_name` AS `first_name`,
           `tabContact`.`last_name` AS `last_name`,
           `tabContact`.`email_id` AS `email`,
           `tabAddress`.`overwrite_company` AS `overwrite_company`,
           `tabAddress`.`address_line1` AS `address_line1`,
           `tabAddress`.`pincode` AS `pincode`,
           `tabAddress`.`city` AS `city`,
           `tabContact`.`institute` AS `institute`,
           `tabContact`.`department` AS `department`,
           `tabCountry`.`code` AS `country`,
           "" AS `ds_nr`,
           `tabAddress`.`address_type` AS `address_type`,
           `tabCustomer`.`tax_id` AS `vat_nr`,
           `tabCustomer`.`siret` AS `siret`,
           `tabCustomer`.`ext_debitor_number` AS `ext_debitor_number`,
           `tabCustomer`.`default_currency` AS `currency`,
           `tabCustomer`.`invoice_email` AS `invoice_email`, 
           `tabCustomer`.`disabled` AS `is_deleted`,
           `tabPrice List`.`general_discount` AS `default_discount`,
           0 AS `is_electronic_invoice`,
           0 AS `receive_updates_per_email`,
           0 AS `is_punchout_user`,
           `tabCustomer`.`punchout_identifier` AS `punchout_identifier`,
           `tabCustomer`.`punchout_shop` AS `punchout_shop_id`,
           `tabContact`.`room` AS `room`,
           `tabContact`.`salutation` AS `salutation`,
           `tabContact`.`designation` AS `title`,
           `tabContact`.`group_leader` AS `group_leader`,
           NULL AS `email_cc`,
           `tabContact`.`phone` AS `phone_number`,
           NULL AS `phone_country`,
           `tabContact`.`institute_key` AS `institute_key`,
           `tabContact`.`receive_newsletter` AS `newsletter_registration_state`,
           `tabContact`.`subscribe_date` AS `newsletter_registration_date`,
           `tabContact`.`unsubscribe_Date` AS `newsletter_unregistration_date`,
           NULL AS `umr_nr`,
           `tabCustomer`.`invoicing_method` AS `invoicing_method`,
           `tabUser`.`username` AS `sales_manager`,
           `tabContact`.`phone` AS `phone`,
           `tabCompany`.`abbr` AS `default_company`
        FROM `tabContact`
        LEFT JOIN `tabDynamic Link` AS `tDLA` ON `tDLA`.`parent` = `tabContact`.`name` 
                                              AND `tDLA`.`parenttype`  = "Contact" 
                                              AND `tDLA`.`link_doctype` = "Customer"
        LEFT JOIN `tabCustomer` ON `tabCustomer`.`name` = `tDLA`.`link_name` 
        LEFT JOIN `tabAddress` ON `tabContact`.`address` = `tabAddress`.`name`
        LEFT JOIN `tabPrice List` ON `tabPrice List`.`name` = `tabCustomer`.`default_price_list`
        LEFT JOIN `tabUser` ON `tabCustomer`.`account_manager` = `tabUser`.`name`
        LEFT JOIN `tabCountry` ON `tabCountry`.`name` = `tabAddress`.`country`
        LEFT JOIN `tabCompany` ON `tabCompany`.`name` = `tabCustomer`.`default_company`
        WHERE `tabCustomer`.`modified` >= "{from_date}"
           OR `tabAddress`.`modified` >= "{from_date}"
           OR `tabContact`.`modified` >= "{from_date}"
    """.format(from_date=from_date)
    data = frappe.db.sql(sql_query, as_dict=True)
    for d in data:       
        # Skip entries that are not a positive number
        if (not d['person_id'].isnumeric() 
            or "-" in d['person_id']
            or not d['customer_id']
            or "-" in d['customer_id']
            or not d['country']):               # country is required for FileMaker Gecko (exclude Contacts without linked address)
            continue

        # Do not change the order of the fields. Changes will corrupt import into Gecko.
        # Only append new lines.
        row = CUSTOMER_HEADER_FIELDS.format(
            person_id = replace_none(d['person_id']),
            customer_id = replace_none(d['customer_id']),
            company = d['overwrite_company'] if d['overwrite_company'] else replace_none(d['customer_name']),
            first_name = "" if d['first_name'] == "-" else replace_none(d['first_name']),
            last_name = replace_none(d['last_name']),
            email = replace_none(d['email']),
            address_line1 = replace_none(d['address_line1']),
            pincode = replace_none(d['pincode']),
            city = replace_none(d['city']),
            institute = replace_none(d['institute']),
            department = replace_none(d['department']),
            country = replace_none(d['country']),
            DS_Nr = replace_none(d['ds_nr']),
            address_type = replace_none("INV" if (d["address_type"]=="Billing") else "DEL"),
            vat_nr = replace_none(d['vat_nr']),
            siret = replace_none(d['siret']),
            currency = replace_none(d['currency']),
            is_deleted = replace_none(d['is_deleted']),
            default_discount = replace_none(d['default_discount']),
            is_electronic_invoice = replace_none(d['is_electronic_invoice']),
            receive_updates_per_email = replace_none(d['receive_updates_per_email']),
            is_punchout_user = replace_none(d['is_punchout_user']),
            punchout_identifier = replace_none(d['punchout_identifier']),
            punchout_shop_id = replace_none(d['punchout_shop_id']),
            room = replace_none(d['room']),
            salutation = replace_none(d['salutation']),
            title = replace_none(d['title']),
            group_leader = replace_none(d['group_leader']),
            email_cc = replace_none(d['email_cc']),
            phone_number = replace_none(d['phone_number']),
            phone_country = replace_none(d['phone_country']),
            institute_key = replace_none(d['institute_key']),
            newsletter_registration_state = replace_none(d['newsletter_registration_state']),
            newsletter_registration_date = replace_none(d['newsletter_registration_date']),
            newsletter_unregistration_date = replace_none(d['newsletter_unregistration_date']),
            umr_nr = replace_none(d['umr_nr']),
            invoicing_method = replace_none(d['invoicing_method']),
            sales_manager = replace_none(d['sales_manager']),
            ext_debitor_number = replace_none(d['ext_debitor_number']),
            invoice_email = replace_none(d['invoice_email']),
            phone = replace_none(d['phone']),
            default_company = replace_none(d['default_company'])
        )
        f.write(row)
    # close file
    f.close()
    return

BILLING_ADDRESS_HEADER = """customer_id;title;first_name;last_name;institute;department;room;customer_name;address_line1;country;pincode;city;invoice_email;phonecountry_gecko;phone_gecko;person_id;tax_id;unreliable;default_discount;;address_type;salutation;;;electronic_invoice;is_punchout_user;punchout_buyer;punchout_identifier;static_billing_address_id;webshop_billing_address_readonly;\n"""
BILLING_ADDRESS_FIELDS = """{customer_id};{title};{first_name};{last_name};{institute};{department};{room};{customer_name};{address_line1};{country};{pincode};{city};{invoice_email};;;{person_id};{tax_id};;{default_discount};;{address_type};{salutation};;;{electronic_invoice};;;;;{webshop_billing_address_readonly};\n"""

def export_billing_address(filename, customer_name):
    """
    This function will create a customer export file from ERP to Gecko
    """
    # create file
    f = open(filename, "w")
    # write header
    f.write(BILLING_ADDRESS_HEADER)
    # get applicable records changed since from_date
    sql_query = """SELECT 
           `tabContact`.`name` AS `person_id`,
           `tabCustomer`.`name` AS `customer_id`,
           `tabCustomer`.`customer_name` AS `customer_name`,
           `tabContact`.`first_name` AS `first_name`,
           `tabContact`.`last_name` AS `last_name`,
           `tabContact`.`email_id` AS `email`,
           `tabAddress`.`overwrite_company` AS `overwrite_company`,
           `tabAddress`.`address_line1` AS `address_line1`,
           `tabAddress`.`pincode` AS `pincode`,
           `tabAddress`.`city` AS `city`,
           `tabContact`.`institute` AS `institute`,
           `tabContact`.`department` AS `department`,
           `tabCountry`.`code` AS `country`,
           "" AS `ds_nr`,
           `tabAddress`.`address_type` AS `address_type`,
           `tabCustomer`.`tax_id` AS `tax_id`,
           `tabCustomer`.`siret` AS `siret`,
           `tabCustomer`.`ext_debitor_number` AS `ext_debitor_number`,
           `tabCustomer`.`default_currency` AS `currency`,
           `tabCustomer`.`invoice_email` AS `invoice_email`, 
           `tabCustomer`.`disabled` AS `is_deleted`,
           `tabPrice List`.`general_discount` AS `default_discount`,
           0 AS `electronic_invoice`,
           0 AS `receive_updates_per_email`,
           0 AS `is_punchout_user`,
           `tabCustomer`.`punchout_identifier` AS `punchout_identifier`,
           `tabCustomer`.`punchout_shop` AS `punchout_shop_id`,
           `tabCustomer`.`webshop_address_readonly` as `webshop_billing_address_readonly`,
           `tabContact`.`room` AS `room`,
           `tabContact`.`salutation` AS `salutation`,
           `tabContact`.`designation` AS `title`,
           `tabContact`.`group_leader` AS `group_leader`,
           NULL AS `email_cc`,
           `tabContact`.`phone` AS `phone_number`,
           NULL AS `phone_country`,
           `tabContact`.`institute_key` AS `institute_key`,
           `tabContact`.`receive_newsletter` AS `newsletter_registration_state`,
           `tabContact`.`subscribe_date` AS `newsletter_registration_date`,
           `tabContact`.`unsubscribe_Date` AS `newsletter_unregistration_date`,
           NULL AS `umr_nr`,
           `tabCustomer`.`invoicing_method` AS `invoicing_method`,
           `tabUser`.`username` AS `sales_manager`,
           `tabContact`.`phone` AS `phone`
        FROM `tabAddress`
        LEFT JOIN `tabDynamic Link` AS `tDLA` ON `tDLA`.`parent` = `tabAddress`.`name` 
                                              AND `tDLA`.`parenttype`  = "Address" 
                                              AND `tDLA`.`link_doctype` = "Customer"
        LEFT JOIN `tabCustomer` ON `tabCustomer`.`name` = `tDLA`.`link_name` 
        LEFT JOIN `tabContact` ON `tabContact`.`address` = `tabAddress`.`name`
        LEFT JOIN `tabPrice List` ON `tabPrice List`.`name` = `tabCustomer`.`default_price_list`
        LEFT JOIN `tabUser` ON `tabCustomer`.`account_manager` = `tabUser`.`name`
        LEFT JOIN `tabCountry` ON `tabCountry`.`name` = `tabAddress`.`country`
        WHERE `tabCustomer`.`name` = "{customer_name}"
        AND `tabAddress`.`address_type` = "Billing"
    """.format(customer_name=customer_name)
    data = frappe.db.sql(sql_query, as_dict=True)       
    for d in data:
        # Do not change the order. Changes will corrupt import into Gecko.
        # Only append new lines.
        row = BILLING_ADDRESS_FIELDS.format(
            person_id = replace_none(d['person_id']),
            customer_id = replace_none(d['customer_id']),
            customer_name = d['overwrite_company'] if d['overwrite_company'] else replace_none(d['customer_name']),
            first_name = "" if d['first_name'] == "-" else replace_none(d['first_name']),
            last_name = replace_none(d['last_name']),
            email = replace_none(d['email']),
            address_line1 = replace_none(d['address_line1']),
            pincode = replace_none(d['pincode']),
            city = replace_none(d['city']),
            institute = replace_none(d['institute']),
            department = replace_none(d['department']),
            country = replace_none(d['country']).upper(),
            DS_Nr = replace_none(d['ds_nr']),
            address_type = replace_none("INV" if (d["address_type"]=="Billing") else "DEL"),
            tax_id = replace_none(d['tax_id']),
            siret = replace_none(d['siret']),
            currency = replace_none(d['currency']),
            is_deleted = replace_none(d['is_deleted']),
            default_discount = replace_none(d['default_discount']),
            electronic_invoice = replace_none(d['electronic_invoice']),
            receive_updates_per_email = replace_none(d['receive_updates_per_email']),
            is_punchout_user = replace_none(d['is_punchout_user']),
            punchout_identifier = replace_none(d['punchout_identifier']),
            punchout_shop_id = replace_none(d['punchout_shop_id']),
            room = replace_none(d['room']),
            salutation = replace_none(d['salutation']),
            title = replace_none(d['title']),
            group_leader = replace_none(d['group_leader']),
            email_cc = replace_none(d['email_cc']),
            phone_number = replace_none(d['phone_number']),
            phone_country = replace_none(d['phone_country']),
            institute_key = replace_none(d['institute_key']),
            newsletter_registration_state = replace_none(d['newsletter_registration_state']),
            newsletter_registration_date = replace_none(d['newsletter_registration_date']),
            newsletter_unregistration_date = replace_none(d['newsletter_unregistration_date']),
            umr_nr = replace_none(d['umr_nr']),
            invoicing_method = replace_none(d['invoicing_method']),
            sales_manager = replace_none(d['sales_manager']),
            ext_debitor_number = replace_none(d['ext_debitor_number']),
            invoice_email = replace_none(d['invoice_email']),
            phone = replace_none(d['phone']),
            webshop_billing_address_readonly = replace_none(d['webshop_billing_address_readonly'])
        )
        f.write(row)
    # close file
    f.close()
    return

@frappe.whitelist()
def export_customer_to_gecko(customer_name):
    billing_address_file = "/mnt/erp_share/Gecko/Export_Customer_Data/Billing/billing_address_export_for_gecko.tab"    
    if os.path.exists(billing_address_file):
        frappe.throw("<b>Export file already exists:</b><br>" + billing_address_file)
    else:    
        export_billing_address(billing_address_file, customer_name)
    frappe.msgprint("Exported for Gecko")
    return

SHIPPING_ADDRESS_HEADER = """customer_id;title;first_name;last_name;institute;department;room;customer_name;address_line1;country;pincode;city;email;phonecountry_gecko;phone_gecko;username;password;person_id;;address_type;;email_cc;salutation;group_leader;;;;is_punchout_user;punchout_buyer;punchout_identifier;newsletter_registration_state;newsletter_registration_date;newsletter_unregistration_date;webshop_address_readonly;\n"""
SHIPPING_ADDRESS_FIELDS = """{customer_id};{title};{first_name};{last_name};{institute};{department};{room};{customer_name};{address_line1};{country};{pincode};{city};{email};;;;;{person_id};;{address_type};;;{salutation};{group_leader};;;;{is_punchout_user};{punchout_buyer};{punchout_identifier};{newsletter_registration_state};{newsletter_registration_date};{newsletter_unregistration_date};{webshop_address_readonly};"""

def export_shipping_address(filename, person_id):
    """
    This function will create a shipping address export file from ERP to Gecko
    """
    # create file
    f = open(filename, "w")
    # write header
    f.write(SHIPPING_ADDRESS_HEADER)
    # get applicable records
    sql_query = """SELECT 
           `tabContact`.`name` AS `person_id`,
           `tabCustomer`.`name` AS `customer_id`,
           `tabCustomer`.`customer_name` AS `customer_name`,
           `tabContact`.`first_name` AS `first_name`,
           `tabContact`.`last_name` AS `last_name`,
           `tabContact`.`email_id` AS `email`,
           `tabAddress`.`overwrite_company` AS `overwrite_company`,
           `tabAddress`.`address_line1` AS `address_line1`,
           `tabAddress`.`pincode` AS `pincode`,
           `tabAddress`.`city` AS `city`,
           `tabContact`.`institute` AS `institute`,
           `tabContact`.`department` AS `department`,
           `tabCountry`.`code` AS `country`,
           "" AS `ds_nr`,
           `tabAddress`.`address_type` AS `address_type`,
           `tabCustomer`.`tax_id` AS `vat_nr`,
           `tabCustomer`.`siret` AS `siret`,
           `tabCustomer`.`ext_debitor_number` AS `ext_debitor_number`,
           `tabCustomer`.`default_currency` AS `currency`,
           `tabCustomer`.`invoice_email` AS `invoice_email`, 
           `tabCustomer`.`disabled` AS `is_deleted`,
           `tabPrice List`.`general_discount` AS `default_discount`,
           0 AS `is_electronic_invoice`,
           0 AS `receive_updates_per_email`,
           0 AS `is_punchout_user`,
           `tabCustomer`.`punchout_identifier` AS `punchout_identifier`,
           `tabCustomer`.`punchout_shop` AS `punchout_shop_id`,
           `tabContact`.`room` AS `room`,
           `tabContact`.`salutation` AS `salutation`,
           `tabContact`.`designation` AS `title`,
           `tabContact`.`group_leader` AS `group_leader`,
           NULL AS `email_cc`,
           `tabContact`.`phone` AS `phone_number`,
           NULL AS `phone_country`,
           `tabContact`.`institute_key` AS `institute_key`,
           `tabContact`.`receive_newsletter` AS `newsletter_registration_state`,
           `tabContact`.`subscribe_date` AS `newsletter_registration_date`,
           `tabContact`.`unsubscribe_Date` AS `newsletter_unregistration_date`,
           NULL AS `umr_nr`,
           `tabCustomer`.`invoicing_method` AS `invoicing_method`,
           `tabUser`.`username` AS `sales_manager`,
           `tabContact`.`phone` AS `phone`
        FROM `tabContact`
        LEFT JOIN `tabDynamic Link` AS `tDLA` ON `tDLA`.`parent` = `tabContact`.`name` 
                                              AND `tDLA`.`parenttype`  = "Contact" 
                                              AND `tDLA`.`link_doctype` = "Customer"
        LEFT JOIN `tabCustomer` ON `tabCustomer`.`name` = `tDLA`.`link_name` 
        LEFT JOIN `tabAddress` ON `tabContact`.`address` = `tabAddress`.`name`
        LEFT JOIN `tabPrice List` ON `tabPrice List`.`name` = `tabCustomer`.`default_price_list`
        LEFT JOIN `tabUser` ON `tabCustomer`.`account_manager` = `tabUser`.`name`
        LEFT JOIN `tabCountry` ON `tabCountry`.`name` = `tabAddress`.`country`
        WHERE `tabContact`.`name` = {contact_name}
    """.format(contact_name=person_id)
    data = frappe.db.sql(sql_query, as_dict=True)
    for d in data:       
        # Do not change the order. Changes will corrupt import into Gecko.
        # Only append new lines.
        row = SHIPPING_ADDRESS_FIELDS.format(
            person_id = replace_none(d['person_id']),
            customer_id = replace_none(d['customer_id']),
            customer_name = d['overwrite_company'] if d['overwrite_company'] else replace_none(d['customer_name']),
            first_name = "" if d['first_name'] == "-" else replace_none(d['first_name']),
            last_name = replace_none(d['last_name']),
            email = replace_none(d['email']),
            address_line1 = replace_none(d['address_line1']),
            pincode = replace_none(d['pincode']),
            city = replace_none(d['city']),
            institute = replace_none(d['institute']),
            department = replace_none(d['department']),
            country = replace_none((d['country'])).upper(),
            DS_Nr = replace_none(d['ds_nr']),
            address_type = replace_none("INV" if (d["address_type"]=="Billing") else "DEL"),
            vat_nr = replace_none(d['vat_nr']),
            siret = replace_none(d['siret']),
            currency = replace_none(d['currency']),
            is_deleted = replace_none(d['is_deleted']),
            default_discount = replace_none(d['default_discount']),
            is_electronic_invoice = replace_none(d['is_electronic_invoice']),
            receive_updates_per_email = replace_none(d['receive_updates_per_email']),
            is_punchout_user = replace_none(d['is_punchout_user']),
            punchout_identifier = replace_none(d['punchout_identifier']),
            punchout_shop_id = replace_none(d['punchout_shop_id']),
            punchout_buyer = "",
            room = replace_none(d['room']),
            salutation = replace_none(d['salutation']),
            title = replace_none(d['title']),
            group_leader = replace_none(d['group_leader']),
            email_cc = replace_none(d['email_cc']),
            phone_number = replace_none(d['phone_number']),
            phone_country = replace_none(d['phone_country']),
            institute_key = replace_none(d['institute_key']),
            receive_newsletter = "",
            newsletter_registration_state = replace_none(d['newsletter_registration_state']),
            newsletter_registration_date = replace_none(d['newsletter_registration_date']),
            newsletter_unregistration_date = replace_none(d['newsletter_unregistration_date']),
            webshop_address_readonly = "",
            umr_nr = replace_none(d['umr_nr']),
            invoicing_method = replace_none(d['invoicing_method']),
            sales_manager = replace_none(d['sales_manager']),
            ext_debitor_number = replace_none(d['ext_debitor_number']),
            invoice_email = replace_none(d['invoice_email']),
            phone = replace_none(d['phone'])
        )
        f.write(row)
    # close file
    f.close()
    return

@frappe.whitelist()
def export_contact_to_gecko(contact_name):
    shipping_address_file = "/mnt/erp_share/Gecko/Export_Customer_Data/Shipping/shipping_address_export_for_gecko.tab"
    if os.path.exists(shipping_address_file):
        frappe.throw("<b>Export file already exists:</b><br>" + shipping_address_file)
    else:    
        export_shipping_address(shipping_address_file, contact_name)
        frappe.msgprint("Exported for Gecko")
    return

def update_customer(customer_data):
    """
    This function will update a customer master (including contact & address)

    The function will either accept one customer_data record or a list of the same
    """
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
        if not frappe.db.exists("Customer", customer_data['customer_id']) and not customer_data['customer_name']: # or not customer_data['address_line1']:
            error = "Mandatory field customer_name missing, skipping ({0})".format(customer_data)
            print(error)
            return

        # country locator
        country = None
        if 'country' in customer_data:
            country = robust_get_country(customer_data['country'])
        if not country and 'addresses' in customer_data:
            for a in customer_data['addresses']:
                # only consider primary address (billing address) for country
                if 'country' in a and a.get('is_primary_address', False):
                    country = robust_get_country(a['country'])
                    if country:
                        break        
        
        
        # check if the customer exists
        if not frappe.db.exists("Customer", customer_data['customer_id']):
            # create customer (force mode to achieve target name)
            print("Creating customer {0}...".format(str(int(customer_data['customer_id']))))
            
            default_company = frappe.get_value("Country", country, "default_company")
            frappe.db.sql("""INSERT INTO `tabCustomer` 
                            (`name`, `customer_name`, `default_company`, `default_currency`, `default_price_list`, `payment_terms`) 
                            VALUES ("{0}", "{1}", "{2}", "{3}", "{4}", "{5}");""".format(
                            str(int(customer_data['customer_id'])), 
                            str(customer_data['customer_name']),
                            default_company,
                            frappe.get_value("Country", country, "default_currency"),
                            frappe.get_value("Country", country, "default_pricelist"),
                            frappe.get_value("Company", default_company, "payment_terms")))
        
        if 'is_deleted' in customer_data:
            if customer_data['is_deleted'] == "Ja" or str(customer_data['is_deleted']) == "1":
                is_deleted = 1
            else:
                is_deleted = 0
        else:
            is_deleted = 0

        # update customer
        customer = frappe.get_doc("Customer", customer_data['customer_id'])
        print("Updating customer {0}...".format(customer.name))
        if 'customer_name' in customer_data:
            customer.customer_name = customer_data['customer_name']
        if 'address_type' in customer_data:
            address_type = customer_data['address_type']
        else:
            address_type = None
        if address_type == "INV":
            if frappe.db.exists("Contact", customer_data['person_id']):     # 2022-09-14. only link valid contacts
                customer.invoice_to = str(customer_data['person_id'])
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
        if 'ext_debitor_number' in customer_data:
            customer.ext_debitor_number = customer_data['ext_debitor_number']
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
        # set invoice_email
        if address_type != "DEL":                                           # 2022-10-03 Do not update 'invoice_email' with Gecko mail of shipping address.
            if 'invoice_email' in customer_data:
                customer.invoice_email = customer_data['invoice_email']
        
        if 'default_company' in customer_data:
            companies = frappe.get_all("Company", filters={'abbr': customer_data['default_company']}, fields=['name'])
            if len(companies) > 0:
                customer.default_company = companies[0]['name']
        if 'punchout_shop_id' in customer_data:
            customer.punchout_buyer = customer_data['punchout_shop_id']
        if 'punchout_buyer' in customer_data:
            customer.punchout_buyer = customer_data['punchout_buyer']
        # fallback in case there is no default company
        if not customer.default_company:
            # fetch default company from country list
            if country:
                customer.default_company = frappe.get_value("Country", country, "default_company")
            
        # extend customer bindings here
        customer.flags.ignore_links = True				# ignore links (e.g. invoice to contact that is imported later)
        customer.save(ignore_permissions=True)       
        
        # update address
        address_name = update_address(customer_data, is_deleted=is_deleted)     # base address
        if 'addresses' in customer_data:
            # multiple addresses:
            _contact_address = None
            for adr in customer_data['addresses']:
                _address_name = update_address(adr, is_deleted=is_deleted, customer_id=customer_data['customer_id'])
            
                if _address_name == customer_data['person_id']:     #Link address with same ID than the contact ID
                    _contact_address = _address_name

            if not address_name:
                if _contact_address:
                    address_name = _contact_address
                else:
                    address_name = _address_name
                
        # update contact
        
        # check if contact exists (force insert onto target id)
        if not frappe.db.exists("Contact", str(int(customer_data['person_id']))):
            print("Creating contact {0}...".format(str(int(customer_data['person_id']))))
            frappe.db.sql("""INSERT INTO `tabContact` 
                            (`name`, `first_name`, `status`) 
                            VALUES ("{0}", "{1}", "Open");""".format(
                            str(int(customer_data['person_id'])), customer_data['first_name']))
        # update contact
        print("Updating contact {0}...".format(str(int(customer_data['person_id']))))
        contact = frappe.get_doc("Contact", str(int(customer_data['person_id'])))
        contact.first_name = customer_data['first_name'] if 'first_name' in customer_data and customer_data['first_name'] else "-"
        contact.last_name = customer_data['last_name'] if 'last_name' in customer_data and customer_data['last_name'] else None
        contact.full_name = "{first_name}{spacer}{last_name}".format(first_name=contact.first_name, spacer = " " if contact.last_name else "", last_name=contact.last_name or "")
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
                'link_name': customer_data['customer_id']
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
        if 'contact_address' in customer_data and frappe.db.exists("Address", customer_data['contact_address']):
            contact.address = customer_data['contact_address']
        # extend contact bindings here
        contact.save(ignore_permissions=True)
        
        frappe.db.commit()

        # some more administration
        configure_customer(customer.name)
    return error

def update_contact(contact_data):
    """
    Update or create a contact record. If no first_name is provided, set it to "-".

    Note: 
    Does not initializes the status "Open", in contrast to the update_customer function.
    This, to differentiate between contacts originating from punchout orders and conventional registrations
    """
    if not 'person_id' in contact_data:
        return None

    if 'first_name' in contact_data and contact_data['first_name'] and contact_data['first_name'] != "":
        first_name = contact_data['first_name']
    else:
        first_name = "-"

    # check if contact exists (force insert onto target id)
    if not frappe.db.exists("Contact", contact_data['person_id']):
        print("Creating contact {0}...".format(contact_data['person_id'] ))
        frappe.db.sql("""INSERT INTO `tabContact` 
                        (`name`, `first_name`) 
                        VALUES ("{0}", "{1}");""".format(
                        contact_data['person_id'], contact_data['first_name']))

    # Update record
    contact = frappe.get_doc("Contact", contact_data['person_id'])
    # TODO Update data
    # copy code from update_customer
    contact.first_name = first_name
    contact.last_name = contact_data['last_name'] if 'last_name' in contact_data and contact_data['last_name'] else None
    contact.full_name = "{first_name}{spacer}{last_name}".format(first_name=contact.first_name, spacer = " " if contact.last_name else "", last_name=contact.last_name or "")
    if 'institute' in contact_data:
        contact.institute = contact_data['institute'] 
    if 'department' in contact_data:
        contact.department = contact_data['department']
    contact.email_ids = []
    if 'email' in contact_data and contact_data['email']:
        contact.append("email_ids", {
            'email_id': contact_data['email'],
            'is_primary': 1
        })
    if 'email_cc' in contact_data and contact_data['email_cc']:
        contact.append("email_ids", {
            'email_id': contact_data['email_cc'],
            'is_primary': 0
        })
    contact.phone_nos = []
    if 'phone_number' in contact_data and contact_data['phone_number']:
        if 'phone_country' in contact_data:
            number = "{0} {1}".format(contact_data['phone_country'] or "", 
                contact_data['phone_number'])
        else:
            number = "{0}".format(contact_data['phone_number'])
        contact.append("phone_nos", {
            'phone': number,
            'is_primary_phone': 1
        })
    contact.links = []
    # if not is_deleted:
    if 'customer_id' in contact_data:
        contact.append("links", {
            'link_doctype': "Customer",
            'link_name': contact_data['customer_id']
        })
    if 'institute_key' in contact_data:
        contact.institute_key = contact_data['institute_key']
    if 'group_leader' in contact_data:
        contact.group_leader = contact_data['group_leader']    
    if 'address' in contact_data:
        contact.address = contact_data['address']
    if 'salutation' in contact_data and contact_data['salutation']:
        if not frappe.db.exists("Salutation", contact_data['salutation']):
            frappe.get_doc({
                'doctype': 'Salutation',
                'salutation': contact_data['salutation']
            }).insert()
        contact.salutation = contact_data['salutation']
    if 'title' in contact_data:
        contact.designation = contact_data['title']
    if 'receive_updates_per_email' in contact_data and contact_data['receive_updates_per_email'] == "Mailing":
        contact.unsubscribed = 0
    else:
        contact.unsubscribed = 1
    if 'room' in contact_data:
        contact.room = contact_data['room']
    if 'punchout_identifier' in contact_data:
        contact.punchout_identifier = contact_data['punchout_identifier']
    if 'newsletter_registration_state' in contact_data:
        if contact_data['newsletter_registration_state'] == "registered":
            contact.receive_newsletter = "registered"
        elif contact_data['newsletter_registration_state'] == "unregistered":
            contact.receive_newsletter = "unregistered"
        elif contact_data['newsletter_registration_state'] == "pending":
            contact.receive_newsletter = "pending"
        elif contact_data['newsletter_registration_state'] == "bounced":
            contact.receive_newsletter = "bounced"
        else:
            contact.receive_newsletter = ""
    if 'newsletter_registration_date' in contact_data:
        try:
            contact.subscribe_date = datetime.fromisoformat(contact_data['newsletter_registration_date'])
        except:
            try:
                contact.subscribe_date = datetime.strptime(contact_data['newsletter_registration_date'], "%d.%m.%Y %H:%M:%S")
            except:
                # fallback date only 
                try:
                    contact.subscribe_date = datetime.strptime(contact_data['newsletter_registration_date'], "%d.%m.%Y")
                except:
                    frappe.throw(":-(")
                    print("failed to parse subscription date: {0}".format(contact_data['newsletter_registration_date']))
    if 'newsletter_unregistration_date' in contact_data:
        try:
            contact.unsubscribe_date = datetime.fromisoformat(contact_data['newsletter_unregistration_date'])
        except:
            try:
                contact.unsubscribe_date = datetime.strptime(contact_data['newsletter_unregistration_date'], "%d.%m.%Y %H:%M:%S")
            except:
                # fallback date only 
                try:
                    contact.unsubscribe_date = datetime.strptime(contact_data['newsletter_unregistration_date'], "%d.%m.%Y")
                except:
                    print("failed to parse unsubscription date: {0}".format(contact_data['newsletter_unregistration_date']))
    if 'contact_address' in contact_data and frappe.db.exists("Address", contact_data['contact_address']):
        contact.address = contact_data['contact_address']

    try:
        # contact.save(ignore_permissions=True)
        contact.save(ignore_permissions=True)
        return contact.name
    except Exception as err:
        print("Failed to save contact: {0}".format(err))
        frappe.log_error("Failed to save contact: {0}".format(err))
        return None


def update_address(address_data, is_deleted=False, customer_id=None):
    """
    Processes data to update an address record
    """
    #frappe.log_error(address_data)
    if not 'person_id' in address_data:
        return None
    if not 'address_line1' in address_data:
        return None

    print("Updating address {0}...".format(str(int(address_data['person_id']))))
    # check if address exists (force insert onto target id)
    if not frappe.db.exists("Address", str(int(address_data['person_id']))):
        print("Creating address {0}...".format(str(int(address_data['person_id']))))
        frappe.db.sql("""INSERT INTO `tabAddress` 
                        (`name`, `address_line1`) 
                        VALUES ("{0}", "{1}");""".format(
                        str(int(address_data['person_id'])), 
                        address_data['address_line1'] if 'address_line1' in address_data else "-"))

    # update record
    if 'address_type' in address_data:
        address_type = address_data['address_type']
    else:
        address_type = None
    address = frappe.get_doc("Address", str(int(address_data['person_id'])))
    if 'customer_name' in address_data and 'address_line1' in address_data:
        address.address_title = "{0} - {1}".format(address_data['customer_name'], address_data['address_line1'])
    if 'overwrite_company' in address_data:
        address.overwrite_company = address_data['overwrite_company']
    if 'address_line1' in address_data:
        address.address_line1 = address_data['address_line1']
    if 'address_line2' in address_data:
        address.address_line2 = address_data['address_line2']
    if 'pincode' in address_data:
        address.pincode = address_data['pincode']
    if 'city' in address_data:
        address.city = address_data['city']
    if 'country' in address_data:
        address.country = robust_get_country(address_data['country'])
    if customer_id or 'customer_id' in address_data:
        address.links = []
        if not is_deleted:
            address.append("links", {
                'link_doctype': "Customer",
                'link_name': customer_id or address_data['customer_id']
            })
    # get type of address
    if address_type == "INV" or address_type == "Billing":
        address.is_primary_address = 1
        address.is_shipping_address = 0
        # address.email_id = address_data['email']        # invoice address: pull email also into address record. 
                                                           # Do not write to invoice_mail to address record anymore. 2022-10-03 Rolf Suter
        address.address_type = "Billing"
    else:
        address.is_primary_address = 0
        address.is_shipping_address = 1
        address.address_type = "Shipping"
    
    # Overwrite is_primary_address and is_shipping_address if provided with the input data
    if 'is_primary_address' in address_data:
        address.is_primary_address = address_data['is_primary_address']
    if 'is_shipping_address' in address_data:
        address.is_shipping_address = address_data['is_shipping_address']

    if 'customer_address_id' in address_data:
        address.customer_address_id = address_data['customer_address_id']

    # extend address bindings here

    try:
        address.save(ignore_permissions=True)
        return address.name
    except Exception as err:
        print("Failed to save address: {0}".format(err))
        frappe.log_error("Failed to save address: {0}".format(err))
        return None


def robust_get_country(country_name_or_code):
    """
    Robust country find function: accepts country name or code
    """
    if frappe.db.exists("Country", country_name_or_code):
        return country_name_or_code
    else:
        # check if this is an ISO code match
        countries = frappe.get_all("Country", filters={'code': (country_name_or_code or "NA").lower()}, fields=['name'])
        if countries and len(countries) > 0:
            return countries[0]['name']
        else:
            return frappe.defaults.get_global_default('country')
            
def import_prices(filename):
    """
    This function imports/updates the item price data from a CSV file

    Run from bench like
    $ bench execute microsynth.microsynth.migration.import_prices --kwargs "{'filename': '/home/libracore/frappe-bench/apps/microsynth/microsynth/docs/articleExport_with_Header.txt'}"
    """
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

def update_prices(price_data):
    """
    This function will update item prices
    """
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

def import_discounts(filename):
    """
    This function imports/updates the discount conditions from a CSV file

    Columns are customer_id\titem_code\tdiscount_percent
    Run from bench like
    $ bench execute microsynth.microsynth.migration.import_discounts --kwargs "{'filename': '/home/libracore/frappe-bench/apps/microsynth/microsynth/docs/discountExport.tab'}"
    """
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

def update_pricing_rule(price_data):
    """
    This function will update pricing rules
    """
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

def import_customer_price_lists(filename):
    """
    Import customer price list

    Headers (\t): PriceList ["1234"], BasisPriceList ["CHF"], GeneralDiscount ["0"], ArticleCode, Discount

    Run from bench like
    $ bench execute microsynth.microsynth.migration.import_customer_price_lists --kwargs "{'filename': '/home/libracore/customerPrices.tab'}"
    """
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
                discount = float(row['Discount']),
                qty = row['Quantity']
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

def map_customer_price_list(filename):
    """
    Map customer price lists to customers

    Headers (\t): PriceList ["1234"], Customer ["1234"]

    Run from bench like
    $ bench execute microsynth.microsynth.migration.map_customer_price_list --kwargs "{'filename': '/home/libracore/customerPrices.tab'}"
    """
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

def populate_price_lists():
    """
    Go through all price lists and populate missing prices

    Run from bench like
    bench execute microsynth.microsynth.migration.populate_price_lists
    """
    price_lists = frappe.db.sql("""
        SELECT `name`
        FROM `tabPrice List`
        WHERE `reference_price_list` IS NOT NULL
        AND `enabled` = 1;""", as_dict=True)
    count = 0
    start_ts = None
    for p in price_lists:
        count += 1
        start_ts = datetime.now()
        print("Updating {0}... ({1}%)".format(p['name'], int(100 * count / len(price_lists))))
        populate_from_reference(price_list=p['name'])
        print("... {0} sec".format((datetime.now() - start_ts).total_seconds()))
    return

def clean_price_lists():
    """
    Go through all price lists and clean up conflicting prices

    Run from bench like
    $ bench execute microsynth.microsynth.migration.clean_price_lists
    """
    from microsynth.microsynth.report.pricing_configurator.pricing_configurator import clean_price_list

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
        clean_price_list(price_list=p['name'])
        print("... {0} sec".format((datetime.now() - start_ts).total_seconds()))
    return

def move_staggered_item_price(filename):
    """
    Move item price from staggered item to base item

    Run from bench like
    $ bench execute microsynth.microsynth.migration.move_staggered_item_price --kwargs "{'filename': '/home/libracore/staggered_prices.tab'}"
    """
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

def set_webshop_address_readonly():
    """ 
    Sets the "webshop_address_readonly" from the contacts
    This is used that users cannot change a jointly used customer/address

    Run from
    $ bench execute microsynth.microsynth.migration.set_webshop_address_readonly
    """
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


def disable_customers_without_contacts():
    """
    Sets the customer field "disabled" for all customers that do not have any contacts.

    Run from
    $ bench execute microsynth.microsynth.migration.disable_customers_without_contacts
    """
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
        if len(linked_contacts) == 0:
            customer = frappe.get_doc("Customer", c['name'])
            customer.disabled = True
            try:
                customer.save()
                print("{1}%... Disabled {0}".format(c['name'], int(100 * count / len(customers))))
            except Exception as err:
                print("{2}%... Failed updating {0} ({1})".format(c['name'], err, int(100 * count / len(customers))))
        else:
            print("{1}%... Skipped {0}".format(c['name'], int(100 * count / len(customers))))
    return


from erpnextswiss.scripts.crm_tools import get_primary_customer_address 

def set_default_company():
    customers = frappe.get_all("Customer", filters={'default_company': ''}, fields=['name'])    
    print(len(customers))
    
    count = 0
    i = 0
    for c in customers:
        count += 1
        i += 1
        
        address = get_primary_customer_address(c["name"])

        if address:
            default_company = frappe.get_value("Country", address.country, "default_company")
            customer = frappe.get_doc("Customer", c["name"])
            if not customer.default_company:
                customer.default_company = default_company
                customer.save()
            
        
        if i > 100:
            frappe.db.commit()
            i = 0

        print(count)

    return

# # refactor to a dict
# def get_item_from_service(service):
#     if service == 0:
#         return '3040'
#     elif service == 1:
#         return '3000'
#     elif service == 2:
#         return '3110'
#     elif service == 3:
#         return '3100'
#     elif service == 4:
#         return None
#     elif service == 5:
#         return None
#     elif service == 6:
#         return None
#     elif service == 7:
#         return '3200'
#     elif service == 8:
#         return '3240'
#     elif service == 9:
#         return '3236'
#     elif service == 10:
#         return '3251'
#     elif service == 11:
#         return '3050'
#     elif service == 12:
#         return '3120'
#     else:
#         return None

SERVICE_ITEM = {
    0: '3040',
    1: '3000',
    2: '3110',
    3: '3100',   
    7: '3200',
    8: '3240',
    9: '3236',
    10: '3251',
    11: '3050',
    12: '3120',
}

# # refactor to a dict 
# def get_label_status_from_status_id(status_id):
#     if status_id == 0:
#         return 'unknown'
#     elif status_id == 1:
#         return 'unused'
#     elif status_id == 2:
#         return 'unused'
#     elif status_id == 3:
#         return 'submitted'
#     elif status_id == 4:
#         return 'received'
#     elif status_id == 5:
#         return 'processed'
#     else:
#         return None

LABEL_STATUS = {
    0: 'unknown',
    1: 'unused',
    2: 'unused',
    3: 'submitted',
    4: 'received',
    5: 'processed'
}


def set_default_payment_terms():
    """
    Populate the customer field 'payment_terms' with the default company value if not set.

    Run from
    $ bench execute microsynth.microsynth.migration.set_default_payment_terms
    """

    companies = frappe.get_all("Company", fields=['name', 'payment_terms'])
    company_terms = {}

    for company in companies:
        key = company['name']
        company_terms[key] = company['payment_terms']
  
    customers = frappe.get_all("Customer", filters={'disabled': 0}, fields=['name'])
    
    def get_name(customer):
        return customer.get('name')
    
    i = 0
    count = 0
    for c in sorted(customers, key=get_name):
        
        customer = frappe.get_doc("Customer", c["name"])

        if not customer.default_company :
            print("Default company is not set for customer '{0}'.".format(c.name))
            continue

        if customer.payment_terms is None:
            print("edit customer '{0}' {1}%".format(customer.name, int(100 * count / len(customers))))
            customer.payment_terms = company_terms[customer.default_company]
            customer.save()
        else:
            print("customer '{0} 'has alread the terms: '{1}' {2}%".format(customer.name, customer.payment_terms, int(100 * count / len(customers))))
        
        i += 1
        count += 1
        
        if i >= 10:
            frappe.db.commit()
            i = 0

    frappe.db.commit()


def set_default_language_for_customers():
    """
    Populate the customer field 'language' with the default value.

    Run from
    bench execute microsynth.microsynth.migration.set_default_language
    """
    from microsynth.microsynth.utils import set_default_language

    customers = frappe.get_all("Customer", filters={'disabled': 0}, fields=['name'])
    
    def get_name(customer):
        return customer.get('name')
    
    i = 0
    length = len(customers)
    for c in sorted(customers, key=get_name):
        print("{1}% - process customer '{0}'".format(c, int(100 * i / length)))
        set_default_language(c.name)
        i += 1

    return


def import_sequencing_labels(filename, skip_rows = 0):
    """
    Imports the sequencing barcode labels from a webshop export file.

    Webshop database query:

    SELECT b.[Id]
      ,[Number]
      ,[UseState]
      ,[BarcodeKind]
      ,[ServiceType]
      ,[Discriminator]
      ,[Purchaser_Id]
      ,[RegisteredTo_Id]
      ,[RegisteredToGroup_Id]
	  ,p.IdPerson as purchaser_person_id
	  ,r.IdPerson as registered_to_person_id
    FROM [Webshop].[dbo].[Barcodes] b
    LEFT JOIN AspNetUsers p on p.id = b.Purchaser_Id
    LEFT JOIN AspNetUsers r on r.id = b.RegisteredTo_Id

    Run
    $ bench execute "microsynth.microsynth.migration.import_sequencing_labels" --kwargs "{'filename':'/mnt/erp_share/Sequencing/Label_Import/webshop_barcodes_unused.txt', 'skip_rows':0}"
    """

    with open(filename) as file:
        header = file.readline()
        count = 1
        i = 0
        for line in file:
            if count > skip_rows:
                start = datetime.now()

                elements = line.split("\t")
                number = int(elements[1])
                status_element = int(elements[2])
                service_type = int(elements[4])
                contact_element = elements[9].strip()
                registered_to_element = elements[10].strip()
                            
                item = SERVICE_ITEM[service_type]
                
                # if the 'UseState' is 2, set the 'registered' flag
                registered = status_element == 2

                # # check if contact exists
                # if contact_element == "NULL":
                #     contact = None
                # elif frappe.db.exists("Contact", int(contact_element)):
                #     contact = int(contact_element)
                # else:
                #     print("Could not find Contact '{0}'.".format(contact_element))
                #     contact = None

                # # find customer
                # if contact:
                #     contact_doc = frappe.get_doc("Contact", contact)
                #     # print(contact_doc.links[0].link_name)
                #     if len(contact_doc.links) > 0 and contact_doc.links[0].link_doctype == "Customer":
                #         customer = contact_doc.links[0].link_name
                #     else:
                #         customer = None
                # else:
                #     customer = None

                # # check if registered_to contact exists:
                # if registered_to_element == "NULL":
                #     registered_to = None
                # elif frappe.db.exists("Contact", int(registered_to_element)):
                #     registered_to = int(registered_to_element)
                # else:
                #     print("Could not find Registered-to-Contact '{0}'.".format(contact_element))
                #     registered_to = None
                
                label_name = find_label(number, item)

                # t1 = datetime.now() - start
                # print(t1)

                # check if label exists
                if not label_name:
                    # create new label
                    label = frappe.get_doc({
                        'doctype': 'Sequencing Label',
                        'label_id': number,
                        'item': item,
                    })
                else:
                    label = frappe.get_doc("Sequencing Label", label_name)

                # set values
                label.contact = contact_element if contact_element != "NULL" else None
                # label.customer = customer
                label.registered = registered
                label.registered_to = registered_to_element if registered_to_element != "NULL" else None
                label.status = LABEL_STATUS[status_element]

                label.flags.ignore_links = True
                label.save()

                if i >= 100:
                    print("commit")
                    frappe.db.commit()
                    i = 0

                # t2 = datetime.now() - start
                # print(t2)

                print("{0}: {1}".format(count, number))
            
            count += 1
            i += 1

        frappe.db.commit()

    return




def create_credit_import_journal_entry(sales_invoice):
    """
    Create a journal entry.

    run
    bench execute "microsynth.microsynth.migration.create_credit_import_journal_entry" --kwargs "{'sales_invoice':'SI-BAL-23000132'}"
    """

    sales_invoice = frappe.get_doc("Sales Invoice", sales_invoice)

    journal_entry = frappe.get_doc({
        'doctype': 'Journal Entry',
        'company': sales_invoice.company,
        'posting_date': sales_invoice.posting_date,
        'user_remark': "Import credit for customer '{0}'".format(sales_invoice.customer),
        'multi_currency': 1
    })
    journal_entry.append('accounts', {
        'account': sales_invoice.debit_to,
        'reference_type': 'Sales Invoice',
        'reference_name': sales_invoice.name,
        'credit_in_account_currency': sales_invoice.outstanding_amount,
        'party_type': 'Customer',
        'party': sales_invoice.customer
    })
    journal_entry.append('accounts', {
        'account': frappe.get_value("Company", sales_invoice.company, "default_cash_account"),
        'debit_in_account_currency': sales_invoice.base_grand_total
    })
    journal_entry.insert()
    journal_entry.submit()


def create_credit_import_sales_invoice(company, customer, currency, total):
    """
    run
    bench execute "microsynth.microsynth.migration.create_credit_import_sales_invoice" --kwargs "{'company': 'Microsynth AG', 'customer': '1257', 'currency': 'CHF', 'total':42}"
    """
    from microsynth.microsynth.utils import get_alternative_account

    if flt(total) <= 0:
        # frappe.log_error("Total credit for Customer '{0}' is '{1}'".format(customer, total), "create_credit_import_sales_invoice")
        return

    customer = frappe.get_doc("Customer", customer)

    if customer.disabled:
        frappe.log_error("Cannot import credit for customer '{0}' because the customer is disabled".format(customer.name), "create_credit_import_sales_invoice")
        return

    if customer.default_currency != currency:
        frappe.log_error("Cannot import credit for customer '{0}' because currency of credit acccount does not match the customer default currency".format(customer.name), "create_credit_import_sales_invoice")
        return

    # select naming series
    naming_series = get_naming_series("Sales Invoice", company)

    tax_templates = {
        "Microsynth AG": "BAL Export (220) - BAL",
        "Microsynth Austria GmbH": "Austria IG - WIE",
        "Microsynth France SAS": "France IG - LYO",
        "Microsynth Seqlab GmbH": "German IG - GOE",
        "Ecogenics GmbH":"Export (220) - ECO"
    }
    sales_invoice = frappe.get_doc({
        'doctype': 'Sales Invoice',
        'company': company,
        'naming_series': naming_series,
        'customer': customer.name,
        'currency': currency,
        'set_posting_time': True,
        'posting_date': "2022-12-31",
        'taxes_and_charges': tax_templates[company]
    })
    item_detail = {
        'item_code': '6100',
        'qty': 1,
        'rate': total
    }
    sales_invoice.append('items', item_detail)
    sales_invoice.insert()

    sales_invoice.items[0].income_account = get_alternative_account(sales_invoice.items[0].income_account, currency)

    sales_invoice.submit()

    create_credit_import_journal_entry(sales_invoice.name)

    return


def import_credit_accounts(filename):
    """
    Import the credit accounts from a tab file

    run
    bench execute "microsynth.microsynth.migration.import_credit_accounts" --kwargs "{'filename':'/mnt/erp_share/Test_Guthaben_Microsynth_AG_NETTO_31.12.2022.txt'}"
    """

    with open(filename) as file:
        header = file.readline()
        i = 0
        for line in file:
            elements = line.split("\t")
            company = elements[0]
            customer = elements[2]
            currency = elements[1].upper()
            total = elements[6]
            print("Import: {0}\t{1}".format(customer, total))
            create_credit_import_sales_invoice(company, customer, currency, total)
            i += 1
            # if i > 5:
            #     break

def set_distributor_carlo_erba():
    """
    Adds to all customers of the distributor 'Carlo Erba' the distributor settings 
    for 'Sequencing' and 'Labels' 

    run 
    bench execute "microsynth.microsynth.migration.set_distributor_carlo_erba" 
    """    
    from microsynth.microsynth.utils import set_distributor

    customers = frappe.db.get_all("Customer",
        filters = {'account_manager': 'servizioclienticer@dgroup.it' },
        fields = ['name'])

    i = 0
    length = len(customers)

    for c in customers:
        print("{1}% - process customer '{0}'".format(c, int(100 * i / length)))
        set_distributor(c.name, 35914214, "Sequencing" )
        set_distributor(c.name, 35914214, "Labels" )
        frappe.db.commit()

        i += 1

    return


def set_distributor_amplikon():
    """
    run
    bench execute microsynth.microsynth.migration.set_distributor_amplikon
    """
    from microsynth.microsynth.utils import get_customers_for_country, set_distributor

    customers = get_customers_for_country("Hungary")

    i = 0
    length = len(customers)
    for c in customers:
        customer = frappe.get_doc("Customer", c)
        
        print("{2}% - Update customer '{0}' '{1}'".format(customer.name, customer.customer_name, int(100 * i / length)))

        customer.default_price_list = "hu_Amplikon_standard"
        customer.save()

        set_distributor(customer.name, 832700, "Oligos")
        set_distributor(customer.name, 832700, "Sequencing")
        set_distributor(customer.name, 832700, "Labels")
        frappe.db.commit()

        i += 1


def activate_fullplasmidseq_dach():
    """
    run
    bench execute microsynth.microsynth.migration.activate_fullplasmidseq_dach
    """
    from microsynth.microsynth.utils import add_webshop_service

    query = """
        SELECT DISTINCT
            `tDLA`.`link_name` AS `name`
        FROM `tabAddress`
        LEFT JOIN `tabDynamic Link` AS `tDLA` ON `tDLA`.`parent` = `tabAddress`.`name`
                                             AND `tDLA`.`parenttype` = "Address"
                                             AND `tDLA`.`link_doctype` = "Customer"
        WHERE `tabAddress`.`country` in (
            "Switzerland", 
            "Germany", 
            "Austria" )
        AND `tDLA`.`link_name` IS NOT NULL
    """

    customers = frappe.db.sql(query, as_dict=True)
    
    i = 0
    length = len(customers)

    for c in customers:
        print("{1}% - process customer '{0}'".format(c.name, int(100 * i / length)))
        add_webshop_service(c.name, "FullPlasmidSeq")
        frappe.db.commit()
        i += 1

    return


def activate_fullplasmidseq_all_customers():
    """
    run
    bench execute microsynth.microsynth.migration.activate_fullplasmidseq_all_customers
    """
    from microsynth.microsynth.utils import add_webshop_service

    customers = frappe.db.get_all("Customer",
        filters = {'disabled': 0 },
        fields = ['name'])
    
    i = 0
    length = len(customers)

    for c in customers:
        print("{1}% - process customer '{0}'".format(c.name, int(100 * i / length)))
        add_webshop_service(c.name, "FullPlasmidSeq")
        frappe.db.commit()
        i += 1

    return


def set_debtors():
    """
    Set the debitor account

    run 
    bench execute microsynth.microsynth.migration.set_debtors
    """    
    from microsynth.microsynth.utils import set_debtor_accounts

    customers = frappe.db.get_all("Customer",
        filters = {'disabled': 0 },
        fields = ['name'])

    i = 0
    length = len(customers)

    for c in customers:
        print("{1}% - process customer '{0}'".format(c, int(100 * i / length)))
        
        try:
            set_debtor_accounts(c.name)
        except Exception as err:
            frappe.log_error("Could not set debtors for customer '{0}'\n{1}".format(c.name, err), "migration.set_debtors")

        i += 1
    return


def set_territory_for_customers():
    """
    Set the territory

    run 
    bench execute microsynth.microsynth.migration.set_territory_for_customers
    """    
    from microsynth.microsynth.utils import set_territory
    
    customers = frappe.db.get_all("Customer",
        filters = {'disabled': 0 },
        fields = ['name'])

    i = 0
    length = len(customers)

    for c in customers:
        print("{1}% - process customer '{0}'".format(c.name, int(100 * i / length)))
        
        try:
            set_territory(c.name)
            frappe.db.commit()
        except Exception as err:
            frappe.log_error("Could not set territory for customer '{0}'\n{1}".format(c.name, err), "migration.set_territory_for_customers")

        i += 1
    return


def remove_item_account_settings():
    """
    Set the debitor account

    run 
    bench execute microsynth.microsynth.migration.remove_item_account_settings
    """

    items = frappe.db.get_all("Item",
        fields = ['name'])

    i = 0
    length = len(items)

    for item_name in items:
        item = frappe.get_doc("Item", item_name)

        if item.item_code == "6100":
            continue
        
        print("{progress}% remove account settings of item '{item}'".format(item = item.item_code, progress = int(100 * i / length)))

        for entry in item.item_defaults:
            entry.income_account = None

        item.save()

        i += 1

    return


def check_sales_order_samples(sales_order):
    """

    run
    bench execute microsynth.microsynth.migration.check_sales_order_samples --kwargs "{'sales_order': 'SO-BAL-22010736'}"
    """
    sales_order = frappe.get_doc("Sales Order", sales_order)
    
    query = """
        SELECT 
            `tabSample`.`name`,
            `tabSample`.`sequencing_label`
        FROM `tabSample Link`
        LEFT JOIN `tabSample` ON `tabSample Link`.`sample` = `tabSample`.`name`
        WHERE
            `tabSample Link`.`parent` = "{sales_order}"
            AND `tabSample Link`.`parenttype` = "Sales Order"
    """.format(sales_order = sales_order.name)

    samples = frappe.db.sql(query, as_dict=True)

    missing_labels = False
    
    for s in samples:
        if s.sequencing_label is None:
            missing_labels = True

    # print("missing labels: {0}".format(missing_labels))
    might_be_invoiced = True

    if missing_labels: 
        for item in sales_order.items:
            if item.item_code not in [ '0901', '0904', '3235', '3237', '0968', '0969', '0975']:
                # print(item.item_code)
                might_be_invoiced = False

        if might_be_invoiced:
            print(sales_order.name)

    return


def find_invoices_of_unprocessed_samples():
    """
    The seqblatt.check_sales_order_completion function created delivery notes of 
    sales orders where the samples had not no sequencing label linked. 
    These deliverye notes were invoiced
    
    run
    bench execute microsynth.microsynth.migration.find_invoices_of_unprocessed_samples
    """

    sales_orders = frappe.db.get_all("Sales Order",
        filters={'product_type': 'Sequencing'},
        fields = ['name'] )

    i = 0
    length = len(sales_orders)
    print(length)

    for order in sales_orders:
        # print("{progress}% check sales order '{so}'".format(so = order.name, progress = int(100 * i / length)))
        check_sales_order_samples(order.name)
        
        # if i > 5:
        #     return
        
        i += 1

    return


def tag_documents_by_web_id(file, tag):
    """
    Tag Sales Orders, Delivery Notes and Sales Invoices if they are in relation with a web order id given with the file.

    run
    bench execute microsynth.microsynth.migration.tag_documents_by_web_id --kwargs "{'file':'/mnt/erp_share/Invoices/tag_invoices.txt', 'tag': 'invoiced'}"
    """

    web_orders = []

    with open(file) as file:
        # header = file.readline()    
        for line in file:
            elements = line.split("\t")

            web_order_id = int("".join(d for d in elements[0] if d.isdigit()))
            web_orders.append(web_order_id)

    i = 0
    length = len(web_orders)
    for o in web_orders:
        print("{progress}% process web id '{id}'".format(id = o, progress = int(100 * i / length)))
        tag_linked_documents(web_order_id = o, tag = tag)
        frappe.db.commit()
        i += 1

    return


def check_sales_invoices(import_file, export_file):
    """
    run
    bench execute microsynth.microsynth.migration.check_sales_invoices --kwargs "{'import_file':'/mnt/erp_share/Invoices/Paynet/2023-06-02_PostFinance_invoices_not_sent_2.txt', 'export_file': '/mnt/erp_share/Invoices/invoices.txt'}"
    """

    invoices = []
    with open(import_file) as file:
        for line in file:
            invoices.append(line.strip())

    file.close()

    with open(export_file, "w") as export_file:

        for invoice in invoices:
            si = frappe.get_doc("Sales Invoice", invoice)

            if si.is_punchout and si.product_type != "Sequencing":
                export_file.write("{0}\r\n".format(si.name))

                print("{0}\t{1}\t{2}\t{3}\t{4}".format(
                    si.name,
                    si.is_punchout,
                    si.punchout_shop,
                    si.customer,
                    si.product_type))

    export_file.close()


def set_reminder_to(contact, customer, email):
    """
    run
    bench execute microsynth.microsynth.migration.set_reminder_to --kwargs "{'contact': '71921', 'customer': '8003', 'email': 'reminder@mail.ch'}"
    """

    if not frappe.db.exists("Contact", contact):
        return

    contact = frappe.get_doc("Contact", contact)
    customer = frappe.get_doc("Customer", customer)

    # Validation
    if contact.name != customer.invoice_to:
        print("Contact '{0}' is not invoice_to contact of customer {1}".format(contact.name, customer.name))
        return

    for link in contact.links:
        if link.link_name != customer.name:
            print("Contact '{0}' does not belong to customer {1}".format(contact.name, customer.name))
            return

    if email != contact.email_id:
        new = contact.as_dict()
        new['person_id'] = contact.name + "-R"
        new['email'] = email
        new['customer_id'] = customer.name
        update_contact(new)

        customer.reminder_to = new['person_id']
    else:
        customer.reminder_to = contact.name
    customer.save()

    return


def import_reminder_emails(file):
    """
    run
    bench execute microsynth.microsynth.migration.import_reminder_emails --kwargs "{'file': '/mnt/erp_share/Gecko/Import_Customer_Data/Reminder_to/reminder_2023-06-13_filtered.tab'}"
    """

    tasks = []

    with open(file) as file:
        for line in file:
            if line.strip() != "":
                elements = line.split("\t")
         
                task = {}
                task['contact'] = elements[0].strip()
                task['customer'] = elements[1].strip()
                task['email'] = elements[2].strip()
                tasks.append(task)

    length = len(tasks)
    i = 0
    for task in tasks:
        print("{progress} process {contact}, {customer}, {email}".format(
            contact = task['contact'],
            customer = task['customer'], 
            email = task['email'],
            progress = int(100 * i / length)))

        set_reminder_to(task['contact'], task['customer'], task['email'])
        frappe.db.commit()
        i += 1


def refactor_date(date_str):
    """
    Reformat a date from DD.MM.YYYY to YYYY-MM-DD
    """
    parts = date_str.split(".")
    return f"{parts[2]}-{parts[1]}-{parts[0]}"


def import_contact_notes(file):
    """
    This function reads every line as a customer.
	:param file_name: name of the TSV file with five columns
    :returns a dict with key = contact ID (person ID)
    
    run
    bench execute microsynth.microsynth.migration.import_contact_notes --kwargs "{'file': '/mnt/erp_share/Gecko/CustomerVisits_edited.tab'}"
    """    
    counter = 0
    with open(file) as tsv:
        for line in csv.reader(tsv, delimiter="\t"):  # it's important to split lines exactly at CR LF (Windows encoding)
            assert len(line) == 5
            contact_note = frappe.get_doc({
                'doctype': 'Contact Note',
                'contact_person': line[1],  # line[1] should be the person ID (contact ID)
                'date': refactor_date(line[3]) if len(line[3]) > 0 else datetime.now(),
                'contact_note_type': "Other",
                'notes': line[4]
            })
            contact_note.save()
            counter += 1
            if counter % 100 == 0:
                print(f"Already imported {counter} contact notes. Still running ...")
    print(f"Imported {counter} contact notes in total.")


def process_sample(sample):
    label_name = frappe.get_value("Sample", sample, "sequencing_label")
    label = frappe.get_doc("Sequencing Label", label_name)
    label.status = "received"
    label.save()
    return


def process_open_sequening_orders(customer):
    """
    Sets the Sequencing Label status of all a samples of the
    open orders to 'received'.

    run
    bench execute microsynth.microsynth.migration.process_open_sequening_orders --kwargs "{'customer':'37497378'}"
    """
    query = """
        SELECT `name`
        FROM `tabSales Order`
        WHERE 
          `customer` = '{customer}'
          AND `docstatus` = 1
          AND `status` NOT IN ("Closed", "Completed")
          AND `product_type` = "Sequencing"
          AND `per_delivered` < 100;
    """.format(customer=customer)

    open_orders = frappe.db.sql(query, as_dict=True)

    for o in open_orders:
        order = frappe.get_doc("Sales Order", o['name'])
        print("process {0}".format(order.name))
        for s in order.samples:
            process_sample(s.sample)
    return


def update_territory(dt, dn, territory):
    query = """UPDATE `tab{dt}`
        SET `territory` = "{territory}"
        WHERE `name` = "{dn}"
    """.format(dt=dt, dn=dn, territory=territory)
    frappe.db.sql(query)    
    return


def update_territories():
    """
    run
    bench execute microsynth.microsynth.migration.update_territories
    """

    sales_invoice_query = """
    SELECT `tabSales Invoice`.`name`, `tabCustomer`.`territory` 
    FROM `tabSales Invoice` 
    LEFT JOIN `tabCustomer` ON `tabCustomer`.`name` = `tabSales Invoice`.`customer` 
    WHERE `tabSales Invoice`.`territory` LIKE "All%";"""

    sales_invoices = frappe.db.sql(sales_invoice_query, as_dict=True)

    i = 0
    length = len(sales_invoices)
    for si in sales_invoices:
        print("{progress}% process '{dn}'".format(dn = si['name'], progress = int(100 * i / length)))
        update_territory("Sales Invoice", si['name'], si['territory'])
        frappe.db.commit()
        i += 1


def revise_delivery_note(delivery_note):
    """
    run
    bench execute microsynth.microsynth.migration.revise_delivery_note --kwargs "{'delivery_note': 'DN-BAL-23142611'}"
    """
    from microsynth.microsynth.utils import find_tax_template
    
    original = frappe.get_doc("Delivery Note", delivery_note)
    original.cancel()

    new = frappe.get_doc(original.as_dict())
    new.name = None
    new.docstatus = 0
    new.set_posting_time = 1
    new.amended_from = original.name
    new.creation = datetime.now()

    if new.product_type == "Oligos" or new.product_type == "Material":
        category = "Material"
    else:
        category = "Service"
    if new.oligos is not None and len(new.oligos) > 0:
        category = "Material"

    tax_template = find_tax_template(new.company, new.customer, new.shipping_address_name, category)
    new.taxes_and_charges = tax_template
    
    tax_template = frappe.get_doc("Sales Taxes and Charges Template", new.taxes_and_charges)
    new.taxes = []
    for tax in tax_template.taxes:
        t = {
            'charge_type': tax.charge_type,
            'account_head': tax.account_head,
            'description': tax.description,
            'cost_center': tax.cost_center,
            'rate': tax.rate
        }    
        new.append("taxes", t)

    new.insert()
    new.submit()
    
    return


def remove_hold_invoice_flag(delivery_note):
    """
    run
    bench execute microsynth.microsynth.migration.remove_hold_invoice_flag --kwargs "{'delivery_note': 'DN-BAL-23116237-1'}"
    """
    delivery_note = frappe.get_doc("Delivery Note", delivery_note)
    sales_order_name = delivery_note.items[0].against_sales_order
    so = frappe.get_doc("Sales Order", sales_order_name)
    so.hold_invoice = 0
    so.save()


def revise_delivery_notes_with_missing_taxes():
    """
    run
    bench execute microsynth.microsynth.migration.revise_delivery_notes_with_missing_taxes
    """
    query = """
    SELECT `name`, `web_order_id`, `status`, `net_total`
    FROM `tabDelivery Note` 
    WHERE `docstatus` < 2
    AND `grand_total` = `net_total` 
    AND `taxes_and_charges` LIKE "%7.7%" 
    AND `net_total` > 0
    AND `status` <> 'Completed';
    """

    delivery_notes = frappe.db.sql(query, as_dict=True)

    i = 0
    length = len(delivery_notes)
    for dn in delivery_notes:
        print("{progress}% process '{dn}'".format(dn = dn['name'], progress = int(100 * i / length)))
        revise_delivery_note(dn['name'])
        remove_hold_invoice_flag(dn['name'])
        frappe.db.commit()
        i += 1


def reopen_sales_order(sales_order):
    """
    run
    bench execute microsynth.microsynth.migration.reopen_sales_order --kwargs "{'sales_order': 'SO-BAL-22004889'}"
    """
    so = frappe.get_doc("Sales Order", sales_order)
    so.update_status("Draft")


def close_draft_delivery_note_and_sales_order(delivery_note):
    """
    run
    bench execute.microsynth.microsynth.migration.close_draft_delivery_note_and_sales_order --kwargs "{'delivery_note':''}"
    """
    delivery_note = frappe.get_doc("Delivery Note", delivery_note)
    
    # get affected sales orders
    sales_orders = []
    for item in delivery_note.items:
        if item.against_sales_order not in sales_orders:
            sales_orders.append(item.against_sales_order)
    
    # re-open sales order if it is closed
    for so in sales_orders:
        so = frappe.get_doc("Sales Order", so)
        if so.status == "Closed":
            so.update_status("Draft")
    
    # submit and close delivery note
    delivery_note.submit()
    delivery_note.update_status("Closed")

    # close sales order
    for so in sales_orders:
        so = frappe.get_doc("Sales Order", so)
        so.update_status("Closed")


def close_invoiced_draft_delivery_notes():
    """
    run
    bench execute microsynth.microsynth.migration.close_invoiced_draft_delivery_notes
    """
    import traceback
    
    query = """
        SELECT `name`, `docstatus`, `status`
        FROM `tabDelivery Note`
        WHERE `_user_tags` LIKE "%invoiced%"
        AND `docstatus` = 0
    """

    delivery_notes = frappe.db.sql(query, as_dict=True)
    
    i = 0
    length = len(delivery_notes)
    for dn in delivery_notes:
        try:
            print("{progress}% process '{dn}': {status}".format(dn = dn['name'], status = dn['status'], progress = int(100 * i / length)))
            close_draft_delivery_note_and_sales_order(dn['name'])
            frappe.db.commit()
        
        except Exception as err:
            msg = "Failed to close delivery note {0}:\n{1}\n{2}".format(dn, err, traceback.format_exc())
            print(msg)
            frappe.log_error(msg, "close_invoiced_draft_delivery_notes")
        i += 1


def close_sales_order_of_delivery_note(delivery_note):
    """
    run
    bench execute.microsynth.microsynth.migration.close_sales_order_of_delivery_note --kwargs "{'delivery_note':''}"
    """
    delivery_note = frappe.get_doc("Delivery Note", delivery_note)
    
    # close delivery note if necessary
    if delivery_note.status != "Closed":
        delivery_note.update_status("Closed")

    # get affected sales orders
    sales_orders = []
    for item in delivery_note.items:
        if item.against_sales_order not in sales_orders:
            sales_orders.append(item.against_sales_order)

    # close sales order if necessary
    for so in sales_orders:
        so = frappe.get_doc("Sales Order", so)
        if so.status != "Closed":
            so.update_status("Closed")


def close_orders_of_closed_delivery_notes():
    """
    run
    bench execute microsynth.microsynth.migration.close_orders_of_closed_delivery_notes
    """
    import traceback

    query = """
        SELECT `name`, `docstatus`, `status`
        FROM `tabDelivery Note`
        WHERE `status` = "Closed"
    """

    delivery_notes = frappe.db.sql(query, as_dict=True)
    
    i = 0
    length = len(delivery_notes)
    for dn in delivery_notes:
        try:
            print("{progress}% process '{dn}': {status}".format(dn = dn['name'], status = dn['status'], progress = int(100 * i / length)))
            close_sales_order_of_delivery_note(dn['name'])
            frappe.db.commit()
        
        except Exception as err:
            msg = "Failed to close order of delivery note {0}:\n{1}\n{2}".format(dn, err, traceback.format_exc())
            print(msg)
            frappe.log_error(msg, "close_orders_of_closed_delivery_notes")
        i += 1
    print("processed delivery notes:")
    print(len(delivery_notes))


def assess_income_account_matrix(from_date, to_date, auto_correct=0):
    """
    This function will assess the impact of the account matrix in a given period

    Run as
    bench execute microsynth.microsynth.migration.assess_income_account_matrix --kwargs "{'from_date': '2023-02-01', 'to_date': '2023-02-28'}"
    """
    invoices = frappe.db.sql("""
        SELECT `name` 
        FROM `tabSales Invoice`
        WHERE `docstatus` = 1
          AND `posting_date` BETWEEN "{from_date}" AND "{to_date}";
        """.format(from_date=from_date, to_date=to_date), as_dict=True)
    
    deviation_count = 0
    skipped_count = 0
    for invoice in invoices:
        doc = frappe.get_doc("Sales Invoice", invoice.get('name'))
        if doc.base_grand_total > 0:        # skip returns and 0-sums
            
            correct_accounts = get_income_accounts(doc.shipping_address_name, doc.currency, doc.items)
        
            for i in range(0, len(doc.items)):
                if doc.items[i].income_account != correct_accounts[i]:
                    print("{doc} ({status}): item {i}: {o} -> {c}".format(
                        doc=doc.name, i = i, o=doc.items[i].income_account, c=correct_accounts[i], status=doc.status))
                    deviation_count += 1
                    
                    if auto_correct:
                        correct_income_account(doc.name)
                        
                    break
        
        else:
            skipped_count += 1
            
    print("Checked {0} invoices, {1} deviations and {2} skipped".format(len(invoices), deviation_count, skipped_count))


def correct_income_account(sales_invoice):
    """
    This function will cancel an invoice, amend it, correct the income accounts an map the payment if applicable
    """
    
    # get old invoice
    old_doc = frappe.get_doc("Sales Invoice", sales_invoice)
    if old_doc.docstatus > 1:
        print("already cancelled")
        return
    # find payment entries
    if old_doc.is_return == 0:
        payments = frappe.db.sql("""
            SELECT `voucher_type`, `voucher_no`, `credit_in_account_currency` AS `credit`
            FROM `tabGL Entry`
            WHERE 
                `account` = "{debit_to}"
                AND `against_voucher` = "{sales_invoice}"
                AND `credit` > 0;
            """.format(debit_to=old_doc.debit_to, sales_invoice=sales_invoice), as_dict=True)
    else:
        payments = []
    
    # check if there is a return on this invoice
    credit_notes = False
    for p in payments:
        if p.get('voucher_type') == "Sales Invoice":
            # this is a credit note
            credit_notes = True
            credit_note = frappe.get_doc("Sales Invoice", p.get('voucher_no'))
            credit_note.cancel()
    
    if credit_notes:
        # reload, because cancellation of credit note will change timestamp of invoice
        frappe.db.commit()
        old_doc = frappe.get_doc("Sales Invoice", sales_invoice)
        
    old_doc.cancel()
    frappe.db.commit()
    
    # create amended invoice
    new_doc = frappe.get_doc(old_doc.as_dict())
    new_doc.name = None
    new_doc.docstatus = 0
    new_doc.set_posting_time = 1
    new_doc.amended_from = old_doc.name
    
    # correct income accounts
    correct_accounts = get_income_accounts(new_doc.shipping_address, new_doc.currency, new_doc.items)
    for i in range(0, len(new_doc.items)):
        new_doc.items[i].income_account = correct_accounts[i]
                        
    # pull payments
    for p in payments:
        if p.get('voucher_type') != "Sales Invoice":
            new_doc.append("advances", {
                'reference_type': p.get('voucher_type'),
                'reference_name': p.get('voucher_no'),
                'advance_amount': p.get('credit'),
                'allocated_amount': p.get('credit')
            })
    
    # insert and submit
    new_doc.insert()
    new_doc.submit()
    frappe.db.commit()
    
    # if applicable: amend credit notes
    for p in payments:
        if p.get('voucher_type') == "Sales Invoice":
            old_cn = frappe.get_doc("Sales Invoice", p.get('voucher_no'))
            # create amended credit note
            new_cn = frappe.get_doc(old_cn.as_dict())
            new_cn.name = None
            new_cn.docstatus = 0
            new_cn.set_posting_time = 1
            new_cn.amended_from = old_cn.name
            new_cn.return_against = new_doc.name
            
            # correct income accounts
            correct_accounts = get_income_accounts(new_cn.shipping_address, new_cn.currency, new_cn.items)
            for i in range(0, len(new_cn.items)):
                new_cn.items[i].income_account = correct_accounts[i]
            new_cn.insert()
            new_cn.submit()
    
    frappe.db.commit()
    return
    

def correct_invoicing_email():
    """
    Corrects Customer.invoice_to in case Customer.invoice_email differs from email_id of the contact linked in Customer.invoice_to due to changes of Lars.
    Belonging to Task #11328 KB ERP.
    The Customer ID list in the SQL query was created via ERP frontend -> Sales Invoice -> report ->
        Filter: Sales Invoice.exclude_from_payment_reminder = 21.08.2023; no company filter! -> Export

    Run from bench
    $ bench execute microsynth.microsynth.migration.correct_invoicing_email
    """
    sql_query = """SELECT 
            `tabCustomer`.`name` AS customer_name,
            `invoice_email`,
            `tabContact`.`email_id`,
            `tabContact`.`name` AS contact_name
        FROM `tabCustomer`
        LEFT JOIN `tabContact` ON `tabContact`.`name` = `tabCustomer`.`invoice_to`
        WHERE `tabCustomer`.`invoice_email` <> `tabContact`.`email_id`
        AND `tabCustomer`.`name` in (
                SELECT DISTINCT `tabSales Invoice`.`customer`
                FROM `tabSales Invoice`
                WHERE `exclude_from_payment_reminder_until` = '2023-08-21')
        ORDER BY `tabContact`.`name`;
    """
    query_results = frappe.db.sql(sql_query, as_dict=True)

    for result in query_results:
        contact = frappe.get_doc("Contact", result['contact_name'])
        new_contact = contact.as_dict()  # see def set_reminder_to
        if "-B" in contact.name:
            print(f"Warning: there is already a contact {contact.name}, going to create {contact.name}-B ...")
        new_contact['person_id'] = contact.name + "-B"
        # new_contact['email_id'] = result['invoice_email']  # should be done manually by Administration
        new_contact['customer_id'] = result['customer_name']
        new_contact['email'] = contact.email_id
        update_contact(new_contact)  # phone, receive_newsletter, subscribe_date, unsubscribe_date, cost_center not saved
        customer = frappe.get_doc("Customer", result['customer_name'])
        customer.invoice_to = new_contact['person_id']
        customer.save()



