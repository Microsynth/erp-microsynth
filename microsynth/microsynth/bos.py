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
            fields={'docstatus': 1, 'web_order_id': web_order_id}
            fields=['name']
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
                    return {'success': True, 'message': 'OK'}
                else:
                    return {'success': False, 'message': "Oligo not found"}       
        else:
            return {'success': False, 'message': "Order not found"}
    else:
        return {'success': False, 'message': 'Authentication failed'}
