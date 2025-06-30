# -*- coding: utf-8 -*-
# Copyright (c) 2022-2024, libracore (https://www.libracore.com) and contributors
# For license information, please see license.txt

from email.policy import default
import os
import frappe
from frappe import _
import pandas as pd
import numpy as np
import json
from frappe.utils import cint, flt, get_url_to_form
from datetime import datetime, timedelta
from microsynth.microsynth.naming_series import get_naming_series
from microsynth.microsynth.utils import find_label, get_sql_list, configure_territory, configure_sales_manager, tag_linked_documents, replace_none, configure_customer, get_alternative_account, get_alternative_income_account, add_webshop_service, get_customer
from microsynth.microsynth.invoicing import get_income_accounts
from erpnextswiss.scripts.crm_tools import get_primary_customer_address
from erpnextswiss.scripts.crm_tools import get_primary_customer_contact
import re
import sys
import csv
csv.field_size_limit(sys.maxsize)

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
            if customer_data['invoicing_method'] in ["Post", "Paynet", "Email", "ARIBA", "Carlo ERBA", "GEP", "Chorus", "X-Rechnung", "Scientist"]:
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
    if 'status' in contact_data:
        contact.status = contact_data['status']

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
    if 'has_webshop_account' in contact_data and contact_data['has_webshop_account'] is not None:
        contact.has_webshop_account = contact_data['has_webshop_account']
    if 'source' in contact_data:
        contact.source = contact_data['source']
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

    # check if address exists (force insert onto target id)
    if not frappe.db.exists("Address", address_data['person_id']):
        print("Creating address {0}...".format(address_data['person_id']))
        frappe.db.sql("""INSERT INTO `tabAddress`
                        (`name`, `address_line1`)
                        VALUES ("{0}", "{1}");""".format(
                        address_data['person_id'],
                        address_data['address_line1'] if 'address_line1' in address_data else "-"))
    print("Updating address {0}...".format(address_data['person_id']))

    # update record
    if 'address_type' in address_data:
        address_type = address_data['address_type']
    else:
        address_type = None
    address = frappe.get_doc("Address", address_data['person_id'])
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
    if 'source' in address_data:
        address.source = address_data['source']
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
    Sets the Customer field "disabled" for all Customers that do not have any non-Billing Contacts.
    Does only disable Customers with a numeric ID and no Quotation, no Sales Order,
    no Delivery Note and no Sales Invoice (Cancelled documents are ignored).

    Run from
    bench execute microsynth.microsynth.migration.disable_customers_without_contacts
    """
    customers = frappe.get_all("Customer", filters={'disabled': 0}, fields=['name'])
    disabled = failed = skipped = 0
    customers_to_report = []

    for count, c in enumerate(customers):
        # find number of linked contacts
        linked_contacts = frappe.db.sql("""
            SELECT `tabContact`.`name` AS `name`
            FROM `tabContact`
            LEFT JOIN `tabDynamic Link` AS `tDLA` ON `tDLA`.`parent` = `tabContact`.`name`
                                              AND `tDLA`.`parenttype`  = "Contact"
                                              AND `tDLA`.`link_doctype` = "Customer"
            LEFT JOIN `tabCustomer` ON `tabCustomer`.`name` = `tDLA`.`link_name`
            LEFT JOIN `tabAddress` ON `tabContact`.`address` = `tabAddress`.`name`
            WHERE `tDLA`.`link_name` = "{customer_id}"
                AND `tabContact`.`status` != "Disabled"
                AND `tabAddress`.`address_type` != "Billing"
        """.format(customer_id=c['name']), as_dict=True)

        if len(linked_contacts) == 0 and c['name'].isnumeric():  # disable only customers with numeric names (created by the webshop)
            quotations = frappe.get_all("Quotation", filters=[['docstatus', '<', '2'], ['party_name', '=', c['name']]], fields=['name'])
            sales_orders = frappe.get_all("Sales Order", filters=[['docstatus', '<', '2'], ['customer', '=', c['name']]], fields=['name'])
            delivery_notes = frappe.get_all("Delivery Note", filters=[['docstatus', '<', '2'], ['customer', '=', c['name']]], fields=['name'])
            sales_invoices = frappe.get_all("Sales Invoice", filters=[['docstatus', '<', '2'], ['customer', '=', c['name']]], fields=['name'])

            if len(quotations) != 0 or len(sales_orders) != 0 or len(delivery_notes) != 0 or len(sales_invoices) != 0:
                skipped += 1
                url_string = f"<a href={get_url_to_form('Customer', c['name'])}>{c['name']}</a>"
                message = f"Customer {url_string} has no shipping contacts and {len(quotations)} Quotations, {len(sales_orders)} Sales Orders, {len(delivery_notes)} Delivery Notes and {len(sales_invoices)} Sales Invoices."
                #print(message)
                customers_to_report.append(message)
                continue

            customer = frappe.get_doc("Customer", c['name'])
            customer.disabled = True
            try:
                customer.save()
            except Exception as err:
                #print(f"{int(100 * count / len(customers))}%... Failed updating {c['name']} ({err})")
                failed += 1
            else:
                #print(f"{int(100 * count / len(customers))}% ({count}/{len(customers)})... Successfully disabled {c['name']}")
                disabled += 1
        else:
            skipped += 1
            #print("{1}%... Skipped {0}".format(c['name'], int(100 * count / len(customers))))
    #print(f"Disabled {disabled} Customers, failed {failed} times, skipped {skipped} Customers.")
    frappe.db.commit()
    if len(customers_to_report) > 0:
        from microsynth.microsynth.utils import send_email_from_template
        customers_to_report_msg = "<br>".join(customers_to_report)
        email_template = frappe.get_doc("Email Template", "Enabled Customers without a Shipping Address but linked documents")
        rendered_content = frappe.render_template(email_template.response, {'customers_to_report_msg': customers_to_report_msg})
        send_email_from_template(email_template, rendered_content)
        #print(message.replace('<br>', '\n'))


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


def create_credit_import_sales_invoice(company, customer, currency, total, product_type):
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
        'product_type': product_type,
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
            product_type = elements[7]
            print("Import: {0}\t{1}".format(customer, total))
            create_credit_import_sales_invoice(company, customer, currency, total, product_type)
            i += 1
            # if i > 5:
            #     break


def set_distributor_carlo_erba(product_type):
    """
    Adds to all enabled Customers of the distributor 'Carlo Erba'
    the distributor settings for the given Product Type

    run
    bench execute "microsynth.microsynth.migration.set_distributor_carlo_erba" --kwargs "{'product_type': 'FLA'}"
    """
    from microsynth.microsynth.utils import set_distributor

    # if product_type not in ['Oligos', 'Labels', 'Sequencing', 'NGS', 'FLA', 'Project', 'Material', 'Service']:
    #     print(f"Product Type '{product_type}' does not exist.")
    #     return

    customers = frappe.db.get_all("Customer",
        filters = [['disabled', '=', 0], ['account_manager', '=', 'servizioclienticer@dgroup.it']],
        fields = ['name'])

    length = len(customers)

    for i, c in enumerate(customers):
        print(f"{int(100 * i / length)} % - process Customer '{c['name']}'")
        set_distributor(c['name'], 35914214, product_type)
        frappe.db.commit()


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


def set_distributor_ktrade_for_slovakia():
    """
    run
    bench execute microsynth.microsynth.migration.set_distributor_ktrade_for_slovakia
    """
    from microsynth.microsynth.utils import get_customers_for_country, set_distributor_ktrade
    from microsynth.microsynth.credits import has_credits

    ktrade_customer_id = "11007"
    price_list = frappe.get_value("Customer", ktrade_customer_id, "default_price_list")
    print(f"{price_list=}")
    customers = get_customers_for_country("Slovakia")

    i = 0
    length = len(customers)
    for c in customers:
        print(f"{int(100 * i / length)} % - process Customer '{c}'")
        i += 1

        if c == ktrade_customer_id:
            print("Skip K-Trade customer")
            continue
        elif not has_credits(c):
            set_distributor_ktrade(c)
            customer = frappe.get_doc("Customer", c)
            customer.default_price_list = price_list
            customer.save()
            frappe.db.commit()
        else:
            print(f"customer {c} has customer credits - do not set the distributor")


def set_distributor_elincou_for_cyprus():
    """
    run
    bench execute microsynth.microsynth.migration.set_distributor_elincou_for_cyprus
    """
    from microsynth.microsynth.utils import get_customers_for_country, set_distributor_elincou
    from microsynth.microsynth.credits import has_credits

    elincou_customer_id = "837936"
    price_list = frappe.get_value("Customer", elincou_customer_id, "default_price_list")
    print(f"{price_list=}")
    customers = get_customers_for_country("Cyprus")

    for i, c in enumerate(customers):
        print(f"{int(100 * i / len(customers))} % - process Customer '{c}'")

        if c == elincou_customer_id:
            print(f"Skip Elincou Customer {elincou_customer_id}")
            continue
        elif not has_credits(c):
            set_distributor_elincou(c)
            customer = frappe.get_doc("Customer", c)
            customer.default_price_list = price_list
            customer.save()
            frappe.db.commit()
        else:
            print(f"Customer {c} has or had Customer credits - do not set the distributor")


def activate_easyrun(territories):
    """
    Add the Webshop Service "EasyRun" for all enabled Customers with one of the given territories.

    bench execute microsynth.microsynth.migration.activate_easyrun --kwargs "{'territories': ['Rest of Europe (West)', 'Rest of Europe (East)', 'Rest of Europe (PL)']}"
    """
    query = f"""
        SELECT `tabCustomer`.`name`
        FROM `tabCustomer`
        WHERE `tabCustomer`.`disabled` = 0
        AND `tabCustomer`.`territory` IN ({get_sql_list(territories)})
        AND `tabCustomer`.`name` NOT IN (
            SELECT `tabWebshop Service Link`.`parent`
            FROM `tabWebshop Service Link`
            JOIN `tabWebshop Service` ON `tabWebshop Service Link`.`webshop_service` = `tabWebshop Service`.`name`
            WHERE `tabWebshop Service`.`service_name` = 'EasyRun'
            );
        """
    customers = frappe.db.sql(query, as_dict=True)
    print(f"Going to process {len(customers)} Customers ...")
    for i, c in enumerate(customers):
        add_webshop_service(c['name'], 'EasyRun')
        if i % 500 == 0 and i > 0:
            frappe.db.commit()
            print(f"##### INFO: Already processed {i}/{len(customers)} Customers.")


def activate_ecolinightseq(blacklist_companies):
    """
    Add the Webshop Service "EcoliNightSeq" for all enabled Customers that have not a Default Company
    in the given blacklist_companies.

    bench execute microsynth.microsynth.migration.activate_ecolinightseq --kwargs "{'blacklist_companies': ['Microsynth Austria GmbH', 'Ecogenics GmbH']}"
    """
    query = f"""
        SELECT `tabCustomer`.`name`
        FROM `tabCustomer`
        WHERE `tabCustomer`.`disabled` = 0
        AND `tabCustomer`.`default_company` NOT IN ({get_sql_list(blacklist_companies)})
        AND `tabCustomer`.`name` NOT IN (
            SELECT `tabWebshop Service Link`.`parent`
            FROM `tabWebshop Service Link`
            JOIN `tabWebshop Service` ON `tabWebshop Service Link`.`webshop_service` = `tabWebshop Service`.`name`
            WHERE `tabWebshop Service`.`service_name` = 'EcoliNightSeq'
            );
        """
    customers = frappe.db.sql(query, as_dict=True)
    print(f"Going to process {len(customers)} Customers ...")
    for i, c in enumerate(customers):
        add_webshop_service(c['name'], 'EcoliNightSeq')
        if i % 500 == 0 and i > 0:
            frappe.db.commit()
            print(f"##### INFO: Already processed {i}/{len(customers)} Customers.")


def activate_easyrun_italy():
    """
    bench execute microsynth.microsynth.migration.activate_easyrun_italy
    """
    query = """
        SELECT DISTINCT
            `tDLA`.`link_name` AS `name`
        FROM `tabAddress`
        LEFT JOIN `tabDynamic Link` AS `tDLA` ON `tDLA`.`parent` = `tabAddress`.`name`
                                             AND `tDLA`.`parenttype` = "Address"
                                             AND `tDLA`.`link_doctype` = "Customer"
        WHERE `tabAddress`.`country` = "Italy"
        AND `tDLA`.`link_name` IS NOT NULL;"""

    customers = frappe.db.sql(query, as_dict=True)

    for i, customer in enumerate(customers):
        query = f"""
            SELECT DISTINCT `tabAddress`.`country`
            FROM `tabAddress`
            LEFT JOIN `tabDynamic Link` AS `tDLA` ON `tDLA`.`parent` = `tabAddress`.`name`
                                                AND `tDLA`.`parenttype` = "Address"
                                                AND `tDLA`.`link_doctype` = "Customer"
            WHERE `tDLA`.`link_name` = "{customer.name}";"""

        countries = frappe.db.sql(query, as_dict=True)
        only_italy = True
        for country in countries:
            if country['country'] != "Italy":
                print(f"Customer {customer.name} has an address in Italy but also an address in {country['country']}.")
                only_italy = False
                break
        if only_italy:
            add_webshop_service(customer.name, "EasyRun")
    frappe.db.commit()


def activate_directoligoorders_carloerba():
    """
    run
    bench execute microsynth.microsynth.migration.activate_directoligoorders_carloerba
    """
    customers = frappe.db.get_all("Customer",
        filters = [['account_manager', '=', 'servizioclienticer@dgroup.it']],
        fields = ['name', 'customer_name'])
    for customer in customers:
        print(f"process {customer['name']} {customer['customer_name']}")
        add_webshop_service(customer['name'], "DirectOligoOrders")


def activate_fullplasmidseq_dach():
    """
    run
    bench execute microsynth.microsynth.migration.activate_fullplasmidseq_dach
    """
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


def activate_fullplasmidseq_all_customers():
    """
    run
    bench execute microsynth.microsynth.migration.activate_fullplasmidseq_all_customers
    """
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


def activate_invoicebydefaultcompany_france(blacklist_customers):
    """
    bench execute microsynth.microsynth.migration.activate_invoicebydefaultcompany_france --kwargs "{'blacklist_customers': ['35414300', '8003']}"
    """
    customers = frappe.db.get_all("Customer",
        filters = [['disabled', '=', 0], ['territory', 'IN', ['Paris', 'France (Southeast)', 'France (Northwest)']]],
        fields = ['name'])

    for customer in customers:
        if customer['name'] in blacklist_customers:
            continue
        add_webshop_service(customer['name'], 'InvoiceByDefaultCompany')


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


def check_territories():
    """
    bench execute microsynth.microsynth.migration.check_territories
    """
    from microsynth.microsynth.utils import determine_territory, get_first_shipping_address

    customers = frappe.db.get_all("Customer",
        filters = [['disabled', '=', 0]],
        fields = ['name', 'customer_name', 'territory'])

    for cust in customers:
        try:
            address_id = get_first_shipping_address(cust['name'])
            if not address_id:
                print(f"### Found no shipping address for Customer '{cust['name']}' ('{cust['customer_name']}'). Unable to determine Territory.")
                continue
            territory = determine_territory(address_id)
            if not territory:
                continue
            if cust['territory'] != territory.name:
                address = frappe.get_doc("Address", address_id)
                print(f"Customer '{cust['name']}' ('{cust['customer_name']}') has Territory {cust['territory']}, but the first shipping address is in {address.country} ({address.pincode} {address.city}) and the Territory should therefore be {territory.name}.")
        except Exception as err:
            print(f"##### Could not update Territory for Customer '{cust['name']}': {err}")


def determine_countries_of_customer(customer_id):
    query = f"""
            SELECT DISTINCT `tabAddress`.`country`
            FROM `tabAddress`
            LEFT JOIN `tabDynamic Link` AS `tDLA` ON `tDLA`.`parent` = `tabAddress`.`name`
                                                AND `tDLA`.`parenttype` = "Address"
                                                AND `tDLA`.`link_doctype` = "Customer"
            WHERE `tDLA`.`link_name` = "{customer_id}"
            ;"""
    countries = frappe.db.sql(query, as_dict=True)
    return [c['country'] for c in countries]


def check_country_mismatches(customer_doc, countries, allowed_countries):
    country_match = ""
    for country in countries:
        if country in allowed_countries:
            country_match = country
            break
    if country_match:
        country_mismatches = set()
        for country in countries:
            if country not in allowed_countries:
                country_mismatches.add(country)
        if len(country_mismatches) > 0:
            print(f"Customer '{customer_doc.name}' ('{customer_doc.customer_name}') has an Address in {country_match} but also Addresses in {country_mismatches}.")
            country_match = ""
    else:
        print(f"Customer '{customer_doc.name}' ('{customer_doc.customer_name}') has no Address in {allowed_countries}.")
    return country_match


def update_territories_and_sales_managers(current_territories, affected_countries, verbose=False, dry_run=True):
    """
    Update the territories and sales managers for all enabled Customers whose current territory is the given current_territory.

    run
    bench execute microsynth.microsynth.migration.update_territories_and_sales_managers --kwargs "{'current_territories': ['Lyon', 'France (without Paris and Lyon)'], 'affected_countries': ['France', 'Réunion', 'French Guiana'], 'verbose': False, 'dry_run': True}"
    """
    from microsynth.microsynth.utils import determine_territory, get_first_shipping_address

    for current_territory in current_territories:
        if not frappe.db.exists("Territory", current_territory):
            print(f"The given Territory '{current_territory}' does not exist. Please correct and restart.")
            return

    customers = frappe.db.get_all("Customer",
        filters = [['disabled', '=', 0], ['territory', 'IN', current_territories]],
        fields = ['name'])

    for i, cust in enumerate(customers):
        try:
            if i % 100 == 0:
                # print(f"Already processed {i}/{len(customers)} Customers.")
                if not dry_run:
                    frappe.db.commit()
            c = frappe.get_doc("Customer", cust['name'])
            countries = determine_countries_of_customer(c.name)
            if len(countries) < 1:
                print(f"Found no Country for Customer '{c.name}' ('{c.customer_name}'). Going to continue.")
                continue
            country_match = check_country_mismatches(c, countries, affected_countries)
            if not country_match:
                continue
            # all Addresses are in affected_countries
            address_id = get_first_shipping_address(c.name)
            if not address_id:
                print(f"Customer '{c.name}' ('{c.customer_name}') has no Shipping Address. Unable to determine Territory. Going to continue.")
                continue
            territory = determine_territory(address_id)
            if not territory:
                continue
            to_save = False
            if c.territory != territory.name:
                if verbose:
                    print(f"{i+1}/{len(customers)}: Changed Territory of Customer '{c.name}' ('{c.customer_name}') from {c.territory} to {territory.name}.")
                if not dry_run:
                    c.territory = territory.name
                    to_save = True
            sales_manager = frappe.get_value("Territory", territory.name, "sales_manager")
            if c.account_manager != sales_manager:
                if verbose:
                    print(f"{i+1}/{len(customers)}: Changed Sales Manager of Customer '{c.name}' ('{c.customer_name}') from {c.account_manager} to {sales_manager}.")
                if not dry_run:
                    c.account_manager = sales_manager
                    to_save = True
            if to_save:
                c.save()
        except Exception as err:
            print(f"##### {i+1}/{len(customers)}: Could not update Territory for Customer '{c.name}': {err}")
    frappe.db.commit()


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


def overwrite_all_item_defaults():
    """
    Take item_group_defaults from Item Group to item_defaults of Item.

    bench execute microsynth.microsynth.migration.overwrite_all_item_defaults
    """
    from microsynth.microsynth.utils import overwrite_item_defaults
    items = frappe.db.get_all("Item", filters={'disabled': 0}, fields=['name'])

    for i, item in enumerate(items):
        print(f"{int(100 * i / len(items))} % Overwriting Item Defaults for Item '{item['name']}'")
        overwrite_item_defaults(item['name'])
        frappe.db.commit()


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
    assert len(parts) == 3
    return f"{parts[2]}-{parts[1]}-{parts[0]}"


def import_lead_notes(notes_file, contact_note_type):
    """
    This function reads every line as a contact note.
    notes_file: name of the TSV file exported from FM/Gecko
    contact_note_type: type that is set for all imported contact notes (e.g. 'Other', 'Marketing', 'Email')
    See commit 5ec21ed24c11f999c41479c17a54a8345f3448b2 and previous for former version used for non-leads import.

    run
    bench execute microsynth.microsynth.migration.import_lead_notes --kwargs "{'notes_file': '/mnt/erp_share/Gecko/JPe_testing/leads_sales_notes.tab', 'contact_note_type': 'Other'}"
    bench execute microsynth.microsynth.migration.import_lead_notes --kwargs "{'notes_file': '/mnt/erp_share/Gecko/JPe_testing/leads_marketing_notes.tab', 'contact_note_type': 'Marketing'}"
    """
    counter = 0
    with open(notes_file) as tsv:
        print(f"Importing contact notes from {notes_file} with {contact_note_type=} ...")
        csv_reader = csv.reader(tsv, delimiter="\t")
        next(csv_reader)  # skip header
        for line in csv_reader:
            assert len(line) == 2
            if line[1].strip() == '':
                continue  # nothing to do, empty notes
            contact_person = f"L-{line[0]}"
            if not frappe.db.exists("Contact", contact_person):
                print(f"WARNING: Contact '{contact_person}' does not exist. Going to return immediatly. "
                      f"Please make sure that the function create_lead_contacts_addresses was executed before and that the DS_Nr columns match.")
                return
            contact_note = frappe.get_doc({
                'doctype': 'Contact Note',
                'contact_person': contact_person,
                'date': datetime.now(),
                'contact_note_type': contact_note_type,
                'notes': line[1]
            })
            contact_note.save()
            counter += 1
            if counter % 100 == 0:
                print(f"Already imported {counter} contact notes.")
    print(f"Finished: Imported {counter} contact notes in total from {notes_file} with {contact_note_type=}.")


def set_newsletter_dates(contact, registration_date, unregistration_date):
    """
    Set newsletter registration and unregistration date for the given contact.
    """
    if len(registration_date) > 3:  # avoid e.g. '-'
        try:
            contact.subscribe_date = datetime.fromisoformat(registration_date)
        except:
            try:
                contact.subscribe_date = datetime.strptime(registration_date, "%d.%m.%Y %H:%M:%S")
            except:
                # fallback date only
                try:
                    contact.subscribe_date = datetime.strptime(registration_date, "%d.%m.%Y")
                except:
                    print(f"WARNING: Failed to parse newsletter subscription date '{registration_date}'.")
    if len(unregistration_date) > 3:
        try:
            contact.unsubscribe_date = datetime.fromisoformat(unregistration_date)
        except:
            try:
                contact.unsubscribe_date = datetime.strptime(unregistration_date, "%d.%m.%Y %H:%M:%S")
            except:
                # fallback date only
                try:
                    contact.unsubscribe_date = datetime.strptime(unregistration_date, "%d.%m.%Y")
                except:
                    print(f"WARNING: Failed to parse newsletter subscription date '{unregistration_date}'.")


def assign_or_create_customer(contact, address, customer_id, customer_name, counters):
    """
    Takes a contact and address of e.g. a lead.
    Tries to assign it to an existing customer by customer_id.
    If not possible, create a new, disabled Customer.
    """
    if customer_id and frappe.db.exists("Customer", customer_id):
        print(f"Customer '{customer_id}' already exists. Going to assign '{contact.name}' to it.")
        counters[1] += 1
        existing_customer_name = frappe.get_value("Customer", customer_id, "customer_name")
        if existing_customer_name != customer_name:
            print(f"{customer_name=} in FM export does not match existing Customer.customer_name={existing_customer_name}. "
                  f"Going to set Address.overwrite_company to '{customer_name}'.")
            address.overwrite_company = customer_name
            counters[2] += 1
        customer = frappe.get_doc("Customer", customer_id)
        if customer.customer_group is None or customer.customer_group == '':
            customer.customer_group = frappe.get_value("Selling Settings", "Selling Settings", "customer_group")  # mandatory when saving the customer later
            counters[3] += 1
    else:
        customer_id = customer_name
        if not frappe.db.exists("Customer", customer_id):
            # Create a new, disabled Customer
            customer_group = frappe.get_value("Selling Settings", "Selling Settings", "customer_group")  # mandatory when saving the customer later
            #print(f"Creating Customer '{customer_id}' with {customer_group=} ...")
            counters[4] += 1
            frappe.db.sql("""INSERT INTO `tabCustomer`
                            (`name`, `customer_name`, `disabled`, `customer_group`)
                            VALUES ("{0}", "{1}", 1, "{2}");""".format(
                            customer_id, customer_name, customer_group))
        else:
            creation = frappe.get_value("Customer", customer_id, "creation")
            delta = datetime.now() - creation
            if timedelta(minutes=60) < delta:  # assuming that the import does not take longer than 60 minutes
                print(f"########## WARNING: Customer with ID (name) and customer_name '{customer_id}' already existed more than 60 minutes ago. "
                      f"Contact '{contact.name}' is going to be assigned to it.")
                counters[5] += 1

    # link customer_id in Contact and Address (in section Reference: Link DocType = Customer, Link Name = Link Title = customer_id)
    contact.append("links", {
        'link_doctype': "Customer",
        'link_name': customer_id
    })
    address.append("links", {
        'link_doctype': "Customer",
        'link_name': customer_id
    })
    return customer_id


def create_lead_contacts_addresses(fm_export_file):
    """
    Parse FM leads export file, create new contacts and addresses.
    Link customer if existing.

    run
    bench execute microsynth.microsynth.migration.create_lead_contacts_addresses --kwargs "{'fm_export_file': '/mnt/erp_share/Gecko/JPe_testing/leads.tab'}"
    """
    counters = [0]*6  # create six counters
    with open(fm_export_file) as tsv:
        print(f"Importing leads from {fm_export_file} ...")
        csv_reader = csv.reader(tsv, delimiter="\t")
        next(csv_reader)  # skip header
        #line_count = sum(1 for row in csv_reader)
        for line in csv_reader:
            assert len(line) == 35
            assert line[1] == ''  # person_id
            assert line[17] == 'Nein'  # is_deleted

            address_name = f"L-{line[0]}"
            address_line1 = line[7]
            if '"' in address_line1:
                #print(f'WARNING: address_line1 of DS_Nr {line[0]} contains ". Going to delete ".')
                address_line1 = address_line1.replace('"', '')
            if not frappe.db.exists("Address", address_name):
                #print(f"Creating Address {address_name} ...")
                # create new address (this way since address.insert() changes name)
                frappe.db.sql("""INSERT INTO `tabAddress`
                                (`name`, `address_line1`)
                                VALUES ("{0}", "{1}");""".format(
                                address_name, address_line1 if address_line1 else '-'))
            else:
                print(f"Address {address_name} does already exist, going to continue with the next line.")
                continue

            address = frappe.get_doc("Address", address_name)
            address.address_title = f"L-{line[0]}"
            address.pincode = line[8]
            address.city = line[9] if line[9].strip() else '-'
            address.country = robust_get_country(line[12])  # needs to be converted from DE, AT, ES, etc. to Germany, Austria, Spain, etc.

            address_type = line[13]
            if address_type == "INV" or address_type == "Billing":
                address.is_primary_address = 1
                address.is_shipping_address = 0
                address.address_type = "Billing"
            else:
                address.is_primary_address = 0
                address.is_shipping_address = 1
                address.address_type = "Shipping"

            contact_name = f"L-{line[0]}"
            if not frappe.db.exists("Contact", contact_name):
                #print(f"Creating Contact {contact_name} ...")
                # create new contact (this way since contact.insert() changes name)
                frappe.db.sql("""INSERT INTO `tabContact`
                                (`name`, `first_name`)
                                VALUES ("{0}", "{1}");""".format(
                                contact_name, line[4] if line[4] else '-'))
            else:
                print(f"Contact {contact_name} does already exist, going to continue with the next line.")
                continue

            salutation = line[22]
            if salutation.strip() and not frappe.db.exists("Salutation", salutation):
                frappe.get_doc({
                    'doctype': 'Salutation',
                    'salutation': salutation
                }).insert()

            contact = frappe.get_doc("Contact", contact_name)
            contact.last_name = line[5]
            contact.full_name = f"{line[4]}{' ' if line[4] else ''}{line[5]}"
            contact.address = address.name  #f"{address.name}-{address.address_type}",
            contact.salutation = salutation
            contact.designation = line[23]  # title
            contact.institute = line[10]
            contact.department = line[11]
            contact.room = line[21]
            contact.institute_key = line[28]
            contact.group_leader = line[25]
            contact.email_ids = []
            if line[6]:  # email
                contact.append("email_ids", {
                    'email_id': line[6],
                    'is_primary': 1
                })
            if line[25]:  # email_cc
                contact.append("email_ids", {
                    'email_id': line[25],
                    'is_primary': 0
                })
            if line[34] and line[34] != line[6] and line[34] != line[25]:
                contact.append("email_ids", {
                    'email_id': line[34],  # invoice_email
                    'is_primary': 0
                })

            contact.phone_nos = []
            #if line[26] and line[27] == '':
                #print(f"WARNING: phone number '{line[26]}' without any country code for DS_Nr {line[0]}")
            if line[26]:  # phone_number
                contact.append("phone_nos", {
                    'phone': f"{line[27]}{' ' if line[27] else ''}{line[26]}",  # phone_country + phone_number
                    'is_primary_phone': 1
                })

            # newsletter_registration_state
            if line[29] == "registered":
                contact.receive_newsletter = 'registered'
            elif line[29].upper() == "NEIN":
                contact.receive_newsletter = 'unregistered'

            set_newsletter_dates(contact, line[30], line[31])

            customer_id = line[2]
            customer_name = line[3]

            if len(customer_name.strip()) > 0:  # do not create a Customer if customer_name is empty
                # need to be done here since at least the address is necessary to be able to set address.overwrite_company
                customer_id = assign_or_create_customer(contact, address, customer_id, customer_name, counters)

            address.save()
            contact.save()
            frappe.db.commit()

            if len(customer_name.strip()) > 0:
                #set_default_language(customer_id)  # will throw a error if there is no billing address
                configure_territory(customer_id)
                configure_sales_manager(customer_id)
            counters[0] += 1
    print(f"Finished: Imported {counters[0]} leads in total from {fm_export_file}. Thereby, {counters[1]} leads could be assigned to an existing customer by ID "
          f"({counters[2]}x existing_customer_name != customer_name and {counters[3]}x customer.customer_group is None or ''), {counters[4]} Customer are "
          f"created and for {counters[5]} leads, a Customer with ID (name) = customer_name already existed more than 60 minutes ago.")


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
    WHERE `tabSales Invoice`.`territory` <> `tabCustomer`.`territory`;"""

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
    from microsynth.microsynth.taxes import find_dated_tax_template

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

    tax_template = find_dated_tax_template(new.company, new.customer, new.shipping_address_name, category, new.posting_date)
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


