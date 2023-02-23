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
from microsynth.microsynth.naming_series import get_naming_series
from microsynth.microsynth.utils import validate_sales_order

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


def check_sales_order_completion():      
    # find sales orders that have no delivery note and are not closed
    open_sequencing_sales_orders = frappe.db.sql("""
        SELECT `name`
        FROM `tabSales Order`
        WHERE `docstatus` = 1
          AND `status` NOT IN ("Closed", "Completed")
          AND `product_type` = "Sequencing"
          AND `per_delivered` < 100;
    """, as_dict=True)
    
    # check completion of each sequencing sales order: sequencing labels of this order on processed
    for sales_order in open_sequencing_sales_orders:

        if not validate_sales_order(sales_order):
            continue

        # check status of labels assigned to each sample
        pending_samples = frappe.db.sql("""
            SELECT 
                `tabSample`.`name`
            FROM `tabSample Link`
            LEFT JOIN `tabSample` ON `tabSample Link`.`sample` = `tabSample`.`name`
            LEFT JOIN `tabSequencing Label` on `tabSample`.`sequencing_label`= `tabSequencing Label`.`name`
            WHERE
                `tabSample Link`.`parent` = "{sales_order}"
                AND `tabSample Link`.`parenttype` = "Sales Order"
                AND `tabSequencing Label`.`status` NOT IN ("processed");
            """.format(sales_order=sales_order), as_dict=True)

        if len(pending_samples) == 0:
            # all processed: create delivery
            customer_name = frappe.get_value("Sales Order", sales_order['name'], 'customer')
            customer = frappe.get_doc("Customer", customer_name)

            if customer.disabled:
                frappe.log_error("Customer '{0}' of order '{1}' is disabled. Cannot create a delivery note.".format(customer.name, sales_order), "Production: sales order complete")
                return
            
            ## create delivery note (leave on draft: submitted in a batch process later on)
            dn_content = make_delivery_note(sales_order['name'])            
            dn = frappe.get_doc(dn_content)
            company = frappe.get_value("Sales Order", sales_order, "company")
            dn.naming_series = get_naming_series("Delivery Note", company)

            # insert record
            dn.flags.ignore_missing = True
            dn.insert(ignore_permissions=True)
            frappe.db.commit()
            
    return
