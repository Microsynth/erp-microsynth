# -*- coding: utf-8 -*-
# Copyright (c) 2022, libracore (https://www.libracore.com) and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import nowdate, add_months
from frappe.utils.password import get_decrypted_password
import json
import base64
from datetime import datetime
from urllib import request, parse
from urllib.error import URLError


TRACKING_URLS = {
    '1101': "https://www.post.ch/swisspost-tracking?formattedParcelCodes=",
    '1102': "https://www.post.ch/swisspost-tracking?formattedParcelCodes=",
    '1105': "https://www.post.at/sv/sendungssuche?snr=",
    '1106': "https://www.deutschepost.de/de/s/sendungsverfolgung.html?piececode=",
    '1108': "https://www.ups.com/track?tracknum=",
    '1113': "https://www.ups.com/track?tracknum=",
    '1114': "https://www.ups.com/track?tracknum=",  # should be disabled once all open invoices are paid (replaced by 1160 and 1165)
    '1115': "https://www.deutschepost.de/de/s/sendungsverfolgung.html?piececode=",
    '1117': "https://www.ups.com/track?tracknum=",  # should be disabled once all open invoices are paid
    '1120': "https://www.dhl.com/en/express/tracking.html?brand=DHL&AWB=",
    '1123': "https://www.dhl.com/ch-en/home/tracking/tracking-express.html?submit=1&tracking-id=",
    '1126': "https://www.fedex.com/fedextrack/?trknbr=",
    '1160': "https://www.ups.com/track?tracknum=",
    '1161': "https://www.ups.com/track?tracknum=",
    '1162': "https://www.ups.com/track?tracknum=",
    '1165': "https://www.ups.com/track?tracknum=",
    '1166': "https://www.ups.com/track?tracknum=",
    '1167': "https://www.ups.com/track?tracknum="
}


def get_shipping_items_with_tracking():
    """
    Returns a list of all Shipping Item Codes that support tracking, based on the above dictionary TRACKING_URLS.

    bench execute microsynth.microsynth.shipping.get_shipping_items_with_tracking
    """
    return TRACKING_URLS.keys()


def get_shipping_service(item_code, ship_adr, cstm_ID):

    SHIPPING_SERVICES = {
        '1100': "P.P.A",
        '1101': "A-plus",
        '1102': "Express",
        '1103': "Austria",
        '1104': "Einschreiben",
        '1105': "EMS",
        '1106': "Germany",
        '1108': "UPS EXP DE",
        '1110': "Abholung",
        '1112': "EU Post DE",
        '1113': "UPS STD",
        '1114': "UPS",  # should be disabled once all open invoices are paid (replaced by 1160 and 1165)
        '1115': "EU Post DE",
        '1117': "UPS",  # should be disabled once all open invoices are paid
        '1118': "Post CH",
        #'1119': "DHL Economy Select",  # only for EU, disabled
        '1120': "DHL CH",  # not for EU
        #'1122': "DHL",  # disabled
        '1123': "DHL/CH", # for countries out of EU
        '1126': "FedEx",
        '1130': "Internal",
        '1133': "Sequencing",
        '1140': "IMP/IMBA",
        '1160': "UPS STD",
        '1161': "UPS STD",
        '1162': "UPS STD",
        '1165': "UPS EXP",
        '1166': "UPS EXP",
        '1167': "UPS EXP"
    }
    # TODO: Move settings to a new DocType (Task #17847)

    try:
        sh_serv = SHIPPING_SERVICES[item_code]
    except:
        sh_serv = ""

    # special cases: Dr. Bohr Gasse 9 and Leberstrasse 20,
    if sh_serv in ["Austria", "EMS"] and (("Bohr" in ship_adr.address_line1
                                                and "Dr" in ship_adr.address_line1
                                                and "Gasse" in ship_adr.address_line1
                                                and ("7" in ship_adr.address_line1
                                                    or "9" in ship_adr.address_line1))
                                            or ("Leberstrasse" in ship_adr.address_line1
                                                and "20" in ship_adr.address_line1)):
        sh_serv = "MFPL"
    # special cases: Tartu, Össu and Jögeva
    elif (sh_serv != "UPS" and (ship_adr.pincode == "48309"
                                or "Tartu" in ship_adr.city
                                or "Õssu" in ship_adr.city
                                or "Össu" in ship_adr.city
                                or "Jõgeva" in ship_adr.city
                                or "Jögeva" in ship_adr.city
                                or "Ülenu" in ship_adr.city)
                                ):
        if sh_serv == "UPS STD":
            sh_serv = "Tartu UPS STD"
        elif sh_serv == "UPS EXP":
            sh_serv = "Tartu UPS EXP"
        else:
            sh_serv = "Tartu"
    # special case: Letgen
    elif item_code == '1123' and cstm_ID in ['36796402', '837342']:
        sh_serv = "Letgen"

    return (sh_serv)