def close_delivery_note(delivery_note):
    """
    run
    bench execute microsynth.microsynth.migration.close_delivery_note --kwargs "{'delivery_note':''}"
    """
    delivery_note = frappe.get_doc("Delivery Note", delivery_note)
    if delivery_note.docstatus > 1 or delivery_note.status == 'Closed':
        return

    delivery_note.update_status("Closed")


def close_draft_delivery_note_and_sales_order(delivery_note):
    """
    run
    bench execute microsynth.microsynth.migration.close_draft_delivery_note_and_sales_order --kwargs "{'delivery_note':''}"
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
    bench execute microsynth.microsynth.migration.close_sales_order_of_delivery_note --kwargs "{'delivery_note':''}"
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


def close_tagged_delivery_notes(status, tag):
    """
    run
    bench execute microsynth.microsynth.migration.close_tagged_delivery_notes --kwargs "{'status': 'To Bill', 'tag':'invoiced'}"
    """
    import traceback

    query = f"""
        SELECT `name`, `docstatus`, `status`, `_user_tags`
        FROM `tabDelivery Note`
        WHERE `_user_tags` like "%{tag}%"
        and `status` = "{status}"
    """

    delivery_notes = frappe.db.sql(query, as_dict=True)

    i = 0
    length = len(delivery_notes)

    for dn in delivery_notes:
        try:
            print(f"{int(100 * i / length)}% - process '{dn['name']}': {dn['status']}; Tags: '{dn['_user_tags']}'")
            close_delivery_note(dn['name'])

        except Exception as err:
            msg = "Failed to close delivery note {0}:\n{1}\n{2}".format(dn, err, traceback.format_exc())
            print(msg)
            frappe.log_error(msg, "close_tagged_delivery_notes")
        i += 1
    print(f"Deliver Notes count: {length}")


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

    Important Note:
        This function does not consider links to invoices caused by deduction of customer credits.

    run
    bench execute microsynth.microsynth.migration.correct_income_account --kwargs "{'sales_invoice': 'SI-BAL-23024016'}"
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
    correct_accounts = get_income_accounts(new_doc.shipping_address_name, new_doc.currency, new_doc.items)
    for i in range(0, len(new_doc.items)):
        new_doc.items[i].income_account = correct_accounts[i]

    # pull payments without Credit Notes and link them as 'advance payments' on the new Sales Invoice
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
    frappe.db.commit()
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
            correct_accounts = get_income_accounts(new_cn.shipping_address_name, new_cn.currency, new_cn.items)
            for i in range(0, len(new_cn.items)):
                new_cn.items[i].income_account = correct_accounts[i]
            new_cn.insert()
            new_cn.submit()

    frappe.db.commit()
    return


def correct_invoicing_email():
    """
    Corrects Customer.invoice_to in case Customer.invoice_email differs from email_id of the contact linked in Customer.invoice_to due to changes of Lars.
    Handels only Customers with exactly 1 Contact.

    Belonging to Task #11328 KB ERP.

    Run from bench
    bench execute microsynth.microsynth.migration.correct_invoicing_email
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
        AND
            (SELECT COUNT(*)
            FROM `tabDynamic Link`
            WHERE `tabDynamic Link`.`parenttype` = "Contact"
            AND `tabDynamic Link`.`link_doctype` = "Customer"
            AND `tabDynamic Link`.`link_name` = `tabCustomer`.`name`) = 1

        ORDER BY `tabContact`.`name`;
    """
    query_results = frappe.db.sql(sql_query, as_dict=True)

    for result in query_results:
        contact = frappe.get_doc("Contact", result['contact_name'])
        new_contact = contact.as_dict()  # see def set_reminder_to
        if "-B" in contact.name:
            print(f"Warning: there is already a contact {contact.name}, going to create {contact.name}-B ...")
        new_contact['person_id'] = contact.name + "-B"
        new_contact['customer_id'] = result['customer_name']
        new_contact['email'] = result['invoice_email']
        update_contact(new_contact)  # phone, receive_newsletter, subscribe_date, unsubscribe_date, cost_center not saved
        customer = frappe.get_doc("Customer", result['customer_name'])
        customer.invoice_to = new_contact['person_id']
        customer.save()


def set_missing_invoice_to():
    """
    Find all active Customers with Invoicing Method = "Email"
    but without an entry in the invoice_to field
    that do only have a single Contact and fix them.
    Belonging to Task #13473 KB ERP.

    Run from bench
    $ bench execute microsynth.microsynth.migration.set_missing_invoice_to
    """
    sql_query = """SELECT `tabCustomer`.`name`
        FROM `tabCustomer`
        WHERE `tabCustomer`.`invoicing_method` = 'Email'
        AND `tabCustomer`.`invoice_to` IS NULL
        AND `tabCustomer`.`disabled` = 0
        AND
            (SELECT COUNT(*)
            FROM `tabDynamic Link`
            WHERE `tabDynamic Link`.`parenttype` = "Contact"
            AND `tabDynamic Link`.`link_doctype` = "Customer"
            AND `tabDynamic Link`.`link_name` = `tabCustomer`.`name`) = 1;
    """
    query_results = frappe.db.sql(sql_query, as_dict=True)

    for result in query_results:
        customer = frappe.get_doc("Customer", result['name'])
        # Get the main (primary) contact of Customer
        main_contact = get_primary_customer_contact(result['name'])
        # duplicate main Contact to create the billing contact.
        billing_contact = main_contact.as_dict()
        billing_contact['person_id'] = main_contact.name + "-B"
        # remove all e-mail addresses of the billing contact
        billing_contact['email_ids'] = [None]
        # save the Customer.invoice_email address to billing contact.email_ids[0] (including flag "is_primary")
        billing_contact['email_ids'][0] = customer.invoice_email
        billing_contact.is_primary_address = 1  # billing_contact.set('is_primary_address', True)
        billing_contact['customer_id'] = customer.name
        billing_contact['email'] = main_contact.email_id
        update_contact(billing_contact)
        # link the billing contact to Customer.invoice_to
        customer.invoice_to = billing_contact['person_id']
        customer.save()


def correct_invoice_to_contacts():
    """
    Find Customers that have an Invoice To contact named '%-B' which has a shipping address linked and has a single billing address.
    Link the single billing address to the invoice_to contact.
    This function corrects contacts created with the set_missing_invoice_to
    and the correct_invoicing_email functions.

    run
    bench execute microsynth.microsynth.migration.correct_invoice_to_contacts
    """

    query = """
        SELECT `tabCustomer`.`name` AS `customer`,
            `tabContact`.`name` AS `contact`,
            `tabAddress`.`name` AS `address`
        FROM `tabCustomer`
        LEFT JOIN `tabContact` ON `tabContact`.`name` = `tabCustomer`.`invoice_to`
        LEFT JOIN `tabAddress` ON `tabAddress`.`name` = `tabContact`.`address`
        WHERE `tabAddress`.`address_type` <> 'Billing'
        AND `tabContact`.`name` <> `tabAddress`.`name`
        AND `tabContact`.`name` LIKE '%-B'
        AND CONCAT(`tabAddress`.`name`, '-B') = `tabContact`.`name`
        AND (
                (SELECT COUNT(*)
                FROM `tabDynamic Link`
                LEFT JOIN `tabAddress` ON `tabAddress`.`name` = `tabDynamic Link`.`parent`
                WHERE `tabDynamic Link`.`parenttype` = "Address"
                    AND `tabDynamic Link`.`link_doctype` = "Customer"
                    AND `tabDynamic Link`.`link_name` = `tabCustomer`.`name`
                    AND `tabAddress`.`is_primary_address` = 1
                    AND `tabAddress`.`address_type` = 'Billing'
                    AND (`tabAddress`.`email_id` IS NULL
                        OR `tabAddress`.`email_id` = '')) = 1)
    """
    results = frappe.db.sql(query, as_dict=True)

    i = 0
    length = len(results)
    for result in results:
        # get billing address
        address_query = """
            SELECT `tabDynamic Link`.`parent` AS `address`
            FROM `tabDynamic Link`
            LEFT JOIN `tabAddress` ON `tabAddress`.`name` = `tabDynamic Link`.`parent`
            WHERE `tabDynamic Link`.`parenttype` = "Address"
            AND `tabDynamic Link`.`link_doctype` = "Customer"
            AND `tabDynamic Link`.`link_name` = {customer}
            AND `tabAddress`.`is_primary_address` = 1
            AND `tabAddress`.`address_type` = 'Billing'
            AND (`tabAddress`.`email_id` IS NULL
                OR `tabAddress`.`email_id` = '')
        """.format(customer=result['customer'])
        address_ids = frappe.db.sql(address_query, as_dict=True)
        address_id = address_ids[0]['address']

        contact = frappe.get_doc("Contact", result['contact'])

        print("{progress}% process '{contact}'".format(contact = contact.name, progress = int(100 * i / length)))

        assert '-B' in contact.name

        contact.address = address_id
        contact.save()

        frappe.rename_doc("Contact", contact.name, address_id, merge=False)
        frappe.db.commit()

        print(f"renamed '{contact.name}' to '{address_id}'")
        i += 1
    print(f"processed {i} invoice_to contacts")


def correct_invoice_addresses():
    """
    Correct invoice_to contacts that don't have a billing address.
    Belongs to task #13718 KB ERP.

    run
    bench execute microsynth.microsynth.migration.correct_invoice_addresses
    """
    sql_query = """SELECT `tabCustomer`.`name` AS `customer`,
            `tabContact`.`name` AS `contact`,
            `tabAddress`.`name` AS `address`
        FROM `tabCustomer`
        LEFT JOIN `tabContact` ON `tabContact`.`name` = `tabCustomer`.`invoice_to`
        LEFT JOIN `tabAddress` ON `tabAddress`.`name` = `tabContact`.`address`
        WHERE `tabAddress`.`address_type` <> 'Billing'
        AND `tabAddress`.`name` = `tabContact`.`name`
        -- AND `tabCustomer`.`invoice_email` = `tabContact`.`email_id`
        AND (
                (SELECT COUNT(*)
                FROM `tabDynamic Link`
                LEFT JOIN `tabAddress` ON `tabAddress`.`name` = `tabDynamic Link`.`parent`
                WHERE `tabDynamic Link`.`parenttype` = "Address"
                    AND `tabDynamic Link`.`link_doctype` = "Customer"
                    AND `tabDynamic Link`.`link_name` = `tabCustomer`.`name`) = 2)
        AND (
                (SELECT COUNT(*)
                FROM `tabDynamic Link`
                LEFT JOIN `tabContact` ON `tabContact`.`name` = `tabDynamic Link`.`parent`
                WHERE `tabDynamic Link`.`parenttype` = "Contact"
                    AND `tabDynamic Link`.`link_doctype` = "Customer"
                    AND `tabDynamic Link`.`link_name` = `tabCustomer`.`name`) = 1);
    """
    query_results = frappe.db.sql(sql_query, as_dict=True)

    for i, result in enumerate(query_results):
        invoice_to_id = frappe.get_value("Customer", result['customer'], 'invoice_to')
        invoice_to_contact = frappe.get_doc("Contact", invoice_to_id)
        # Duplicate Invoice_to contact
        new_contact = invoice_to_contact.as_dict()

        # Get billing address
        query = """SELECT `tabDynamic Link`.`parent` AS `address`
            FROM `tabDynamic Link`
            LEFT JOIN `tabAddress` ON `tabAddress`.`name` = `tabDynamic Link`.`parent`
            WHERE `tabDynamic Link`.`parenttype` = "Address"
            AND `tabDynamic Link`.`link_doctype` = "Customer"
            AND `tabDynamic Link`.`link_name` = {customer}
            AND `tabAddress`.`is_primary_address` = 1
            AND `tabAddress`.`address_type` = 'Billing'
        """.format(customer=result['customer'])
        billing_address_ids = frappe.db.sql(query, as_dict=True)
        assert len(billing_address_ids) == 1
        billing_address_id = billing_address_ids[0]['address']

        # Rename the new duplicate contact to the name of the billing address (tabAddress.name)
        new_contact['person_id'] = billing_address_id
        # Change the address of the new contact to the name of the billing address (Contact.address = tabAddress.name)
        new_contact['address'] = billing_address_id
        new_contact['customer_id'] = result['customer']
        new_contact['email'] = frappe.get_value("Customer", result['customer'], 'invoice_email')
        update_contact(new_contact)
        # Set the Customer.invoice_to to the name of the new contact (= name of billing address)
        customer = frappe.get_doc("Customer", result['customer'])
        customer.invoice_to = new_contact['person_id']
        customer.save()
        print(f"Changed invoice_to of customer {result['customer']} from {invoice_to_id} to {new_contact['person_id']}.")
    frappe.db.commit()


def correct_email_ids():
    """
    Find non-Disabled Contacts with no email_id.
    If the length of Contact.email_ids is 1, set this entry as 'Is Primary' and Contact.email_id to this email address.

    bench execute microsynth.microsynth.migration.correct_email_ids
    """
    sql_query = """
        SELECT
            `tabContact`.`name` AS `contact_id`,
            `tabAddress`.`address_type` AS `address_type`,
            `tabContact`.`first_name` AS `first_name`,
            `tabContact`.`last_name` AS `last_name`,
            `tabContact`.`contact_classification`,
            `tabContact`.`creation` AS `creation_date`,
            `tabContact`.`owner` AS `creator`
        FROM `tabContact`
        LEFT JOIN `tabAddress` ON `tabContact`.`address` = `tabAddress`.`name`
        WHERE `tabContact`.`status` != 'Disabled'
            AND (`tabContact`.`email_id` IS NULL OR `tabContact`.`email_id` = '')
        ;"""
    contacts = frappe.db.sql(sql_query, as_dict=True)
    print(f"There are {len(contacts)} non-Disabled Contacts without an email_id.")

    for contact in contacts:
        contact_doc = frappe.get_doc("Contact", contact['contact_id'])
        if len(contact_doc.email_ids) == 1:
            try:
                if not contact_doc.email_ids[0].is_primary:
                    print(f"Contact {contact_doc.name} has exactly one Email address ('{contact_doc.email_ids[0].email_id}'), but it is not marked as 'Is Primary' (created by {contact_doc.owner} on {contact_doc.creation}). Going to set as 'Is Primary'.")
                    contact_doc.email_ids[0].is_primary = 1
                    contact_doc.email_ids[0].save()
                    contact_doc.email_id = contact_doc.email_ids[0].email_id
                    contact_doc.save()
                else:
                    # This should never be the case
                    print(f"### Contact {contact_doc.name} has exactly one Email address ('{contact_doc.email_ids[0].email_id}') and it is marked as 'Is Primary'. Going to set email_id of this Contact.")
                    contact_doc.email_id = contact_doc.email_ids[0].email_id
                    contact_doc.save()
            except Exception as err:
                print(f"Error: {err}")
        elif len(contact_doc.email_ids) > 1:
            print(f"# Contact {contact_doc.name} has {len(contact_doc.email_ids)} Email addresses ('{contact_doc.email_ids[0].email_id}'), but none of them is marked as 'Is Primary'.")


def export_abacus_file_with_account_matrix(abacus_export_file, output_file, validate=False):
    """
    Export an Abacus Export File and replace income accounts according to account matrix

    Run as
    bench execute microsynth.microsynth.migration.export_abacus_file_with_account_matrix --kwargs "{'abacus_export_file': '2023-03-01..2023-03-01', 'output_file': '/tmp/aba_out.xml', 'validate': 1}"
    """
    doc = frappe.get_doc("Abacus Export File", abacus_export_file)

    transactions = doc.get_individual_transactions()

    for t in transactions:
        if frappe.db.exists("Sales Invoice", t.get("text1")):
            si = frappe.get_doc("Sales Invoice", t.get("text1"))

            # fetch applicable country
            country = frappe.get_value("Address", si.shipping_address_name, "country")

            # go through against accounts and switch according to matrix
            for i in t.get("against_singles"):
                if i['account'] == "2010":
                    income_account = get_alternative_account(get_account_by_number(i['account'], si.company), si.currency)
                else:
                    income_account = get_alternative_income_account(
                        get_account_by_number(i['account'], si.company),
                        country
                    )
                i['account'] = doc.get_account_number(income_account)

            # optional: validate according to assessment
            if validate:
                # fetch all corrected income accounts
                correct_accounts = get_income_accounts(si.shipping_address_name, si.currency, si.items)
                # check if all accounts are in the correct income accounts
                for a in t.get("against_singles"):
                    if get_account_by_number(a.get('account'), si.company) not in correct_accounts:
                        print("{0} does not validate: {1} is not in the correct accounts ({2})".format(
                            t.get("text1"), a.get('account'), correct_accounts))

    # render output xml content
    data = {
        'transactions': transactions
    }
    content = frappe.render_template('erpnextswiss/erpnextswiss/doctype/abacus_export_file/transfer_file.html', data)

    # write to output file
    f = open(output_file, "w")
    f.write(content)
    f.close()
    print ("Created {0}.".format(output_file))
    return


def get_account_by_number(account_number, company):
    accounts = frappe.get_all("Account", filters={'account_number': account_number, 'company': company}, fields=['name'])
    if len(accounts) > 0:
        return accounts[0]['name']
    else:
        return None


def export_sanger_customers(filepath):
    """
    Create a CSV file of Contacts that appear as Contact Person
    on at least one Sales Order with Product Type Labels or Sequencing

    run
    bench execute microsynth.microsynth.migration.export_sanger_customers --kwargs "{'filepath': '/mnt/erp_share/sanger_customers.csv'}"
    """
    sql_query = """
            SELECT DISTINCT `tabCustomer`.`default_company`,
                `tabCustomer`.`territory`,
                `tabCustomer`.`language`,
                `tabContact`.`first_name`,
                `tabContact`.`last_name`,
                `tabContact`.`email_id`,
                `tabContact`.`name` AS `contact_id`,
                `tabCustomer`.`customer_name`,
                `tabCustomer`.`name` AS `customer_id`
            FROM `tabSales Order`
            JOIN `tabCustomer` ON `tabCustomer`.`name` = `tabSales Order`.`customer`
            JOIN `tabContact` ON `tabContact`.`name` = `tabSales Order`.`contact_person`
            WHERE `tabSales Order`.`product_type` in ('Sequencing', 'Labels')
            AND `tabSales Order`.`total` > 0
            AND `tabSales Order`.`docstatus` = 1
            AND `tabSales Order`.`status` NOT IN ("Closed", "Cancelled");
            """

    contacts = frappe.db.sql(sql_query, as_dict=True)

    with open(filepath, mode='w') as file:
        header = 'Default Company of Customer;Territory of Customer;Language of Customer;First name (Contact);Last name (Contact);Email (Contact);Contact ID;Customer name;Customer ID\n'
        file.write(header)
        for c in contacts:
            file.write(f"{c['default_company']};{c['territory']};{c['language']};{c['first_name']};{c['last_name']};"
                       f"{c['email_id']};{c['contact_id']};{c['customer_name']};{c['customer_id']}\n")


def correct_inverted_credit_journal_entries():
    """
    This is a bugfix-patch for journal entries of customer credits that were returned before 2023-11-30

    run
    bench execute microsynth.microsynth.migration.correct_inverted_credit_journal_entries
    """
    from microsynth.microsynth.credits import book_credit

    affected_jvs = frappe.get_all("Journal Entry", filters=[['user_remark', 'LIKE', 'Credit from CN-%'], ['docstatus', '=', 1]], fields=['name', 'user_remark'])

    for jv in affected_jvs:
        print("processing {0} ({1})".format(jv['name'], jv['user_remark']))
        # cancel "original"/faulty JV:
        doc = frappe.get_doc("Journal Entry", jv['name'])
        try:
            doc.cancel()
        except Exception as e:
            print("Could not cancel {0} ({1})\n{2}".format(jv['name'], jv['user_remark'], e))

        # re-create journal entry
        sales_invoice = jv['user_remark'].split(" ")[-1]
        if not frappe.db.exists("Sales Invoice", sales_invoice):
            print("Sales invoice not found for {0} ({1})".format(jv['name'], jv['user_remark']))
            continue

        if frappe.get_value("Sales Invoice", sales_invoice, "docstatus") == 1:
            book_credit(sales_invoice)

    frappe.db.commit()


def initialize_field_customer_credits():
    """
    Loops over all non-disabled Customers and initializes the new Select field customer_credits
    according to the existing checkbox has_credit_account.
    Expected runtime: less than 5 seconds

    Run
    bench execute microsynth.microsynth.migration.initialize_field_customer_credits
    """
    customers = frappe.get_all("Customer", filters={'disabled': 0}, fields=['name', 'has_credit_account'])
    counter = 0
    for customer in customers:
        if customer['has_credit_account']:
            frappe.db.set_value("Customer", customer['name'], "customer_credits", "Credit Account", update_modified = False)
            counter += 1
            if counter % 100 == 0:
                frappe.db.commit()
    frappe.db.commit()


def check_remaining_labels(filepath):
    """
    expected runtime: more than one hour

    bench execute microsynth.microsynth.migration.check_remaining_labels --kwargs "{'filepath': '/mnt/erp_share/Sequencing/Label_Sync/SeqBlattExport_2023-12-18/'}"
    """
    total_counter = total_with_date = total_no_date = total_found = total_not_found = total_multiple = 0
    for comp in ('BAL', 'GOE', 'LYO'):
        full_path = f"{filepath}{comp}/remaining.tab"
        with_date = no_date = counter = found = not_found = multiple = 0
        with open(full_path, 'r', encoding = "ISO-8859-1") as file:
            row_count = sum(1 for row in file)
            file.seek(0)  # go to the start of the file again
            csv_reader = csv.reader((x.replace('\0', '') for x in file), delimiter='\t')  # replace NULL bytes (throwing an error)
            for line in csv_reader:
                if len(line) != 7:
                    print(f"{len(line)=}; {line=}; skipping")
                    continue
                counter += 1
                unused_labels = line[-1].split('\v')
                if line[0]:
                    with_date += len(unused_labels)
                else:
                    no_date += len(unused_labels)

                for label_code in unused_labels:
                    # get all Sequencing Labels with Label Barcode == label_code
                    labels = frappe.get_all("Sequencing Label", filters=[['label_id', '=', label_code]], fields=['name'])
                    if len(labels) == 1:
                        found += 1
                    elif len(labels) == 0:
                        not_found += 1
                    elif len(labels) > 1:
                        found += 1
                        multiple += 1

                if counter % 100 == 0:
                    print(f"Already processed {round((counter/row_count) * 100, 2)} % ({counter}/{row_count}) of lines of {full_path}: {found=}, {not_found=}, {with_date=}, {no_date=}, {multiple=}")
        print(f"{comp}: {counter=}, {with_date=}, {no_date=}, {found=}, {not_found=}, {multiple=}")
        total_counter += counter
        total_with_date += with_date
        total_no_date += no_date
        total_found += found
        total_not_found += not_found
        total_multiple += multiple
    print(f"together: {total_counter=}, {total_with_date=}, {total_no_date=}, {total_found=}, {total_not_found=}, {total_multiple=}")


def try_label_save(label, counters):
    try:
        label.save()
    except Exception as error:
        counters['customer_disabled'] += 1
        #print(f"Got the following exception when trying to save {label.name=} ({label.label_id=}) with '{label.customer=}', '{label.sales_order=}', '{label.contact=}':\n{error}")


def update_label_status(labels, counters):
    """
    Only used by the functions update_used_tube_labels and update_used_plate_labels to avoid code duplication
    """
    if len(labels) == 1:
        counters['found'] += 1
        if labels[0]['status'] != 'received':
            #print(f"Label not marked as used in the ERP: {line=}, status={labels[0]['status']}")
            counters['status_mismatch'] += 1
            label = frappe.get_doc("Sequencing Label", labels[0]['name'])
            label.status = 'processed'
            try_label_save(label, counters)
            #print(f"Set Label '{label.name}' to Status processed.")
    else:
        if len(labels) > 1:
            counters['found'] += 1
            #print(f"Found more than one Sequencing Label in the ERP: {line=}")
            counters['multiple'] += 1
            if len(labels) > 2:
                print(f"{len(labels)=}, {labels=}")
            else:
                label0 = frappe.get_doc("Sequencing Label", labels[0]['name'])
                label1 = frappe.get_doc("Sequencing Label", labels[1]['name'])
                if label0.customer and label0.sales_order and label0.contact and not label1.customer and not label1.sales_order and not label1.contact:
                    label1.status = 'locked'
                    try_label_save(label1, counters)
                    #print(f"Set Label '{label1.name}' to Status locked.")
                elif label1.customer and label1.sales_order and label1.contact and not label0.customer and not label0.sales_order and not label0.contact:
                    label0.status = 'locked'
                    try_label_save(label0, counters)
                    #print(f"Set Label '{label0.name}' to Status locked.")
                else:
                    counters['sold_twice'] += 1
                    print(f"It seems that the label with Barcode {label1.label_id} was sold twice with {label1.sales_order} and {label0.sales_order}.")
        else:
            counters['not_found'] += 1
            #print(f"Sequencing Label not found in the ERP: {line=}")


def update_used_tube_labels(filepath):
    """
    expected runtime: many minutes

    bench execute microsynth.microsynth.migration.update_used_tube_labels --kwargs "{'filepath': '/mnt/erp_share/Sequencing/Label_Sync/SeqBlattExport_2023-12-18/'}"
    """
    total_counter = total_found = total_not_found = total_status_mismatch = total_multiple = total_customer_disabled = total_sold_twice = 0
    for comp in ('BAL', 'GOE', 'LYO'):
        full_path = f"{filepath}{comp}/tubes.tab"
        with open(full_path, 'r', encoding = "ISO-8859-1") as file:
            counters = {'counter': 0, 'found': 0, 'not_found': 0, 'status_mismatch': 0, 'multiple': 0, 'customer_disabled': 0, 'sold_twice': 0}
            file.seek(0)  # go to the start of the file again
            csv_reader = csv.reader((x.replace('\0', '') for x in file), delimiter='\t')  # replace NULL bytes (throwing an error)
            for line in csv_reader:
                if len(line) != 5:
                    print(f"{len(line)=}; {line=}; skipping")
                    continue
                if line[3] == '' or int(line[3]) < 30:
                    continue
                counters['counter'] += 1

                labels = frappe.get_all("Sequencing Label", filters=[['label_id', '=', line[0]]], fields=['name', 'status'])
                update_label_status(labels, counters)

                if counters['counter']% 10000 == 0:
                    frappe.db.commit()
                    print(f"Already processed {counters['counter']} Labels: {comp=}: found={counters['found']}; not_found={counters['not_found']}, status_mismatch={counters['status_mismatch']}, multiple={counters['multiple']}, customer_disabled={counters['customer_disabled']}, sold_twice={counters['sold_twice']}")

        frappe.db.commit()
        print(f"{comp}: counter={counters['counter']}, found={counters['found']}; not_found={counters['not_found']}, status_mismatch={counters['status_mismatch']}, multiple={counters['multiple']}, customer_disabled={counters['customer_disabled']}, sold_twice={counters['sold_twice']}")
        total_counter += counters['counter']
        total_found += counters['found']
        total_not_found += counters['not_found']
        total_status_mismatch += counters['status_mismatch']
        total_multiple += counters['multiple']
        total_customer_disabled += counters['customer_disabled']
        total_sold_twice += counters['sold_twice']
    print(f"together: {total_counter=}, {total_found=}, {total_not_found=}, {total_status_mismatch=}, {total_multiple=}, {total_customer_disabled=}, {total_sold_twice=}")


def update_used_plate_labels(filepath):
    """
    expected runtime: a few seconds

    bench execute microsynth.microsynth.migration.update_used_plate_labels --kwargs "{'filepath': '/mnt/erp_share/Sequencing/Label_Sync/SeqBlattExport_2023-12-18/'}"
    """
    total_counter = total_found = total_not_found = total_status_mismatch = total_multiple = total_customer_disabled = total_sold_twice = 0
    for comp in ('BAL', 'GOE', 'LYO'):
        full_path = f"{filepath}{comp}/plates.tab"
        with open(full_path, 'r', encoding = "ISO-8859-1") as file:
            counters = {'counter': 0, 'found': 0, 'not_found': 0, 'status_mismatch': 0, 'multiple': 0, 'customer_disabled': 0, 'sold_twice': 0}
            csv_reader = csv.reader((x.replace('\0', '') for x in file), delimiter='\t')  # replace NULL bytes (throwing an error)
            for line in csv_reader:
                if len(line) != 4:
                    print(f"{len(line)=}; {line=}; skipping")
                    continue
                order_nr = line[0]
                if order_nr.startswith("H"):
                    continue
                if not line[3] or int(line[3]) < 30:  # line[3] != '99'
                    continue
                counters['counter'] += 1
                labels = frappe.get_all("Sequencing Label", filters=[['label_id', '=', line[1]]], fields=['name', 'status'])
                update_label_status(labels, counters)

        frappe.db.commit()
        print(f"{comp}: counter={counters['counter']}, found={counters['found']}; not_found={counters['not_found']}, status_mismatch={counters['status_mismatch']}, multiple={counters['multiple']}, customer_disabled={counters['customer_disabled']}, sold_twice={counters['sold_twice']}")
        total_counter += counters['counter']
        total_found += counters['found']
        total_not_found += counters['not_found']
        total_status_mismatch += counters['status_mismatch']
        total_multiple += counters['multiple']
        total_customer_disabled += counters['customer_disabled']
        total_sold_twice += counters['sold_twice']
    print(f"together: {total_counter=}, {total_found=}, {total_not_found=}, {total_status_mismatch=}, {total_multiple=}, {total_customer_disabled=}, {total_sold_twice=}")


def lock_all_contacts():
    """
    Create Contact Locks for all Contacts

    run
    bench execute microsynth.microsynth.migration.lock_all_contacts
    """
    from microsynth.microsynth.marketing import lock_contact

    contacts = frappe.get_all("Contact", fields=['name'])

    for i, c in enumerate(contacts):
        lock_contact(c)
        if i % 1000 == 0:
            print(f"{datetime.now()} Already locked {i}/{len(contacts)} Contacts.")
            frappe.db.commit()
    print(f"{datetime.now()} Finished locking of {len(contacts)} Contacts.")


# Mapping from BOS to ERP Oligo scales
SCALES = {
    'GEN': 'Genomics',
    '0.04': '0.04 µmol',
    '0.2': '0.2 µmol',
    '1.0': '1.0 µmol',
    '15': '15 µmol',
}


def import_oligo_scales(directory_path):
    """
    Parses several files exported from BOS having all the following format:
    IDX   IDORDERPOS	OLIGOID	WEBID	SCALE
    1    	4657881	    4657881	1801066	GEN

    Sets the Scale of the Oligo with the given Web ID accordingly.
    Estimated runtime: 4-5 h

    bench execute microsynth.microsynth.migration.import_oligo_scales --kwargs "{'directory_path': '/mnt/erp_share/Oligo/'}"
    """
    oligo_dict = {}

    for filename in os.scandir(directory_path):
        if filename.is_file():
            with open(filename.path, 'r') as file:
                csv_reader = csv.reader(file, delimiter='\t')
                next(csv_reader)  # skip header
                for line in csv_reader:
                    if len(line) != 5:
                        print(f"{len(line)=}; {line=}; skipping")
                        continue
                    id_order_pos = line[1]
                    web_id = line[3]
                    scale = line[4]
                    if web_id not in oligo_dict:
                        oligo_dict[web_id] = [(id_order_pos, scale)]
                    else:
                        oligo_dict[web_id].append((id_order_pos, scale))
            print(f"{datetime.now()} Successfully read file '{filename.path}': {len(oligo_dict)=}.")
    counter = multiple_counter = none_counter = 0
    for web_id, tuple_list in oligo_dict.items():
        if counter % 1000 == 0:
            print(f"{datetime.now()} Already processed {counter}/{len(oligo_dict)} Oligos (Number of Web IDs occured more than once in the BOS export: {multiple_counter}; Number of distinct Web IDs from BOS export not found in the ERP: {none_counter}).")
            frappe.db.commit()
        counter += 1
        if len(tuple_list) > 1:
            multiple_counter += 1
            # Sort list of tuples by id_order_pos ascending
            tuple_list.sort()  # a list of tuples is sorted by the first elemenent of each tuple ascending by default
        # Take the scale of the smallest (first) id_order_pos
        scale = tuple_list[0][1]
        oligos = frappe.get_all("Oligo", filters=[['web_id', '=', web_id]], fields=['name'])
        if len(oligos) < 1:
            #print(f"There is no Oligo with Web ID '{web_id}' in the ERP.")
            none_counter += 1
            continue
        elif len(oligos) > 1:
            print(f"{web_id=}: {len(oligos)=}; {oligos=}")
        oligo = frappe.get_doc("Oligo", oligos[0]['name'])
        oligo.scale = SCALES[scale]
        oligo.save()
    print(f"{datetime.now()} Finished: processed {counter}/{len(oligo_dict)} Oligos (Number of Web IDs occured more than once in the BOS export: {multiple_counter}; Number of distinct Web IDs from BOS export not found in the ERP: {none_counter}).")
    frappe.db.commit()


def check_weborderids_of_deleted_sos():
    """
    Search for deleted Sales Orders with a Web Order ID and
    search this Web Order on non-deleted Sales Orders, Delivery Notes and Sales Invoices.

    bench execute microsynth.microsynth.migration.check_weborderids_of_deleted_sos
    """
    deleted_orders = frappe.get_all('Deleted Document',
                                    filters=[['deleted_doctype', '=', 'Sales Order'], ['data', 'LIKE', '%"web_order_id": "%']],
                                    fields=['name', 'deleted_name', 'data', 'owner', 'creation'])

    for do in deleted_orders:
        content = json.loads(do['data'])
        web_order_id = content['web_order_id']
        product_type = content['product_type']
        if content['owner'] != do['owner']:
            print(f"'{do['deleted_name']}' with {product_type=} created by {content['owner']=} deleted by {do['owner']=}, deleted on {do['creation']}")
        # sales_orders = frappe.get_all('Sales Order', filters=[['web_order_id', '=', web_order_id]], fields=['name', 'status', 'docstatus', 'product_type'])
        # delivery_notes = frappe.get_all('Delivery Note', filters=[['web_order_id', '=', web_order_id]], fields=['name', 'status', 'docstatus', 'product_type'])
        # sales_invoices = frappe.get_all('Sales Invoice', filters=[['web_order_id', '=', web_order_id]], fields=['name', 'status', 'docstatus', 'product_type'])
        # if len(delivery_notes) > 0 or len(sales_invoices) > 0:
        #     print(f"\nFound Sales Order '{do['deleted_name']}' with Product Type '{product_type}' created by {content['owner']} deleted by {do['owner']} with Web Order ID '{web_order_id}' that appears on the following non-deleted documents:")
        #     if len(delivery_notes) != len(sales_invoices):
        #         print(f"Attention: Number of Delivery Notes and Sales Invoices does not match.")
        #     if content['owner'] != do['owner']:
        #         print(f"##### Attention: content['owner'] != do['owner']")
        #     for so in sales_orders:
        #         print(f"Sales Order '{so['name']}' with Product Type '{so['product_type']}' and docstatus {so['docstatus']}")
        #     for dn in delivery_notes:
        #         print(f"Delivery Note '{dn['name']}' with Product Type '{dn['product_type']}' and docstatus {dn['docstatus']}")
        #     for si in sales_invoices:
        #         print(f"Sales Invoice '{si['name']}' with Product Type '{si['product_type']}' and docstatus {si['docstatus']}")


def calculate_prices_from_so(filepath):
    """
    Used to compute the total rate of labels sold at one Microsynth company and
    used at another Microsynth company (quick and dirty script version).
    This computation is done yearly in Q1.

    Takes a table with four columns:
    0: Web Order ID or Sales Order ID of label order
    1: Number of labels
    2: Item Code
    3: Customer or Contact name (not needed)

    a) parse input table
    b) find Sales Order
    c) lookup rate of specified Item
    d) mutiply rate with the given number of labels
    e) writes output

    bench execute microsynth.microsynth.migration.calculate_prices_from_so  --kwargs "{'filepath': '/mnt/erp_share/JPe/labels/labels_used_at_another_company.csv'}"
    """
    results = []
    with open(filepath, 'r') as file:
        csv_reader = csv.reader(file, delimiter=';')
        next(csv_reader)  # skip header
        for line in csv_reader:
            if len(line) != 4:
                print(f"Expected line of length 4, but got {len(line)=}; {line=}; skipping")
                continue
            order = line[0]
            qty = cint(line[1])
            item_code = line[2]
            contact = line[3]
            total = 0
            found = missing = False
            if '-' in order:
                # assume it is a Sales Order ID
                so = frappe.get_doc("Sales Order", order)
                for item in so.items:
                    if item.item_code == item_code:
                        rate = item.rate
                        total = qty * rate
                        found = True
                        if qty > item.qty:
                            print(f"WARNING: Item quantity in the input ({qty}) is larger than on the order '{order}' ({item.qty}).")
            else:
                # assume it is a Web Order ID
                sales_orders = frappe.get_all("Sales Order", filters={'web_order_id': order, 'docstatus': 1}, fields=['name'])
                if len(sales_orders) == 1:
                    so = frappe.get_doc("Sales Order", sales_orders[0]['name'])
                    for item in so.items:
                        if item.item_code == item_code:
                            rate = item.rate
                            total = qty * rate
                            found = True
                            if qty > item.qty:
                                print(f"WARNING: Item quantity in the input ({qty}) is larger than on the order '{order}' ({item.qty}).")
                elif len(sales_orders) == 0:
                    print(f"There is no Sales Order with Web Order ID '{order}' in the ERP.")
                    missing = True
                else:  # len > 1
                    print(f"There is more than one Sales Order with the Web Order ID '{order}' in the ERP.")
            if not found:
                if not missing:
                    print(f"Did not found the Item Code {item_code} on the order '{order}'.")
                results.append([order, qty, '-', '-', item_code, contact])
            else:
                results.append([order, qty, rate, round(total, 2), item_code, contact])

        with open(filepath + '_results.csv', 'w') as outfile:
            writer = csv.writer(outfile, delimiter=';')
            writer.writerow(['order', 'qty', 'rate', 'rate*qty', 'item_code', 'contact'])
            for res in results:
                writer.writerow(res)


def import_user_process_assignments(filepath):
    """
    Imports the User Process Assignments from the given CSV with the format:

    Full Name; Email;Process;Subprocess;Chapter;All Chapters
    Rolf Suter;rolf.suter@microsynth.ch;5;3;2;

    bench execute microsynth.microsynth.migration.import_user_process_assignments --kwargs "{'filepath': '/mnt/erp_share/JPe/user_process_assignments.csv'}"
    """
    assignments = {}
    with open(filepath, 'r') as file:
        csv_reader = csv.reader(file, delimiter=';')
        next(csv_reader)  # skip header
        for line in csv_reader:
            if len(line) != 6:
                print(f"{len(line)=}; {line=}; skipping")
                continue
            email = line[1]
            if not email:
                print(f"No email given for '{line[0]}'. Unable to create User Settings.")
                continue
            if not email in assignments:
                assignments[email] = []
            assignments[email].append((line[2], line[3], line[4], line[5]))

    for email, processes in assignments.items():
        if not frappe.db.exists('User', email):
            print(f"User '{email}' does not exist in the ERP. Please create and configure this User manually.")
            continue
        if not frappe.db.exists('User Settings', email):
            new_user_settings = frappe.get_doc({
                'doctype': 'User Settings',
                'user': email
            })
            new_user_settings.insert(ignore_permissions=True)
            frappe.db.commit()

        user_settings = frappe.get_doc('User Settings', email)
        user_settings.qm_process_assignments = []  # reset qm_process_assignments
        for proc in processes:
            if not proc[0] or not proc[1]:
                print(f"Please specify at least process and subprocess for '{email}' in '{filepath}'.")
                continue
            process = {
                'process_number': proc[0],
                'subprocess_number': proc[1],
                'all_chapters': proc[3] or 0,
                'chapter': proc[2]
            }
            user_settings.append('qm_process_assignments', process)
        user_settings.save()
    frappe.db.commit()


def patch_invoice_sent_on_dates():
    """
    Find all invoice sent on with milliseconds and remove the millisecond part

    Fixes the invoice not saved on open bug

    Run as
    bench execute microsynth.microsynth.migration.patch_invoice_sent_on_dates
    """
    print("Executing cleanup query...")
    frappe.db.sql("""
        UPDATE `tabSales Invoice`
        SET `invoice_sent_on` = SUBSTRING(`invoice_sent_on`, 1, 19)
        WHERE LENGTH(`invoice_sent_on`) > 19;""")
    print("done ;-)")
    return


def patch_label_printed_on_dates():
    """
    Find all Sales Orders with milliseconds in the field Shipping Label printed on and remove the millisecond part.
    Fixes the Sales Order not saved on open bug

    bench execute microsynth.microsynth.migration.patch_label_printed_on_dates
    """
    print("Executing cleanup query...")
    frappe.db.sql("""
        UPDATE `tabSales Order`
        SET `label_printed_on` = SUBSTRING(`label_printed_on`, 1, 19)
        WHERE LENGTH(`label_printed_on`) > 19;""")
    print("Done :-)")


def check_tax_ids():
    """
    Loop over all enabled Customers and check their non-empty Tax ID if it does not start with CH, GB, IS, NO or TR.

    bench execute microsynth.microsynth.migration.check_tax_ids
    """
    from erpnextaustria.erpnextaustria.utils import check_uid
    #from erpnextswiss.erpnextswiss.zefix import get_company
    from microsynth.microsynth.utils import get_first_shipping_address

    customers = frappe.db.get_all("Customer",
        filters = [['disabled', '=', 0], ['customer_type', '!=', 'Individual']],
        fields = ['name', 'customer_name', 'tax_id'])
    print(f"Going to check {len(customers)} enabled Customers ...")
    print("i;Customer;Customer Name;Country;Invalid Tax ID")
    for i, customer in enumerate(customers):
        try:
            if not customer['tax_id']:
                continue
            shipping_address = get_first_shipping_address(customer['name'])
            if shipping_address is None:
                msg = f"Customer '{customer['name']}' has no shipping address."
                print(msg)
                frappe.log_error(msg, "migration.check_tax_ids")
                continue
            country = frappe.get_value("Address", shipping_address, "Country")
            if not country in ['Austria', 'Belgium', 'Bulgaria', 'Cyprus', 'Czech Republic', 'Germany', 'Denmark', 'Estonia', 'Greece',
                            'Spain', 'Finland', 'France', 'Croatia', 'Hungary', 'Ireland', 'Italy', 'Lithuania', 'Luxembourg', 'Latvia',
                            'Malta', 'Netherlands', 'Poland', 'Portugal', 'Romania', 'Sweden', 'Slovenia', 'Slovakia']:
                continue
            elif customer['tax_id'][:2] in ['CH']:
                continue  # currently unable to check Swiss UID
            #     company = get_company(customer['tax_id'], debug=True)  # does not yet work
            #     if 'error' in company:
            #         print(f"{i}/{len(customers)}: Customer '{customer['name']}' ('{customer['customer_name']}'): '{customer['tax_id']}'")
            # elif customer['tax_id'][:2] in ['GB', 'IS', 'NO', 'TR'] and not 'NOT' in customer['tax_id']:
            #     # unable to check Tax ID from Great Britain, Iceland, Norway or Turkey
            #     continue
            # el
            if not check_uid(customer['tax_id']):
                print(f"{i};{customer['name']};{customer['customer_name']};{country};{customer['tax_id']}")
        except Exception as err:
            print(f"unable to check {i};{customer['name']};{customer['customer_name']};{customer['tax_id']}")


def is_workday_before_10am(date):
    """
    DEPRECATED
    Returns true if the given date is a workday (Monday to Friday and no holiday), otherwise false.
    Currently adapted to public holidays of St. Gallen 2023-2024.
    Source: https://www.sg.ch/verkehr/strassenverkehr/formulare_merkblaetter/feiertage-und-spezielle-oeffnungszeiten.html
    """
    holidays_st_gallen = [datetime(2023, 1, 1), datetime(2023, 1, 2), datetime(2023, 4, 7), datetime(2023, 4, 10),
                            datetime(2023, 5, 18), datetime(2023, 5, 29), datetime(2023, 8, 1),
                            datetime(2023, 11, 1), datetime(2023, 12, 25), datetime(2023, 12, 26),
                            datetime(2024, 1, 1), datetime(2024, 1, 2), datetime(2024, 3, 29),
                            datetime(2024, 4, 1), datetime(2024, 5, 9), datetime(2024, 5, 20),
                            datetime(2024, 8, 1), datetime(2024, 11, 1), datetime(2024, 12, 25),
                            datetime(2024, 12, 26)]
    if date.weekday() < 5 and date not in holidays_st_gallen:  # https://docs.python.org/3/library/datetime.html#datetime.date.weekday
        if date.hour < 10:  # before 10 am
            return True
    return False


def evaluate_same_day_oligos(export_file, start_date='2023-10-01', end_date='2024-03-31'):
    """
    DEPRECATED, see same_day_oligos.py
    Determine Oligo Sales Orders that fulfill the advertised same day delivery conditions
    and compute the proportion of Sales Orders that were shipped in-time (on the same day).

    Run from bench
    bench execute microsynth.microsynth.migration.evaluate_same_day_oligos --kwargs "{'export_file':'/mnt/erp_share/JPe/same_day_oligos_2023-10-01_2024-03-31.csv'}"
    """
    try:
        is_valid = bool(datetime.strptime(start_date, "%Y-%m-%d"))
        is_valid = is_valid and bool(datetime.strptime(end_date, "%Y-%m-%d"))
    except ValueError:
        is_valid = False

    if not is_valid:
        print("Please provide both start and end date in the format YYYY-MM-DD.")
        return

    sql_query = f"""SELECT
            `tabSales Order`.`name`,
            `tabSales Order`.`customer_name`,
            `tabSales Order`.`transaction_date`,
            `tabSales Order`.`label_printed_on`,
            `tabSales Order`.`status`
        FROM `tabSales Order`
        LEFT JOIN `tabAddress` ON `tabAddress`.`name` = `tabSales Order`.`customer_address`
        WHERE
        `tabSales Order`.`docstatus` = 1
        AND `tabSales Order`.`status` NOT IN ('Draft', 'Cancelled', 'On Hold', 'Closed')
        AND `tabSales Order`.`product_type` = 'Oligos'
        -- AND `tabSales Order`.`customer_name` LIKE '%Microsynth%'
        -- AND `tabAddress`.`city` LIKE '%Balgach%'
        AND `tabSales Order`.`transaction_date` >= DATE('{start_date}')
        AND `tabSales Order`.`transaction_date` <= DATE('{end_date}')
        ORDER BY `tabSales Order`.`transaction_date`;
    """
    query_results = frappe.db.sql(sql_query, as_dict=True)
    print(f"There are {len(query_results)} SQL query results.")
    should_be_same_day = is_same_day = 0

    with open(export_file, "w") as file:
        writer = csv.writer(file)
        writer.writerow(['sales_order.name', 'sales_order.customer', 'sales_order.customer_name', 'sales_order.creation',
                         'sales_order.label_printed_on', 'sales_order.status', 'same_day_fulfilled'])

        for result in query_results:
            sales_order = frappe.get_doc("Sales Order", result['name'])
            if len(sales_order.oligos) >= 20:  # the same day criteria only applies to Sales Orders with less than 20 Oligos
                continue
            unallowed_items = False
            for i in sales_order.items:
                if i.item_code not in ('0010', '0050', '0100', '1100', '1101', '1102'):
                    unallowed_items = True
                    break
            if not unallowed_items:
                for oligo_link in sales_order.oligos:
                    oligo = frappe.get_doc("Oligo", oligo_link.oligo)
                    if len(oligo.items) != 1:  # exclude Oligos with modifications (more than one item) and Oligos without any items
                        if len(oligo.items) == 0:
                            #print(f"WARNING: {len(oligo.items)=} for {sales_order.name}, Web Order ID {sales_order.web_order_id}. Going to take sequence length instead")
                            if not oligo.sequence:
                                print(f"Oligo {oligo.name} from Sales Order {sales_order.name} has no items and no sequence. Going to skip this Sales Order.")
                                oligo_too_complicated = True
                                break
                            if len(oligo.sequence) <= 25:  # check if oligo is longer than 25 nt
                                continue
                            else:
                                oligo_too_complicated = True
                                break
                        else:
                            print(f"{len(oligo.items)=} for {sales_order.name}, Web Order ID {sales_order.web_order_id}")
                            oligo_too_complicated = True
                            break
                    oligo_too_complicated = False
                    if oligo.items[0].qty > 25:  # check if oligo is longer than 25 nt
                        oligo_too_complicated = True
                        break
                if not oligo_too_complicated:
                    creation_time = sales_order.creation
                    creation_date = str(creation_time).split(' ')[0]
                    if creation_date != str(sales_order.transaction_date):
                        print(f"creation_date != sales_order.transaction_date for {sales_order.name}, Web Order ID {sales_order.web_order_id}. Going to skip this Sales Order.")
                        continue
                    if is_workday_before_10am(sales_order.creation):
                        if not sales_order.label_printed_on:
                            print(f"There is no Label printed on date on {sales_order.name}, Web Order ID {sales_order.web_order_id}. Going to skip this Sales Order.")
                            continue
                        should_be_same_day += 1
                        same_day_fulfilled = (sales_order.creation.day == sales_order.label_printed_on.day) and (sales_order.label_printed_on.hour < 18)
                        if same_day_fulfilled:
                            is_same_day += 1
                        writer.writerow([sales_order.name, sales_order.customer, sales_order.customer_name, sales_order.creation,
                                         sales_order.label_printed_on, sales_order.status, same_day_fulfilled])

    print(f"There are {should_be_same_day} Sales Orders that meet the same day criteria and are written to {export_file}.")
    print(f"Of these {should_be_same_day} Sales Orders, {is_same_day} were actually shipped on the same day before 6 pm, "
          f"which corresponds to a proportion of {((is_same_day/should_be_same_day)*100):.2f} percent.")


def find_oligo_orders_without_shipping_item(from_date):
    """
    bench execute microsynth.microsynth.migration.find_oligo_orders_without_shipping_item --kwargs "{'from_date': '2023-12-31'}"
    """
    orders = frappe.db.get_all("Sales Order",
                               filters=[['docstatus', '=', 1],
                                        ['product_type', '=', 'Oligos'],
                                        ['transaction_date', '>=', from_date]],
                               fields=['name'])
    print(f"Sales Order;Is Punchout;Date;Web Order ID;Status;Customer;Customer Name;Grand Total;Currency;Creator")
    for i, order in enumerate(orders):
        if i % 100 == 0:
            print(f"{i}/{len(orders)} ...")
        so = frappe.get_doc("Sales Order", order['name'])
        shipping = False
        unwanted_item = False
        for item in reversed(so.items):
            if item.item_group == "Shipping":
                shipping = True
                break
            if item.item_code == '0975' or item.item_code == '6100':
                unwanted_item = True
                break
        if not shipping and not unwanted_item:
            print(f"{so.name};{so.is_punchout};{so.transaction_date};{so.web_order_id};{so.status};{so.customer};{so.customer_name};{so.grand_total};{so.currency};{so.owner}")


def find_contacts_without_address():
    """
    bench execute microsynth.microsynth.migration.find_contacts_without_address
    """
    sql_query = """
        SELECT
            `tabContact`.`name` AS `contact_id`,
            `tabContact`.`first_name` AS `first_name`,
            `tabContact`.`last_name` AS `last_name`,
            `tabContact`.`contact_classification`,
            `tabContact`.`creation` AS `creation_date`,
            `tabContact`.`owner` AS `creator`
        FROM `tabContact`
        WHERE `tabContact`.`status` != 'Disabled'
            AND (`tabContact`.`address` IS NULL OR `tabContact`.`address` = '')
        ;"""
    contacts = frappe.db.sql(sql_query, as_dict=True)
    print(f"There are {len(contacts)} non-Disabled Contacts without an address.")


def fix_contacts_without_address():
    """
    Search for Contacts without an Address.
    Check if there is an Address with the same ID as the Contact and if both belong to the same Customer.

    bench execute microsynth.microsynth.migration.fix_contacts_without_address
    """
    sql_query = f"""
        SELECT `tabContact`.`name`,
            `tabContact`.`full_name`,
            `tabContact`.`owner`,
            `tabContact`.`creation`,
            `tabCustomer`.`name` AS `customer`,
            `tabCustomer`.`customer_name`,
            `tabContact`.`customer_status`,
            `tabContact`.`contact_classification`
        FROM `tabContact`
        LEFT JOIN `tabDynamic Link` AS `tDLA` ON `tDLA`.`parent` = `tabContact`.`name`
                                            AND `tDLA`.`parenttype` = "Contact"
                                            AND `tDLA`.`link_doctype` = "Customer"
        LEFT JOIN `tabCustomer` ON `tabCustomer`.`name` = `tDLA`.`link_name`
        WHERE `tabContact`.`address` IS NULL
            AND `tabContact`.`status` = 'Passive'
        """
    contacts = frappe.db.sql(sql_query, as_dict=True)

    print(f"{len(contacts)=}")
    for contact in contacts:
        if frappe.db.exists("Address", contact['name']):
            address = frappe.get_doc("Address", contact['name'])
            for reference in address.links:
                if reference.link_doctype == "Customer":
                    if reference.link_name == contact['customer']:
                        print(f"Found a matching address with the same ID for Contact {contact['name']} belonging both to Customer {contact['customer']}.")
                    else:
                        print(f"Contact {contact['name']} belongs to Customer {contact['customer']} but Address {address.name} belongs to Customer {reference.link_name}.")


def parse_abacus_account_sheet(account_sheet, export_file):
    """
    Parse the abacus account sheet. To that end, copy the data from Excel to a TAB-delimited text file.

    Important Note:

    The column 'C' is hidden in the Excel sheet. First expand the column before copying the data to the text file.

    run
    bench execute microsynth.microsynth.migration.parse_abacus_account_sheet --kwargs "{'account_sheet': '/mnt/erp_share/abacus_account_sheet.txt', 'export_file': '/mnt/erp_share/abacus_transactions.txt'}"
    """

    transactions = []

    def append_without_duplicates(transactions, _tx):
        if len(transactions) > 0 and transactions[-1]['reference'] == _tx['reference']:
            transactions[-1]['gross'] += _tx.get('gross') or 0
            transactions[-1]['tax'] += _tx.get('tax') or 0
            transactions[-1]['net'] += _tx.get('net') or 0
            transactions[-1]['debit'] += _tx.get('debit') or 0
            transactions[-1]['credit'] += _tx.get('credit') or 0
        else:
            transactions.append(_tx)
        return

    _tx = None

    with open(account_sheet) as file:
        for l in file:
        # for l in aba_txs.split("\n"):
            # field definition 0:date|1:reference|2:account|3:??|4:code|5:doc_no|6:debit|7:credit|8:balance
            fields = l.replace("\n","").split("\t")

            if len(fields) != 9:
                raise ValueError(f"The line does not have 8 fields:\n{fields}\nnumber of fields: {len(fields)}\n\nDid you include the hidden column C from the Excel sheet?")

            debit = float(fields[6].replace("'", "").replace("’", "")) if fields[6] else 0
            credit = float(fields[7].replace("'", "").replace("’", "")) if fields[7] else 0
            if fields[0]:
                if _tx:
                    # check if this is the same reference as the row before
                    append_without_duplicates(transactions, _tx)
                _gross = debit - credit
                _tx = {
                    'date': fields[0],
                    'reference': fields[1],
                    'gross': _gross,
                    'debit': debit,
                    'credit': credit,
                    'tax': 0,
                    'net': 0
                }
            else:
                if _tx:
                    _tax = debit - credit
                    _tx.update({
                        'tax': _tax,
                        'net': round((_tx['gross'] + _tax), 2),
                        'debit': round((_tx['debit'] + debit), 2),
                        'credit': round((_tx['credit'] + credit), 2)
                    })
        if _tx:         # append last transaction
            append_without_duplicates(transactions, _tx)
    file.close()

    with open(export_file, "w") as export_file:
        net_total = 0
        for t in transactions:
            export_line = ("{0}\t{1}\t{2}\t{3}\t{4}\t{5}\t{6}".format(
                t.get('date'), t.get('reference'), t.get('gross'), t.get('tax') or 0, (t.get('net') or t.get('gross')), t.get('debit'), t.get('credit')))
            export_file.write(export_line + "\n")
            # print(export_line)
            net_total += (t.get('net') or t.get('gross'))

        summary_line=("Net total:\t{0}".format(round(net_total, 2)))
        export_file.write(summary_line)
        print(summary_line)

    export_file.close()


def find_duplicate_items():
    """
    bench execute microsynth.microsynth.migration.find_duplicate_items
    """
    duplicates = set()
    enabled_items = frappe.db.get_all("Item", filters={'disabled': 0}, fields=['name', 'item_name', 'item_group', 'creation'])
    print("Item Group;Item Code;Item Name;Creation")
    for item in enabled_items:
        potential_duplicates = frappe.db.get_all("Item", filters={'disabled': 0, 'item_name': item['item_name']}, fields=['name', 'item_name', 'item_group', 'creation'])
        if len(potential_duplicates) > 1:
            for duplicate in potential_duplicates:
                if not duplicate['name'] in duplicates:
                    print(f"{duplicate['item_group']};{duplicate['name']};{duplicate['item_name']};{duplicate['creation']}")
                duplicates.add(duplicate['name'])


def find_unused_enabled_items():
    """
    Find Items that do not occur on any valid document, oligo or sample.

    bench execute microsynth.microsynth.migration.find_unused_enabled_items
    """
    from datetime import date
    enabled_items = frappe.db.get_all("Item", filters={'disabled': 0}, fields=['name', 'item_name', 'item_group', 'creation'])
    counter = 0
    price_counter = 0
    print("There are Item Prices for the following enabled Items that do not occur on any valid SQ, QTN, SO, DN, SI, Oligo or Sample in the ERP:")
    print("Item Group;Item Code;Item Name;Item Prices")
    for item in enabled_items:
        if "AC-" in item['name']:
            continue
        sq_items = frappe.db.get_all("Standing Quotation Item", filters={'docstatus': 1, 'item_code': item['name']}, fields=['name'])
        qtn_items = frappe.db.get_all("Quotation Item", filters={'docstatus': 1, 'item_code': item['name']}, fields=['name'])
        so_items = frappe.db.get_all("Sales Order Item", filters={'docstatus': 1, 'item_code': item['name']}, fields=['name'])
        dn_items = frappe.db.get_all("Delivery Note Item", filters={'docstatus': 1, 'item_code': item['name']}, fields=['name'])
        si_items = frappe.db.get_all("Sales Invoice Item", filters={'docstatus': 1, 'item_code': item['name']}, fields=['name'])
        sample_items = frappe.db.get_all("Sample Item", filters={'item_code': item['name']}, fields=['name'])
        oligo_items = frappe.db.get_all("Oligo Item", filters={'item_code': item['name']}, fields=['name'])
        if len(sq_items) + len(qtn_items) + len(so_items) + len(dn_items) + len(si_items) + len(sample_items) + len(oligo_items) == 0:
            item_prices = frappe.db.get_all("Item Price", filters={'item_code': item['name']}, fields=['name'])
            print(f"{item['item_group']};{item['name']};'{item['item_name']}';{len(item_prices)}")
            counter += 1
            price_counter += len(item_prices)
    print(f"There are {counter} enabled Items in the ERP that do not occur on any valid document.")
    print(f"There seem to be {price_counter} useless Item Prices of enabled Items.")


def find_unused_enabled_items_with_price():
    """
    Find Items that are created before 2023-09-01, do not occur on any valid document, oligo or sample and have at least one Item Price.

    bench execute microsynth.microsynth.migration.find_unused_enabled_items_with_price
    """
    from datetime import date
    enabled_items = frappe.db.get_all("Item", filters={'disabled': 0}, fields=['name', 'item_name', 'item_group', 'creation'])
    counter = 0
    price_counter = 0
    print("There are Item Prices for the following enabled Items that do not occur on any valid SQ, QTN, SO, DN, SI, Oligo or Sample in the ERP:")
    print("Item Group;Item Code;Item Name;Item Prices")
    for item in enabled_items:
        if "AC-" in item['name'] or item['creation'].date() > date(2023, 8, 31):
            continue
        sq_items = frappe.db.get_all("Standing Quotation Item", filters={'docstatus': 1, 'item_code': item['name']}, fields=['name'])
        qtn_items = frappe.db.get_all("Quotation Item", filters={'docstatus': 1, 'item_code': item['name']}, fields=['name'])
        so_items = frappe.db.get_all("Sales Order Item", filters={'docstatus': 1, 'item_code': item['name']}, fields=['name'])
        dn_items = frappe.db.get_all("Delivery Note Item", filters={'docstatus': 1, 'item_code': item['name']}, fields=['name'])
        si_items = frappe.db.get_all("Sales Invoice Item", filters={'docstatus': 1, 'item_code': item['name']}, fields=['name'])
        sample_items = frappe.db.get_all("Sample Item", filters={'item_code': item['name']}, fields=['name'])
        oligo_items = frappe.db.get_all("Oligo Item", filters={'item_code': item['name']}, fields=['name'])
        if len(sq_items) + len(qtn_items) + len(so_items) + len(dn_items) + len(si_items) + len(sample_items) + len(oligo_items) == 0:
            item_prices = frappe.db.get_all("Item Price", filters={'item_code': item['name']}, fields=['name'])
            if len(item_prices) > 0:
                print(f"{item['item_group']};{item['name']};'{item['item_name']}';{len(item_prices)}")
                counter += 1
                price_counter += len(item_prices)
    print(f"There are {counter} enabled Items in the ERP that do not occur on any valid document but have at least one Item Price.")
    print(f"There seem to be {price_counter} useless Item Prices of enabled Items.")


def check_items_to_disable(items_to_disable):
    """
    Takes a list of Item Codes and checks if they appear on any new document, Sample or Oligo (created 2024-01-01 or later).
    Already disabled Items are skipped.

    bench execute microsynth.microsynth.migration.check_items_to_disable --kwargs "{'items_to_disable': ['0001','0002','0346','0347','0446','0447','0610','0611','0612','0681','0682','0683','0684','0685','0686','0687','0688','0689','0690','0691','0692','0693','0694','0695','0990','0991','0992','0999','1002','1003','1005','1006','1007','3001','3002','3003','3004','3005','3006','3007','3008','3009','3010','3051','3052','3053','3054','3055','3056','3057','3058','3059','3060','3101','3102','3103','3121','3122','3123','3201','3202','3203','3204','3205','3206','3207','3208','3209','3210','3241','3242','3243']}"
    """
    for item_code in items_to_disable:
        if frappe.get_value("Item", item_code, "disabled"):  # check if Item is already disabled
            continue
        my_filters = [['docstatus', '<', '2'], ['item_code', '=', item_code], ['creation', '>=', '2024-01-01']]
        my_fields = ['name', 'parent']

        sq_items = frappe.db.get_all("Standing Quotation Item", filters=my_filters, fields=my_fields)
        if len(sq_items) > 0:
            print(f"Item {item_code} is used on {len(sq_items)} Standing Quotations: {', '.join(sq_item['parent'] for sq_item in sq_items)}")

        qtn_items = frappe.db.get_all("Quotation Item", filters=my_filters, fields=my_fields)
        if len(qtn_items) > 0:
            print(f"Item {item_code} is used on {len(qtn_items)} Quotations: {', '.join(qtn_item['parent'] for qtn_item in qtn_items)}")

        so_items = frappe.db.get_all("Sales Order Item", filters=my_filters, fields=my_fields)
        if len(so_items) > 0:
            print(f"Item {item_code} is used on {len(so_items)} Sales Orders: {', '.join(so_item['parent'] for so_item in so_items)}")

        dn_items = frappe.db.get_all("Delivery Note Item", filters=my_filters, fields=my_fields)
        if len(dn_items) > 0:
            print(f"Item {item_code} is used on {len(dn_items)} Delivery Notes: {', '.join(dn_item['parent'] for dn_item in dn_items)}")

        si_items = frappe.db.get_all("Sales Invoice Item", filters=my_filters, fields=my_fields)
        if len(si_items) > 0:
            print(f"Item {item_code} is used on {len(si_items)} Sales Invoices: {', '.join(si_item['parent'] for si_item in si_items)}")

        sample_items = frappe.db.get_all("Sample Item", filters=my_filters, fields=my_fields)
        if len(sample_items) > 0:
            print(f"Item {item_code} is used on {len(sample_items)} Samples: {', '.join(sample_item['parent'] for sample_item in sample_items)}")

        oligo_items = frappe.db.get_all("Oligo Item", filters=my_filters, fields=my_fields)
        if len(oligo_items) > 0:
            print(f"Item {item_code} is used on {len(oligo_items)} Oligos: {', '.join(oligo_item['parent'] for oligo_item in oligo_items)}")


def find_users_without_signature():
    """
    bench execute microsynth.microsynth.migration.find_users_without_signature
    """
    users = frappe.get_all("User", filters={'enabled': 1, 'user_type': 'System User'}, fields=['email'])

    for user in users:
        if not frappe.db.exists("Signature", user['email']):
            print(f"There is no Signature for {user['email']}")


def find_users_without_user_settings():
    """
    bench execute microsynth.microsynth.migration.find_users_without_user_settings
    """
    users = frappe.get_all("User", filters={'enabled': 1, 'user_type': 'System User'}, fields=['email'])

    for user in users:
        if not frappe.db.exists("User Settings", user['email']):
            print(f"There are no User Settings for {user['email']}")


# def clean_phone_number(number):
#     number = number.strip()
#     # replace leading + by 00
#     if number[0] == '+':
#         if number.count('+') == 1:
#             number = number.replace('+', '00')
#     number.replace('(0)', '')
#     return re.sub('[ \+.\-\/]', '', number)


# def clean_all_phone_numbers():
#     """
#     bench execute microsynth.microsynth.migration.clean_all_phone_numbers
#     """
#     sql_query = f"""
#         SELECT `tabContact`.`name`
#         FROM `tabContact`
#         WHERE `tabContact`.`status` != 'Disabled'
#             AND `tabContact`.`contact_classification` = 'Buyer'
#             AND `tabContact`.`phone` IS not NULL
#             AND `tabContact`.`phone` != ''
#             AND `tabContact`.`phone` NOT REGEXP '^[0-9]+$';
#         """
#     contacts = frappe.db.sql(sql_query, as_dict=True)

