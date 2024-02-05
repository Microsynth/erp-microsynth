# -*- coding: utf-8 -*-
# Copyright (c) 2022, Microsynth AG, libracore (https://www.libracore.com) and contributors
# For license information, please see license.txt
#
# For more details, refer to https://github.com/Microsynth/erp-microsynth/
#

import requests
import frappe
from frappe.core.doctype.communication.email import make
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
    """
    find sales orders that have no delivery note and are not closed
    run 
    bench execute microsynth.microsynth.seqblatt.check_sales_order_completion
    """
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

        if not validate_sales_order(sales_order['name']):
            # validate_sales_order writes to the error log in case of an issue
            continue

        try:
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
                    AND `tabSequencing Label`.`status` NOT IN ("received", "processed");
                """.format(sales_order=sales_order['name']), as_dict=True)

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

        except Exception as err:
            frappe.log_error("Cannot create a Delivery Note for Sales Order '{0}': \n{1}".format(sales_order['name'], err), "seqblatt.check_sales_order_completion")
    return


def check_submit_delivery_note(delivery_note):
    """
    Check if the delivery note is eligible for autocompletion and submit it.

    run
    bench execute microsynth.microsynth.seqblatt.check_submit_delivery_note --kwargs "{'delivery_note':'DN-BAL-23111770'}"
    """
    try:
        delivery_note = frappe.get_doc("Delivery Note", delivery_note)

        if delivery_note.docstatus != 0:
            msg = "Delivery Note '{0}' is not in Draft. docstatus: {1}".format(delivery_note.docstatus)
            print(msg)
            frappe.log_error(msg, "seqblatt.check_submit_delivery_note")

        sales_orders = []
        for i in delivery_note.items:
            if i.item_code not in [ '0901', '0904', '3235', '3237', '3252', '3254', '0968', '0969', '0975', '3264', '3265', '3266', '3270' ]:
                print("Delivery Note '{0}': Item '{1}' is not allowed for autocompletion".format(delivery_note.name, i.item_code))
                return
            if i.against_sales_order not in sales_orders:
                sales_orders.append(i.against_sales_order)

        if len(sales_orders) != 1:
            msg = "Delivery Note '{0}' is derived from none or multiple sales orders".format(delivery_note.name)
            print(msg)
            frappe.log_error(msg, "seqblatt.check_submit_delivery_note")
            return

        # Check that the delivery note was created at least 7 days ago
        time_between_insertion = datetime.today() - delivery_note.creation
        if time_between_insertion.days <= 7:
            print("Delivery Note '{0}' was created on {1}".format(delivery_note.name, delivery_note.creation))
            return

        # # Check that the sales order was created at least 7 days ago
        # sales_order_creation = frappe.get_value("Sales Order", sales_orders[0], "creation")
        # time_between_insertion = datetime.today() - sales_order_creation
        # if time_between_insertion.days <= 7:
        #     print("Delivery Note '{0}' is from a sales order created on {1}".format(delivery_note.name, sales_order_creation))
        #     return

        # Check that the Delivery Note does not contain a Sample with a Barcode Label associated with more than one Sample
        for sample in delivery_note.samples:
            barcode_label = frappe.get_value("Sample", sample.sample, "sequencing_label")
            samples = frappe.get_all("Sample", filters=[["sequencing_label", "=", barcode_label]], fields=['name', 'web_id', 'creation'])
            if len(samples) > 1:
                if 'GOE' in delivery_note.name:
                    recipient = 'karla.busch@microsynth.seqlab.de'
                    person = 'Karla'
                elif 'LYO' in delivery_note.name:
                    recipient = 'agnes.nguyen@microsynth.fr'
                    person = 'Agnes'
                else:
                    recipient = 'katja.laengle@microsynth.ch'
                    person = 'Katja'
                subject = f"Barcode label {barcode_label} used multiple times"
                message = f"Dear {person},<br><br>this is an automatic email to inform you that Delivery Note '{delivery_note.name}' won't be submitted automatically in the ERP, because it contains a Sample with Barcode Label '{barcode_label}' that is used for {len(samples)} different Samples:<br>"
                for s in samples:
                    message += f"Sample '{s['name']}' with Web ID '{s['web_id']}', created {s['creation']}<br>"
                message += f"<br>Please check these samples. If you are sure that there is no problem, please submit '{delivery_note.name}' manually in the ERP.<br><br>Best regards,<br>Jens"
                non_html_message = message.replace("<br>","\n")
                print(non_html_message)
                frappe.log_error(non_html_message, "seqblatt.check_submit_delivery_note: " + subject)
                make(
                    recipients = recipient,
                    sender = "jens.petermann@microsynth.ch",
                    subject = subject,
                    content = message,
                    send_email = True
                    )
                return

        delivery_note.submit()

    except Exception as err:
        frappe.log_error("Cannot process Delivery Note '{0}': \n{1}".format(delivery_note.name, err), "seqblatt.check_submit_delivery_note")


def submit_delivery_notes():
    """
    Checks all delivery note drafts of product type sequencing and submits them if eligible.

    run
    bench execute microsynth.microsynth.seqblatt.submit_delivery_notes
    """
    delivery_notes = frappe.db.get_all("Delivery Note",
        filters = {'docstatus': 0, 'product_type': 'Sequencing' },
        fields = ['name'])

    i = 0
    length = len(delivery_notes)
    for dn in delivery_notes:
        print("{1}% - process delivery note '{0}'".format(dn.name, int(100 * i / length)))
        check_submit_delivery_note(dn.name)
        frappe.db.commit()
        i += 1