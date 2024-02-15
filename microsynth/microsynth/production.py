# -*- coding: utf-8 -*-
# Copyright (c) 2022, libracore (https://www.libracore.com) and contributors
# For license information, please see license.txt
#
# For more details, refer to https://github.com/Microsynth/erp-microsynth/
#

from erpnext.selling.doctype.sales_order.sales_order import make_delivery_note, close_or_unclose_sales_orders
import frappe
from microsynth.microsynth.labels import print_raw
from microsynth.microsynth.utils import get_export_category, validate_sales_order_status, validate_sales_order
from microsynth.microsynth.naming_series import get_naming_series

@frappe.whitelist()
def oligo_status_changed(content=None):
    """
    Update the status of a sales order item (Canceled, Completed)

    Testing from console:
    bench execute "microsynth.microsynth.production.oligo_status_changed" --kwargs "{'content':{'oligos':[{'web_id': '84554','production_id': '4567763.2','status': 'Completed'}]}}"
    """
    # check mandatory
    if not content:
        return {'success': False, 'message': "Please provide content", 'reference': None}
    if not 'oligos' in content:
        return {'success': False, 'message': "Please provide oligos", 'reference': None}
    
    # go through oligos and update status
    affected_sales_orders = []
    updated_oligos = []
    error_oligos = []
    for oligo in content['oligos']:
        if not 'web_id' in oligo:
            return {'success': False, 'message': "Oligos need to have a web_id", 'reference': None}
        if not 'status' in oligo:
            return {'success': False, 'message': "Oligos need to have a status (Open, Completed, Canceled)", 'reference': None}

        # find oligo
        oligos = frappe.db.sql("""
            SELECT 
              `tabOligo`.`name`,
              `tabOligo Link`.`parent` AS `sales_order`
            FROM `tabOligo`
            LEFT JOIN `tabOligo Link` ON `tabOligo Link`.`oligo` = `tabOligo`.`name`
            WHERE 
              `tabOligo`.`web_id` = "{web_id}"
              AND `tabOligo Link`.`parenttype` = "Sales Order"
            ORDER BY `tabOligo Link`.`creation` DESC;
        """.format(web_id=oligo['web_id']), as_dict=True)
        
        if len(oligos) > 0:
            # get oligo to update the status
            oligo_doc = frappe.get_doc("Oligo", oligos[0]['name'])
            if oligo_doc.status != oligo['status']:
                oligo_doc.status = oligo['status']
                if 'production_id' in oligo:
                    oligo_doc.prod_id = oligo['production_id']
                oligo_doc.save(ignore_permissions=True)
                updated_oligos.append(oligos[0]['name'])
            # append sales order (if available and not in list)
            if oligos[0]['sales_order'] and oligos[0]['sales_order'] not in affected_sales_orders:
                affected_sales_orders.append(oligos[0]['sales_order'])
        else:
            frappe.log_error("Oligo status update: oligo {0} not found.".format(oligo['web_id']), "Production: oligo status update error")
            error_oligos.append(oligo['web_id'])
    frappe.db.commit()
    # check and process sales order (in case all is complete)
    if len(affected_sales_orders) > 0:
        check_sales_order_completion(affected_sales_orders)
    return {
        'success': len(error_oligos) == 0, 
        'message': 'Processed {0} oligos from {1} orders (Errors: {2}))'.format(
            len(updated_oligos), len(affected_sales_orders), ", ".join(map(str, error_oligos))
        )
    }


def get_customer_from_sales_order(sales_order):
    customer_name = frappe.get_value("Sales Order", sales_order, 'customer')
    customer = frappe.get_doc("Customer", customer_name)
    return customer