#     print(f"{len(contacts)=}")
#     for i, contact in enumerate(contacts):
#         if i > 100:
#             break
#         continued = False
#         contact_doc = frappe.get_doc("Contact", contact['name'])
#         for number in contact_doc.phone_nos:
#             if number.is_primary_phone:
#                 original_number = number.phone
#                 if len(original_number) > 20:
#                     print(f"{len(original_number)=}: {original_number} (Contact {contact_doc.name}), please process manually, going to continue")
#                     continued = True
#                     continue
#                 number.phone = clean_phone_number(number.phone)
#                 #print(f"{original_number=}, cleaned_number={number.phone}")
#                 if len(number.phone) > 15:
#                     print(f"The cleaned phone number is too long for UPS (length > 15): {number.phone} (Contact {contact_doc.name})")
#                 contact_doc.phone = number.phone
#                 break
#         if continued:
#             continue
#         contact_doc.append("phone_nos", {
#                 'phone': original_number,
#                 'is_primary_phone': 0
#             })
#         contact_doc.save()
#         if not contact_doc.phone.isnumeric():
#             print(f"There are still non-numeric characters in the phone number '{contact_doc.phone}' of Contact {contact_doc.name}. Please process manually.")


def check_clean_docstatus_deviations():
    """
    This function will find and resolve deviations in child docstati (when the document has e.g. status 2, but the child node don't)

    bench execute microsynth.microsynth.migration.check_clean_docstatus_deviations
    """
    # find all submittable doctypes
    submittable_doctypes = frappe.get_all("DocType", filters={'is_submittable': 1}, fields=['name'])
    # for each doctype, find children doctypes
    for doctype in submittable_doctypes:
        dt = doctype['name']
        print("Analysing {0}...".format(dt))
        for f in frappe.get_meta(dt).fields:
            if f.fieldtype == "Table":
                # find deviations:
                deviations = frappe.db.sql("""
                    SELECT
                        "{dt}" AS `doctype`,
                        "{child_dt}" AS `child_doctype`,
                        `tab{dt}`.`name` AS `docname`,
                        `tab{dt}`.`docstatus` AS `docstatus`,
                        `tab{child_dt}`.`name` AS `childname`,
                        `tab{child_dt}`.`docstatus` AS `child_docstatus`
                    FROM `tab{dt}`
                    LEFT JOIN `tab{child_dt}` ON `tab{child_dt}`.`parent` = `tab{dt}`.`name`
                                                 AND `tab{child_dt}`.`parenttype` = "{dt}"
                    WHERE `tab{dt}`.`docstatus` != `tab{child_dt}`.`docstatus`
                    ;
                """.format(dt=dt, child_dt=f.options), as_dict=True)
                for d in deviations:
                    frappe.db.sql("""
                        UPDATE `tab{child_dt}`
                        SET `docstatus` = {parent_docstatus}
                        WHERE `name` = "{child_name}";
                        """.format(
                            child_dt=d['child_doctype'],
                            child_name=d['childname'],
                            parent_docstatus=d['docstatus']
                        ), as_dict=True
                    )
                    print("{0}".format(d))
                frappe.db.commit()


