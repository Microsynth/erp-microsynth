# Copyright (c) 2024, Microsynth
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
import re
import json
from microsynth.microsynth.seqblatt import set_status


def get_columns(filters):
    return [
        {"label": _("Label Barcode"), "fieldname": "label_id", "fieldtype": "Data", "width": 100 },
        {"label": _("Status"), "fieldname": "status", "fieldtype": "Data", "width": 75 },
        {"label": _("Customer"), "fieldname": "customer", "fieldtype": "Link", "options": "Customer", "width": 75 },
        {"label": _("Customer Name"), "fieldname": "customer_name", "fieldtype": "Data", "width": 175 },
        {"label": _("Contact"), "fieldname": "contact", "fieldtype": "Link", "options": "Contact", "width": 70 },
        {"label": _("Sales Order"), "fieldname": "sales_order", "fieldtype": "Link", "options": "Sales Order", "width": 125 },
        {"label": _("Web Order ID"), "fieldname": "web_order_id", "fieldtype": "Data", "width": 95 },
        {"label": _("Item Code"), "fieldname": "item_code", "fieldtype": "Link", "options": "Item", "width": 75 },
        {"label": _("Registered"), "fieldname": "registered", "fieldtype": "Check", "width": 80 },
        {"label": _("Registered To"), "fieldname": "registered_to", "fieldtype": "Link", "options": "Contact", "width": 100 },
        {"label": _("Sequencing Label"), "fieldname": "name", "fieldtype": "Link", "options": "Sequencing Label", "width": 115 }
    ]


def get_data(filters):
    if not filters:
        return []
    conditions = ""
    
    if filters.get('contact'):
        conditions += f"AND `tabSequencing Label`.`contact` = '{filters.get('contact')}'"
    if filters.get('registered_to'):
        conditions += f"AND `tabSequencing Label`.`registered_to` = '{filters.get('registered_to')}'"
    if filters.get('customer'):
        conditions += f"AND `tabSequencing Label`.`customer` = '{filters.get('customer')}'"
    if filters.get('customer_name'):
        conditions += f"AND `tabSequencing Label`.`customer_name` LIKE '{filters.get('customer_name')}'"
    if filters.get('sales_order'):
        conditions += f"AND `tabSequencing Label`.`sales_order` = '{filters.get('sales_order')}'"
    if filters.get('web_order_id'):
        conditions += f"AND `tabSales Order`.`web_order_id` = '{filters.get('web_order_id')}'"
    if filters.get('item_code'):
        conditions += f"AND `tabSequencing Label`.`item` = '{filters.get('item_code')}'"
    if filters.get('registered'):
        conditions += f"AND `tabSequencing Label`.`registered` = 1"
    if filters.get('from_barcode') and filters.get('to_barcode'):
        if filters.get('from_barcode').isnumeric() and filters.get('to_barcode').isnumeric():
            from_barcode = filters.get('from_barcode')
            to_barcode = filters.get('to_barcode')
            if len(from_barcode) != len(to_barcode):
                frappe.throw("From Barcode and To Barcode need to have the same length. Please use leading zeros if necessary.")
            barcode_list = ','.join(f'"{i:0{len(to_barcode)}d}"' for i in range(int(from_barcode), int(to_barcode) + 1))
            conditions += f"AND `tabSequencing Label`.`label_id` IN ({barcode_list})"
            #conditions += f"AND `tabSequencing Label`.`label_id` BETWEEN '{filters.get('from_barcode')}' AND '{filters.get('to_barcode')}'"  # leads to false positive search results
        else:
            from_prefix = ''.join([i for i in filters.get('from_barcode') if not i.isdigit()])
            to_prefix = ''.join([i for i in filters.get('to_barcode') if not i.isdigit()])
            if from_prefix != to_prefix:
                frappe.throw("From Barcode and To Barcode need to have the same Prefix.")
            from_barcode = re.sub("[^0-9]", "", filters.get('from_barcode'))
            to_barcode = re.sub("[^0-9]", "", filters.get('to_barcode'))
            if len(from_barcode) != len(to_barcode):
                frappe.throw("From Barcode and To Barcode need to have the same length.")
            barcode_list = ','.join(f'"{to_prefix}{i:0{len(to_barcode)}d}"' for i in range(int(from_barcode), int(to_barcode) + 1))
            conditions += f"AND `tabSequencing Label`.`label_id` IN ({barcode_list})"
    elif (filters.get('from_barcode') or filters.get('to_barcode')) and not conditions:
    #    frappe.throw( _("For using from and to barcode, please set both filters.") )
        return []
    elif filters.get('from_barcode') or filters.get('to_barcode'):
    #    frappe.msgprint( _("From and to barcode are both required, this filter is being ignored.") )
        return []
    
    sql_query = f"""
        SELECT
            `tabSequencing Label`.`name`,
            `tabSequencing Label`.`status`,
            `tabSequencing Label`.`registered`,
            `tabSequencing Label`.`label_id`,
            `tabSequencing Label`.`item` AS `item_code`,
            `tabSequencing Label`.`customer`,
            `tabSequencing Label`.`customer_name`,
            `tabSequencing Label`.`sales_order`,
            `tabSales Order`.`web_order_id`,
            `tabSequencing Label`.`contact`,
            `tabSequencing Label`.`registered_to`
        FROM `tabSequencing Label`
        LEFT JOIN `tabSales Order` ON `tabSales Order`.`name` = `tabSequencing Label`.`sales_order`
        WHERE TRUE
            {conditions}
        ORDER BY `tabSequencing Label`.`label_id`;
        """
    data = frappe.db.sql(sql_query, as_dict=True)
    return data