def check_sales_order_completion(sales_orders):
    """
    Check if all oligos of the provided orders are completed and generate a delivery note.
    
    Run
    bench execute "microsynth.microsynth.production.check_sales_order_completion" --kwargs "{'sales_orders':['SO-BAL-23000058', 'SO-BAL-23000051']}"
    """
    settings = frappe.get_doc("Flushbox Settings", "Flushbox Settings")
    for sales_order in sales_orders:
        #print(f"Processing '{sales_order}' ...")

        if not validate_sales_order(sales_order):
            continue
        
        # get open items
        so_open_items = frappe.db.sql("""
            SELECT 
                `tabOligo Link`.`parent`
            FROM `tabOligo Link`
            LEFT JOIN `tabOligo` ON `tabOligo Link`.`oligo` = `tabOligo`.`name`
            WHERE
                `tabOligo Link`.`parent` = "{sales_order}"
                AND `tabOligo Link`.`parenttype` = "Sales Order"
                AND `tabOligo`.`status` = "Open";
        """.format(sales_order=sales_order), as_dict=True)

        if len(so_open_items) == 0:
            # all items are either complete or cancelled

            ## create delivery note (leave on draft: submitted by flushbox after processing)
            dn_content = make_delivery_note(sales_order)
            dn = frappe.get_doc(dn_content)
            if not dn:
                #print(f"Delivery Note for '{sales_order}' is None.")
                continue
            if not dn.get('oligos'):
                #print(f"Delivery Note for '{sales_order}' has no Oligos.")
                continue
            company = frappe.get_value("Sales Order", sales_order, "company")
            dn.naming_series = get_naming_series("Delivery Note", company)
            # set export code
            dn.export_category = get_export_category(dn.shipping_address_name)

            # remove oligos that are canceled
            cleaned_oligos = []
            cancelled_oligo_item_qtys = {}
            for oligo in dn.oligos:
                oligo_doc = frappe.get_doc("Oligo", oligo.oligo)
                if oligo_doc.status != "Canceled":
                    cleaned_oligos.append(oligo)
                else:
                    # append items
                    for item in oligo_doc.items:
                        if item.item_code in cancelled_oligo_item_qtys:
                            cancelled_oligo_item_qtys[item.item_code] = cancelled_oligo_item_qtys[item.item_code] + item.qty
                        else:
                            cancelled_oligo_item_qtys[item.item_code] = item.qty

            dn.oligos = cleaned_oligos
            # subtract cancelled items from oligo items
            for item in dn.items:
                if item.item_code in cancelled_oligo_item_qtys:
                    item.qty -= cancelled_oligo_item_qtys[item.item_code]
            # remove items with qty == 0
            keep_items = []
            for item in dn.items:
                if item.qty > 0:
                    keep_items.append(item)

            # if there are no items left or only the shipping item, close the order and exit with an error trace.
            if len(keep_items) == 0 or (len(keep_items) == 1 and keep_items[0].item_group == "Shipping"):
                frappe.log_error("No items left in {0}. Cannot create a delivery note.".format(sales_order), "Production: sales order complete")
                close_or_unclose_sales_orders("""["{0}"]""".format(sales_order), "Closed")
                continue

            dn.items = keep_items
            # insert record
            dn.flags.ignore_missing = True
            dn.insert(ignore_permissions=True)
            frappe.db.commit()

            # create PDF for delivery note
            try:
                pdf = frappe.get_print(
                    doctype="Delivery Note", 
                    name=dn.name,
                    print_format=settings.dn_print_format,
                    as_pdf=True
                )
                output = open("{0}/{1}.pdf".format(
                    settings.pdf_path, 
                    dn.web_order_id), 'wb')
                # convert byte array and write to binray file            
                output.write((''.join(chr(i) for i in pdf)).encode('charmap'))
                output.close()
            except Exception as err:
                frappe.log_error( "Error on pdf creation of {0}: {1}".format(dn.name, err),
                    "PDF creation failed (production API)" )
    return


@frappe.whitelist()
def get_orders_for_packaging(destination="CH"):
    """
    Get deliverable units

    Destination: CH, EU, ROW (see Country:Export Code)
    """
    deliveries = frappe.db.sql("""
        SELECT 
            `tabDelivery Note`.`web_order_id` AS `web_order_id`,
            `tabDelivery Note`.`name` AS `delivery_note`, 
            `tabAddress`.`country` AS `country`, 
            `tabCountry`.`export_code` AS `export_code`
        FROM `tabDelivery Note`
        LEFT JOIN `tabAddress` ON `tabAddress`.`name` = `tabDelivery Note`.`shipping_address_name`
        LEFT JOIN `tabCountry` ON `tabCountry`.`name` = `tabAddress`.`country`
        WHERE `tabDelivery Note`.`docstatus` = 0
          AND `tabCountry`.`export_code` LIKE "{export_code}"
          AND `tabDelivery Note`.`product_type` = "Oligos";
    """.format(export_code=destination), as_dict=True)
        
    return {'success': True, 'message': 'OK', 'orders': deliveries}


@frappe.whitelist()
def count_orders_for_packaging(destination="CH"):
    """
    Get number of deliverable units

    Destination: CH, EU, ROW (see Country:Export Code)
    """
    deliveries = get_orders_for_packaging(destination)['orders']

    return {'success': True, 'message': 'OK', 'order_count': len(deliveries)}