def lock_seq_label_duplicates(label_barcodes):
    """
    Takes a list of Label Barcodes.
    For each Label Barcode:
    1) Search Sequencing Labels
    2) Check expectation: Exact 2 Sequencing Labels, one with status locked, one with status unused (if not, print an error and continue)
    3) Set the status of the unused Sequencing Label to locked

    bench execute microsynth.microsynth.migration.lock_seq_label_duplicates --kwargs "{'label_barcodes': ['27591', '27352', '27353']}"
    """
    disabled_customers = set()

    for label_barcode in label_barcodes:
        sequencing_labels = frappe.get_all("Sequencing Label", filters={'label_id': label_barcode}, fields=['name', 'status'])
        if len(sequencing_labels) == 2:
            locked_id = None
            unused_id = None
            for seq_label in sequencing_labels:
                if seq_label['status'] == 'locked':
                    locked_id = seq_label['name']
                elif seq_label['status'] == 'unused':
                    unused_id = seq_label['name']
            if locked_id and unused_id:
                # Set the status of the unused Sequencing Label to locked
                seq_label_doc = frappe.get_doc("Sequencing Label", unused_id)
                if seq_label_doc.status == 'unused':
                    seq_label_doc.status = 'locked'
                    try:
                        seq_label_doc.save()
                        print(f"Set status of Sequencing Label {seq_label_doc.name} with Label Barcode {seq_label_doc.label_id} from status unused to status {seq_label_doc.status}.")
                    except Exception as err:
                        print(f"Got the following exception when trying to save Sequencing Label {seq_label.name}: {err}. Trying to enable the Customer.")
                        if seq_label_doc.customer:
                            customer_doc = frappe.get_doc("Customer", seq_label_doc.customer)
                            if customer_doc.disabled:
                                # enable Customer
                                customer_doc.disabled = 0
                                customer_doc.save(ignore_permissions=True)
                                disabled_customers.add(customer_doc.name)
                                print(f"Enabled Customer '{customer_doc.name}'.")
                                try:
                                    seq_label_doc = frappe.get_doc("Sequencing Label", unused_id)
                                    seq_label_doc.status = 'locked'
                                    seq_label_doc.save()
                                    print(f"Set status of Sequencing Label {seq_label_doc.name} with Label Barcode {seq_label_doc.label_id} from status unused to status {seq_label_doc.status}.")
                                except Exception as err:
                                    print(f"### Got the following exception when trying to save Sequencing Label {seq_label.name}: {err}. Unable to save Sequencing Label. Going to continue.")
                            else:
                                print(f"Customer '{customer_doc.name}' of Sequencing Label {seq_label_doc.name} is not disabled. Please check the error message above. Going to continue.")
                                continue
                        else:
                            print(f"Sequencing Label {seq_label_doc.name} has no Customer. Please check the error message above. Going to continue.")
                            continue
                else:
                    print(f"This should not happen: Sequencing Label {seq_label_doc.name} has status {seq_label_doc.status} but expected status unused. Going to continue.")
                    continue
            else:
                print(f"Found 2 Sequencing Labels for Label Barcode {label_barcode} but not 1 locked and 1 unused: {sequencing_labels}. Going to continue.")
                continue
        else:
            print(f"Found {len(sequencing_labels)} Sequencing Labels for Label Barcode {label_barcode}: {sequencing_labels}. Going to continue.")
            continue

    # Disable Customers that were disabled before calling this function
    for customer_to_disable in disabled_customers:
        customer_doc = frappe.get_doc("Customer", customer_to_disable)
        customer_doc.disabled = 1
        customer_doc.save(ignore_permissions=True)
        print(f"Disabled Customer '{customer_doc.name}'.")


