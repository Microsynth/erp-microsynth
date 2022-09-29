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
    try:
        for l in labels:
            label = frappe.get_doc({
                'doctype': "Sequencing Label",
                'label_id': l["label_id"],
                'item': l["item_code"]
            })
            # ToDo: Check if status transition is allowed
            label.status = status
            label.save()
        frappe.db.commit()        
        return {'success': True, 'message': None }
    except Exception as err:
        return {'success': False, 'message': err }

@frappe.whitelist(allow_guest=True)
def set_unused(labels):
    """
    Set label status to 'unused'. Labels must be a list of dictionaries 
    (see `set_status` function).
    """
    set_status("unused", labels)

@frappe.whitelist(allow_guest=True)
def lock_labels(labels):
    """
    Set label status to 'locked'. Labels must be a list of dictionaries 
    (see `set_status` function).
    """
    set_status("locked", labels)
@frappe.whitelist(allow_guest=True)
def received_labels(labels):

    """
    Set label status to 'received'. Labels must be a list of dictionaries 
    (see `set_status` function).
    """
    set_status("received", labels)

@frappe.whitelist(allow_guest=True)
def processed_labels(labels):
    """
    Set label status to 'processed'. Labels must be a list of dictionaries 
    (see `set_status` function).
    """
    set_status("processed", labels)

@frappe.whitelist(allow_guest=True)
def lock_labels(labels):
    """
    Set label status to 'locked'. Labels must be a list of dictionaries 
    (see `set_status` function).
    """
    set_status("locked", labels)