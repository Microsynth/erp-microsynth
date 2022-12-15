# -*- coding: utf-8 -*-
# Copyright (c) 2022, Microsynth AG, libracore (https://www.libracore.com) and contributors
# For license information, please see license.txt
#
# For more details, refer to https://github.com/Microsynth/erp-microsynth/
#

import requests
import frappe
from erpnext.selling.doctype.sales_order.sales_order import make_delivery_note
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
        for l in labels or []:
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




def check_sales_order_completion(sales_orders):
    for sales_order in sales_orders:
        customer_name = frappe.get_value("Sales Order", sales_order, 'customer')
        customer = frappe.get_doc("Customer", customer_name)

        if customer.disabled:
            frappe.log_error("Customer '{0}' of order '{1}' is disabled. Cannot create a delivery note.".format(customer.name, sales_order), "Production: sales order complete")
            return

        # TODO 
        # * Sample does not have a status field like oligo does
        # * Sequencing Label does have a status (trigger: status = received or processed?)
        # * Add status field to sample and handle it like the oligos?

        so_open_items = frappe.db.sql("""
            SELECT 
                `tabSample Link`.`parent`
            FROM `tabSample Link`
            LEFT JOIN `tabSample` ON `tabSample Link`.`sample` = `tabSample`.`name`
            WHERE
                `tabSample Link`.`parent` = "{sales_order}"
                AND `tabSample Link`.`parenttype` = "Sales Order"
                AND `tabSample`.`status` = "Open";
        """.format(sales_order=sales_order), as_dict=True)
        if len(so_open_items) == 0:
            # all items are either complete or cancelled
            
            ## create delivery note (leave on draft: submitted in a batch process later on)
            dn_content = make_delivery_note(sales_order)
            dn = frappe.get_doc(dn_content)
            # remove samples that are canceled
            cleaned_samples = []
            cancelled_sample_item_qtys = {}
            for sample in dn.samples:
                sample_doc = frappe.get_doc("Sample", sample.oligo)
                if sample_doc.status != "Canceled":
                    cleaned_samples.append(sample)
                else:
                    # append items
                    for item in sample_doc.items:
                        if item.item_code in cancelled_sample_item_qtys:
                            cancelled_sample_item_qtys[item.item_code] = cancelled_sample_item_qtys[item.item_code] + item.qty
                        else:
                            cancelled_sample_item_qtys[item.item_code] = item.qty
                    
            dn.samples = cleaned_samples
            # subtract cancelled items from oligo items
            for item in dn.items:
                if item.item_code in cancelled_sample_item_qtys:
                    item.qty -= cancelled_sample_item_qtys[item.item_code]
            # remove items with qty == 0
            keep_items = []
            for item in dn.items:
                if item.qty > 0:
                    keep_items.append(item)
            # if there are no items left, exit with an error trace
            if len(keep_items) == 0:
                frappe.log_error("No items left in {0}. Cannot create a delivery note.".format(sales_order), "Production: sales order complete")
                return
            dn.items = keep_items
            # insert record
            dn.flags.ignore_missing = True
            dn.insert(ignore_permissions=True)
            frappe.db.commit()
            
    return