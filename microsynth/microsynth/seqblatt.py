# -*- coding: utf-8 -*-
# Copyright (c) 2022, Microsynth AG, libracore (https://www.libracore.com) and contributors
# For license information, please see license.txt
# For more details, refer to https://github.com/Microsynth/erp-microsynth/

import time
import json
import traceback
from datetime import datetime

import frappe
from frappe.utils import get_url_to_form
from erpnext.selling.doctype.sales_order.sales_order import make_delivery_note

from microsynth.microsynth.naming_series import get_naming_series
from microsynth.microsynth.utils import validate_sales_order, has_items_delivered_by_supplier, get_customer, get_sql_list
from microsynth.microsynth.shipping import create_receiver_address_lines


def check_and_get_label(label):
    """
    Take a label dictionary (item, barcode, status), search it in the ERP and return it if it is unique or an error message otherwise.

    bench execute microsynth.microsynth.seqblatt.check_and_get_label --kwargs "{'label': {'item': '6030', 'barcode': 'MY004450', 'status': 'submitted'}}"
    """
    sql_query = """
        SELECT `name`,
            `item`,
            `label_id` AS `barcode`,
            `status`,
            `registered`,
            `contact`,
            `registered_to`,
            `sales_order`,
            `customer`
        FROM `tabSequencing Label`
        WHERE `label_id` = %s
            AND `item` = %s
        ;"""
    sequencing_labels = frappe.db.sql(sql_query, (label['barcode'], label['item']), as_dict=True)
    if len(sequencing_labels) == 0:
        return {'success': False, 'message': f"Found no label with barcode {label['barcode']} and Item {label['item']} in the ERP.", 'label': None}
    elif len(sequencing_labels) > 1:
        return {'success': False, 'message': f"Found multiple labels with barcode {label['barcode']} and Item {label['item']} in the ERP.", 'label': None}
    else:
        return {'success': True, 'message': "OK", 'label': sequencing_labels[0]}


def check_and_get_labels(labels):
    """
    Batch-fetch Sequencing Labels from the ERP based on barcode and item pairs.

    Parameters:
        labels (list): List of label dicts with 'barcode' and 'item' keys.

    Returns:
        dict: Mapping from (barcode, item) → label data or error

    bench execute microsynth.microsynth.seqblatt.check_and_get_labels --kwargs "{'labels': [{'label_id': 'MY004450', 'item_code': '6030'}, {'label_id': 'MY004449', 'item_code': '6030'}]}"
    """
    if not labels:
        return {}

    label_map = {}
    valid_pairs = []
    seen_keys = set()

    # Normalize and deduplicate input
    for l in labels:
        barcode = l.get("barcode") or l.get("label_id")
        item = l.get("item") or l.get("item_code")
        key_str = f"{barcode}|{item}"

        if key_str in seen_keys:
            continue
        seen_keys.add(key_str)

        if not barcode or not item:
            # Incomplete pair — cannot query
            label_map[key_str] = {"error": "not_found"}
        else:
            valid_pairs.append((barcode, item))

    if not valid_pairs:
        # All were incomplete → nothing to query
        return label_map

    # Build tuple-based condition
    values = [v for pair in valid_pairs for v in pair]
    tuple_conditions = ', '.join(['(%s, %s)'] * len(valid_pairs))

    sql = f"""
        SELECT
            name,
            item,
            label_id AS barcode,
            status,
            registered,
            contact,
            registered_to,
            sales_order,
            customer
        FROM `tabSequencing Label`
        WHERE (label_id, item) IN ({tuple_conditions});
    """
    results = frappe.db.sql(sql, values, as_dict=True)

    for row in results:
        key_str = f"{row['barcode']}|{row['item']}"
        if key_str in label_map:
            # mark duplicates
            label_map[key_str] = {"error": "duplicate"}
        else:
            label_map[key_str] = row

    # Add not_found for valid pairs not returned from DB
    for barcode, item in valid_pairs:
        key_str = f"{barcode}|{item}"
        if key_str not in label_map:
            label_map[key_str] = {"error": "not_found"}

    return label_map