def execute(filters):
    columns, data = get_columns(filters), get_data(filters)
    return columns, data


def create_label_log(from_status, to_status, reason, description, content_str, filters):
    label_log_doc = frappe.get_doc({
        'doctype': 'Label Log',
        'user': frappe.session.user,
        'from_status': from_status,
        'to_status': to_status,
        'reason': reason,
        'description': description,
        'labels': content_str
    })
    label_log_doc.insert()
    label_log_doc.update(filters)
    # add Web Order ID from Sales Order if missing
    if filters.get('sales_order') and not filters.get('web_order_id'):
        label_log_doc.web_order_id = frappe.get_value("Sales Order", filters.get('sales_order'), 'web_order_id')
    # add Customer from Sales Order if missing
    if filters.get('sales_order') and not filters.get('customer'):
        label_log_doc.customer = frappe.get_value("Sales Order", filters.get('sales_order'), 'customer')
    # add Customer Name from Sales Order if missing
    if filters.get('sales_order') and not filters.get('customer_name'):
        label_log_doc.customer_name = frappe.get_value("Sales Order", filters.get('sales_order'), 'customer_name')
    # add Item Code if missing
    if not filters.get('item_code') and content_str:
        content = json.loads(content_str)
        labels = content.get('labels')
        item_codes = set()
        for l in labels:
            item_codes.add(l.get('item_code'))
        if len(item_codes) == 1:
            [item_code] = item_codes  # tuple unpacking verifies the assumption that the set contains exactly one element (raising ValueError if it has too many or too few elements)
            label_log_doc.item_code = item_code
    label_log_doc.save()
    frappe.db.commit()


@frappe.whitelist()
def lock_labels(content_str, filters, reason, description):
    """
    Set label status to 'locked'. Labels must be a list of dictionaries 
    (see `set_status` function).
    If locking was successfull, create a Label Log.
    """
    if type(content_str) == str:
        content = json.loads(content_str)
    else:
        content = content_str
    if type(filters) == str:
        filters = json.loads(filters)
    response = set_status("locked", content.get("labels"))
    if response['success']:
        create_label_log('unused', 'locked', reason, description, content_str, filters)
    return response


@frappe.whitelist()
def set_labels_unused(content_str, filters, reason, description):
    """
    Set label status to 'unused'. Labels must be a list of dictionaries 
    (see `set_status` function).
    If setting to unused was successfull, create a Label Log.
    """
    if type(content_str) == str:
        content = json.loads(content_str)
    else:
        content = content_str
    if type(filters) == str:
        filters = json.loads(filters)
    response = set_status("unused", content.get("labels"))
    if response['success']:
        create_label_log('locked', 'unused', reason, description, content_str, filters)
    return response
