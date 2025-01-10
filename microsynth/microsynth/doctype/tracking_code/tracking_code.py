# -*- coding: utf-8 -*-
# Copyright (c) 2023, Microsynth, libracore and contributors and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
import requests
import csv
from datetime import datetime
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


def parse_ups_file(file_path, expected_line_length=78):
    """
    bench execute microsynth.microsynth.doctype.tracking_code.tracking_code.parse_ups_file --kwargs "{'file_path': '/mnt/erp_share/JPe/2_UPSMC4b-20241121-075023_01.11.-15.11.2024.csv'}"
    """
    with open(file_path) as file:
        print(f"Parsing UPS Delivery dates from '{file_path}' ...")
        csv_reader = csv.reader(file, delimiter=",")
        next(csv_reader)  # skip header
        for line in csv_reader:
            if len(line) != expected_line_length:
                print(f"Line '{line}' has length {len(line)}, but expected length {expected_line_length}. Going to continue.")
                continue
            tracking_number = line[0]
            status = line[2]
            if "canceled" in status.lower():
                # skip if shipment was canceled
                continue
            date_str = line[13]
            delivery_date = datetime.strptime(date_str, '%m/%d/%Y')
            time_str = line[15]
            time_str = time_str.replace('.', '')  # Remove periods
            try:
                delivery_time = datetime.strptime(time_str, '%I:%M %p')
            except Exception:
                # no valid time -> use 00:00 from delivery_date instead
                delivery_time = delivery_date
            delivery_datetime = datetime.combine(delivery_date.date(), delivery_time.time())
            print(f"Tracking Number {tracking_number}: Delivery: {delivery_datetime.strftime('%Y-%m-%d %H:%M')}")
            add_delivery_date_to_tracking_code(tracking_number, delivery_datetime)


def add_delivery_date_to_tracking_code(tracking_code, delivery_datetime):
    tracking_codes = frappe.get_all("Tracking Code", filters={'tracking_code': tracking_code}, fields=['name'])
    if len(tracking_codes) == 0:
        print(f"Found no Tracking Code for {tracking_code=}")
    elif len(tracking_codes) > 1:
        print(f"Found {len(tracking_codes)} Tracking Code for {tracking_code=}")
    else:
        # TODO: Check if there is already a delivery_datetime stored
        # yes: compare it and log an error if it differs
        # no: save it
        pass
