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
        {"label": _("Qty"), "fieldname": "qty", "fieldtype": "Float", "precision": "1", "width": 60},
        {"label": _("UOM"), "fieldname": "uom", "fieldtype": "Link", "options": "UOM", "width": 50},
        {"label": "{0} [{1}]".format(_("Reference Rate"), reference_currency), "fieldname": "reference_rate", "fieldtype": "Float", "precision": 2, "width": 150},
        {"label": "{0} [{1}]".format(_("Price List Rate"), price_list_currency), "fieldname": "price_list_rate", "fieldtype": "Float", "precision": 2, "width": 150},
        {"label": _("Discount"), "fieldname": "discount", "fieldtype": "Percent", "precision": 2, "width": 150},
        {"label": _("Record"), "fieldname": "record", "fieldtype": "Link", "options": "Item Price", "width": 100},
        {"label": _(""), "fieldname": "blank", "fieldtype": "Data", "width": 20}
    ]

def get_item_prices(price_list):
    """
    Returns the item prices for a given price list. Fields: 'record', 'item_code', 'item_group', 'uom', 'item_name', 'min_qty', 'rate'
    """
    simple_sql_query = """
        SELECT
            `tabItem Price`.`name` as record,
            `tabItem Price`.`item_code`,
            `tabItem`.`item_group`,
            `tabItem`.`stock_uom` AS `uom`,
            `tabItem Price`.`item_name`,
            `tabItem Price`.`min_qty`,
            `tabItem Price`.`price_list_rate` as rate
        FROM `tabItem Price`        
        JOIN `tabItem` ON `tabItem`.`item_code` = `tabItem Price`.`item_code`
        WHERE `price_list` = "{price_list}"
    """.format(price_list=price_list)
    data = frappe.db.sql(simple_sql_query, as_dict=True)
    return data

def get_data(filters):
    """
    Returns a list of dictionaries with the data to be shown in the table of the pricing configurator.
    """
    if type(filters) == str:
        filters = json.loads(filters)
    elif type(filters) == dict:
        pass
    else:
        filters = dict(filters)
    
    reference_price_list = get_reference_price_list(filters['price_list'])
    # currency = frappe.get_value("Price List", filters['price_list'], "currency")
    
    raw_customer_prices = get_item_prices(filters['price_list'])
    raw_reference_prices = get_item_prices(reference_price_list)
    
    customer_prices = {}
    for p in raw_customer_prices:        
        customer_prices[p.item_code, p.min_qty] = p  
   
    reference_prices = {}
    for p in raw_reference_prices:
        reference_prices[p.item_code, p.min_qty] = p     

    data = []
    for key, reference in sorted(reference_prices.items()):
        
        reference_rate = reference.rate        
        
        if key in customer_prices:
            customer_rate = customer_prices[key].rate
            discount = (reference_rate - customer_rate) / reference_rate * 100 if reference_rate else None
            record = customer_prices[key].record
        else:
            customer_rate = None 
            discount = None
            record = None
            
        entry = { 
            "item_code": reference.item_code,
            "item_name": reference.item_name,
            "item_group": reference.item_group,
            "qty": reference.min_qty,
            "uom": reference.uom,            
            "reference_rate": reference_rate,
            "price_list_rate": customer_rate,
            "discount": discount,
            "record": record }
            
        data.append(entry)

    def filter_by_item_group(entry):
        if 'item_group' in filters:
            return filters['item_group'] == entry['item_group']                
        else:
            return True
        
    filtered_data = [ x for x in data if filter_by_item_group(x) ]
    
    if 'discounts' in filters:
        general_discount = frappe.get_value("Price List", filters['price_list'], "general_discount")        
        return [ x for x in filtered_data if x['discount'] is not None and round(x['discount'],2) != general_discount and x['discount'] != 0 ]
    else:
        return filtered_data
    
