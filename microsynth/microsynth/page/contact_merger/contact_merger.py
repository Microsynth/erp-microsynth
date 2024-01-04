# -*- coding: utf-8 -*-
# Copyright (c) 2024, Microsynth AG, libracore (https://www.libracore.com) and contributors
# For license information, please see license.txt
#
# For more details, refer to https://github.com/Microsynth/erp-microsynth/
#

import frappe
import json

@frappe.whitelist()
def get_contact_details(contact_1=None, contact_2=None):
    data = {'contact_1': {}, 'contact_2': {}}
    if frappe.db.exists("Contact", contact_1):
        data['contact_1'] = frappe.get_doc("Contact", contact_1).as_dict()
    if frappe.db.exists("Contact", contact_2):
        data['contact_2'] = frappe.get_doc("Contact", contact_2).as_dict()
        
    html = frappe.render_template("microsynth/microsynth/page/contact_merger/contact_details.html", data)
    
    return {'data': data, 'html': html}
    
@frappe.whitelist()
def merge_contacts(contact_1, contact_2, values):
    if not frappe.db.exists("Contact", contact_1):
        return {'error': "Contact 1 not found"}
    if not frappe.db.exists("Contact", contact_2):
        return {'error': "Contact 2 not found"}
        
    contact = frappe.get_doc("Contact", contact_1)
    
    values = json.loads(values)         # parse string to dict
    contact.update(values)
    
    contact.save()
    
    if frappe.db.exists("Contact", contact_2):
        # make sure to replace all traces to new contact
        # TODO
        #frappe.db.delete("Contact", contact_2)
        contact2 = frappe.get_doc("Contact", contact_2)
        contact2.status = "Disabled"
        contact2.save()
        
    frappe.db.commit()
    
    return