@frappe.whitelist()
def get_next_order_for_packaging(destination="CH"):
    """
    Get next order to deliver

    Destination: CH, EU, ROW (see Country:Export Code)
    """
    deliveries = get_orders_for_packaging(destination)['orders']
    
    if len(deliveries) > 0:
        return {'success': True, 'message': 'OK', 'orders': [deliveries[0]] }
    else:
        return {'success': False, 'message': 'Nothing more to deliver'}


@frappe.whitelist()
def oligo_delivery_packaged(delivery_note):
    """
    Mark a delivery as packaged
    """
    if frappe.db.exists("Delivery Note", delivery_note):
        dn = frappe.get_doc("Delivery Note", delivery_note)
        if dn.docstatus > 0:
            return {'success': False, 'message': "Delivery Note already completed"}
        try:
            dn.submit()
            frappe.db.commit()
            return {'success': True, 'message': 'OK'}
        except Exception as err:
            return {'success': False, 'message': err}
    else:
        return {'success': False, 'message': "Delivery Note not found: {0}".format(delivery_note)}


@frappe.whitelist()
def oligo_order_packaged(web_order_id):
    """
    Find Delivery Note and mark it as packaged
    """
    delivery_notes = frappe.db.sql("""
            SELECT 
                `tabDelivery Note`.`name`
            FROM `tabDelivery Note`
            WHERE
                `tabDelivery Note`.`web_order_id` = "{web_order_id}"
            AND `tabDelivery Note`.`docstatus` = 0;
        """.format(web_order_id=web_order_id), as_dict=True)
    
    if len(delivery_notes) == 0:
        return {'success': False, 'message': "Could not find Delivery Note with web_order_id: {0}".format(web_order_id)}
    elif len(delivery_notes) > 1: 
        return {'success': False, 'message': "Multiple Delivery Notes found for web_order_id: {0}".format(web_order_id)}
    else:
        return oligo_delivery_packaged(delivery_notes[0].name)


@frappe.whitelist()
def print_delivery_label(delivery_note):
    """
    Print delivery note address label
    """
    if frappe.db.exists("Delivery Note", delivery_note):
        dn = frappe.get_doc("Delivery Note", delivery_note)
        settings = frappe.get_doc("Flushbox Settings", "Flushbox Settings")
        # render content
        label_content = frappe.render_template("microsynth/templates/labels/oligo_delivery_note_address_label.html", dn.as_dict())
        if settings.label_printer_ip and settings.label_printer_port:
            print_raw(settings.label_printer_ip, settings.label_printer_port, label_content)
        else:
            print(label_content)
            frappe.log_error( "Please define Flusbox Settings: label printer ip/port; cannot print label", "Production:address_label" )
        return {'success': True, 'message': 'OK'}
    else:
        return {'success': False, 'message': "Delivery Note not found"}


def process_internal_order(sales_order):
    from microsynth.microsynth.utils import get_tags
    print("process {0}".format(sales_order))
    sales_order = frappe.get_doc("Sales Order", sales_order)
    
    tags = get_tags("Sales Order", sales_order.name)

    for tag in tags:
        if "invoice" in tag.lower() or "duplicate invoice" in tag.lower():
            print("invoiced")
            return

    if sales_order.hold_invoice or sales_order.hold_order:
        print("hold")
        return

    if sales_order.status == "Closed":
        print("closed")
        return

    check_sales_order_completion( [sales_order.name] )
    oligo_order_packaged(sales_order.web_order_id)
    frappe.db.commit()
    return


def process_internal_oligos(file):
    """
    run
    bench execute microsynth.microsynth.production.process_internal_oligos --kwargs "{'file': '/mnt/erp_share/internal_oligos.txt'}"
    """
    internal_oligos = []

    with open(file) as file:
        header = file.readline()    # skip header line
        for line in file:
            if line.strip() != "":
                elements = line.split("\t")
                oligo = {}
                oligo['web_id'] = elements[1].strip()
                oligo['production_id'] = elements[2].split('.')[0]  # only consider root oligo ID
                oligo['status'] = elements[3].strip()
                internal_oligos.append(oligo) 

    affected_sales_orders = []
    i =0
    for oligo in internal_oligos:
        print("oligo {} ({})".format(oligo['production_id'], oligo['web_id']))

        # find oligo
        oligos = frappe.db.sql("""
            SELECT 
              `tabOligo`.`name`,
              `tabOligo Link`.`parent` AS `sales_order`
            FROM `tabOligo`
            LEFT JOIN `tabOligo Link` ON `tabOligo Link`.`oligo` = `tabOligo`.`name`
            WHERE 
              `tabOligo`.`web_id` = "{web_id}"
              AND `tabOligo Link`.`parenttype` = "Sales Order"
            ORDER BY `tabOligo Link`.`creation` DESC;
        """.format(web_id=oligo['web_id']), as_dict=True)

        if len(oligos) > 0:
            # update oligo
            oligo_doc = frappe.get_doc("Oligo", oligos[0]['name'])
            if oligo_doc.status != oligo['status']:
                oligo_doc.status = oligo['status']
                if 'production_id' in oligo:
                    oligo_doc.prod_id = oligo['production_id']
                oligo_doc.save(ignore_permissions=True)

            process_internal_order(oligos[0]['sales_order'])
        else: 
            continue