def delete_seq_label_duplicates(sequencing_label_ids, dry_run=True):
    """
    Takes a list of Sequencing Label IDs.
    For each Sequencing Label ID:
    1) Get Sequencing Label Doc
    2) Check expectation: Exact 2 Sequencing Labels with the Label Barcode of the Sequencing Label Doc (if not, print an error and continue)
    3) Delete Sequencing Label Doc of the given ID

    bench execute microsynth.microsynth.migration.delete_seq_label_duplicates --kwargs "{'sequencing_label_ids': ['SL003108894', 'SL003108895'], 'dry_run': False}"
    """
    for sequencing_label_id in sequencing_label_ids:
        seq_label_doc = frappe.get_doc("Sequencing Label", sequencing_label_id)
        sequencing_labels = frappe.get_all("Sequencing Label", filters={'label_id': seq_label_doc.label_id}, fields=['name'])
        if len(sequencing_labels) > 1:
            base_string = f"Sequencing Label {seq_label_doc.name} with Label Barcode {seq_label_doc.label_id}, Status {seq_label_doc.status}, Item {seq_label_doc.item}, Sales Order {seq_label_doc.sales_order}, Contact {seq_label_doc.contact} and Customer {seq_label_doc.customer}"
            if not dry_run:
                seq_label_doc.delete()
                print(f"Deleted {base_string}.")
            else:
                print(f"Would delete {base_string}.")
        else:
            print(f"There is only one Sequencing Label with Label Barcode {seq_label_doc.label_id}. Not deleting {seq_label_doc.name}, going to continue.")


