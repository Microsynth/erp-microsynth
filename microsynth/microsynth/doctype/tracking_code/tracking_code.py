# -*- coding: utf-8 -*-
# Copyright (c) 2023, Microsynth, libracore and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
import requests
import csv
import os
import re
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


def prepare_tracking_log(file_id):
    """
    helper function for the next three parsing functions
    """
    tracking_log = frappe.get_doc({
        'doctype': 'Tracking Log',
        'tracking_log_file': file_id
    })
    tracking_log.insert()
    file_doc = frappe.get_doc("File", file_id)
    base_path = os.path.join(frappe.utils.get_bench_path(), "sites", frappe.utils.get_site_path()[2:]) 
    file_path = f"{base_path}{file_doc.file_url}"
    return file_path


@frappe.whitelist()
def parse_dhl_file(file_id, expected_line_length=90):
    """
    bench execute microsynth.microsynth.doctype.tracking_code.tracking_code.parse_dhl_file --kwargs "{'file_id': '0f69f96ed0'}"
    """
    file_path = prepare_tracking_log(file_id)
    error_str = ""
    counter = 0
    with open(file_path) as file:
        csv_reader = csv.reader((x.replace('\0', '') for x in file), delimiter=';')  # replace NULL bytes (throwing an error)
        next(csv_reader)  # skip header
        for line in csv_reader:
            if len(line) != expected_line_length:
                msg = f"Line '{line}' has length {len(line)}, but expected length {expected_line_length}."
                return {'success': False, 'message': msg}
            tracking_number = line[0]
            datetime_str = line[49]
            if not datetime_str:
                continue
            try:
                delivery_datetime = datetime.fromisoformat(datetime_str)
            except Exception as e:
                frappe.log_error(f"File path: {file_path}\nError: {e}", "parse_dhl_file")
                continue
            error = add_delivery_date_to_tracking_code(tracking_number, delivery_datetime)
            if error:
                error_str += f"<br>{error}"
            else:
                counter += 1
    if error_str:
        return {'success': True, 'message': f"Completed with the following problems: {error_str}"}
    else:
        return {'success': True, 'message': f"Successfully processed {counter} tracking codes"}


@frappe.whitelist()
def parse_ups_file(file_id, expected_line_length=78):
    """
    bench execute microsynth.microsynth.doctype.tracking_code.tracking_code.parse_ups_file --kwargs "{'file_id': '0f69f96ed0'}"
    """
    file_path = prepare_tracking_log(file_id)
    error_str = ""
    counter = 0
    with open(file_path) as file:
        csv_reader = csv.reader((x.replace('\0', '') for x in file), delimiter=';')  # replace NULL bytes (throwing an error)
        next(csv_reader)  # skip header
        for line in csv_reader:
            if len(line) != expected_line_length:
                msg = f"Line '{line}' has length {len(line)}, but expected length {expected_line_length}."
                return {'success': False, 'message': msg}
            tracking_number = line[0]
            status = line[2]
            if "canceled" in status.lower():
                # skip if shipment was canceled
                continue
            date_str = line[13]
            if not date_str:
                continue
            delivery_date = datetime.strptime(date_str, '%m/%d/%Y')
            time_str = line[15]
            time_str = time_str.replace('.', '')  # Remove periods
            try:
                delivery_time = datetime.strptime(time_str, '%I:%M %p')
            except Exception:
                # no valid time -> use 00:00 from delivery_date instead
                delivery_time = delivery_date
            delivery_datetime = datetime.combine(delivery_date.date(), delivery_time.time())
            error = add_delivery_date_to_tracking_code(tracking_number, delivery_datetime)
            if error:
                error_str += f"<br>{error}"
            else:
                counter += 1
    if error_str:
        return {'success': True, 'message': f"Completed with the following problems: {error_str}"}
    else:
        return {'success': True, 'message': f"Successfully processed {counter} tracking codes"}


