# -*- coding: utf-8 -*-
# Copyright (c) 2023, Microsynth, libracore and contributors and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document
from microsynth.microsynth.shipping import get_shipping_item, TRACKING_URLS

class TrackingCode(Document):
    pass

@frappe.whitelist()
def create_tracking_code(web_order_id, tracking_code):
    sales_orders = frappe.get_all("Sales Order", 
        filters = { 'web_order_id': web_order_id, 'docstatus': 1 },
        fields = ['name', 'contact_email', 'contact_display'] )
    
    if len(sales_orders) > 0:
        sales_order = frappe.get_doc("Sales Order", sales_orders[0]['name'])

        shipping_item = get_shipping_item(sales_order.items)
        if shipping_item is None:
            frappe.throw("Sales Order '{0}' does not have a shipping item".format(sales_order.name))
        if shipping_item not in TRACKING_URLS:
            frappe.throw("Sales Order '{0}' has the shipping item '{1}' without tracking code".format(sales_order.name, shipping_item))

        tracking_url = "{url}{code}".format(
            url = TRACKING_URLS[shipping_item], 
            code = tracking_code)

        tracking = frappe.get_doc({
            'doctype': 'Tracking Code',
            'sales_order': sales_order.name,
            'tracking_code': tracking_code,
            'tracking_url': tracking_url,
            'recipient_email': sales_orders[0]['contact_email'],
            'recipient_name': sales_orders[0]['contact_display']
        })
        tracking.insert()
        frappe.db.commit()

        # TODO
        # Transmit to webshop using the requests module

    else:
        frappe.throw("Sales Order with web_order_id '{}' not found or multiple sales orders".format(web_order_id))
    return tracking.name
