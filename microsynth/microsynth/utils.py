# -*- coding: utf-8 -*-
# Copyright (c) 2022, libracore (https://www.libracore.com) and contributors
# For license information, please see license.txt

import frappe
import json

@frappe.whitelist()
def update_address_links_from_contact(address_name, links):
    
    if frappe.db.exists("Address", address_name):
        address = frappe.get_doc("Address", address_name)
        address.links = []
        if type(links) == str:
           links = json.loads(links) 
        for link in links:
            address.append("links", { 
                "link_doctype": link["link_doctype"],
                "link_name": link["link_name"]
            } )
        address.save()
    return

def create_oligo(oligo):
    oligo_doc = None
    # check if this oligo is already in the database
    if oligo['web_id']:
        oligo_matches = frappe.get_all("Oligo", 
            filters={'web_id': oligo['web_id']}, fields=['name'])
        if len(oligo_matches) > 0:
            # update and return this item
            oligo_doc = frappe.get_doc("Oligo", oligo_matches[0]['name'])
    if not oligo_doc:
        # create oligo
        oligo_doc = frappe.get_doc({
            'doctype': 'Oligo',
            'oligo_name': oligo['name'],
            'web_id': oligo['web_id']
        })
        oligo_doc.insert(ignore_permissions=True)
    # update record
    if 'name' in oligo:
        oligo_doc.oligo_name = oligo['name']
    if 'substance_type' in oligo:
        oligo_doc.substance_type = oligo['substance_type']
    if 'sequence' in oligo:
        oligo_doc.sequence = oligo['sequence']
    # update child table
    if 'items' in oligo:
        oligo_doc.items = []
        for i in oligo['items']:
            oligo_doc.append("items", {
                'item_code': i['item_code'],
                'qty':i['qty']
            })
    oligo_doc.save(ignore_permissions=True)

    return oligo_doc.name

def create_sample(sample):
    sample_doc = None
    # check if this oligo is already in the database
    if sample['sample_web_id']:
        sample_matches = frappe.get_all("Sample", 
            filters={'web_id': sample['sample_web_id']}, fields=['name'])
        if len(sample_matches) > 0:
            # update and return this item
            sample_doc = frappe.get_doc("Sample", sample_matches[0]['name'])
    if not sample_doc:
        # fetch sequencing label
        matching_labels = frappe.get_all("Sequencing Label",filters={
            'label_id': sample.get("sequencing_label"),
            'item': sample.get("label_item_code")
        }, fields=['name'])

        if matching_labels and len(matching_labels) == 1:
            label = frappe.get_doc("Sequencing Label", matching_labels[0]["name"])
        else:
            # TODO: activate error logging, when labels are in the ERP
            # frappe.log_error("Sequencing Label for sample with web id '{web_id}' not found: barcode number '{barcode}', item '{item}'".format(
            #     web_id = sample['sample_web_id'], 
            #     barcode = sample.get("sequencing_label"),
            #     item =sample.get("label_item_code") ), "utils: create_sample")
            label = None

        # create sample
        web_id = None
        if 'sample_web_id' in sample:
            web_id = sample['sample_web_id']
        elif 'web_id' in sample:
            web_id = sample['web_id']
        sample_doc = frappe.get_doc({
            'doctype': 'Sample',
            'sample_name': sample['name'],
            'web_id': web_id,
            'sequencing_label': label.name if label else None
        })
        sample_doc.insert(ignore_permissions=True)
    # update record
    sample_doc.sample_name = sample['name']
    # update child table
    if 'items' in sample:
        sample_doc.items = []
        for i in sample['items']:
            sample_doc.append("items", {
                'item_code': i['item_code'],
                'qty':i['qty']
            })
    sample_doc.save(ignore_permissions=True)

    return sample_doc.name

@frappe.whitelist()
def find_tax_template(company, customer, customer_address, category):
    """
    Find the corresponding tax template
    """
    
    # if the customer is "Individual" (B2C), always apply default tax template (with VAT)
    if frappe.get_value("Customer", customer, "customer_type") == "Individual":
        default = frappe.get_all("Sales Taxes and Charges Template",
            filters={'company': company, 'is_default': 1},
            fields=['name']
        )
        if default and len(default) > 0:
            return default[0]['name']
        else:
            return None
    else:
        country = frappe.get_value("Address", customer_address, "country")
        if frappe.get_value("Country", country, "eu"):
            eu_pattern = """ OR `country` = "EU" """
        else:
            eu_pattern = ""
        find_tax_record = frappe.db.sql("""SELECT `sales_taxes_template`
            FROM `tabTax Matrix Entry`
            WHERE `company` = "{company}"
              AND (`country` = "{country}" OR `country` = "%" {eu_pattern})
              AND `category` = "{category}"
            ORDER BY `idx` ASC;""".format(
            company=company, country=country, category=category, eu_pattern=eu_pattern), 
            as_dict=True)
        if len(find_tax_record) > 0:
            return find_tax_record[0]['sales_taxes_template']
        else:
            return None

@frappe.whitelist(allow_guest=True)
def login(usr, pwd):
    """
    Create a user session
    """
    from frappe.auth import LoginManager
    lm = LoginManager()
    lm.authenticate(usr, pwd)
    lm.login()
    return frappe.local.session

@frappe.whitelist()
def get_print_address(contact, address, customer=None, customer_name=None):
    if customer and not customer_name:
        customer_name = frappe.get_value("Customer", customer, 'customer_name')
    
    return frappe.render_template("microsynth/templates/includes/address.html", 
        {
            'contact': contact, 
            'address': address, 
            'customer_name':  customer_name
        }) 