def get_shipping_item(items):
    for i in reversed(items):
        if i.item_group == "Shipping":
            return i.item_code


def create_receiver_address_lines(customer_name, contact, address):
    '''creates a list of strings that represent the sequence of address lines of the receiver'''

    if contact: contact_doc = frappe.get_doc("Contact", contact)
    if address: address_doc = frappe.get_doc("Address", address)

    rec_adr_lines = []
    if address and address_doc.overwrite_company:
        rec_adr_lines.append(address_doc.overwrite_company)
    else:
        rec_adr_lines.append(customer_name)
    if contact:
        if contact_doc.institute:   rec_adr_lines.append(contact_doc.institute)
        if contact_doc.designation: rec_adr_lines.append(contact_doc.designation)
        if contact_doc.first_name and contact_doc.first_name != "-": rec_adr_lines.append(contact_doc.first_name)
        if contact_doc.last_name:   rec_adr_lines[-1] += " " + contact_doc.last_name
        if contact_doc.department:  rec_adr_lines.append(contact_doc.department)
        if contact_doc.room:        rec_adr_lines.append(contact_doc.room)

    if address:
        if address_doc.address_line1: rec_adr_lines.append(address_doc.address_line1)
        if address_doc.address_line2: rec_adr_lines.append(address_doc.address_line2)

        if address_doc.city and address_doc.pincode:
            if address_doc.country and address_doc.country in ['United Kingdom']:
                rec_adr_lines.append(address_doc.city + " " + address_doc.pincode)
            else:
                rec_adr_lines.append(address_doc.pincode + " " + address_doc.city)
        elif address_doc.city: rec_adr_lines.append(address_doc.city)
        elif address_doc.pincode: rec_adr_lines.append(address_doc.pincode)

        if address_doc.country: rec_adr_lines.append(address_doc.country)

    return rec_adr_lines


def get_sender_address_line(sales_order, shipping_address_country):

    letter_head_name = ""
    letter_head = ""

    if sales_order.company == "Microsynth AG" and shipping_address_country.name == "Austria":
        letter_head_name = "Microsynth AG Wolfurt"
    elif sales_order.company == "Microsynth AG" and shipping_address_country.eu:
        letter_head_name = "Microsynth AG Lindau"
    else:
        letter_head_name = sales_order.company

    letter_head = frappe.get_doc("Letter Head", letter_head_name)

    if not letter_head.sender_address_line:
        # frappe.throw("Letter head '{0}' does not have a 'sender_address_line' specified.".format(letter_head_name))
        return ""

    return letter_head.sender_address_line


def update_shipping_item_name(item_codes, dry_run=True):
    """
    Takes a list of item codes.
    Check that each of them has Item Group 'Shipping'.
    Search those Shipping Items with item_name != Item.item_name.
    Set Shipping Item.item_name to Item.item_name.

    bench execute microsynth.microsynth.shipping.update_shipping_item_name --kwargs "{'item_codes': ['1103'], 'dry_run': True}"
    """
    for item_code in item_codes:
        if not frappe.db.exists("Item", item_code):
            print(f"Item '{item_code}' does not exist. Going to continue.")
            continue
        item = frappe.get_doc("Item", item_code)
        if item.item_group != 'Shipping':
            print(f"Item {item_code}: {item.item_name} has Item Group {item.item_group} and is not a Shipping Item. Going to continue.")
            continue
        shipping_items = frappe.db.get_all("Shipping Item",
            filters = [['item', '=', item_code], ['item_name', '!=', item.item_name]],
            fields = ['name', 'item_name', 'parent'])
        for shipping_item in shipping_items:
            if dry_run:
                print(f"Would change Item Name of {item_code} on {shipping_item['parent']} from '{shipping_item['item_name']}' to '{item.item_name}'.")
                continue
            else:
                print(f"Going to change Item Name of {item_code} on {shipping_item['parent']} from '{shipping_item['item_name']}' to '{item.item_name}'.")
                frappe.db.sql(f"""
                    UPDATE `tabShipping Item`
                    SET `item_name` = '{item.item_name}'
                    WHERE `name` = '{shipping_item['name']}';""")
    print("Done")