def lock_both_seq_label_duplicates(label_barcodes):
    """
    Takes a list of Label Barcodes.
    For each Label Barcode:
    1) Search all Sequencing Labels
    2) Check expectation: Exact 2 Sequencing Labels
    3) Set the status of both Sequencing Labels to locked

    bench execute microsynth.microsynth.migration.lock_both_seq_label_duplicates --kwargs "{'label_barcodes': ['27353', '8566169', '10292411']}"
    """
    disabled_customers = set()

    for label_barcode in label_barcodes:
        sequencing_labels = frappe.get_all("Sequencing Label", filters={'label_id': label_barcode}, fields=['name', 'status'])
        if len(sequencing_labels) == 2:
            for seq_label in sequencing_labels:
                # Set the status of the Sequencing Label to locked
                try:
                    seq_label_doc = frappe.get_doc("Sequencing Label", seq_label['name'])
                    seq_label_doc.status = 'locked'
                    seq_label_doc.save()
                    print(f"Set status of Sequencing Label {seq_label_doc.name} with Label Barcode {seq_label_doc.label_id} from status {seq_label['status']} to status {seq_label_doc.status}.")
                except Exception as err:
                    print(f"Got the following exception when trying to save Sequencing Label {seq_label.name}: {err}. Trying to enable the Customer.")
                    if seq_label_doc.customer:
                        customer_doc = frappe.get_doc("Customer", seq_label_doc.customer)
                        if customer_doc.disabled:
                            # enable Customer
                            customer_doc.disabled = 0
                            customer_doc.save(ignore_permissions=True)
                            disabled_customers.add(customer_doc.name)
                            print(f"Enabled Customer '{customer_doc.name}'.")
                            try:
                                seq_label_doc = frappe.get_doc("Sequencing Label", seq_label['name'])  # necessary to avoid error "modified after opened"
                                seq_label_doc.status = 'locked'
                                seq_label_doc.save()
                                print(f"Set status of Sequencing Label {seq_label_doc.name} with Label Barcode {seq_label_doc.label_id} from status {seq_label['status']} to status {seq_label_doc.status}.")
                            except Exception as err:
                                print(f"### Got the following exception when trying to save Sequencing Label {seq_label.name}: {err}. Unable to save Sequencing Label. Going to continue.")
                        else:
                            print(f"##### Customer '{customer_doc.name}' of Sequencing Label {seq_label_doc.name} is not disabled. Please check the error message above. Going to continue.")
                            continue
                    else:
                        print(f"#### Sequencing Label {seq_label_doc.name} has no Customer. Please check the error message above. Going to continue.")
                        continue
        else:
            print(f"Found {len(sequencing_labels)} Sequencing Labels for Label Barcode {label_barcode}: {sequencing_labels}. Going to continue.")
            continue

    # Disable Customers that were disabled before calling this function
    for customer_to_disable in disabled_customers:
        customer_doc = frappe.get_doc("Customer", customer_to_disable)
        customer_doc.disabled = 1
        customer_doc.save(ignore_permissions=True)
        print(f"Disabled Customer '{customer_doc.name}'.")


