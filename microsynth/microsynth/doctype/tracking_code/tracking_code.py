# -*- coding: utf-8 -*-
# Copyright (c) 2023, Microsynth, libracore and contributors and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document

class TrackingCode(Document):
    pass

@frappe.whitelist()
def create_tracking_code(web_order_id, tracking_code):
    sales_orders = frappe.get_all("Sales Order", 
        filters = { 'web_order_id': web_order_id, 'doc_status': 1 }, 
        fields = ['name', 'contact_email', 'contact_display'] )
    
    if len(sales_orders) > 0:        
        # TODO tracking url
        tracking_url = "https://srvweb.microsynth.ch"
        tracking = frappe.get_doc({
            'doctype': 'Tracking Code',
            'sales_order': sales_orders[0]['name'],
            'tracking_code': tracking_code,
            'tracking_url': tracking_url,
            'recipient_email': sales_orders[0]['contact_email'],
            'recipient_name': sales_orders[0]['contact_display']
        })
        tracking.insert()
        frappe.db.commit()
    else:
        frappe.throw("Sales Order with web_order_id '{}' not found or multiple sales orders".format(web_order_id))
    return tracking.name

