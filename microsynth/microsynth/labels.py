# -*- coding: utf-8 -*-
# Copyright (c) 2022, libracore (https://www.libracore.com) and contributors
# For license information, please see license.txt

import frappe
import socket
from datetime import datetime
from microsynth.microsynth.shipping import get_shipping_service, get_shipping_item, create_receiver_address_lines, get_sender_address_line

NOVEXX_PRINTER_TEMPLATE = "microsynth/templates/includes/address_label_novexx.html"
BRADY_PRINTER_TEMPLATE = "microsynth/templates/includes/address_label_brady.html"


def print_raw(ip, port, content):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect((ip, port))
    s.send(content.encode())
    s.close()
    return


def print_test_label_brady():
    """Test functions are hardcoded to specific printer IPs and are useful only during initial development - delete after finishing development"""

    content = ''';###load Microsynth logo###
M l IMG;01_MIC_Logo_Swiss_black

m m
J
H 100
S 0,-2.5,145,150,105
O R

; ###Microsynth logo, rotated 90 degree###
I 100,137,180,2,2;01_MIC_Logo_Swiss_black

;###print date and time during development###

;T 1,140,0,3,pt 10;[DATE]-[TIME]-function: print_test_label_brady
A 1
'''
    print_raw('192.0.1.71', 9100, content )


def print_test_label_novexx():
    """Test functions are hardcoded to specific printer IPs and are useful only during initial development - delete after finishing development"""

    content = '''#!A1
#IMS105/148
#N13
#ER

#T19#J28.6#YG/3///C:\Logos\Microsynth_black_140x27.bmp#G

#T4#J130#YN101/0U/45///Schützenstrasse 15, 9436 Balgach#G
#T4#J127#YL0/0/0.5/95

#T60#J105#YN101/3U/45///first address line#G

#T78#J54#YN101/3U/85///some country#G
#T75#J54#YN101/3U/45///postal service#G
#T69#J22#YR0/0/0.5/15/33

#T4#J105#YN101/3U/45///hardcoded from print_test_label_novexx#G
#Q1/
#!P1
'''
    print_raw('192.0.1.72', 9100, content )


def choose_brady_printer(company):
    """
    Returns the Brady printer specified for the user with the 'User Printer' DocType
    or alternatively the one defined in 'Sequencing Settings'.

    Printers have to be set in Sequencing Settings based on company name. The IP and port
    of the printer are specified on the 'Brady Printer' DocType.
    """

    # check if there is a user-specific printer
    user = frappe.get_user()
    if frappe.db.exists("User Printer", user.name):
        printer_name = frappe.get_value("User Printer", user.name, "label_printer")
        printer = frappe.get_doc("Brady Printer", printer_name)

        return printer

    # Austria labels will be handled in by Microsynth AG
    if company == "Microsynth Austria GmbH":
        company = "Microsynth AG"

    if not company:
        frappe.throw("Company missing for deciding on printer IP")

    settings = frappe.get_doc("Sequencing Settings", "Sequencing Settings")
    for printer in settings.label_printers:
        if printer.company == company:
            printer = frappe.get_doc("Brady Printer", printer.brady_printer)
            return printer


def get_label_data(sales_order):
    """
    Returns the data for printing a shipping label from a sales order.
    run
    bench execute microsynth.microsynth.labels.get_label_data --kwargs "{'sales_order': 'SO-BAL-25025120'}"
    """
    if type(sales_order) == str:
        sales_order = frappe.get_doc('Sales Order', sales_order)

    if not sales_order.shipping_address_name:
        frappe.throw("Sales Order '{0}': Address missing".format(sales_order.name))
    elif not sales_order.customer:
        frappe.throw("Sales Order '{0}': Customer missing".format(sales_order.name))
    elif not sales_order.contact_person:
        frappe.throw("Sales Order '{0}': Contact missing".format(sales_order.name))

    if sales_order.shipping_contact:
        contact_id = sales_order.shipping_contact
    else:
        contact_id = sales_order.contact_person

    shipping_item = get_shipping_item(sales_order.items)

    address_id = sales_order.shipping_address_name
    shipping_address = frappe.get_doc("Address", address_id)
    destination_country = frappe.get_doc("Country", shipping_address.country)
    plate_aliquot_hint = ""

    for item in sales_order.items:
        if item.item_code in ['0011', '0051', '0101', '0104', '0641', '0773', '0774', '0780']:
            plate_aliquot_hint = "(Plate)"
            break
        if item.item_code in ['0770', '0771']:
            plate_aliquot_hint = "(Aliquots)"
            break

    data = {
        'lines': create_receiver_address_lines(customer_name = sales_order.order_customer_display or sales_order.customer_name, contact = contact_id, address = address_id),
        'sender_header': get_sender_address_line(sales_order, destination_country),
        'destination_country': shipping_address.country,
        'shipping_service': get_shipping_service(shipping_item, shipping_address, sales_order.customer),
        'po_no': sales_order.po_no,
        'web_id': sales_order.web_order_id,
        'cstm_id': sales_order.customer,
        'oligo_count': len(sales_order.oligos),
        'plate_aliquot_hint': plate_aliquot_hint
    }
    return data