def process_label_status_change(labels, target_status, required_current_statuses=None, check_not_used=False, stop_on_first_failure=False):
    """
    Unified handler to change the status of sequencing labels, with options for validation and strict failure handling.

    Parameters:
        labels (list): A list of dictionaries representing labels.
                       Each label must contain:
                         - "barcode" (or "label_id")
                         - "item" (or "item_code")
        target_status (str): The status to which the label should be set, e.g., "submitted" or "unused".
        required_current_status (list of str or None, optional): If set, only labels that currently have one of these statuses in the ERP will be processed.
                                                 Others will be skipped (or cause immediate failure if `stop_on_first_failure` is True).
        check_not_used (bool, optional): If True, verifies that the label is not used for any open Sales Orders
                                         (DocStatus <= 1) other than the one it was ordered with.
        stop_on_first_failure (bool, optional): If True, aborts processing immediately upon the first invalid label
                                                (e.g. not found, wrong status, or used for another SO).
                                                If False, attempts to process all valid labels and returns partial success if any fail.
    Returns:
        dict:
            {
                "success": bool,     # False if any label failed (or immediately on first error, if strict mode)
                "message": str,      # 'OK' or error message
                "labels": list       # List of labels with their status and optional error messages (if not strict mode)
            }

    Example usage:
    bench execute microsynth.microsynth.seqblatt.process_label_status_change --kwargs "{'labels': [{'label_id': 'MY004450', 'item_code': '6030'}, {'label_id': 'MY004449', 'item_code': '6030'}], 'target_status': 'unused', 'required_current_statuses': ['locked'], 'check_not_used': True, 'stop_on_first_failure': True}"
    """
    if not labels or len(labels) == 0:
        return {'success': False, 'message': "Please provide at least one Label", 'labels': None}

    success = True

    try:
        # Normalize and deduplicate
        normalized = [{
            "barcode": l.get("barcode") or l.get("label_id"),
            "item": l.get("item") or l.get("item_code")
        } for l in labels]

        label_lookup = check_and_get_labels(normalized)
        processed_labels = []
        labels_to_process = []
        customers_to_enable = set()

        for label in normalized:
            key = (label["barcode"], label["item"])
            key_str = f"{label['barcode']}|{label['item']}"
            if key_str not in label_lookup:
                label['message'] = f"Label {key[0]} with Item {key[1]} not found."
                processed_labels.append(label)
                success = False
                if stop_on_first_failure:
                    return {'success': False, 'message': label['message'], 'labels': None}
                continue
            result = label_lookup.get(key_str)

            if "error" in result:
                if result["error"] == "not_found":
                    label['message'] = f"Label {key[0]} with Item {key[1]} not found."
                    processed_labels.append(label)
                    success = False
                    if stop_on_first_failure:
                        return {'success': False, 'message': label['message'], 'labels': None}
                    continue

                elif result["error"] == "duplicate":
                    label['message'] = f"Multiple labels found for {key[0]} and {key[1]}."
                    processed_labels.append(label)
                    success = False
                    if stop_on_first_failure:
                        return {'success': False, 'message': label['message'], 'labels': None}
                    continue

            erp_label = result

            if required_current_statuses and erp_label['status'] not in required_current_statuses:
                erp_label['message'] = f"The label has currently not one of the required status {', '.join(required_current_statuses)} in the ERP."
                processed_labels.append(erp_label)
                success = False
                if stop_on_first_failure:
                    return {'success': False, 'message': erp_label['message'], 'labels': None}
                continue

            if check_not_used:
                sql_query = """
                    SELECT `tabSample`.`name` AS `sample`
                    FROM `tabSample Link`
                    LEFT JOIN `tabSample` ON `tabSample Link`.`sample` = `tabSample`.`name`
                    LEFT JOIN `tabSales Order` ON `tabSales Order`.`name` = `tabSample Link`.`parent`
                    WHERE `tabSample`.`sequencing_label` = %s
                        AND `tabSample Link`.`parent` != %s
                        AND `tabSample Link`.`parenttype` = "Sales Order"
                        AND `tabSales Order`.`docstatus` <= 1;
                """
                samples = frappe.db.sql(sql_query, (erp_label['barcode'], erp_label['sales_order']), as_dict=True)
                if samples:
                    erp_label['message'] = f"Label '{erp_label['barcode']}' is used in open Sales Orders other than {erp_label['sales_order']}."
                    processed_labels.append(erp_label)
                    success = False
                    if stop_on_first_failure:
                        return {'success': False, 'message': erp_label['message'], 'labels': None}
                    continue

            if erp_label.get('customer'):
                customers_to_enable.add(erp_label['customer'])

            labels_to_process.append(erp_label)

        # Batch enable Customers (only fetch and modify disabled ones)
        disabled_customers = []
        if customers_to_enable:
            disabled_customers_to_enable = frappe.get_all("Customer", filters={"name": [ "in", [ f'"{x}"' for x in customers_to_enable ] ], "disabled": 1}, fields=["name"])
            for c in disabled_customers_to_enable:
                customer_doc = frappe.get_doc("Customer", c.name)
                customer_doc.disabled = 0
                customer_doc.save(ignore_permissions=True, ignore_version=True)  # Do not create a version.
                disabled_customers.append(c.name)

        # Set label statuses
        for erp_label in labels_to_process:
            #frappe.db.set_value("Sequencing Label", erp_label['name'], "status", target_status)  # would be much faster, but no validation
            label_doc = frappe.get_doc("Sequencing Label", erp_label['name'])
            label_doc.status = target_status
            label_doc.save(ignore_permissions=True)
            processed_labels.append({
                "item": label_doc.item,
                "barcode": label_doc.label_id,
                "status": label_doc.status,
                "message": "OK"
            })

        # Disable previously disabled Customers
        for customer in disabled_customers:
            customer_doc = frappe.get_doc("Customer", customer)
            customer_doc.disabled = 1
            customer_doc.save(ignore_permissions=True, ignore_version=True)  # Do not create a version.

        frappe.db.commit()
        #message = f"The following Customers were temporarily enabled and are now disabled again: {','.join(disabled_customers)}" if disabled_customers else "OK"

        if not processed_labels:
            return {
                'success': False,
                'message': "All labels failed validation",
                'labels': labels
            }

        return {
            'success': success,
            'message': "OK",
            'labels': processed_labels
        }

    except Exception as err:
        msg = f"Error setting labels to {target_status}: {err}"
        frappe.log_error(f"{msg}\n\n{traceback.format_exc()}", f"process_label_status_change")
        return {'success': False, 'message': msg, 'labels': None}


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

    bench execute microsynth.microsynth.seqblatt.set_status --kwargs "{'status': 'locked', 'labels': [{'label_id': 'MY004450', 'item_code': '6030'}, {'label_id': 'MY004449', 'item_code': '6030'}]}"
    """
    if isinstance(labels, str):
        labels = json.loads(labels)
    check_not_used = status == "unused"
    return process_label_status_change(labels, target_status=status, check_not_used=check_not_used)


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
    #start_ts = datetime.now()
    open_sequencing_sales_orders = frappe.db.sql("""
        SELECT `tabSales Order`.`name`,
            `tabSales Order`.`web_order_id`
        FROM `tabSales Order`
        LEFT JOIN `tabDelivery Note Item` ON `tabSales Order`.`name` = `tabDelivery Note Item`.`against_sales_order`
                                          AND `tabDelivery Note Item`.`docstatus` < 2
        LEFT JOIN `tabDelivery Note` ON `tabDelivery Note`.`name` = `tabDelivery Note Item`.`parent`
                                     AND `tabDelivery Note`.`docstatus` < 2
        WHERE `tabSales Order`.`docstatus` = 1
            AND `tabSales Order`.`status` NOT IN ("Closed", "Completed")
            AND `tabSales Order`.`product_type` = "Sequencing"
            AND `tabSales Order`.`per_delivered` < 100
            AND (
                `tabSales Order`.`web_order_id` IS NULL
                OR NOT EXISTS (
                    SELECT 1
                    FROM `tabDelivery Note`
                    WHERE `tabDelivery Note`.`web_order_id` = `tabSales Order`.`web_order_id`
                        AND `tabDelivery Note`.`docstatus` < 2
                )
            )
        GROUP BY `tabSales Order`.`name`
        HAVING COUNT(`tabDelivery Note Item`.`parent`) = 0;
    """, as_dict=True)
    #print(f"Found {len(open_sequencing_sales_orders)} open Sequencing Sales Orders.")
    # check completion of each sequencing sales order: sequencing labels of this order on processed
    for sales_order in open_sequencing_sales_orders:
        #print(f"processing {sales_order['name']} ...")

        if not validate_sales_order(sales_order['name']):
            # validate_sales_order writes to the error log in case of an issue
            continue

        try:
            # check status of labels assigned to each sample and consider Samples without a label
            pending_samples = frappe.db.sql("""
                SELECT
                    `tabSample`.`name`
                FROM `tabSample Link`
                LEFT JOIN `tabSample` ON `tabSample Link`.`sample` = `tabSample`.`name`
                LEFT JOIN `tabSequencing Label` on `tabSample`.`sequencing_label` = `tabSequencing Label`.`name`
                WHERE
                    `tabSample Link`.`parent` = "{sales_order}"
                    AND `tabSample Link`.`parenttype` = "Sales Order"
                    AND (`tabSequencing Label`.`status` NOT IN ("received", "processed")
                        OR `tabSample`.`sequencing_label` IS NULL);
                """.format(sales_order=sales_order['name']), as_dict=True)

            if len(pending_samples) == 0:
                # all processed: create delivery
                if has_items_delivered_by_supplier(sales_order['name']):
                    # do not create a DN if any item has the flag delivered_by_supplier set
                    continue
                customer_name = frappe.get_value("Sales Order", sales_order['name'], 'customer')
                customer = frappe.get_doc("Customer", customer_name)

                if customer.disabled:
                    frappe.log_error("Customer '{0}' of order '{1}' is disabled. Cannot create a delivery note.".format(customer.name, sales_order), "Production: sales order complete")
                    return

                ## create delivery note (leave on draft: submitted in a batch process later on)
                dn_content = make_delivery_note(sales_order['name'])
                dn = frappe.get_doc(dn_content)
                company = frappe.get_value("Sales Order", sales_order['name'], "company")
                dn.naming_series = get_naming_series("Delivery Note", company)

                # insert record
                dn.flags.ignore_missing = True
                dn.insert(ignore_permissions=True)
                #print(f"### Inserted {dn.name} for {sales_order['name']}.")
                frappe.db.commit()

        except Exception as err:
            frappe.log_error(f"Cannot create a Delivery Note for Sales Order '{sales_order['name']}': \n{err}\n{traceback.format_exc()}", "seqblatt.check_sales_order_completion")
    #elapsed_time = timedelta(seconds=(datetime.now() - start_ts).total_seconds())
    #frappe.log_error(f"{datetime.now()}: Finished seqblatt.check_sales_order_completion after {elapsed_time} hh:mm:ss for {len(open_sequencing_sales_orders)} open_sequencing_sales_orders.", "monitoring check_sales_order_completion")
    return


def check_submit_delivery_note(delivery_note):
    """
    Check if the delivery note is eligible for autocompletion and submit it.

    run
    bench execute microsynth.microsynth.seqblatt.check_submit_delivery_note --kwargs "{'delivery_note': 'DN-BAL-23111770'}"
    """
    try:
        delivery_note = frappe.get_doc("Delivery Note", delivery_note)

        if delivery_note.docstatus != 0:
            msg = f"Delivery Note '{delivery_note.name}' is not in Draft. docstatus: {delivery_note.docstatus}"
            print(msg)
            frappe.log_error(msg, "seqblatt.check_submit_delivery_note")

        sales_orders = []
        for i in delivery_note.items:
            if i.item_code not in [ '0901', '0904', '3235', '3237', '3252', '3254', '0968', '0969', '0975', '3264', '3265', '3266', '3270' ]:
                print("Delivery Note '{0}': Item '{1}' is not allowed for autocompletion".format(delivery_note.name, i.item_code))
                return
            if i.against_sales_order and (i.against_sales_order not in sales_orders):
                sales_orders.append(i.against_sales_order)

        if len(sales_orders) != 1:
            msg = "Delivery Note '{0}' is derived from none or multiple sales orders".format(delivery_note.name)
            print(msg)
            frappe.log_error(msg, "seqblatt.check_submit_delivery_note")
            return

        # Check that the delivery note was created at least 7 days ago
        time_between_insertion = datetime.today() - delivery_note.creation
        if time_between_insertion.days <= 7:
            print("Delivery Note '{0}' is not older than 7 days and was created on {1}".format(delivery_note.name, delivery_note.creation))
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
                from microsynth.microsynth.utils import send_email_from_template
                # Would require three different Email Templates to get rid of the recipients here
                if 'GOE' in delivery_note.name:
                    email_template = frappe.get_doc("Email Template", "GOE - Barcode label used multiple times")
                elif 'LYO' in delivery_note.name:
                    email_template = frappe.get_doc("Email Template", "LYO - Barcode label used multiple times")
                else:
                    email_template = frappe.get_doc("Email Template", "BAL - Barcode label used multiple times")

                dn_url_string = f"<a href={get_url_to_form('Delivery Note', delivery_note.name)}>{delivery_note.name}</a>"
                sample_details = ""
                for s in samples:
                    sales_orders = frappe.get_all("Sample Link", filters=[["sample", "=", s['name']], ["parenttype", "=", "Sales Order"]], fields=['parent'])
                    sales_order_links = ", ".join([f"<a href={get_url_to_form('Sales Order', so['parent'])}>{so['parent']}</a>" for so in sales_orders])
                    url = get_url_to_form("Sample", s['name'])
                    sample_details += f"Sample <a href={url}>{s['name']}</a> with Web ID '{s['web_id']}', created {s['creation']} on Sales Order(s) {sales_order_links}<br>"

                rendered_subject = frappe.render_template(email_template.subject, {'barcode_label': barcode_label})
                rendered_content = frappe.render_template(email_template.response, {'dn_url_string': dn_url_string, 'barcode_label': barcode_label, 'len_samples': len(samples), 'sample_details': sample_details})
                send_email_from_template(email_template, rendered_content, rendered_subject)
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


def submit_seq_primer_dns():
    """
    Check all Delivery Note Drafts of Product Type Oligos and with Item Code 0975 and submit them if eligible.

    bench execute microsynth.microsynth.seqblatt.submit_seq_primer_dns
    """
    delivery_notes = frappe.db.sql("""
        SELECT `tabDelivery Note`.`name`
        FROM `tabDelivery Note`
        JOIN `tabDelivery Note Item` ON (`tabDelivery Note Item`.`parent` = `tabDelivery Note`.`name`
                AND `tabDelivery Note Item`.`item_code` IN ('0975'))
        WHERE
            `tabDelivery Note`.`product_type` = 'Oligos'
            AND `tabDelivery Note`.`docstatus` = 0;
        """, as_dict=True)

    for dn in delivery_notes:
        print(f"Processing '{dn['name']}' ...")
        check_submit_delivery_note(dn['name'])
        frappe.db.commit()


def close_partly_delivered_paid_orders(product_type='Sequencing', days=0, dry_run=True):
    """
    Find Sales Orders that are at least partly delivered, paid,
    and created more than :param days: days ago. Close and tag these Sales Orders.
    Should be run by a daily cronjob in the early morning:
    30 5 * * * cd /home/frappe/frappe-bench && /usr/local/bin/bench --site erp.microsynth.local microsynth.microsynth.seqblatt.close_partly_delivered_paid_orders --kwargs "{'dry_run': False}"

    bench execute microsynth.microsynth.seqblatt.close_partly_delivered_paid_orders --kwargs "{'product_type': 'Oligos', 'days': 60, 'dry_run': True}"
    """
    from frappe.desk.tags import add_tag
    counter = 0
    cutoff_date = frappe.utils.add_days(frappe.utils.today(), -days)

    sales_orders = frappe.db.sql("""
        SELECT * FROM
            (SELECT `tabSales Order`.`name`,
                `tabSales Order`.`transaction_date`,
                ROUND(`tabSales Order`.`total`, 2) AS `total`,
                `tabSales Order`.`currency`,
                `tabSales Order`.`customer`,
                `tabSales Order`.`customer_name`,
                `tabSales Order`.`web_order_id`,
                `tabSales Order`.`product_type`,
                `tabSales Order`.`company`,
                `tabSales Order`.`owner`,
                (SELECT COUNT(`tabSales Invoice Item`.`name`)
                    FROM `tabSales Invoice Item`
                    LEFT JOIN `tabSales Invoice`
                        ON `tabSales Invoice Item`.`parent` = `tabSales Invoice`.`name`
                    WHERE `tabSales Invoice Item`.`docstatus` = 1
                      AND `tabSales Invoice Item`.`sales_order` = `tabSales Order`.`name`
                      AND `tabSales Invoice`.`status` = 'Paid'
                ) AS `paid_si_items`,
                (SELECT COUNT(`tabDelivery Note Item`.`name`)
                    FROM `tabDelivery Note Item`
                    WHERE `tabDelivery Note Item`.`docstatus` = 1
                      AND `tabDelivery Note Item`.`against_sales_order` = `tabSales Order`.`name`
                ) AS `dn_items`
            FROM `tabSales Order`
            WHERE `tabSales Order`.`product_type` = %(product_type)s
              AND `tabSales Order`.`transaction_date` <= %(cutoff_date)s
              AND `tabSales Order`.`per_delivered` > 0
              AND `tabSales Order`.`per_delivered` < 100
              AND `tabSales Order`.`docstatus` = 1
              AND `tabSales Order`.`status` NOT IN ('Closed', 'Completed')
              AND `tabSales Order`.`per_billed` > 0
              AND `tabSales Order`.`billing_status` != 'Not Billed'
            ) AS raw
        WHERE raw.paid_si_items > 0
          AND raw.dn_items > 0
        ORDER BY raw.transaction_date;
    """, {
        "product_type": product_type,
        "cutoff_date": cutoff_date
    }, as_dict=True)

    print(f"Going to process {len(sales_orders)} Sales Orders.")

    for i, so in enumerate(sales_orders):
        so_doc = frappe.get_doc("Sales Order", so['name'])
        if not so_doc.web_order_id:
            msg = f"Sales Order {so_doc.name} has no Web Order ID. Please check to close it manually."
            print(msg)
            frappe.log_error(msg, "seqblatt.close_partly_delivered_paid_orders")
            continue
        # check that there is exactly one submitted Delivery Note with a matching Web Order ID
        delivery_notes = frappe.db.sql(f"""
            SELECT DISTINCT `tabDelivery Note Item`.`parent` AS `name`,
                `tabDelivery Note`.`total`
            FROM `tabDelivery Note Item`
            LEFT JOIN `tabDelivery Note` ON `tabDelivery Note`.`name` = `tabDelivery Note Item`.`parent`
            WHERE `tabDelivery Note Item`.`docstatus` = 1
                AND `tabDelivery Note`.`web_order_id` = {so_doc.web_order_id}
            ;""", as_dict=True)

        if len(delivery_notes) > 0:
            if len(delivery_notes) == 1:
                if dry_run:
                    print(f"Would close {so_doc.name} created {so_doc.creation}")
                    counter += 1
                else:
                    try:
                        add_tag(tag="partly_delivered", dt="Sales Order", dn=so_doc.name)
                        # set Sales Order status to Closed
                        so_doc.update_status('Closed')
                        so_doc.save()
                    except Exception as err:
                        msg = f"Unable to close Sales Order {so_doc.name} due to the following error:\n{err}"
                        print(msg)
                        frappe.log_error(msg, "seqblatt.close_partly_delivered_paid_orders")
                    else:
                        print(f"{i+1}/{len(sales_orders)}: Tagged and closed {so_doc.name} created {so_doc.creation}")
                        counter += 1
            else:
                msg = f"Sales Order {so_doc.name} has the following {len(delivery_notes)} submitted Delivery Notes: {delivery_notes}"
                print(msg)
                frappe.log_error(msg, "seqblatt.close_partly_delivered_paid_orders")
        else:
            msg = f"Found no Delivery Note for Sales Order {so_doc.name} with Web Order ID '{so_doc.web_order_id}'."
            print(msg)
            frappe.log_error(msg, "seqblatt.close_partly_delivered_paid_orders")

    if dry_run:
        print(f"\nWould have closed {counter} Sales Orders.")
    else:
        print(f"\nClosed {counter} Sales Orders.")


def check_sequencing_delivery_note_duplicates():
    """
    Monitoring function to check if there are any new Sequencing Sales Orders
    with more than one non-cancelled Delivery Note.
    Should be run by a daily cronjob:
    30 1 * * * cd /home/frappe/frappe-bench && /usr/local/bin/bench --site erp.microsynth.local execute microsynth.microsynth.seqblatt.check_sequencing_delivery_note_duplicates
    """
    sql_query = """
        SELECT * FROM
            (SELECT `tabSales Order`.`name` AS `sales_order`,
                `tabSales Order`.`creation`,
                ROUND(`tabSales Order`.`total`, 2) AS `total`,
                `tabSales Order`.`currency`,
                `tabSales Order`.`customer`,
                `tabSales Order`.`customer_name`,
                `tabSales Order`.`web_order_id`,
                `tabSales Order`.`company`,
                (SELECT COUNT(DISTINCT(`tabDelivery Note Item`.`parent`))
                    FROM `tabDelivery Note Item`
                    LEFT JOIN `tabDelivery Note` ON `tabDelivery Note Item`.`parent` = `tabDelivery Note`.`name`
                    WHERE `tabDelivery Note`.`docstatus` < 2
                        AND `tabDelivery Note Item`.`against_sales_order` = `tabSales Order`.`name`
                ) AS `valid_DNs`
            FROM `tabSales Order`
            WHERE   `tabSales Order`.`product_type` = 'Sequencing'
                AND `tabSales Order`.`docstatus` = 1
                AND `tabSales Order`.`creation` > DATE('2024-11-01')
            ) AS `raw`
        WHERE `raw`.`valid_DNs` > 1
        ORDER BY `raw`.`creation`;
        """
    sales_orders = frappe.db.sql(sql_query, as_dict=True)
    if len(sales_orders) > 0:
        from microsynth.microsynth.utils import send_email_from_template
        email_template = frappe.get_doc("Email Template", "Sequencing Sales Orders with more than one Delivery Note")
        so_details = ""
        for so in sales_orders:
            so_details += f"<br>{so['sales_order']}, created on {so['creation']}"
        rendered_content = frappe.render_template(email_template.response, {'so_details': so_details})
        send_email_from_template(email_template, rendered_content)


@frappe.whitelist()
def get_shipping_addresses(webshop_accounts):
    """
    * Accepts a list of webshop accounts (Contact IDs)
    * Looks up the Webshop Address and return the default shipping address:
    * Return example:
        "sucess": true,
        "message": "OK",
        "internal_message": null,
        "account_addresses": [
            {
                "webshop_account": "215856",
                "first_name": "Rolf",
                "last_name": "Suter",
                "salutation": "Mr.",
                "title": null,
                "full_name": "Rolf Suter",
                "shipping_address_lines": [
                    "Microsynth AG",
                    "Rolf Suter",
                    "IT Applications",
                    "Schützenstrasse 15",
                    "9436 Balgach",
                    "Switzerland"
                ]
            }
        ]

    bench execute microsynth.microsynth.seqblatt.get_shipping_addresses --kwargs "{'webshop_accounts': ['215856', '215857']}"
    """
    account_addresses = []
    for webshop_account in list(set(webshop_accounts)):  # remove duplicates
        if not webshop_account or webshop_account.strip() == "" or not isinstance(webshop_account, str):
            return {
                "success": False,
                "message": "Wrong input",
                "internal_message": f"Webshop account '{webshop_account}' is not a valid non-empty string.",
                "account_addresses": account_addresses
            }
        customer_id = None
        contact_id = None
        address_id = None
        try:
            webshop_address_doc = frappe.get_doc("Webshop Address", webshop_account)
        except frappe.DoesNotExistError as err:
            return {
                "success": False,
                "message": f"Unable to get Webshop Address '{webshop_account}'",
                "internal_message": str(err),
                "account_addresses": account_addresses
            }
        for a in webshop_address_doc.addresses:
            if a.is_default_shipping and not a.disabled:
                customer_id = get_customer(a.contact)
                contact_id = a.contact
                contact_doc = frappe.get_doc("Contact", contact_id)
                address_id = contact_doc.address
                break
        if customer_id and contact_id and address_id:
            customer_name = frappe.get_value("Customer", customer_id, "customer_name")
            shipping_address_lines = create_receiver_address_lines(customer_name, contact_id, address_id)
        else:
            return {
                "success": False,
                "message": f"Unable to get default shipping address for webshop account {webshop_account}",
                "internal_message": f"No default shipping address found for webshop account {webshop_account}",
                "account_addresses": account_addresses
            }

        account_addresses.append({
            "webshop_account": webshop_account,
            "first_name": contact_doc.first_name,
            "last_name": contact_doc.last_name,
            "salutation": contact_doc.salutation,
            "title": contact_doc.designation,
            "full_name": contact_doc.full_name,
            "email": contact_doc.email_id,
            "email_cc": [email.get("email_id") for email in contact_doc.get("email_ids") if email.get("email_id") != contact_doc.email_id],
            "shipping_address_lines": shipping_address_lines
        })

    return {
        "success": True,
        "message": "OK",
        "internal_message": None,
        "account_addresses": account_addresses
    }


@frappe.whitelist()
def get_unused_easy_run_label_ranges():
    """
    Return ranges of all unused Sequencing Labels for Item Code 3050 where label_id needs to be grouped into barcode_start_range to barcode_start_range.
    Return example:
    {
        "message": {
            "success": true,
            "message": "OK",
            "internal_message": null,
            "ranges": [
                {
                    "contact": "215856",
                    "registered": false,
                    "registered_to": null,
                    "item": "3050",
                    "barcode_start_range": "642601",
                    "barcode_end_range": "642700",
                    "sales_order": "SO-GOE-26007741",
                    "web_order_id": 4722438
                },
                {
                    "contact": "215856",
                    "registered": true,
                    "registered_to": "237365",
                    "item": "3050",
                    "barcode_start_range": "642801",
                    "barcode_end_range": "642900",
                    "sales_order": "SO-GOE-26007741",
                    "web_order_id": 4722438
                }
            ]
        }
    }

    bench execute microsynth.microsynth.seqblatt.get_unused_easy_run_label_ranges
    """
    sql_query = """
        SELECT
            `sequencing_label_grouped`.`contact`,
            `sequencing_label_grouped`.`registered`,
            `sequencing_label_grouped`.`registered_to`,
            `sequencing_label_grouped`.`item`,
            `sequencing_label_grouped`.`sales_order`,
            (SELECT `web_order_id` FROM `tabSales Order` WHERE `name` = `sequencing_label_grouped`.`sales_order`) AS `web_order_id`,
            MIN(`sequencing_label_grouped`.`label_id`) AS `barcode_start_range`,
            MAX(`sequencing_label_grouped`.`label_id`) AS `barcode_end_range`
        FROM (
            SELECT
                `tabSequencing Label`.`contact`,
                `tabSequencing Label`.`registered`,
                `tabSequencing Label`.`registered_to`,
                `tabSequencing Label`.`item`,
                `tabSequencing Label`.`sales_order`,
                `tabSequencing Label`.`label_id`,
                `tabSequencing Label`.`label_id` - ROW_NUMBER() OVER (
                    PARTITION BY
                        `tabSequencing Label`.`contact`,
                        `tabSequencing Label`.`registered`,
                        `tabSequencing Label`.`registered_to`,
                        `tabSequencing Label`.`item`
                    ORDER BY
                        `tabSequencing Label`.`label_id`
                ) AS `group_identifier`
            FROM `tabSequencing Label`
            WHERE
                `tabSequencing Label`.`item` = '3050'
                AND `tabSequencing Label`.`status` = 'unused'
        ) AS `sequencing_label_grouped`
        GROUP BY
            `sequencing_label_grouped`.`contact`,
            `sequencing_label_grouped`.`registered`,
            `sequencing_label_grouped`.`registered_to`,
            `sequencing_label_grouped`.`item`,
            `sequencing_label_grouped`.`sales_order`,
            `sequencing_label_grouped`.`group_identifier`
        ORDER BY
            `barcode_start_range`
        """
    ranges = frappe.db.sql(sql_query, as_dict=True)
    return {
        "success": True,
        "message": "OK",
        "internal_message": None,
        "ranges": ranges
    }


### The following functions are alternative implementations of the same logic as get_unused_easy_run_label_ranges but implemented in Python without SQL window functions.

# def get_unused_easy_run_label_ranges_simple():
#     """
#     Same as get_unused_easy_run_label_ranges but implemented in Python without SQL window functions.
#     Should return the same result but is expected to be much slower. Used for testing and comparison.

