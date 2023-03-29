# -*- coding: utf-8 -*-
# Copyright (c) 2023, Microsynth, libracore and contributors and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
import requests
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

        url = "{0}/erp/set_tracking_code".format(frappe.get_value("Microsynth Settings", "Microsynth Settings", "url"))
        secret = frappe.get_value("Microsynth Settings", "Microsynth Settings", "shared_secret")

        json = """{{
                "shared_secret": "{secret}",
                "web_order_id": {web_order_id},
                "tracking_code": "{tracking_code}",
                "tracking_url": "{tracking_url}"
            }}""".format(secret = secret,
            web_order_id = sales_order.web_order_id,
            tracking_code = tracking_code,
            tracking_url = tracking_url
        )

        response = requests.post(
            url,
            data = json)

        if response.status_code != 200:
            frappe.throw("Could not transmit Tracking Code '{0}' to the webshop.<br>{1}".format(tracking.name, response.text))
    else:
        frappe.throw("Sales Order with web_order_id '{0}' not found or multiple sales orders".format(web_order_id))
    return tracking.name
