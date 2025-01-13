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
        if len(sales_orders) > 1:
            msg = f"Found {len(sales_orders)} submitted Sales Orders with Web Order ID '{web_order_id}': {sales_orders=}"
            frappe.log_error(msg, "tracking_code.create_tracking_code")
            #frappe.throw(msg)
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
            'shipping_item': shipping_item,
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
        frappe.throw("Sales Order with web_order_id '{0}' not found".format(web_order_id))
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
            #print(f"Tracking Number {tracking_number}: Delivery: {delivery_datetime.strftime('%Y-%m-%d %H:%M')}")
            add_delivery_date_to_tracking_code(tracking_number, delivery_datetime)


def add_delivery_date_to_tracking_code(tracking_code, delivery_datetime):
    tracking_codes = frappe.get_all("Tracking Code", filters={'tracking_code': tracking_code}, fields=['name', 'tracking_code', 'delivery_date'])
    if len(tracking_codes) == 0:
        print(f"Found no Tracking Code for '{tracking_code=}'. Going to skip.")
    elif len(tracking_codes) > 1:
        msg = f"Found {len(tracking_codes)} Tracking Codes for '{tracking_code=}'. Going to skip."
        print(msg)
        frappe.log_error(msg, "tracking_code.add_delivery_date_to_tracking_code")
    else:
        tracking_code = tracking_codes[0]
        # Check if there is already a delivery_datetime stored
        if tracking_code['delivery_date']:
            # yes: compare it and log an error if it differs
            if tracking_code['delivery_date'] != delivery_datetime:
                msg = f"Tracking Code '{tracking_code=}' has delivery date {tracking_code['delivery_date']} and should be {delivery_datetime}. Going to skip."
                print(msg)
                frappe.log_error(msg, "tracking_code.add_delivery_date_to_tracking_code")
        else:
            # no: save it
            tracking_code_doc = frappe.get_doc("Tracking Code", tracking_code['name'])
            tracking_code_doc.delivery_date = delivery_datetime
            tracking_code_doc.save()


def add_shipping_items(from_date, to_date):
    """
    Migration: For all Tracking Codes created in the given date range:
    Fetch the Shipping Item from the linked Sales Order and add it to the Tracking Code

    bench execute microsynth.microsynth.doctype.tracking_code.tracking_code.add_shipping_items --kwargs "{'from_date': '2024-10-01', 'to_date': '2025-01-31'}"
    """
    sql_query = f"""
        SELECT `name`, `shipping_item`
        FROM `tabTracking Code`
        WHERE `creation` BETWEEN DATE('{from_date}') AND DATE('{to_date}')
            AND `shipping_item` IS NULL
        """
    tracking_codes = frappe.db.sql(sql_query, as_dict=True)
    print(f"Going to process {len(tracking_codes)} Tracking Codes ...")
    for i, tc in enumerate(tracking_codes):
        if i % 100 == 0:
            print(i)
        tracking_code_doc = frappe.get_doc("Tracking Code", tc['name'])
        if tracking_code_doc.sales_order:
            sales_order_doc = frappe.get_doc("Sales Order", tracking_code_doc.sales_order)
            shipping_item = get_shipping_item(sales_order_doc.items)
            if shipping_item:
                tracking_code_doc.shipping_item = shipping_item
                tracking_code_doc.save()
            else:
                print(f"Sales Order {sales_order_doc.name} from Tracking Code {tracking_code_doc.name} has no Shipping Item.")
        else:
            print(f"Tracking Code {tracking_code_doc.name} has no Sales Order.")


def add_shipping_date(from_date, to_date):
    """
    Migration: For all Tracking Codes created in the given date range:
    Fetch the Delivery Note from the linked Sales Order and add the
    Posting Date and Posting Time as Shipping Date to the Tracking Code

    bench execute microsynth.microsynth.doctype.tracking_code.tracking_code.add_shipping_date --kwargs "{'from_date': '2024-10-01', 'to_date': '2025-01-31'}"
    """
    sql_query = f"""
        SELECT `name`, `sales_order`
        FROM `tabTracking Code`
        WHERE `creation` BETWEEN DATE('{from_date}') AND DATE('{to_date}')
        """
    tracking_codes = frappe.db.sql(sql_query, as_dict=True)
    print(f"Going to process {len(tracking_codes)} Tracking Codes ...")
    for i, tc in enumerate(tracking_codes):
        if i % 100 == 0:
            print(i)
        tracking_code_doc = frappe.get_doc("Tracking Code", tc['name'])
        if tracking_code_doc.sales_order:
            sql_query = f"""
                SELECT DISTINCT
                    `tabDelivery Note`.`name`,
                    `tabDelivery Note`.`posting_date`,
                    `tabDelivery Note`.`posting_time`,
                    `tabDelivery Note Item`.`parent` AS `delivery_note`
                FROM `tabDelivery Note`
                LEFT JOIN `tabDelivery Note Item` ON `tabDelivery Note Item`.`parent` = `tabDelivery Note`.`name`
                WHERE `tabDelivery Note`.`docstatus` = 1
                    AND `tabDelivery Note Item`.`against_sales_order` = '{tracking_code_doc.sales_order}'
                """
            delivery_notes = frappe.db.sql(sql_query, as_dict=True)
            if len(delivery_notes) == 1:
                dn = delivery_notes[0]
                if not dn['posting_date']:
                    print(f"Delivery Note {dn['name']} has no Date. Going to continue.")
                    continue
                if not dn['posting_time']:
                    print(f"Delivery Note {dn['name']} has no Posting Time. Going to continue.")
                    continue
                shipping_time = (datetime.min + dn['posting_time']).time()  # convert from datetime.timedelta to datetime.time
                shipping_datetime = datetime.combine(dn['posting_date'], shipping_time)
                tracking_code_doc.shipping_date = shipping_datetime
                tracking_code_doc.save()
            else:
                print(f"Found {len(delivery_notes)} submitted Delivery Notes for Sales Order {tracking_code_doc.sales_order} of Tracking Code {tracking_code_doc.name}")
        else:
            print(f"Tracking Code {tracking_code_doc.name} has no Sales Order.")