def get_data_legacy(filters):
    # fetch accounts
    conditions = ""
    raw_conditions = ""
    #frappe.throw("{0}".format(type(filters)))
    if type(filters) == str:
        filters = json.loads(filters)
    elif type(filters) == dict:
        pass
    else:
        filters = dict(filters)
        
    if 'item_group' in filters:
        conditions += """ AND `item_group` = "{0}" """.format(filters['item_group'])
    if 'discounts' in filters:
        # get general discount 
        general_discount = frappe.get_value("Price List", filters['price_list'], "general_discount")
        raw_conditions += """ WHERE `all`.`discount` !=0 AND `all`.`discount` != "{0}" """.format(general_discount)
        
    reference_price_list = get_reference_price_list(filters['price_list'])
    currency = frappe.get_value("Price List", filters['price_list'], "currency")
    
    sql_query = """
        SELECT
            *
        FROM
        (SELECT
            `item_code`,
            `item_name`,
            `item_group`,
            `qty`,
            `uom`,
            `reference_rate`,
            `price_list_rate`,
            IF(`reference_rate` IS NULL, 0, 100 * (`reference_rate` - `price_list_rate`) / `reference_rate`) AS `discount`,
            "{currency}" AS `currency`,
            `record`
        FROM
        (SELECT 
            `tabItem`.`item_code`,
            `tabItem`.`item_name`,
            `tabItem`.`item_group`,
            `tabItem`.`stock_uom` AS `uom`,
            `tP`.`min_qty` AS `qty`,
            `tP`.`price_list_rate` AS `price_list_rate`,
            (SELECT
                `tPref`.`price_list_rate`
             FROM `tabItem Price` AS `tPref`
             WHERE `tPref`.`item_code` = `tabItem`.`item_code`
               AND `tPref`.`price_list` = "{reference_price_list}"
               AND `tPref`.`min_qty` = `tP`.`min_qty`
               AND (`tPref`.`valid_from` IS NULL OR `tPref`.`valid_from` <= CURDATE())
               AND (`tPref`.`valid_upto` IS NULL OR `tPref`.`valid_upto` >= CURDATE())
             ORDER BY `tPref`.`valid_from` ASC
             LIMIT 1) AS `reference_rate`,
            `tP`.`name` AS `record`
         FROM `tabItem`
         LEFT JOIN `tabItem Price` AS `tP` ON
            `tP`.`item_code` = `tabItem`.`item_code`
            AND `tP`.`price_list` = "{price_list}"
            AND (`tP`.`valid_from` IS NULL OR `tP`.`valid_from` <= CURDATE())
            AND (`tP`.`valid_upto` IS NULL OR `tP`.`valid_upto` >= CURDATE())
         WHERE `tabItem`.`disabled` = 0
           {conditions}
        ) AS `raw`
        ) AS `all`
        {raw_conditions}
        ORDER BY `all`.`item_code` ASC, `all`.`qty` ASC;
    """.format(reference_price_list=reference_price_list, 
        price_list=filters['price_list'], conditions=conditions, raw_conditions=raw_conditions, currency=currency)

    data = frappe.db.sql(sql_query, as_dict=True)   
    return data

def get_reference_price_list(price_list):
    return frappe.get_value("Price List", price_list, "reference_price_list")

def get_rate(item_code, price_list, qty):
    data = frappe.db.sql("""
        SELECT
            IFNULL(`tP`.`price_list_rate`, 0) AS `rate`
         FROM `tabItem Price` AS `tP`
         WHERE `tP`.`item_code` = "{item_code}"
           AND `tP`.`price_list` = "{price_list}"
           AND (`tP`.`valid_from` IS NULL OR `tP`.`valid_from` <= CURDATE())
           AND (`tP`.`valid_upto` IS NULL OR `tP`.`valid_upto` >= CURDATE())
           AND `tP`.`min_qty` <= {qty}
         ORDER BY `tP`.`min_qty` DESC, `tP`.`valid_from` ASC
         LIMIT 1;
        """.format(item_code=item_code, price_list=price_list, qty=qty), as_dict=True)
    # frappe.throw("item: {item}, quantity: {qty}, rate: {rate}".format(item=item_code, qty=qty, rate=data[0]['rate']))
    if len(data) > 0:
        return data[0]['rate']
    else:
        return 0

