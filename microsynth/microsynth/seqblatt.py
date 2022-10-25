# -*- coding: utf-8 -*-
# Copyright (c) 2022, Microsynth AG, libracore (https://www.libracore.com) and contributors
# For license information, please see license.txt
#
# For more details, refer to https://github.com/Microsynth/erp-microsynth/
#

import requests
import frappe
from frappe import _
from frappe.utils import cint
import json
from datetime import datetime

def set_status(status, labels):
    """
    This is the generic core function that will be called by the 
    rest endpoints for the SeqBlatt API. 
    labels must be a list of dictionaries. E.g.
    [
        {
            "label_id": "4568798",
            "item_code": "3110"
        },
        {
            "label_id": "4568799",
            "item_code": "3110"
        }
    ]
    """
    if type(labels) == str:
        labels = json.loads(labels)
    try:        
        for l in labels:
            matching_labels = frappe.get_all("Sequencing Label",filters={
                'label_id': l.get("label_id"),
                'item': l.get("item_code")
            }, fields=['name'])
            
            if matching_labels and len(matching_labels) == 1:
                label = frappe.get_doc("Sequencing Label", matching_labels[0]["name"])
                # ToDo: Check if status transition is allowed               
                label.status = status
                label.save(ignore_permissions=True)
            else:
                return {'success': False, 'message': "none or multiple labels." }            
        frappe.db.commit()        
        return {'success': True, 'message': None }
    except Exception as err:
        return {'success': False, 'message': err }

@frappe.whitelist(allow_guest=True)
def set_unused(content):
    """
    Set label status to 'unused'. Labels must be a list of dictionaries 
    (see `set_status` function).
    """
    if type(content) == str:
        content = json.loads(content)
    return set_status("unused", content.get("labels"))

@frappe.whitelist(allow_guest=True)
def lock_labels(content):
    """
    Set label status to 'locked'. Labels must be a list of dictionaries 
    (see `set_status` function).
    """
    if type(content) == str:
        content = json.loads(content)
    return set_status("locked", content.get("labels"))
    
@frappe.whitelist(allow_guest=True)
def received_labels(content):

    """
    Set label status to 'received'. Labels must be a list of dictionaries 
    (see `set_status` function).
    """
    if type(content) == str:
        content = json.loads(content)
    return set_status("received", content.get("labels"))

@frappe.whitelist(allow_guest=True)
def processed_labels(content):
    """
    Set label status to 'processed'. Labels must be a list of dictionaries 
    (see `set_status` function).
    """
    if type(content) == str:
        content = json.loads(content)
    return set_status("processed", content.get("labels"))

#@frappe.whitelist(allow_guest=True)
#def unlock_labels(content):
#    """
#    Set label status to 'locked'. Labels must be a list of dictionaries 
#    (see `set_status` function).
#    """
#    if type(content) == str:
#        content = json.loads(content)
#    return set_status("unknown", content.get("labels"))