#     bench execute microsynth.microsynth.seqblatt.get_unused_easy_run_label_ranges_simple
#     """
#     rows = frappe.db.sql("""
#         SELECT
#             `contact`,
#             `registered`,
#             `registered_to`,
#             `item`,
#             `label_id`
#         FROM `tabSequencing Label`
#         WHERE
#             `item` = '3050'
#             AND `status` = 'unused'
#         ORDER BY
#             `contact`,
#             `registered`,
#             `registered_to`,
#             `item`,
#             `label_id`
#     """, as_dict=True)

#     # normalize types (important!)
#     for row in rows:
#         row["label_id"] = int(row["label_id"])
#         row["registered"] = int(row["registered"]) if row["registered"] is not None else 0
#         row["registered_to"] = row["registered_to"] or None

#     ranges = []
#     current = None

#     for row in rows:
#         key = (
#             row["contact"],
#             row["registered"],
#             row["registered_to"],
#             row["item"]
#         )
#         if current is None:
#             current = {"key": key, "start": row["label_id"], "end": row["label_id"]}
#             continue

#         # same group + consecutive?
#         if key == current["key"] and row["label_id"] == current["end"] + 1:
#             current["end"] = row["label_id"]
#         else:
#             ranges.append({
#                 "contact": current["key"][0],
#                 "registered": current["key"][1],
#                 "registered_to": current["key"][2],
#                 "item": current["key"][3],
#                 "barcode_start_range": current["start"],
#                 "barcode_end_range": current["end"]
#             })
#             current = {"key": key, "start": row["label_id"], "end": row["label_id"]}