def add_shipping_item_to_country(country, item_code, rate, threshold, preferred_express):
    """
    Adds the given Shipping Item with the given rate, threshold and preferred_express flag
    to the given Country if there is no Shipping Item with the given Item Code on the given Country.
    """
    try:
        shipping_items = frappe.db.sql(f"""
            SELECT `tabShipping Item`.`name`
            FROM `tabShipping Item`
            LEFT JOIN `tabItem` ON `tabItem`.`name` = `tabShipping Item`.`item`
            WHERE `tabShipping Item`.`parenttype` = "Country"
                AND `tabShipping Item`.`parent` = '{country}'
                AND `tabItem`.`item_code` = '{item_code}'
            ;""", as_dict=True)
        if len(shipping_items) > 0:
            print(f"Shipping Item {item_code} on Country {country} does already exist, going to skip.")
            return False
        country_doc = frappe.get_doc("Country", country)
        country_doc.append("shipping_items", {
            'item': item_code,
            'qty': 1.0,
            'rate': rate,
            'threshold': threshold,
            'preferred_express': preferred_express
        })
        country_doc.save()
        return True
    except Exception as err:
        print(f"Got the following error when trying to add Shipping Item {item_code} on Country {country}: {err}")
        return False


def replace_shipping_items_on_countries(items_to_replace, country_to_code, code_to_rate, threshold, preferred_express):
    """
    Takes a list of Shipping Item codes to replace and searches them on all Countries.
    Replaces them by the given Item code for the given Country code with the given rate
    if preferred_express matches, the qty was 1.0 and the threshold matches.

    bench execute microsynth.microsynth.shipping.replace_shipping_items_on_countries --kwargs "{'items_to_replace': ['1114', '1117'], 'country_to_code': {'PL': '1165', 'FR': '1165', 'BE': '1166', 'BG': '1166', 'CZ': '1166', 'ES': '1166', 'HU': '1166', 'NL': '1166', 'LV': '1166', 'LT': '1166', 'LU': '1166', 'IE': '1166', 'IT': '1166', 'PT': '1166', 'RO': '1166', 'SK': '1166', 'SI': '1166', 'CY': '1167', 'DK': '1167', 'FI': '1167', 'GR': '1167', 'HR': '1167', 'MT': '1167', 'EE': '1167', 'SE': '1167'}, 'code_to_rate': {'1165': 12.00, '1166': 16.00, '1167': 20.00}, 'threshold': 1000, 'preferred_express': 1}"
    """
    if type(country_to_code) == str:
        country_to_code = json.loads(country_to_code)
    if type(code_to_rate) == str:
        code_to_rate = json.loads(code_to_rate)
    countries_replaced = []

    shipping_items = frappe.db.sql(f"""
        SELECT `tabShipping Item`.`name`,
            `tabShipping Item`.`item`,
            `tabShipping Item`.`item_name`,
            `tabShipping Item`.`parent` AS `country`,
            `tabShipping Item`.`qty`,
            `tabShipping Item`.`rate`,
            `tabShipping Item`.`threshold`,
            `tabShipping Item`.`preferred_express`
        FROM `tabShipping Item`
        LEFT JOIN `tabItem` ON `tabItem`.`name` = `tabShipping Item`.`item`
        WHERE `tabShipping Item`.`parenttype` = "Country"
            AND `tabItem`.`item_code` IN ({','.join(f'"{item_code}"' for item_code in items_to_replace)})
        ORDER BY `tabShipping Item`.`parent` ASC;""", as_dict=True)

    for shipping_item in shipping_items:
        if shipping_item['preferred_express'] != preferred_express:
            print(f"Shipping Item {shipping_item['item']}: {shipping_item['item_name']} on Country {shipping_item['country']}  has preferred_express = {shipping_item['preferred_express']}, but got {preferred_express=}, going to skip.")
            continue
        if float(shipping_item['qty']) != 1.0:
            print(f"Shipping Item {shipping_item['item']}: {shipping_item['item_name']} on Country {shipping_item['country']} has not 'qty' 1.0 ({shipping_item['qty']=}), going to skip.")
            continue
        if threshold != shipping_item['threshold']:
            print(f"Shipping Item {shipping_item['item']}: {shipping_item['item_name']} on Country {shipping_item['country']} has threshold {shipping_item['threshold']} but the given threshold is {threshold}, going to skip.")
            continue
        country_code = frappe.get_value("Country", shipping_item['country'], 'code').upper()
        if country_code not in country_to_code:
            print(f"Got no Shipping Item Code for Country {shipping_item['country']} with Country code '{country_code}', going to skip Shipping Item {shipping_item['item']}: {shipping_item['item_name']}.")
            continue
        item_code = country_to_code[country_code]
        if item_code not in code_to_rate:
            print(f"Got no rate for Item code '{item_code}', going to skip Shipping Item {shipping_item['item']}: {shipping_item['item_name']} on Country {shipping_item['country']}.")
            continue
        rate = code_to_rate[item_code]
        added = add_shipping_item_to_country(shipping_item['country'], item_code, rate, threshold, preferred_express)
        if added:
            # delete existing Shipping Item
            shipping_item_doc = frappe.get_doc("Shipping Item", shipping_item['name'])
            shipping_item_doc.delete()
            #frappe.db.commit()
            print(f"Successfully replaced Shipping Item {shipping_item['item']}: {shipping_item['item_name']} with rate {shipping_item['rate']} and threshold {shipping_item['threshold']} with preferred_express = {shipping_item['preferred_express']} on Country {shipping_item['country']} by Shipping Item {item_code} with rate {rate} and threshold {threshold} and {preferred_express=}.")
            countries_replaced.append(country_code)
    for country_code in country_to_code.keys():
        if country_code not in countries_replaced:
            print(f"Country with country code {country_code} had no Shipping Item with an Item code in {items_to_replace} or it was skipped due to an error mentioned above.")


