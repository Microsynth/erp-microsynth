# -*- coding: utf-8 -*-
# Copyright (c) 2023, libracore (https://www.libracore.com) and contributors
# For license information, please see license.txt

from datetime import datetime
import frappe
from frappe.model.mapper import get_mapped_doc
from erpnextswiss.erpnextswiss.finance import get_exchange_rate


@frappe.whitelist()
def make_quotation(contact_name):
    """
    bench execute microsynth.microsynth.quotation.make_quotation --kwargs "{'contact_name': '1234'}"
    """
    doc = get_mapped_doc(
        "Contact",
        contact_name,
        {"Contact": { "doctype": "Quotation"}})

    contact = frappe.get_doc('Contact', contact_name)
    if len(contact.links) != 1:
        msg = f"WARNING: Contact.links has length {len(contact.links)} for Contact {contact_name} "\
            f"and Quotation {doc.name}. Took contact.links[0].link_name for Quotation.party_name "\
            f"but might be wrong. Please check Contact {contact_name} and Quotation {doc.name}."
        frappe.log_error(msg, 'microsynth.quotation.make_quotation')

    doc.contact_person = contact_name
    doc.contact_display = contact.full_name
    doc.contact_email = contact.email_id
    doc.contact_mobile = ""

    customer = frappe.get_doc("Customer", contact.links[0].link_name)
    doc.party_name = customer.name

    doc.company = customer.default_company
    doc.territory = customer.territory
    doc.currency = customer.default_currency
    doc.selling_price_list = customer.default_price_list
    doc.conversion_rate = get_exchange_rate(from_currency=doc.currency,
                                            company=doc.company,
                                            date=datetime.today().date())
    doc.sales_manager = customer.account_manager
    invoice_to = customer.invoice_to
    doc.customer_address = frappe.get_value('Contact', invoice_to, 'address')
    doc.shipping_address_name = frappe.get_value('Contact', doc.contact_person, 'address')
    # Prevent inserting Contact.source or Address.source to the Quotation.source field
    doc.source = None
    doc.quotation_type = None
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
    # check that the Quotation is submitted
    if qtn.docstatus == 0:
        frappe.throw(f"Unable to link Quotation {quotation} in Draft status. Please check to submit it first.")
    if qtn.docstatus > 1:
        frappe.throw(f"Unable to link cancelled Quotation {quotation}.")
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
        return None  # to satisfy linter
    if sales_order_doc.docstatus == 1:
        sales_order_doc.cancel()
        new_so = frappe.get_doc(sales_order_doc.as_dict())
        new_so.name = None
        new_so.docstatus = 0
        new_so.amended_from = sales_order_doc.name
        so_doc = new_so
        created_new_order = True
    else:  # Draft
        so_doc = sales_order_doc
    if created_new_order:
        so_doc.insert()
    # write the Quotation ID into the field Sales Order Item.prevdoc_docname
    for item in so_doc.items:
        item.prevdoc_docname = quotation
        # Rates are taken from the Quotation
        for qtn_itm in qtn.items:
            if item.item_code == qtn_itm.item_code and item.qty >= qtn_itm.qty:
                item.rate = qtn_itm.rate
                item.parent = so_doc.name
                break
        item.save()
    so_doc.save()  # necessary to update item amount, order total etc.
    return so_doc.name


def validate_item_sales_status(doc, event=None):
    """
    Validate that no Items in the Quotation are In Preparation or Discontinued.
    This function checks each item in the Quotation and raises an error if any item is found with
    a sales status of "In Preparation" or "Discontinued". The error message lists all such items.
    """
    invalid_items = []

    for item in doc.items:
        sales_status = frappe.get_value("Item", item.item_code, "sales_status")
        if sales_status in ["In Preparation", "Discontinued"]:
            invalid_items.append((item.item_code, item.item_name, sales_status))

    if invalid_items:
        # Build HTML table
        html = """
        <p>The following Items cannot be added to this Quotation:</p>
        <table class="table table-bordered">
            <thead>
                <tr>
                    <th>Item</th>
                    <th>Sales Status</th>
                </tr>
            </thead>
            <tbody>
        """
        for item_code, item_name, status in invalid_items:
            html += f"<tr><td>{item_code}: {item_name}</td><td>{status}</td></tr>"

        html += """
            </tbody>
        </table>
        <p><b>Please remove or replace these items.</b></p>
        """
        frappe.throw(html, title="Invalid Items")