#     # append last range
#     if current:
#         ranges.append({
#             "contact": current["key"][0],
#             "registered": current["key"][1],
#             "registered_to": current["key"][2],
#             "item": current["key"][3],
#             "barcode_start_range": current["start"],
#             "barcode_end_range": current["end"]
#         })

#     return {
#         "success": True,
#         "message": "OK",
#         "internal_message": None,
#         "ranges": ranges
#     }


# def compare_easy_run_label_range_methods(validate=True):
#     """
#     Compare SQL vs Python implementation for label range grouping.

#     bench execute microsynth.microsynth.seqblatt.compare_easy_run_label_range_methods --kwargs "{'validate': True}"
#     """
#     # 1. SQL (window function)
#     start_sql = time.perf_counter()
#     sql_result = get_unused_easy_run_label_ranges()
#     duration_sql = time.perf_counter() - start_sql
#     print(f"Efficient SQL: {duration_sql:.6f} seconds")

#     # 2. Python (simple)
#     start_py = time.perf_counter()
#     py_result = get_unused_easy_run_label_ranges_simple()
#     duration_py = time.perf_counter() - start_py
#     print(f"Efficient Python: {duration_py:.6f} seconds")

#     # 3. Python (very simple)
#     start_py_very_simple = time.perf_counter()
#     duration_py_very_simple = time.perf_counter() - start_py_very_simple
#     print(f"Non-efficient Python: {duration_py_very_simple:.6f} seconds")

#     # 4. Validation
#     start_validation = time.perf_counter()
#     is_equal_sql_py = None

#     if validate:
#         def normalize(ranges):
#             def s(val):
#                 return val or ""

#             return sorted([
#                 (
#                     s(r["contact"]),
#                     int(r["registered"]) if r["registered"] is not None else 0,
#                     s(r["registered_to"]),
#                     s(r["item"]),
#                     int(r["barcode_start_range"]),
#                     int(r["barcode_end_range"]),
#                 )
#                 for r in ranges
#             ])

#         sql_norm = normalize(sql_result["ranges"])
#         py_norm = normalize(py_result["ranges"])
#         is_equal_sql_py = sql_norm == py_norm

#         if not is_equal_sql_py:
#             print("[COMPARE] ❌ Mismatch detected!")
#             print("SQL (first 5):", sql_norm[:5])
#             print("PY efficient (first 5):", py_norm[:5])

#     duration_validation = time.perf_counter() - start_validation
#     print(f"Validation: {duration_validation:.6f} seconds")
#     print(f"Results identical SQL vs Efficient Python: {is_equal_sql_py}")