def add_shipping_items_to_countries(country_to_code, code_to_rate, threshold, preferred_express):
    """
    Adds the given Item codes with the given rates and threshold to the given Countries
    if there is not already a Shipping Item with the same Item code on the Country.

    bench execute microsynth.microsynth.shipping.add_shipping_items_to_countries --kwargs "{'country_to_code': {'PL': '1160', 'FR': '1160', 'BE': '1161', 'BG': '1161', 'CZ': '1161', 'ES': '1161', 'HU': '1161', 'NL': '1161', 'LV': '1161', 'LT': '1161', 'LU': '1161', 'IE': '1161', 'IT': '1161', 'PT': '1161', 'RO': '1161', 'SK': '1161', 'SI': '1161', 'CY': '1162', 'DK': '1162', 'FI': '1162', 'GR': '1162', 'HR': '1162', 'MT': '1162', 'EE': '1162', 'SE': '1162'}, 'code_to_rate': {'1160': 7.00, '1161': 9.00, '1162': 14.00}, 'threshold': 1000, 'preferred_express': 0}"
    """
    if type(country_to_code) == str:
        country_to_code = json.loads(country_to_code)
    if type(code_to_rate) == str:
        code_to_rate = json.loads(code_to_rate)
    for country_code, item_code in country_to_code.items():
        countries = frappe.get_all("Country", filters={'code': country_code}, fields=['name'])
        if len(countries) == 0:
            print(f"Unknown country code '{country_code}', going to skip.")
            continue
        elif len(countries) > 1:
            print(f"Found the following {len(countries)} Countries for country code '{country_code}' in the ERP, going to skip: {countries}")
            continue
        else:
            country = countries[0]['name']
        rate = code_to_rate[item_code]
        added = add_shipping_item_to_country(country, item_code, rate, threshold, preferred_express)
        if added:
            print(f"Successfully added Shipping Item {item_code} with rate {rate}, threshold {threshold} and {preferred_express=} to Country {country}.")


def get_ups_settings():
    """
    Fetch UPS OAuth credentials and API base URL from settings.
    """
    settings = frappe.get_single("Shipment Tracking Settings")
    client_id = get_decrypted_password("Shipment Tracking Settings", "Shipment Tracking Settings", "client_id")
    client_secret = get_decrypted_password("Shipment Tracking Settings", "Shipment Tracking Settings", "client_secret")
    return settings.ups_rest_url, settings.oauth_token_url, client_id, client_secret, settings.merchant_id


def fetch_pending_tracking_codes():
    """
    Fetch tracking codes that are missing a delivery date and were created in the last 3 months.
    """
    three_months_ago = add_months(nowdate(), -3)
    query = """
        SELECT `name`, `tracking_code`
        FROM `tabTracking Code`
        WHERE `tracking_code` LIKE %s
          AND `shipping_date` IS NOT NULL
          AND `delivery_date` IS NULL
          AND `creation` > %s
        ORDER BY `creation` DESC
    """
    return frappe.db.sql(query, ("1ZH%", three_months_ago), as_dict=True)