def create_delivery_note_for_lost_oligos(sales_orders):
    """
    run
    bench execute microsynth.microsynth.production.draft_delivery_note_for_lost_oligos --kwargs "{'sales_orders':['SO-BAL-23000058', 'SO-BAL-23000051']}"
    """

    settings = frappe.get_doc("Flushbox Settings", "Flushbox Settings")
    for sales_order in sales_orders:
        print(f"Processing '{sales_order}' ...")

        if not validate_sales_order_status(sales_order):
            continue
        
        # get open items
        so_open_items = frappe.db.sql("""
            SELECT 
                `tabOligo Link`.`parent`
            FROM `tabOligo Link`
            LEFT JOIN `tabOligo` ON `tabOligo Link`.`oligo` = `tabOligo`.`name`
            WHERE
                `tabOligo Link`.`parent` = "{sales_order}"
                AND `tabOligo Link`.`parenttype` = "Sales Order"
                AND `tabOligo`.`status` = "Open";
        """.format(sales_order=sales_order), as_dict=True)

        if len(so_open_items) == 0:
            # all items are either complete or cancelled

            ## create delivery note (leave on draft: submitted by flushbox after processing)
            dn_content = make_delivery_note(sales_order)
            dn = frappe.get_doc(dn_content)
            if not dn:
                #print(f"Delivery Note for '{sales_order}' is None.")
                continue
            if not dn.get('oligos'):
                #print(f"Delivery Note for '{sales_order}' has no Oligos.")
                continue
            company = frappe.get_value("Sales Order", sales_order, "company")
            dn.naming_series = get_naming_series("Delivery Note", company)
            # set export code
            dn.export_category = get_export_category(dn.shipping_address_name)

            # remove oligos that are canceled
            cleaned_oligos = []
            cancelled_oligo_item_qtys = {}
            for oligo in dn.oligos:

                #TODO: SQL query to test that the Oligo is not on a Delivery Note

                oligo_doc = frappe.get_doc("Oligo", oligo.oligo)

                # TODO: check that the Oligo is not already on a delivery note (SQL above). Include in condition below
                if oligo_doc.status != "Canceled":
                    cleaned_oligos.append(oligo)
                else:
                    # append items
                    for item in oligo_doc.items:
                        if item.item_code in cancelled_oligo_item_qtys:
                            cancelled_oligo_item_qtys[item.item_code] = cancelled_oligo_item_qtys[item.item_code] + item.qty
                        else:
                            cancelled_oligo_item_qtys[item.item_code] = item.qty

            dn.oligos = cleaned_oligos
            # subtract cancelled items from oligo items
            for item in dn.items:
                if item.item_code in cancelled_oligo_item_qtys:
                    item.qty -= cancelled_oligo_item_qtys[item.item_code]
            # remove items with qty == 0
            keep_items = []
            for item in dn.items:
                if item.qty > 0:
                    keep_items.append(item)

            # TODO: consider not closing the SO
            # if there are no items left or only the shipping item, close the order and exit with an error trace.
            if len(keep_items) == 0 or (len(keep_items) == 1 and keep_items[0].item_group == "Shipping"):
                frappe.log_error("No items left in {0}. Cannot create a delivery note.".format(sales_order), "Production: sales order complete")
                close_or_unclose_sales_orders("""["{0}"]""".format(sales_order), "Closed")
                continue

            dn.items = keep_items
            # TODO Tag the Delivery Note
            # TODO Tag the Sales Order

            # insert record
            dn.flags.ignore_missing = True
            dn.insert(ignore_permissions=True)
            frappe.db.commit()

    return
