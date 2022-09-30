# -*- coding: utf-8 -*-
# Copyright (c) 2022, libracore (https://www.libracore.com) and contributors
# For license information, please see license.txt
#
# For more details, refer to https://github.com/Microsynth/erp-microsynth/
#

from erpnext.selling.doctype.sales_order.sales_order import make_delivery_note
import frappe
from microsynth.microsynth.labels import print_raw

"""
Update the status of a sales order item (Canceled, Completed)
"""
@frappe.whitelist()
def oligo_status_changed(content):
    # check mandatory
    if not 'oligos' in content:
        return {'success': False, 'message': "Please provide oligos", 'reference': None}
    
    # go through oligos and update status
    affected_sales_orders = []
    updated_oligos = []
    error_oligos = []
    for oligo in content['oligos']:
        if not 'oligo_web_id' in oligo:
            return {'success': False, 'message': "Oligos need to have a oligo_web_id", 'reference': None}
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
              AND `tabOligo Link`.`parenttype` = "Sales Order";
        """.format(web_id=oligo['oligo_web_id']), as_dict=True)
        
        if len(oligos) > 0:
            # get sales order
            oligo_doc = frappe.get_doc("Oligo", oligos[0]['name'])
            if oligo_doc.status != oligo['status']:
                oligo_doc.status = oligo['status']
                if 'production_id' in content:
                    oligo_doc.prod_id = oligo['production_id']
                oligo_doc.save(ignore_permissions=True)
                updated_oligos.append(oligos[0]['name'])
            # append sales order (if available and not in list)
            if oligos[0]['sales_order'] and oligos[0]['sales_order'] not in affected_sales_orders:
                affected_sales_orders.append(oligos[0]['sales_order'])
        else:
            frappe.log_error("Oligo status update: oligo {0} not found.".format(oligo['oligo_web_id']), "Production: oligo status update error")
            error_oligos.append(oligo['oligo_web_id'])
    frappe.db.commit()
    # check and process sales order (in case all is complete)
    if len(affected_sales_orders) > 0:
        check_sales_order_completion(affected_sales_orders)
    return {
        'success': True, 
        'message': 'Processed {0} oligos from {1} orders (Errors: {2}))'.format(
            len(updated_oligos), len(affected_sales_orders), ", ".join(error_oligos)
        )
    }

def check_sales_order_completion(sales_orders):
    settings = frappe.get_doc("Flushbox Settings", "Flushbox Settings")
    for sales_order in sales_orders:
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
            dn.items = keep_items
            # insert record
            dn.flags.ignore_missing = True
            dn.insert(ignore_permissions=True)
            frappe.db.commit()
            
            # create PDF for delivery note
            pdf = frappe.get_print(
                doctype="Delivery Note", 
                name=dn.name,
                print_format=settings.dn_print_format,
                as_pdf=True
            )
            output = open("{0}{1}.pdf".format(
                settings.pdf_path, 
                dn.name), 'wb')
            # convert byte array and write to binray file
            output.write((''.join(chr(i) for i in pdf)).encode('charmap'))
            output.close()
    return

"""
Get deliverable units

Destination: CH, EU, ROW (see Country:Export Code)
"""
@frappe.whitelist()
def get_orders_for_packaging(destination="CH"):
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

"""
Get number of deliverable units

Destination: CH, EU, ROW (see Country:Export Code)
"""
@frappe.whitelist()
def count_orders_for_packaging(destination="CH"):
    deliveries = get_orders_for_packaging(destination)['orders']
        
    return {'success': True, 'message': 'OK', 'order_count': len(deliveries)}

"""
Get next order to deliver

Destination: CH, EU, ROW (see Country:Export Code)
"""
@frappe.whitelist()
def get_next_order_for_packaging(destination="CH"):
    deliveries = get_orders_for_packaging(destination)['orders']
    
    if len(deliveries) > 0:
        return {'success': True, 'message': 'OK', 'orders': [deliveries[0]] }
    else:
        return {'success': False, 'message': 'Nothing more to deliver'}
        
"""
Mark a delivery as packaged
"""
@frappe.whitelist()
def oligo_order_packaged(delivery_note):
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
        return {'success': False, 'message': "Delivery Note not found"}

"""
Print delivery note address label
"""
@frappe.whitelist()
def print_delivery_label(delivery_note):
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


