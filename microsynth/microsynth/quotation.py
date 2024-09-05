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


@frappe.whitelist()
def link_quotation_to_order(sales_order, quotation):
    """
    Check if the given Sales Order and Quotation matches.
    If the given Sales Order is submitted, cancel & amend it.
    Link the Quotation to the Sales Order Items.
    Return the name of the (new) Sales Order.

    bench execute microsynth.microsynth.quotation.link_quotation_to_order --kwargs "{'sales_order': 'SO-WIE-24001533-3', 'quotation': 'QTN-2402702'}"
    """
    qtn = frappe.get_doc("Quotation", quotation)
    sales_order_doc = frappe.get_doc("Sales Order", sales_order)
    # check that the Quotation belongs to the same Customer than the Sales Order
    if qtn.party_name != sales_order_doc.customer:
        frappe.throw(f"Quotation {quotation} belongs to Customer {qtn.party_name} but Sales Order {sales_order} belongs to Customer {sales_order_doc.customer}. Unable to link.")
    # check that the Quotation belongs to the same Contact than the Sales Order
    if not qtn.customer_web_access and qtn.contact_person != sales_order_doc.contact_person:
        frappe.throw(f"Quotation {quotation} belongs to Contact {qtn.contact_person} but Sales Order {sales_order} belongs to Contact {sales_order_doc.contact_person}. Unable to link.")
    # check that all Sales Order Items are on the Quotation
    for so_itm in sales_order_doc.items:
        found = False
        for qtn_itm in qtn.items:
            if so_itm.item_code == qtn_itm.item_code and so_itm.qty >= qtn_itm.qty:
                found = True
                break
        if not found:
            frappe.throw(f"Item {so_itm.item_code} is not on Quotation {quotation} or the Quantity on the Quotation is higher. Unable to link.")
    created_new_order = False
    if sales_order_doc.docstatus > 1:
        frappe.throw(f"Sales Order {sales_order} is cancelled. Unable to link.")
    elif sales_order_doc.docstatus == 1:
        sales_order_doc.cancel()
        new_so = frappe.get_doc(sales_order_doc.as_dict())
        new_so.name = None
        new_so.docstatus = 0
        new_so.amended_from = sales_order_doc.name
        so_doc = new_so
        created_new_order = True
    else:  # Draft
        so_doc = sales_order_doc
    # write the Quotation ID into the field Sales Order Item.prevdoc_docname
    for item in so_doc.items:
        item.prevdoc_docname = quotation
        # Rates are taken from the Quotation
        for qtn_itm in qtn.items:
            if item.item_code == qtn_itm.item_code and item.qty >= qtn_itm.qty:
                item.rate = qtn_itm.rate
                break
    if created_new_order:
        so_doc.insert()
    return so_doc.name