@frappe.whitelist()
def populate_from_reference(price_list, item_group=None):
    """
    This will fill up the missing rates from the reference
    """
    filters = {
        'price_list': price_list,
    }
    if item_group:
        filters['item_group'] = item_group
    # get base data
    data = get_data(filters)    
    print("Number of data sets: {0}".format(len(data)))
    reference_price_list = get_reference_price_list(filters['price_list'])
    general_discount = frappe.get_value("Price List", price_list, "general_discount")
    # set new prices
    for d in data:
        #frappe.throw("{0} - {1}".format(d['reference_rate'], d['price_list_rate']))
        if d['reference_rate'] and not d['price_list_rate']:
            #frappe.throw("code: {code}, quantity: {qty}".format(code=d['item_code'], qty=d['qty']))
            # create new price
            rate = get_rate(d['item_code'], reference_price_list, d['qty'])
            # frappe.throw("code: {item}, quantity: {qty}, rate: {rate}".format(item = d['item_code'], qty = d['qty'], rate=rate))

            # rate based on general discount for item groups 3.1 & 3.2
            group = frappe.get_value("Item", d['item_code'], "item_group")
            if "3.1 " in group or "3.2" in group:
                rate = ((100 - general_discount) / 100) * rate
            new_rate = frappe.get_doc({
                'doctype': 'Item Price',
                'item_code': d['item_code'],
                'price_list': price_list,
                'price_list_rate': rate,
                'min_qty': d['qty']
            })
            try:
                new_rate.insert()
            except Exception as err:
                # frappe.throw("Cannot insert code {code}, qty {qty}, reference {refrate}, rate {rate} in {price_list}:<br>{error}".format(code=d['item_code'], qty=d['qty'], refrate = d['reference_rate'], rate=rate, price_list = price_list, error = err))
                print("Cannot insert {0} in {1}: {2}".format(d['item_code'], price_list, err))
    frappe.db.commit()

    clean_price_list(price_list=price_list)

    return

@frappe.whitelist()
def populate_with_factor(price_list, item_group=None, factor=1.0):
    """
    This will set all rates from the reference price list with a factor
    """
    filters = {
        'price_list': price_list,
    }
    if item_group:
        filters['item_group'] = item_group
    if type(factor) == str:
        factor = float(factor)
    # get base data
    data = get_data(filters)
    reference_price_list = get_reference_price_list(filters['price_list'])
    # set new prices
    for d in data:
        if d['reference_rate']:
            reference_rate = get_rate(d['item_code'], reference_price_list, d['qty'])
            new_rate = factor * reference_rate
            set_rate(d['item_code'], price_list, d['qty'], new_rate)
    
    clean_price_list(price_list=price_list)
    
    return

@frappe.whitelist()
def set_rate(item_code, price_list, qty, rate):
    """
    This function will set the rate for an item
    """
    existing_item_prices = frappe.get_all("Item Price", 
        filters={
            'item_code': item_code,
            'min_qty': qty,
            'price_list': price_list
        }, 
        fields=['name']
    )
    if len(existing_item_prices) > 0:
        existing_price = frappe.get_doc("Item Price", existing_item_prices[0]['name'])
        existing_price.price_list_rate = rate
        existing_price.save()
    else:
        # create new price
        new_rate = frappe.get_doc({
            'doctype': 'Item Price',
            'item_code': item_code,
            'price_list': price_list,
            'price_list_rate': rate
        })
        new_rate.insert()
    frappe.db.commit()
    return

@frappe.whitelist()
def get_discount_items(price_list):
    """
    Pull all items with discounts for external use (~standing quotation)
    """
    return get_data(filters={'price_list': price_list, 'discounts': 1})

@frappe.whitelist()
def clean_price_list(price_list):
    """
    Corrects rates if there is a lower rate for a smaller quantity.
    """
    print("process '{0}'".format(price_list))
    
    item_prices = get_item_prices(price_list)


    prices = {}
    for p in item_prices:
        prices[p.item_code, p.min_qty] = p

    sorted_prices = sorted(prices.items())

    # initialize memory from first element
    (code_memory, quantity_memory), memory = sorted_prices[0]
    rate_memory = memory.rate

    for key, item_price in sorted_prices:

        if item_price.item_code == memory.item_code: 
        
            if item_price.rate > rate_memory and item_price.min_qty > memory.min_qty:
                set_rate(item_price.item_code, price_list, item_price.min_qty, rate_memory)
                print("Set rate for item {code}, quantity {qty}: {rate} --> {mem_rate}".format(code=item_price.item_code, qty=str(item_price.min_qty).rjust(6), rate=item_price.rate, mem_rate=rate_memory))
            else:                
                rate_memory = item_price.rate
        
        else:
            rate_memory = item_price.rate            
        
        memory = item_price

    return