def change_default_company(old_company, new_company, countries_to_change, dry_run=True):
    """
    bench execute microsynth.microsynth.migration.change_default_company --kwargs "{'old_company': 'Microsynth Austria GmbH', 'new_company': 'Microsynth Seqlab GmbH', 'countries_to_change': ['Croatia', 'Hungary', 'Slovakia', 'Slovenia']}"
    """
    customers = frappe.db.get_all("Customer",
                                filters=[['disabled', '=', '0']],
                                fields=['name', 'customer_name'])
    print(f"Going to check {len(customers)} enabled Customers ...")
    for c in customers:
        query = f"""
            SELECT DISTINCT `tabAddress`.`country`
            FROM `tabAddress`
            LEFT JOIN `tabDynamic Link` AS `tDLA` ON `tDLA`.`parent` = `tabAddress`.`name`
                                                AND `tDLA`.`parenttype` = "Address"
                                                AND `tDLA`.`link_doctype` = "Customer"
            WHERE `tDLA`.`link_name` = "{c['name']}";"""

        countries = frappe.db.sql(query, as_dict=True)
        country_match = ""
        for country in countries:
            if country['country'] in countries_to_change:
                country_match = country['country']
                break
        if country_match:
            country_mismatches = set()
            for country in countries:
                if country['country'] not in countries_to_change:
                    country_mismatches.add(country['country'])
            if len(country_mismatches) > 0:
                print(f"Enabled Customer '{c['name']}' ('{c['customer_name']}') has an Address in {country_match} but also Addresses in {country_mismatches}.")
                continue
            else:
                customer_doc = frappe.get_doc("Customer", c['name'])
                if customer_doc.default_company == old_company:
                    if dry_run:
                        print(f"Would change Default Company of enabled Customer '{c['name']}' ('{c['customer_name']}') with an Address in {country_match} from {customer_doc.default_company} to {new_company}.")
                    else:
                        customer_doc.default_company = new_company
                        customer_doc.save()
                        print(f"Changed Default Company of enabled Customer '{c['name']}' ('{c['customer_name']}') with an Address in {country_match} from {customer_doc.default_company} to {new_company}.")
                else:
                    print(f"Enabled Customer '{c['name']}' ('{c['customer_name']}') with an Address in {country_match} has Default Company {customer_doc.default_company}.")


def change_contact_email(old_email, new_email):
    """
    Change all primary Email Addresses of Passive (enabled) Contacts from old_email to new_email.

    bench execute microsynth.microsynth.migration.change_contact_email --kwargs "{'old_email': 'firstname.lastname@microsynth.ch', 'new_email': '...@microsynth.ch'}"
    """
    contacts = frappe.get_all("Contact", filters={'email_id': old_email, 'status': 'Passive'}, fields=['name'])
    for contact in contacts:
        contact_doc = frappe.get_doc("Contact", contact['name'])
        for email_id in contact_doc.email_ids:
            if email_id.email_id == old_email and email_id.is_primary:
                email_id.email_id = new_email
            else:
                #print(f"### Contact '{contact_doc.name}': {email_id.is_primary=} {email_id.email_id}")
                continue
        if contact_doc.user == old_email:
            contact_doc.user = None
        contact_doc.email_id = new_email
        contact_doc.save()
        print(f"Changed email_id of Contact '{contact_doc.name}' from {old_email} to {new_email}")


def update_customers_payment_terms(country, email_id, new_payment_terms_template, update_invoicing_method=False, dry_run=True):
    """
    Set all enabled Customers with an enabled billing Address in the given Country,
    an enabled Contact with the given email_id and Payment Terms unequal the given Payment Terms Template
    to the given Payment Terms Template.

    bench execute microsynth.microsynth.migration.update_customers_payment_terms --kwargs "{'country': 'France', 'email_id': 'i...@microsynth.ch', 'new_payment_terms_template': '30 days net', 'update_invoicing_method': True, 'dry_run': True}"
    """
    sql_query = f"""
        SELECT DISTINCT `tabCustomer`.`name` AS `customer_id`,
            `tabCustomer`.`customer_name`,
            `tabCustomer`.`payment_terms`
        FROM `tabCustomer`
        LEFT JOIN `tabContact` ON `tabContact`.`name` = `tabCustomer`.`invoice_to`
        LEFT JOIN `tabAddress` ON `tabAddress`.`name` = `tabContact`.`address`
        WHERE `tabAddress`.`country` = "{country}"
            AND `tabAddress`.`address_type` = 'Billing'
            AND `tabAddress`.`disabled` = 0
            AND `tabContact`.`email_id` = "{email_id}"
            AND `tabContact`.`status` != "Disabled"
            AND `tabCustomer`.`disabled` = 0
            AND `tabCustomer`.`payment_terms` != "{new_payment_terms_template}"
        ;"""
    customers = frappe.db.sql(sql_query, as_dict=True)
    print(f"{len(customers)=}")
    for c in customers:
        customer_doc = frappe.get_doc("Customer", c['customer_id'])
        old_payment_terms = customer_doc.payment_terms
        if not dry_run:
            customer_doc.payment_terms = new_payment_terms_template
            customer_doc.save()
        print(f"{'Would set' if dry_run else 'Set'} Customer {c['customer_id']} ({c['customer_name']}) from Default Payment Terms Template '{old_payment_terms}' to '{new_payment_terms_template}'.")
        if update_invoicing_method:
            if customer_doc.invoicing_method == "Email":
                if not dry_run:
                    customer_doc.invoicing_method = "Chorus"
                    customer_doc.save()
                print(f"{'Would set' if dry_run else 'Set'} Customer {c['customer_id']} ({c['customer_name']}) from Invoicing Method Email to Chorus.")
            else:
                print(f"WARNING: Customer {c['customer_id']} ({c['customer_name']}) has Invoicing Method {customer_doc.invoicing_method}. Not going to set to Chorus.")


def delete_lost_reasons_from_not_lost_quotations():
    """
    bench execute microsynth.microsynth.migration.delete_lost_reasons_from_not_lost_quotations
    """
    query = """SELECT DISTINCT
            `tabQuotation`.`name`,
            `tabQuotation`.`status`
        FROM `tabQuotation`
        LEFT JOIN `tabLost Reason Detail` ON `tabLost Reason Detail`.`parent` = `tabQuotation`.`name`
        WHERE `tabLost Reason Detail`.`lost_reason` IS NOT NULL
            AND `tabQuotation`.`status` <> 'Lost';
        """
    quotations = frappe.db.sql(query, as_dict=True)
    for quote in quotations:
        # use DB operation due to cancelled QTNs
        frappe.db.sql(f"""
            DELETE FROM `tabLost Reason Detail`
            WHERE `tabLost Reason Detail`.`parent` = '{quote['name']}';
            """)
        print(f"Deleted the Lost Reasons from Quotation {quote['name']} with status {quote['status']}")


def rename_lost_reasons():
    """
    The new reasons should already exist as Opportunity Lost Reasons before executing this function.

    bench execute microsynth.microsynth.migration.rename_lost_reasons
    """
    mapping = {
        'More expensive than competitor': 'Price',
        'Delivery time too long': 'Turnaround Time (TAT)',
        'Did not get the funds for the project': 'Budget/Funding Issues',
        'choose another provider': 'Other',
        'wrongTitle': 'Other',
        'accidentally submitted': 'Other',
        'aborted by customer': 'Other',
        'exipred': 'Other',
        'No need': 'Other',
        '[object Object]Delivery time too long': 'Turnaround Time (TAT)',
        'expired': 'Other',
        'Analysis not required': 'Other',
        'Too expensive': 'Price',
        'technical issue': 'Missing Product/Service Feature'
    }
    for current_reason, new_reason in mapping.items():
        frappe.db.sql(f"""
            UPDATE `tabLost Reason Detail`
            SET `lost_reason` = '{new_reason}'
            WHERE `lost_reason` = '{current_reason}';""")
        print(f"Renamed Lost Reason '{current_reason}' on all Lost Reason Detail entries to '{new_reason}'.")


def lookup_unused_sequencing_labels(input_filepath, not_in_webshop_output, used_in_webshop_output):
    """
    Parse a Webshop export of Barcode Labels.
    Write those Sequencing Labels to the given output file that are unused in the ERP but received or processed in the given Webshop export.

    bench execute microsynth.microsynth.migration.lookup_unused_sequencing_labels --kwargs "{'input_filepath': '/mnt/erp_share/Sequencing/Label_Sync/2025-03-21_Webshop_Export.txt', 'not_in_webshop_output': '/mnt/erp_share/Sequencing/Label_Sync/2025-04-08_Missing_in_Webshop_Export.csv', 'used_in_webshop_output': '/mnt/erp_share/Sequencing/Label_Sync/2025-04-08_Used_in_Webshop_Export.csv'}"
    """
    print(f"Selecting unused and submitted Sequencing Labels from ERP ...")
    erp_unused_labels = frappe.get_all('Sequencing Label', filters=[['status', 'IN', ['unused', 'submitted'] ]],
                                       fields=['name', 'creation', 'owner', 'customer_name', 'locked', 'customer', 'sales_order', 'item', 'registered', 'contact', 'label_id', 'status', 'registered_to'])
    print(f"There are {len(erp_unused_labels)} unused Sequencing Labels in the ERP.")
    use_states = ['unknown', 'unused_unregistered', 'unused_registered', 'submitted', 'received', 'processed']
    counters = {state: 0 for state in use_states}
    counters['not_in_webshop'] = 0
    not_in_webshop = []
    used_in_webshop = []
    print(f"Parsing Webshop export ...")
    webshop_table = {}
    with open(input_filepath, 'r') as file:
        csv_reader = csv.reader(file, delimiter='\t')
        next(csv_reader)  # skip header
        for line in csv_reader:
            if len(line) != 9:
                print(f"{len(line)=}; {line=}; skipping")
                continue
            number = line[1]
            use_state = int(line[2])
            webshop_table[number] = use_state
    print(f"Comparing unused ERP labels to Webshop ...")
    for erp_label in erp_unused_labels:
        if erp_label['label_id'] in webshop_table:
            webshop_use_state = webshop_table[erp_label['label_id']]
            counters[use_states[webshop_use_state]] += 1
            if webshop_use_state > 3:  # received or processed
                erp_label['webshop_use_state'] = webshop_use_state
                used_in_webshop.append(erp_label)
        else:
            counters['not_in_webshop'] += 1
            not_in_webshop.append(erp_label)

    print(f"The {len(erp_unused_labels)} unused Sequencing Labels in the ERP have the following statuses in the Webshop:")
    for status, counter in counters.items():
        print(f"{status}: {counter} ({(counter/len(erp_unused_labels))*100:.2f} %)")

    print(f"Writing file {not_in_webshop_output} ...")
    if len(not_in_webshop) > 0:
        with open(not_in_webshop_output, mode='w') as file:
            writer = csv.DictWriter(file, fieldnames=not_in_webshop[0].keys())
            # Write the header (column names)
            writer.writeheader()
            # Write each dictionary as a row
            writer.writerows(not_in_webshop)

    print(f"Writing file {used_in_webshop_output} ...")
    if len(used_in_webshop) > 0:
        with open(used_in_webshop_output, mode='w') as file:
            writer = csv.DictWriter(file, fieldnames=used_in_webshop[0].keys())
            # Write the header (column names)
            writer.writeheader()
            # Write each dictionary as a row
            writer.writerows(used_in_webshop)
    print("Finished migration.lookup_unused_sequencing_labels")


