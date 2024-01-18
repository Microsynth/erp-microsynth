# -*- coding: utf-8 -*-
# Copyright (c) 2024, Microsynth AG, libracore (https://www.libracore.com) and contributors
# For license information, please see license.txt
#
# For more details, refer to https://github.com/Microsynth/erp-microsynth/
#

import json
from datetime import datetime
import frappe
from frappe.model.rename_doc import rename_doc
from microsynth.microsynth.marketing import update_marketing_classification


@frappe.whitelist()
def get_contact_details(contact_1=None, contact_2=None):
    """
    Get and add Contact details, call HTML rendering.
    """
    data = {'contact_1': {}, 'contact_2': {}, 'address_1':{}, 'address_2':{} }

    if frappe.db.exists("Contact", contact_1):
        data['contact_1'] = frappe.get_doc("Contact", contact_1).as_dict()
        for l in data['contact_1'].get("links"):
            if l.link_doctype == "Customer":
                data['contact_1']['customer'] = l.link_name
                break
        data['contact_1']['email_id2'] = data['contact_1']['email_ids'][1].email_id if len(data['contact_1']['email_ids']) > 1 else None
        data['contact_1']['email_id3'] = data['contact_1']['email_ids'][2].email_id if len(data['contact_1']['email_ids']) > 2 else None
        data['contact_1']['email_id_count'] = len(data['contact_1']['email_ids'])
        # Address of Contact 1
        if frappe.db.exists("Address", data['contact_1']['address']):
            data['address_1'] = frappe.get_doc("Address", data['contact_1']['address']).as_dict()
            add_address_print(data, 'contact_1', 'address_1')
        add_document_count(data, 'contact_1')

    if frappe.db.exists("Contact", contact_2):
        data['contact_2'] = frappe.get_doc("Contact", contact_2).as_dict()
        for l in data['contact_2'].get("links"):
            if l.link_doctype == "Customer":
                data['contact_2']['customer'] = l.link_name
                break
        data['contact_2']['email_id2'] = data['contact_2']['email_ids'][1].email_id if len(data['contact_2']['email_ids']) > 1 else None
        data['contact_2']['email_id3'] = data['contact_2']['email_ids'][2].email_id if len(data['contact_2']['email_ids']) > 2 else None
        data['contact_2']['email_id_count'] = len(data['contact_2']['email_ids'])
        # Address of Contact 2
        if frappe.db.exists("Address", data['contact_2']['address']):
            data['address_2'] = frappe.get_doc("Address", data['contact_2']['address']).as_dict()
            add_address_print(data, 'contact_2', 'address_2')
        add_document_count(data, 'contact_2')

    html = frappe.render_template("microsynth/microsynth/page/contact_merger/contact_details.html", data)
    return {'data': data, 'html': html}


def add_address_print(data, contact_key, address_key):
    """
    Add Address data to the Contact details using the adress template.
    """
    contact_id = data[contact_key]['name']
    customer_name = frappe.get_value("Customer", data[contact_key]['customer'], "customer_name")
    data[address_key]['address_print'] = frappe.render_template("microsynth/templates/includes/address.html",
                                                        {
                                                            'contact': contact_id,
                                                            'address': data[contact_key]['address'],
                                                            'customer_name': customer_name
                                                        })


def add_document_count(data, contact_key):
    """
    Determine and add the number of documents (Contact Note, QTN, SO, DN, SI) to the Contact details.
    """
    contact_id = data[contact_key]['name']

    contact_notes = frappe.db.sql(f"""
        SELECT `tabContact Note`.`name`
        FROM `tabContact Note`
        WHERE `tabContact Note`.`contact_person` = '{contact_id}'
        """, as_dict=True)
    data[contact_key]['contact_note_count'] = len(contact_notes)

    quotations = frappe.db.sql(f"""
        SELECT `tabQuotation`.`name`
        FROM `tabQuotation`
        WHERE `tabQuotation`.`contact_person` = '{contact_id}'
        """, as_dict=True)
    data[contact_key]['quotation_count'] = len(quotations)

    sales_orders = frappe.db.sql(f"""
        SELECT `tabSales Order`.`name`
        FROM `tabSales Order`
        WHERE `tabSales Order`.`contact_person` = '{contact_id}'
        """, as_dict=True)
    data[contact_key]['sales_order_count'] = len(sales_orders)

    delivery_notes = frappe.db.sql(f"""
        SELECT `tabDelivery Note`.`name`
        FROM `tabDelivery Note`
        WHERE `tabDelivery Note`.`contact_person` = '{contact_id}'
        """, as_dict=True)
    data[contact_key]['delivery_note_count'] = len(delivery_notes)

    sales_invoices = frappe.db.sql(f"""
        SELECT `tabSales Invoice`.`name`
        FROM `tabSales Invoice`
        WHERE `tabSales Invoice`.`contact_person` = '{contact_id}'
        """, as_dict=True)
    data[contact_key]['sales_invoice_count'] = len(sales_invoices)