@frappe.whitelist()
def print_shipping_label(sales_order_id):
    """
    function calls respective template for creating a transport label

    bench execute "microsynth.microsynth.labels.print_shipping_label" --kwargs "{'sales_order_id': 'SO-BAL-24016620'}"
    """
    sales_order = frappe.get_doc("Sales Order", sales_order_id)
    label_data = get_label_data(sales_order)
    content = frappe.render_template(BRADY_PRINTER_TEMPLATE, label_data)

    printer = choose_brady_printer(sales_order.company)

    if printer:
        print_raw(printer.ip, printer.port, content)
        sales_order.label_printed_on = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        sales_order.save()
        frappe.db.commit()
    else:
        frappe.log_error(f"Found no Brady printer for Company '{sales_order.company}' and Sales Order '{sales_order_id}'.", "labels.print_shipping_label")


@frappe.whitelist()
def print_contact_shipping_label(address_id, contact_id, customer_id):
    """
    function calls respective template for creating a transport label

    bench execute "microsynth.microsynth.labels.print_contact_shipping_label" --kwargs "{'contact_id': '215856'}"
    """
    try:
        user_settings = frappe.get_doc("User Settings", frappe.session.user)
        sender_company = user_settings.qm_process_assignments[0].company
    except Exception as err:
        frappe.log_error(f"{err}", "labels.print_contact_shipping_label")
        sender_company = "Microsynth AG"
    letter_head = frappe.get_doc("Letter Head", sender_company)
    country = frappe.get_value("Address", address_id, "country")
    customer_name = frappe.get_value("Customer", customer_id, "customer_name")
    if not letter_head.sender_address_line:
        sender_header = ""
    else:
        sender_header = letter_head.sender_address_line
    label_data = {
        'lines': create_receiver_address_lines(customer_name=customer_name, contact=contact_id, address=address_id),
        'sender_header': sender_header,
        'destination_country': country,
        'cstm_id': customer_id
    }
    content = frappe.render_template("microsynth/templates/includes/contact_address_label_brady.html", label_data)
    printer = choose_brady_printer(sender_company)
    if printer:
        print_raw(printer.ip, printer.port, content)
    else:
        frappe.log_error(f"Found no Brady printer for Company '{sender_company}' and Address '{address_id}'.", "labels.print_contact_shipping_label")


@frappe.whitelist()
def print_oligo_order_labels(sales_orders):
    """
    Prints the shipping labels from a list of sales order names.

    Run
    bench execute "microsynth.microsynth.labels.print_oligo_order_labels" --kwargs "{'sales_orders': ['SO-BAL-22011340']}"
    """
    create_ups_batch_file(sales_orders)

    settings = frappe.get_doc("Flushbox Settings", "Flushbox Settings")

    for o in sales_orders:
        warning = ""
        sales_order = frappe.get_doc("Sales Order", o)
        try:
            label_data = get_label_data(sales_order)
            content = frappe.render_template(NOVEXX_PRINTER_TEMPLATE, label_data)
            if not sales_order.label_printed_on:
                print_raw(settings.label_printer_ip, settings.label_printer_port, content)
                sales_order.label_printed_on = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                sales_order.save()
                frappe.db.commit()
            else:
                warning = f"Shipping Label for Sales Order {sales_order.name} seems to be already printed on {sales_order.label_printed_on}. Not going to print again. Please make sure that you are in the correct report and refresh it."
        except Exception as err:
            msg = "Error printing label for '{0}':\n{1}".format(sales_order.name, err)
            if str(err) != '[Errno 111] Connection refused':
                frappe.log_error(msg, "print_oligo_order_labels")
            frappe.throw(msg)
        if warning:
            frappe.log_error(warning, "print_oligo_order_labels")
            frappe.throw(warning)
    return


