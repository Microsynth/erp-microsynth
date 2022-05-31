# Copyright (c) 2022, libracore (https://www.libracore.com) and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
import json

def execute(filters=None):
    columns = get_columns(filters)
    data = get_data(filters)
    return columns, data

def get_columns(filters):
    price_list_currency = frappe.get_value("Price List", filters.price_list, "currency")
    reference_price_list = frappe.get_value("Price List", filters.price_list, "reference_price_list")
    if reference_price_list:
        reference_currency = frappe.get_value("Price List", reference_price_list, "currency")
    else:
        reference_currency = "-" 
    return [
        {"label": _("Item code"), "fieldname": "item_code", "fieldtype": "Link", "options": "Item", "width": 100},
        {"label": _("Item name"), "fieldname": "item_name", "fieldtype": "Data", "width": 120},
        {"label": _("Item Group"), "fieldname": "item_group", "fieldtype": "Link", "options": "Item Group", "width": 120},
        {"label": "{0} [{1}]".format(_("Reference Rate"), reference_currency), "fieldname": "reference_rate", "fieldtype": "Float", "precision": 2, "width": 150},
        {"label": "{0} [{1}]".format(_("Price List Rate"), price_list_currency), "fieldname": "price_list_rate", "fieldtype": "Float", "precision": 2, "width": 150},
        {"label": _("Discount"), "fieldname": "discount", "fieldtype": "Percent", "precision": 2, "width": 150},
        {"label": _(""), "fieldname": "blank", "fieldtype": "Data", "width": 20}
    ]

def get_data(filters):
    # fetch accounts
    conditions = ""
    #frappe.throw("{0}".format(type(filters)))
    if type(filters) == str:
        filters = json.loads(filters)
    elif type(filters) == dict:
        pass
    else:
        filters = dict(filters)
        
    if 'item_group' in filters:
        conditions += """ AND `item_group` = "{0}" """.format(filters['item_group'])

    reference_price_list = get_reference_price_list(filters['price_list'])
    
    sql_query = """
        SELECT
            `item_code`,
            `item_name`,
            `item_group`,
            `reference_rate`,
            `price_list_rate`,
            IF(`reference_rate` IS NULL, 0, 100 * (`reference_rate` - `price_list_rate`) / `reference_rate`) AS `discount`
        FROM
        (SELECT 
            `tabItem`.`item_code`,
            `tabItem`.`item_name`,
            `tabItem`.`item_group`,
            (SELECT
                `tPref`.`price_list_rate`
             FROM `tabItem Price` AS `tPref`
             WHERE `tPref`.`item_code` = `tabItem`.`item_code`
               AND `tPref`.`price_list` = "{reference_price_list}"
               AND (`tPref`.`valid_from` IS NULL OR `tPref`.`valid_from` <= CURDATE())
               AND (`tPref`.`valid_upto` IS NULL OR `tPref`.`valid_upto` >= CURDATE())
             ORDER BY `tPref`.`valid_from` ASC
             LIMIT 1) AS `reference_rate` ,
            (SELECT
                `tP`.`price_list_rate`
             FROM `tabItem Price` AS `tP`
             WHERE `tP`.`item_code` = `tabItem`.`item_code`
               AND `tP`.`price_list` = "{price_list}"
               AND (`tP`.`valid_from` IS NULL OR `tP`.`valid_from` <= CURDATE())
               AND (`tP`.`valid_upto` IS NULL OR `tP`.`valid_upto` >= CURDATE())
             ORDER BY `tP`.`valid_from` ASC
             LIMIT 1) AS `price_list_rate`
         FROM `tabItem`
         WHERE `tabItem`.`disabled` = 0
           {conditions}
         ORDER BY `tabItem`.`item_code` ASC
        ) AS `raw`;
    """.format(reference_price_list=reference_price_list, price_list=filters['price_list'], conditions=conditions)

    data = frappe.db.sql(sql_query, as_dict=True)
    return data

def get_reference_price_list(price_list):
    return frappe.get_value("Price List", price_list, "reference_price_list")

def get_rate(item_code, price_list):
    return frappe.db.sql("""
        SELECT
            IFNULL(`tP`.`price_list_rate`, 0) AS `rate`
         FROM `tabItem Price` AS `tP`
         WHERE `tP`.`item_code` = "{item_code}"
           AND `tP`.`price_list` = "{price_list}"
           AND (`tP`.`valid_from` IS NULL OR `tP`.`valid_from` <= CURDATE())
           AND (`tP`.`valid_upto` IS NULL OR `tP`.`valid_upto` >= CURDATE())
         ORDER BY `tP`.`valid_from` ASC
         LIMIT 1;
        """.format(item_code=item_code, price_list=price_list), as_dict=True)[0]['rate']

@frappe.whitelist()
def populate_from_reference(price_list, item_group=None):
    filters = {
        'price_list': price_list,
    }
    if item_group:
        filters['item_group'] = item_group
    # get base data
    data = get_data(filters)
    reference_price_list = get_reference_price_list(filters['price_list'])
    # set new prices
    for d in data:
        #frappe.throw("{0} - {1}".format(d['reference_rate'], d['price_list_rate']))
        if d['reference_rate'] and not d['price_list_rate']:
            #frappe.throw(d['item_code'])
            # create new price
            new_rate = frappe.get_doc({
                'doctype': 'Item Price',
                'item_code': d['item_code'],
                'price_list': price_list,
                'price_list_rate': get_rate(d['item_code'], reference_price_list)
            })
            new_rate.insert()
    frappe.db.commit()
    return
