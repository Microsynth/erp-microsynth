# -*- coding: utf-8 -*-
# Copyright (c) 2024, Microsynth AG, libracore (https://www.libracore.com) and contributors
# For license information, please see license.txt
#
# For more details, refer to https://github.com/Microsynth/erp-microsynth/
#

import frappe
import json
from datetime import datetime


@frappe.whitelist()
def get_contact_details(contact_1=None, contact_2=None):
    data = {'contact_1': {}, 'contact_2': {}, 'address_1':{}, 'address_2':{} }

    if frappe.db.exists("Contact", contact_1):
        data['contact_1'] = frappe.get_doc("Contact", contact_1).as_dict()
        for l in data['contact_1'].get("links"):
            if l.link_doctype == "Customer":
                data['contact_1']['customer'] = l.link_name
                break
        if frappe.db.exists("Address", data['contact_1']['address']):
            data['address_1'] = frappe.get_doc("Address", data['contact_1']['address']).as_dict()
    if frappe.db.exists("Contact", contact_2):
        data['contact_2'] = frappe.get_doc("Contact", contact_2).as_dict()
        for l in data['contact_2'].get("links"):
            if l.link_doctype == "Customer":
                data['contact_2']['customer'] = l.link_name
                break
        if frappe.db.exists("Address", data['contact_2']['address']):
            data['address_2'] = frappe.get_doc("Address", data['contact_2']['address']).as_dict()

    html = frappe.render_template("microsynth/microsynth/page/contact_merger/contact_details.html", data)

    return {'data': data, 'html': html}


@frappe.whitelist()
def merge_contacts(contact_1, contact_2, values):
    if not frappe.db.exists("Contact", contact_1):
        return {'error': "Contact 1 not found"}
    if not frappe.db.exists("Contact", contact_2):
        return {'error': "Contact 2 not found"}

    contact_1 = frappe.get_doc("Contact", contact_1)
    values = json.loads(values)  # parse string to dict
    contact_1.update(values)
    contact_1.save()

    if frappe.db.exists("Contact", contact_2):
        # make sure to replace all traces to new contact
        # TODO
        #frappe.db.delete("Contact", contact_2)
        contact2 = frappe.get_doc("Contact", contact_2)
        contact2.status = "Disabled"
        contact2.add_comment(comment_type='Comment', text=(f"Merged into Contact '{contact_1.name}' on {datetime.now()}"))
        contact2.save()

    frappe.db.commit()