@frappe.whitelist()
def create_ups_batch_file(sales_orders):
    """
    This functionality is included in the button "Print Shipping Labels" on the report "Oligo Orders Export".

    bench execute "microsynth.microsynth.labels.create_ups_batch_file" --kwargs "{'sales_orders': ['SO-BAL-24045626']}"
    """
    import re
    lines_to_write = []
    for o in sales_orders:
        sales_order = frappe.get_doc("Sales Order", o)
        label_data = get_label_data(sales_order)
        # TODO: Store a mapping from Shipping Item Codes to UPS Service Types somewhere in the ERP settings
        if not label_data or not label_data['shipping_service'] or not 'UPS' in label_data['shipping_service']:
            continue
        address = frappe.get_doc("Address", sales_order.shipping_address_name)
        # Check if all values exist
        if not address.country:
            frappe.log_error(f"country missing on Shipping Address '{sales_order.shipping_address_name}' on Sales Order {sales_order.name}", "create_ups_batch_file")
            continue
        country_code = frappe.get_value("Country", address.country, "code")
        if not country_code:
            frappe.log_error(f"country code missing on Country '{address.country}' of Shipping Address '{sales_order.shipping_address_name}' on Sales Order {sales_order.name}", "create_ups_batch_file")
            continue
        if not sales_order.contact_display:
            frappe.log_error(f"contact_display missing on Sales Order {sales_order.name}", "create_ups_batch_file")
            continue
        if not sales_order.customer_name:
            frappe.log_error(f"customer_name missing on Sales Order {sales_order.name}", "create_ups_batch_file")
            continue
        if not address.address_line1:
            frappe.log_error(f"address_line1 missing for Address '{address.name}' on Sales Order {sales_order.name}", "create_ups_batch_file")
            continue
        if not address.city:
            frappe.log_error(f"city missing for Address '{address.name}' on Sales Order {sales_order.name}", "create_ups_batch_file")
            continue
        if not address.pincode:
            frappe.log_error(f"pincode missing for Address '{address.name}' on Sales Order {sales_order.name}", "create_ups_batch_file")
            continue
        if not sales_order.contact_phone:
            frappe.log_error(f"contact_phone missing on Sales Order {sales_order.name}", "create_ups_batch_file")
            continue
        phone = re.sub('[ \+.,\-\/]', '', sales_order.contact_phone.replace('+', '00').replace('(0)', ''))[:15]
        if not phone:
            frappe.log_error(f"contact_phone on Sales Order {sales_order.name} contains only unallowed characters", "create_ups_batch_file")
            continue
        if not phone.isdigit():
            frappe.log_error(f"WARNING: Cleaned phone='{phone}' on Sales Order {sales_order.name} contains characters that are not digits. The original contact_phone was '{sales_order.contact_phone}'.", "create_ups_batch_file")
        weight = '"0,1"'
        customer_name = (sales_order.order_customer_display or sales_order.customer_name).replace(',', '')[:35]
        lines_to_write.append(f"{sales_order.contact_display.replace(',', '')[:35]},{customer_name},{country_code.upper()},{address.address_line1.replace(',', '')[:35]},,,{address.city.replace(',', '')[:30]},,{address.pincode.replace(',', '')[:10]},{phone},,,{sales_order.contact_email[:50]},2,,{weight},36,25,2,,Nukleotides,,,,11,,,,,,,,{sales_order.web_order_id.replace(',', '')[:35]},,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,\n")

    if len(lines_to_write) > 0:
        with open(f"/mnt/erp_share/UPS_batch_files/{datetime.now().strftime('%Y-%m-%d_%H-%M')}_ups_batch.csv", mode='w') as file:  # TODO: Move file path to Microsynth Settings
            for line in lines_to_write:
                file.write(line)


@frappe.whitelist()
def print_purchasing_labels(label_table):
    import json
    purchase_label_template = "microsynth/templates/includes/purchase_label_novexx.html"
    label_printer_ip = "192.0.1.73"
    label_printer_port = 9100
    user = frappe.get_user().name
    username = frappe.get_value("User", user, "username")

    if isinstance(label_table, str):
        label_table = json.loads(label_table)
    try:
        for row in label_table:
            row['username'] = username
            labels_to_print = int(row.get("labels_to_print") or 0)
            if labels_to_print <= 0:
                continue

            for _ in range(labels_to_print):
                # Render the label
                content = frappe.render_template(
                    purchase_label_template,
                    {"row": row}
                )
                #frappe.log_error(content, "content")
                print_raw(label_printer_ip, label_printer_port, content)
    except Exception as err:
        frappe.log_error(frappe.get_traceback(), "print_purchasing_labels")
        frappe.throw(f"Error printing labels: {err}")


def print_test_purchasing_label_novexx():
    """
    bench execute microsynth.microsynth.labels.print_test_purchasing_label_novexx
    """
    content = '''
#!A1
#IMS30/22
#N13
#ER

#T1.2#J19.5#YN101//28///Receipt: 10.06.2025 / JPe#G

#T1.2#J16.5#YN101//34///Shelf life: 10.06.2026#G

#T1.2#J13#YN101//42///OxiPy2#G
#T1.2#J9.4#YN101//42///1234
#T15.4#J10#IDM/0R16S36/4///P012345:abcdefghijklmnopqrstuvwxyz0123456789ab


#T1.2#J6.7#YN101//28///Opening date / initials:#G

#Q1/
#!P1l
'''
    print_raw('192.0.1.79', 9100, content)