@frappe.whitelist()
def parse_fedex_file(file_id, expected_line_length=89):
    """
    bench execute microsynth.microsynth.doctype.tracking_code.tracking_code.parse_fedex_file --kwargs "{'file_id': '0f69f96ed0'}"
    """
    file_path = prepare_tracking_log(file_id)
    error_str = ""
    counter = 0
    with open(file_path) as file:
        csv_reader = csv.reader((x.replace('\0', '') for x in file), delimiter=',')  # replace NULL bytes (throwing an error)
        next(csv_reader)  # skip header
        for line in csv_reader:
            if len(line) != expected_line_length:
                msg = f"Line '{line}' has length {len(line)}, but expected length {expected_line_length}."
                return {'success': False, 'message': msg}
            tracking_number = line[0]
            date_str = line[21]
            if not date_str:
                continue
            delivery_date = datetime.strptime(date_str, '%m/%d/%y')
            time_str = line[22]
            try:
                delivery_time = datetime.strptime(time_str, '%I:%M %p')
            except Exception:
                # no valid time -> use 00:00 from delivery_date instead
                delivery_time = delivery_date
            delivery_datetime = datetime.combine(delivery_date.date(), delivery_time.time())
            error = add_delivery_date_to_tracking_code(tracking_number, delivery_datetime)
            if error:
                error_str += f"<br>{error}"
            else:
                counter += 1
    if error_str:
        return {'success': True, 'message': f"Completed with the following problems: {error_str}"}
    else:
        return {'success': True, 'message': f"Successfully processed {counter} tracking codes"}


@frappe.whitelist()
def parse_ems_file(file_id, expected_line_length=36):
    """
    bench execute microsynth.microsynth.doctype.tracking_code.tracking_code.parse_ems_file --kwargs "{'file_id': '0f69f96ed0'}"
    """
    file_path = prepare_tracking_log(file_id)
    error_str = ""
    counter = 0
    with open(file_path) as file:
        csv_reader = csv.reader((x.replace('\0', '') for x in file), delimiter=';')  # replace NULL bytes (throwing an error)
        next(csv_reader)  # skip header
        for line in csv_reader:
            if len(line) == 0:
                continue
            if len(line) != expected_line_length:
                msg = f"Line '{line}' has length {len(line)}, but expected length {expected_line_length}."
                return {'success': False, 'message': msg}
            tracking_number = line[0].replace('"', '').replace('=', '')
            datetime_str = re.sub(r'\.\d+\+', '+', line[24])  # remove microseconds
            if not datetime_str:
                continue
            try:
                delivery_datetime = datetime.fromisoformat(datetime_str)
                delivery_datetime = delivery_datetime.replace(tzinfo=None)
            except Exception as e:
                frappe.log_error(f"File path: {file_path}\nError: {e}", "parse_ems_file")
                continue
            error = add_delivery_date_to_tracking_code(tracking_number, delivery_datetime)
            if error:
                error_str += f"<br>{error}"
            else:
                counter += 1
    if error_str:
        return {'success': True, 'message': f"Completed with the following problems: {error_str}"}
    else:
        return {'success': True, 'message': f"Successfully processed {counter} tracking codes"}


def add_delivery_date_to_tracking_code(tracking_code, delivery_datetime):
    tracking_codes = frappe.get_all("Tracking Code", filters={'tracking_code': tracking_code}, fields=['name', 'tracking_code', 'delivery_date'])
    if len(tracking_codes) == 0:
        #print(f"Found no Tracking Code for '{tracking_code=}'. Going to skip.")
        return ""
    elif len(tracking_codes) > 1:
        msg = f"Found the following {len(tracking_codes)} Tracking Codes for '{tracking_code}': {','.join(tc['name'] for tc in tracking_codes)}. Going to skip."
        #print(msg)
        return msg
    else:
        tracking_code = tracking_codes[0]
        # Check if there is already a delivery_datetime stored
        if tracking_code['delivery_date']:
            # yes: compare it and log an error if it differs
            if tracking_code['delivery_date'] != delivery_datetime:
                msg = f"Tracking Code '{tracking_code=}' has already delivery date {tracking_code['delivery_date']} and should now be {delivery_datetime}. Going to skip."
                #print(msg)
                return msg
        else:
            # no: save it
            tracking_code_doc = frappe.get_doc("Tracking Code", tracking_code['name'])
            tracking_code_doc.delivery_date = delivery_datetime
            tracking_code_doc.save()
    return ""


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