def get_ups_oauth_token(client_id: str, client_secret: str, token_url: str, merchant_id: str) -> str:
    """
    Retrieve UPS OAuth2 access token using client credentials.
    """
    data = parse.urlencode({'grant_type': 'client_credentials'}).encode()
    headers = {
        'Content-Type': 'application/x-www-form-urlencoded',
        'Accept': 'application/json',
        'User-Agent': 'Mozilla/5.0',
        'Authorization': f'Basic {base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()}',
        'Merchant-Id': merchant_id
    }
    req = request.Request(token_url, data=data, headers=headers)
    try:
        with request.urlopen(req, timeout=15) as response:
            raw = response.read().decode()
            result = json.loads(raw)
            return result.get('access_token')
    except URLError as e:
        raise Exception(f"Failed to get UPS OAuth token: {e}") from e
    except json.JSONDecodeError:
        raise Exception(f"Invalid JSON response from UPS OAuth endpoint: {raw}")


def call_ups_tracking_api(tracking_code: str, url: str, access_token: str, merchant_id: str) -> dict:
    """
    Calls the UPS Tracking API using the provided OAuth2 access token.
    """
    if not access_token:
        raise Exception("Missing UPS access token.")
    payload = {
        "TrackRequest": {
            "Request": {"RequestOption": "1"},
            "InquiryNumber": tracking_code
        }
    }
    data = json.dumps(payload).encode('utf-8')
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {access_token}',
        'Merchant-Id': merchant_id
    }
    req = request.Request(url, data=data, headers=headers)
    try:
        with request.urlopen(req, timeout=15) as response:
            return json.loads(response.read().decode())
    except URLError as e:
        raise Exception(f"UPS tracking API error: {e}") from e
    except json.JSONDecodeError as e:
        raise Exception(f"Failed to parse UPS tracking response for {tracking_code}") from e


def parse_delivery_datetime(response_json: dict):
    """
    Extract delivery datetime from the UPS tracking API response.
    """
    if "Fault" in response_json:
        raise Exception(f"UPS API returned error: {json.dumps(response_json['Fault'], indent=2)}")
    try:
        shipment = response_json["TrackResponse"]["Shipment"]
        packages = shipment["Package"]
        if not isinstance(packages, list):
            packages = [packages]

        for package in packages:
            activities = package.get("Activity", [])
            if not isinstance(activities, list):
                activities = [activities]

            for activity in activities:
                status = activity["Status"]["Description"].lower()
                if "delivered" in status:
                    date_str = activity.get("Date")  # e.g., '20250626'
                    time_str = activity.get("Time", "000000")  # e.g., '144152'
                    if date_str:
                        return datetime.strptime(date_str + time_str, "%Y%m%d%H%M%S")
    except Exception as e:
        msg = f"Error parsing delivery datetime: {e}\nRaw response:\n{json.dumps(response_json, indent=2)}"
        frappe.log_error(msg, title="UPS Delivery Date Parsing Error")
        print(msg)
    return None


def update_ups_delivery_dates(request_limit: int = None):
    """
    Should be run once per night by a daily cronjob:
    # Status request for UPS tracking codes without a delivery date
    30 3 * * * cd /home/frappe/frappe-bench && /usr/local/bin/bench --site erp.microsynth.local execute microsynth.microsynth.shipping.update_ups_delivery_dates --kwargs "{'request_limit': 50}"

    bench execute microsynth.microsynth.shipping.update_ups_delivery_dates --kwargs "{'request_limit': 1}"
    """
    url, token_url, client_id, client_secret, merchant_id = get_ups_settings()
    access_token = get_ups_oauth_token(client_id, client_secret, token_url, merchant_id)
    #print("Access token:", access_token)
    tracking_codes = fetch_pending_tracking_codes()

    for i, tracking_code in enumerate(tracking_codes):
        if request_limit and i >= request_limit:
            break

        code = tracking_code["tracking_code"]
        try:
            response_json = call_ups_tracking_api(code, url, access_token, merchant_id)
            delivery_datetime = parse_delivery_datetime(response_json)

            if delivery_datetime:
                doc = frappe.get_doc("Tracking Code", tracking_code["name"])
                doc.delivery_date = delivery_datetime
                doc.save(ignore_permissions=True)
                frappe.db.commit()
                print(f"✅ Delivered: {code} on {delivery_datetime}")
            else:
                print(f"⏳ Still in transit: {code}")
        except Exception as e:
            error_msg = f"Error updating {code}: {e}"
            frappe.log_error(title="UPS Tracking Update Failed", message=error_msg)
            print(f"❌ {error_msg}")
