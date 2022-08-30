# -*- coding: utf-8 -*-
# Copyright (c) 2022, libracore (https://www.libracore.com) and contributors
# For license information, please see license.txt
#
# For more details, refer to https://github.com/Microsynth/erp-microsynth/
#

from erpnext.selling.doctype.sales_order.sales_order import make_delivery_note

"""
Update the status of a sales order item (cancel, complete)

To cancel: set cancel=1, to complete, set complete=1
"""
@frappe.whitelist(allow_guest=True)
def oligo_status_changed(key, content, client="bos"):
    # check access
    if check_key(key):
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
                    oligo_doc.save(ignore_permission=True)
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
    else:
        return {'success': False, 'message': 'Authentication failed'}

def check_sales_order_completion(sales_orders):
    for sales_order in sales_orders:
        so_open_items = frappe.db.sql("""
            SELECT 
                `tabOligo Link`.`parent`
            FROM `tabOligo Link`
            LEFT JOIN `tabOligo` ON `tabOligo Link`.`oligo` = `tabOligo`.`name`
            WHERE
                `tabOligo Link.`parent` = "{sales_order}"
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
                        if i['item_code'] in cancelled_oligo_item_qtys:
                            cancelled_oligo_item_qtys[i['item_code']] = cancelled_oligo_item_qtys[i['item_code']] + i['qty']
                        else:
                            cancelled_oligo_item_qtys[i['item_code']] = i['qty']
                    
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
            dn.insert(ignore_permission=True)
            frappe.db.commit()
            
            ## TODO: create PDF for delivery note and address label
            
    return

"""
Get deliverable units

Export codes: CH, EU, ROW
"""
@frappe.whitelist(allow_guest=True)
def get_deliverable_units(key, export_code="CH", client="bos"):
    # check access
    if check_key(key):
        deliveries = frappe.db.sql("""
            SELECT 
                `tabDelivery Note`.`name`, 
                `tabAddress`.`country`, 
                `tabCountry`.`export_code`
            FROM `tabDelivery Note`
            LEFT JOIN `tabAddress` ON `tabAddress`.`name` = `tabDelivery Note`.`shipping_address_name`
            LEFT JOIN `tabCountry` ON `tabCountry`.`name` = `tabAddress`.`country`
            WHERE `tabDelivery note`.`docstatus` == 0
              AND `tabCountry`.`export_code` = "{export_code}";""".format(export_code=export_code), as_dict=True)
            
        return {'success': True, 'message': 'OK', 'deliveries': deliveries}
    else:
        return {'success': False, 'message': 'Authentication failed'}

"""
Mark a delivery as packaged
"""
@frappe.whitelist(allow_guest=True)
def deliver_unit(key, delivery_note, client="bos"):
    # check access
    if check_key(key):
        dn = frappe.get_doc("Delivery note", delivery_note)
        try:
            dn.submit()
            return {'success': True, 'message': 'OK'}
        except Exception as err:
            return {'success': False, 'message': err}
    else:
        return {'success': False, 'message': 'Authentication failed'}
