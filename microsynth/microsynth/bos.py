# -*- coding: utf-8 -*-
# Copyright (c) 2022, libracore (https://www.libracore.com) and contributors
# For license information, please see license.txt
#
# For more details, refer to https://github.com/Microsynth/erp-microsynth/
#


"""
Update the status of a sales order item (cancel, complete)

To cancel: set cancel=1, to complete, set complete=1
"""
@frappe.whitelist(allow_guest=True)
def update_order_item_status(key, web_order_id, oligo_web_id=None, cancel=0, complete=0, client="bos"):
    # check access
    if check_key(key):
        sales_orders = frappe.get_all("Sales Order", 
            fields={'docstatus': 1, 'web_order_id': web_order_id},
            filters=['name']
        )
        if len(sales_orders) > 0:
            so = frappe.get_order("Sales Order", sales_orders[0]['name'])
            # update by oligo code
            if oligo_web_id:
                oligos = frappe.db.sql("""
                    SELECT `name`
                    FROM `tabOligo`
                    WHERE `web_id` = "{web_id}"; """, as_dict=True)
                if len(oligos) > 0:
                    oligo = oligos[0]['name']
                    for i in so.items:
                        if i.oligo == oligo:
                            if complete:
                                i.status = "Complete"
                            elif cancel:
                                i.status = "Cancelled"
                    oligo.save(ignore_permissions=True)
                    frappe.db.commit()
                    # check and process sales order (in case all is complete)
                    check_sales_order_completion(sales_order)
                    return {'success': True, 'message': 'OK'}
                else:
                    return {'success': False, 'message': "Oligo not found"}       
        else:
            return {'success': False, 'message': "Order not found"}
    else:
        return {'success': False, 'message': 'Authentication failed'}

def check_sales_order_completion(sales_order):
    so = frappe.get_doc("Sales Order", sales_order)
    for i in so.items:
        if i.status == "Open":
            # not complete, return
            return
    # all items are either complete or cancelled
    
    ## TODO: create delivery note (leave on draft)
    
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
