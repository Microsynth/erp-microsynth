# -*- coding: utf-8 -*-
# Copyright (c) 2023, libracore (https://www.libracore.com) and contributors
# For license information, please see license.txt

import frappe
from frappe.model.mapper import get_mapped_doc
from erpnextswiss.erpnextswiss.finance import get_exchange_rate
from datetime import datetime

@frappe.whitelist()
def make_quotation(contact_name):

    doc = get_mapped_doc(
        "Contact", 
        contact_name, 
        {"Contact": { "doctype": "Quotation"}})
    
    contact = frappe.get_doc('Contact', contact_name)
    if len(contact.links) != 1:
        frappe.log_error(f"WARNING: Contact.links has length {len(contact.links)} != 1 for Contact {contact_name} and Quotation {doc.name}. "
                         f"Took contact.links[0].link_name for Quotation.party_name but might be wrong. Please check Contact {contact_name} "
                         f"and Quotation {doc.name}.", 'microsynth.quotation.make_quotation')

    doc.party_name = contact.links[0].link_name
    doc.contact_person = contact_name
    customer = frappe.get_doc("Customer", doc.party_name)
    doc.company = customer.default_company
    doc.territory = customer.territory
    doc.currency = customer.default_currency
    doc.selling_price_list = customer.default_price_list
    doc.conversion_rate = get_exchange_rate(from_currency=doc.currency, company=doc.company, date=datetime.today().date())
    doc.sales_manager = customer.account_manager
    invoice_to = customer.invoice_to
    doc.customer_address = frappe.get_value('Contact', invoice_to, 'address')
    doc.shipping_address_name = frappe.get_value('Contact', doc.contact_person, 'address')
    return doc