@frappe.whitelist()
def merge_contacts(contact_1, contact_2, values):
    """
    Merge Contact 2 into Contact 1 preserving the values in the parameter 'values'.
    Thereby, Contact 2 is deleted.
    Return an error if there is a value for punchout_identifier or punchout_shop.
    Update Customer Status and Contact Classification (Marketing section) after merging.
    """
    try:
        if not frappe.db.exists("Contact", contact_1):
            return {'error': f"Contact 1 '{contact_1}' not found", 'contact': None}
        if not frappe.db.exists("Contact", contact_2):
            return {'error': f"Contact 2 '{contact_2}' not found", 'contact': None}

        shipping_1 = frappe.get_value("Address", frappe.get_value("Contact", contact_1, "address"), "is_shipping_address")
        shipping_2 = frappe.get_value("Address", frappe.get_value("Contact", contact_2, "address"), "is_shipping_address")
        billing_1 = frappe.get_value("Address", frappe.get_value("Contact", contact_1, "address"), "is_primary_address")
        billing_2 = frappe.get_value("Address", frappe.get_value("Contact", contact_2, "address"), "is_primary_address")
        if shipping_1 != shipping_2 or billing_1 != billing_2:
            return {'error': "Not allowed to merge a billing with a shipping Contact or vice versa.", 'contact': None}

        values = json.loads(values)  # parse string to dict

        if ('punchout_identifier' in values and values['punchout_identifier']) or ('punchout_shop' in values and values['punchout_shop']):
            return {'error': f"Not allowed to merge punchout Contact: punchout_shop='{values['punchout_shop'] if 'punchout_shop' in values else None}', punchout_identifier='{values['punchout_identifier'] if 'punchout_identifier' in values else None}'", 'contact': None}

        # remove lock
        frappe.db.sql(f"""DELETE FROM `tabContact Lock` WHERE `tabContact Lock`.`name` = '{contact_2}'; """)
        frappe.db.commit()

        # rename_doc is a core function and deletes the old Contact (here contact_2)
        new_contact_name = rename_doc(doctype="Contact", old=contact_2, new=contact_1, merge=True, ignore_permissions=True)
        frappe.db.commit()  # try to prevent issue with documente was edited
        new_contact = frappe.get_doc("Contact", new_contact_name)
        new_contact.update(values)
        links = new_contact.as_dict()['links']  # this is to preserve potential other links
        new_contact.links = []
        new_contact.append('links', {
            'link_doctype': "Customer",
            'link_name': values['customer']
        })
        for l in links:
            if l.link_doctype != "Customer":
                new_contact.append('links', {
                    'link_doctype': l.link_doctype,
                    'link_name': l.link_name
                })
        new_contact.email_ids = []
        if 'email_id' in values and values['email_id']:
            new_contact.append("email_ids", {
                        'email_id': values['email_id'],
                        'is_primary': 1
                    })
        if 'email_id2' in values and values['email_id2']:
            new_contact.append("email_ids", {
                        'email_id': values['email_id2'],
                        'is_primary': 0
                    })
        if 'email_id3' in values and values['email_id3']:
            new_contact.append("email_ids", {
                        'email_id': values['email_id3'],
                        'is_primary': 0
                    })
        new_contact.save()
        frappe.db.commit()
        update_marketing_classification(new_contact_name)
    except Exception as err:
        frappe.log_error(f"Error when merging contact {contact_2} into {contact_1}\n{err}", "contact_merger.merge_contacts")
        return {'error': err, 'contact': None}
    else:
        return {'error': None, 'contact': new_contact_name}