def lookup_used_sequencing_labels(input_filepath, output_filepath):
    """
    Parse a Seqblatt export of used Sequencing Labels.
    Write those to the given output file that are unused in the ERP, but used according to the given Seqblatt export.

    bench execute microsynth.microsynth.migration.lookup_used_sequencing_labels --kwargs "{'input_filepath': '/mnt/erp_share/JPe/2025-03-28_seqblatt_used_labels.csv', 'output_filepath': '/mnt/erp_share/JPe/2025-04-01_wrongly_unused_Sequencing_Labels.csv'}"
    """
    #import gc  # garbage collection
    print(f"Selecting unused and submitted Sequencing Labels from ERP ...")
    erp_unused_labels = frappe.get_all('Sequencing Label', filters=[['status', 'IN', ['unused', 'submitted']]],
                                       fields=['name', 'creation', 'owner', 'customer_name', 'locked', 'customer', 'sales_order', 'item', 'registered', 'contact', 'label_id', 'status', 'registered_to'])
    print(f"There are {len(erp_unused_labels)} unused Sequencing Labels in the ERP.")
    used_in_seqblatt = []
    print(f"Writing unused ERP labels to a dictionary ...")
    erp_unused_table = {}
    for erp_label in erp_unused_labels:
        erp_unused_table[erp_label['label_id']] = erp_label
    #gc.collect()  # manually free erp_unused_labels
    print(f"Comparing used Seqblatt export to unused ERP labels ...")
    with open(input_filepath, 'r') as file:
        csv_reader = csv.reader(file, delimiter=';')
        next(csv_reader)  # skip header
        for line in csv_reader:
            if len(line) != 3:
                print(f"{len(line)=}; {line=}; skipping")
                continue
            label_no = line[0]
            if not label_no:
                continue
            web_order_id = int(line[1])
            date = line[2]
            if label_no in erp_unused_table:
                erp_label = erp_unused_table[label_no]
                erp_label['web_order_id'] = web_order_id
                erp_label['date'] = date
                used_in_seqblatt.append(erp_label)

    print(f"There are {len(used_in_seqblatt)} Labels that are used in Seqblatt but unused (incl. submitted) in the ERP. Going to write them to {output_filepath} ...")

    if len(used_in_seqblatt) > 0:
        with open(output_filepath, mode='w') as file:
            writer = csv.DictWriter(file, fieldnames=used_in_seqblatt[0].keys())
            # Write the header (column names)
            writer.writeheader()
            # Write each dictionary as a row
            writer.writerows(used_in_seqblatt)


def set_sequencing_labels_to_received(input_filepath, verbose=False, dry_run=True):
    """
    Parse the output file of the previous function lookup_used_sequencing_labels.
    Set all these Sequencing Labels to status "received" in the ERP if they have still status "unused".

    bench execute microsynth.microsynth.migration.set_sequencing_labels_to_received --kwargs "{'input_filepath': '/mnt/erp_share/JPe/2025-04-01_wrongly_unused_Sequencing_Labels.csv', 'verbose': True, 'dry_run': True}"
    """
    counter = 0
    with open(input_filepath, 'r') as file:
        csv_reader = csv.reader(file, delimiter=',')
        next(csv_reader)  # skip header
        for line in csv_reader:
            if len(line) != 15:
                print(f"{len(line)=}; {line=}; skipping")
                continue
            seq_label_id = line[0].strip()
            if not seq_label_id:
                continue
            seq_label_doc = frappe.get_doc('Sequencing Label', seq_label_id)
            if seq_label_doc.status != 'unused':
                print(f"Sequencing Label {seq_label_doc.name} with barcode {seq_label_doc.label_id} has status {seq_label_doc.status} in the ERP. Not going to set it to received, goint to continue.")
                continue
            if not dry_run:
                try:
                    seq_label_doc.status = 'received'
                    seq_label_doc.save()
                except Exception as err:
                    print(f"Unable to set Sequencing Label {seq_label_doc.name} with barcode {seq_label_doc.label_id} to status {seq_label_doc.status}: {err}")
                else:
                    counter += 1
                if counter % 1000 == 0:
                    frappe.db.commit()
            if verbose:
                print(f"Set Sequencing Label {seq_label_doc.name} with barcode {seq_label_doc.label_id} to status {seq_label_doc.status}.")
    print(f"Successfully set {counter} Sequencing Labels to received.")


def set_unused_sequencing_labels_to_received(input_filepath, verbose=False, dry_run=True):
    """
    Parse a Webshop export and set unused and submitted ERP Sequencing Labels to "received" if they have use state 4 (=received) in the Webshop export.

    bench execute microsynth.microsynth.migration.set_unused_sequencing_labels_to_received --kwargs "{'input_filepath': '/mnt/erp_share/Sequencing/Label_Sync/2025-03-21_Webshop_Export.txt', 'verbose': False, 'dry_run': True}"
    """
    print(f"Selecting unused and submitted Sequencing Labels from ERP ...")
    erp_unused_labels = frappe.get_all('Sequencing Label', filters=[['status', 'IN', ['unused', 'submitted'] ]],
                                       fields=['name', 'label_id', 'status'])
    print(f"There are {len(erp_unused_labels)} unused Sequencing Labels in the ERP. Parsing Webshop export ...")

    webshop_table = {}
    with open(input_filepath, 'r') as file:
        csv_reader = csv.reader(file, delimiter='\t')
        next(csv_reader)  # skip header
        for line in csv_reader:
            if len(line) != 9:
                print(f"{len(line)=}; {line=}; skipping")
                continue
            number = line[1]
            use_state = int(line[2])
            webshop_table[number] = use_state
    print(f"Comparing unused ERP labels to Webshop and setting received ...")
    received_counter = 0
    for erp_label in erp_unused_labels:
        if erp_label['label_id'] in webshop_table:
            webshop_use_state = webshop_table[erp_label['label_id']]
            if webshop_use_state == 4:  # 4 = received
                received_counter += 1
    changed_counter = 0
    for erp_label in erp_unused_labels:
        if erp_label['label_id'] in webshop_table:
            webshop_use_state = webshop_table[erp_label['label_id']]
            if webshop_use_state == 4:  # 4 = received
                erp_label_doc = frappe.get_doc("Sequencing Label", erp_label['name'])
                if verbose:
                    print(f"{changed_counter+1}/{received_counter}: Setting the status of Sequencing Label {erp_label_doc.name} with Barcode {erp_label_doc.label_id} from {erp_label_doc.status} to received.")
                if not dry_run:
                    erp_label_doc.status = "received"
                    try:
                        erp_label_doc.save()
                    except Exception as err:
                        print(f"Unable to set the status of Sequencing Label {erp_label_doc.name} with Barcode {erp_label_doc.label_id} from {erp_label_doc.status} to received: {err}")
                    else:
                        changed_counter += 1
                        if not verbose and changed_counter % 100 == 0:
                            frappe.db.commit()
                            print(f"Already changed status of {changed_counter}/{received_counter} Sequencing Labels.")
    print(f"Successfully set {changed_counter} ERP Sequencing Labels from status unused to status received according to the Webshop.")


def change_payable_account_on_supplier(company, old_account, new_account, exclude_microsynth=True):
    """
    bench execute microsynth.microsynth.migration.change_payable_account_on_supplier --kwargs "{'company': 'Microsynth France SAS', 'old_account': '4191000 - Clients acptes s/com - LYO', 'new_account': '4010000 - Fournisseurs - LYO'}"
    """
    suppliers = frappe.get_all("Supplier", filters={'disabled': 0}, fields=['name', 'supplier_name'])
    print(f"Going to process {len(suppliers)} enabled Suppliers.")

    for supplier in suppliers:
        if exclude_microsynth and 'Microsynth' in supplier['supplier_name']:
            continue
        supplier_doc = frappe.get_doc('Supplier', supplier['name'])
        for account in supplier_doc.accounts:
            if account.company == company:
                if account.account == old_account:
                    account.account = new_account
                    print(f"Supplier {supplier.name} ({supplier.supplier_name}): Changed Account '{old_account}' for Company {company} to '{new_account}'.")
                else:
                    print(f"### Supplier {supplier.name} ({supplier.supplier_name}) has Account '{account.account}' for Company {company}.")
        supplier_doc.save()


def find_missing_web_order_ids(input_filepath, output_filepath):
    """
    Read an export of the Webshop table Orders assuming that the Web Order ID is in the second column with index 1.
    For each Web Order ID: Search all submitted Sales Orders in the ERP.
    If no submitted Sales Order was found in the ERP, write the corresponding line from the input file to the output file.
    Could be more efficient by doing just one DB query and using some hash tables in Python.

    bench execute microsynth.microsynth.migration.find_missing_web_order_ids --kwargs "{'input_filepath': '/mnt/erp_share/JPe/2025-04-30_Webshop_orders_2024_without_oligo_or_sequencing.csv', 'output_filepath': '/mnt/erp_share/JPe/2025-04-30_ERP_missing_web_order_ids_from_2024.csv'}"
    """
    import io

    # Read the file in binary mode to get raw bytes
    with open(input_filepath, "rb") as input_file:
        raw = input_file.read()

    # Split only on CRLF (\r\n) — treat this as the true line ending
    lines = raw.split(b'\r\n')
    # Decode each line from bytes to string
    decoded_lines = [line.decode('utf-8') for line in lines]
    # Join the lines using '\n' to form a consistent CSV block
    csv_content = '\n'.join(decoded_lines)
    # Use csv.reader to parse the cleaned content
    csv_reader = csv.reader(io.StringIO(csv_content), delimiter=';')
    counter = 0

    with open(output_filepath, mode='w') as output_file:
        writer = csv.writer(output_file, delimiter=';')
        writer.writerow(next(csv_reader))
        for i, line in enumerate(csv_reader):
            if i % 100 == 0:
                print(f"Processing line {i} ...")
            if len(line) != 56:
                print(f"{len(line)=}; {line=}; skipping")
                continue
            web_order_id = line[1].strip()
            submitted_sales_orders = frappe.get_all("Sales Order", filters=[['docstatus', '<', '2'], ['web_order_id', '=', web_order_id]], fields=['name'])
            if len(submitted_sales_orders) == 0:
                writer.writerow(line)
                counter += 1
            # else:
            #     print(f"Found {len(submitted_sales_orders)} submitted Sales Order for Web Order ID {web_order_id}.")
    print(f"Wrote {counter} lines to {output_filepath}.")


def import_has_webshop_account(input_filepath):
    """
    Set Contact.has_webshop_account according to an export of the Wehshop table AspNetUsers.
    Expected runtime: several hours

    bench execute microsynth.microsynth.migration.import_has_webshop_account --kwargs "{'input_filepath': '/mnt/erp_share/JPe/2025-05-26_Export_AspNetUsers_Webshop.txt'}"
    """
    contacts_to_disable = []
    changes = 0
    print(f"{datetime.now()}: Parsing Webshop Accounts from {input_filepath} ...")
    with open(input_filepath, "r") as input_file:
        csv_reader = csv.reader(input_file, delimiter='\t')
        next(csv_reader)  # skip header
        for counter, line in enumerate(csv_reader):
            if len(line) != 35:
                print(f"{len(line)=}; {line=}; skipping")
                continue
            if counter % 100 == 0:
                frappe.db.commit()
                print(f"INFO: Already processed {counter} Webshop Accounts.")
            is_deleted = line[26]
            person_id = line[29]
            if not person_id:
                print(f"Missing IdPerson for Id {line[0]}; skipping")
                continue
            if frappe.db.exists("Contact", person_id):
                contact_doc = frappe.get_doc("Contact", person_id)
                if is_deleted == "1" and contact_doc.status != "Disabled":
                    print(f"WARNING: Person ID '{person_id}' is marked as deleted in the Webshop, but has status {contact_doc.status} in the ERP.")
                    contacts_to_disable.append(person_id)
                    # contact_doc.status = "Disabled"
                    # contact_doc.save()
                if not contact_doc.has_webshop_account:
                    contact_to_disable = False
                    address_to_disable = False
                    if contact_doc.status == "Disabled":
                        contact_doc.status = "Open"  # do not set to Passive to avoid sending an email
                        contact_to_disable = True
                    try:
                        contact_doc.has_webshop_account = 1
                        contact_doc.save()
                    except frappe.exceptions.ValidationError as err:
                        print(f"INFO: {str(err)}")
                        if contact_doc.address:
                            address_doc = frappe.get_doc("Address", contact_doc.address)
                            if address_doc.disabled == 1:
                                address_doc.disabled = 0
                                address_doc.save()
                                address_to_disable = True
                                contact_doc = frappe.get_doc("Contact", person_id)  # necessary to avoid "Document has been modified after you have opened it" error
                                contact_doc.has_webshop_account = 1
                                contact_doc.save()
                        else:
                            print(f"WARNING: Contact {person_id} has no Address.")
                    except Exception as err:
                        print(f"ERROR: Got the following unexpected Error: {str(err)}")
                    if contact_to_disable:
                        contact_doc.status = "Disabled"
                        contact_doc.save()
                    if address_to_disable:
                        address_doc.disabled = 1
                        address_doc.save()
                    changes += 1
            else:
                if is_deleted == "0":
                    print(f"ERROR: Person ID '{person_id}' is not marked as deleted in the Webshop, but not found in the ERP.")
    print(f"The following {len(contacts_to_disable)} Contacts are marked as deleted in the Webshop, but are not Disabled in the ERP: {contacts_to_disable}")
    print(f"{datetime.now()}: Set 'Has Webshop Account' on {changes} Contacts.")


def check_webshop_address_billing():
    """
    Checks for all Webshop Addresses, if the default billing Contact is equals
    the Invoice to Contact of the Customer of the Webshop Account Contact.
    If not, a warning is printed.

    bench execute microsynth.microsynth.migration.check_webshop_address_billing
    """
    webshop_addresses = frappe.get_all("Webshop Address", fields=['name'])
    print(f"Going to check {len(webshop_addresses)} Webshop Addresses ...")

    for we in webshop_addresses:
        webshop_address_doc = frappe.get_doc("Webshop Address", we['name'])
        customer_id = get_customer(webshop_address_doc.webshop_account)
        invoice_to_contact = frappe.get_value("Customer", customer_id, "invoice_to")
        default_billing_contact = None
        found = False

        for row in webshop_address_doc.addresses:
            if row.is_default_billing:
                if found:
                    print(f"ERROR: Webshop Address {webshop_address_doc.name} has more than one default billing Contact.")
                    continue
                default_billing_contact = row.contact
                found = True
        if not found:
            print(f"ERROR: Webshop Address {webshop_address_doc.name} has no default billing Contact.")
            continue

        if default_billing_contact != invoice_to_contact:
            print(f"WARNING: Webshop Address {webshop_address_doc.name} has the Default Billing Contact {default_billing_contact} but the Customer {customer_id} of Contact {webshop_address_doc.webshop_account} has the Invoice to Contact {invoice_to_contact}.")


def add_shipping_item_to_customers(customers, shipping_item_code, rate, threshold, preferred_express):
    """
    Add the given Shipping Item with Qty 1 to each of the given Customers.

    bench execute microsynth.microsynth.migration.add_shipping_item_to_customers --kwargs "{'customers': ['37640699', '832460'], 'shipping_item_code': '1126', 'rate': 75, 'threshold': 1500, 'preferred_express': 1}"
    """
    item_name = frappe.get_value('Item', shipping_item_code, 'item_name')
    print(f"{item_name=}")
    for customer_id in customers:
        customer_doc = frappe.get_doc('Customer', customer_id)
        already_has_item = False
        for si in customer_doc.shipping_items:
            if si.item == shipping_item_code:
                already_has_item = True
                break
        if not already_has_item:
            #print(f"Going to add Shipping Item {shipping_item_code} with rate {rate} {customer_doc.default_currency}, {threshold=} and {preferred_express=} to Customer {customer_id}.")
            customer_doc.append("shipping_items", {
                "item": shipping_item_code,
                "item_name": item_name,
                "qty": 1,
                "rate": rate,
                "threshold": threshold,
                "preferred_express": preferred_express
            })
            customer_doc.save()
            print(f"Sucessfully added Shipping Item {shipping_item_code} with rate {rate} {customer_doc.default_currency} to Customer {customer_id}.")
        else:
            print(f"Customer {customer_id} already has Shipping Item {shipping_item_code} with rate {rate} {customer_doc.default_currency}. Going to skip.")
