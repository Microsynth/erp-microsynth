# Copyright (c) 2022, libracore (https://www.libracore.com) and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
from datetime import datetime, timedelta
import json
import csv


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
        {"label": _("Item code"), "fieldname": "item_code", "fieldtype": "Link", "options": "Item", "width": 350},
        {"label": _("Item name"), "fieldname": "item_name", "fieldtype": "Data", "width": 250},
        {"label": _("Item Group"), "fieldname": "item_group", "fieldtype": "Link", "options": "Item Group", "width": 150},
        {"label": _("Qty"), "fieldname": "qty", "fieldtype": "Float", "precision": "1", "width": 60},
        {"label": _("UOM"), "fieldname": "uom", "fieldtype": "Link", "options": "UOM", "width": 50},
        {"label": "{0} [{1}]".format(_("Reference Rate"), reference_currency), "fieldname": "reference_rate", "fieldtype": "Float", "precision": 2, "width": 140},
        {"label": "{0} [{1}]".format(_("Price List Rate"), price_list_currency), "fieldname": "price_list_rate", "fieldtype": "Float", "precision": 2, "width": 140},
        {"label": _("Discount"), "fieldname": "discount", "fieldtype": "Percent", "precision": 2, "width": 75},
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
    # key is a tuple of item_code and min_qty.
    # reference is the item price from the reference.
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


def get_price_list_rates(item_code, price_list, qty):
    """
    Only called by get_rate and get_rate_or_none to avoid too much code duplication.
    Returns a dictionary of price list rates sorted ascending by minimum quantity.
    """
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
    return data


def get_rate(item_code, price_list, qty):
    data = get_price_list_rates(item_code, price_list, qty)
    if len(data) > 0:
        return data[0]['rate']
    else:
        return 0


def get_rate_or_none(item_code, price_list, qty):
    """
    Return the rate for the given combination of item code and quantity on the given price list
    or None if the given item code is not on the price list or the smallest minimum quantity is not reached.
    """
    data = get_price_list_rates(item_code, price_list, qty)
    if len(data) > 0:
        return data[0]['rate']
    else:
        return None


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
            'min_qty': qty,
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


@frappe.whitelist()
def change_general_discount(price_list_name, new_general_discount, user):
    """
    Calculate new item price with the new general discount in relation to the item price of the reference price list
    if calculated discount of the item price in relation to the item price of the reference price list = old general discount of price list.
    Save the new general discount on the price list.
    """
    warnings = ""
    try:
        new_general_discount = float(new_general_discount)
    except ValueError:
        frappe.throw(f"Cannot convert '{new_general_discount}' to a float. No changes are made. Going to return.")
        return  # should not be necessary after throw but just for safety
    
    if not frappe.get_value("Price List", price_list_name, "enabled"):
        frappe.throw(f"Unable to change Item Prices since Price List '{price_list_name}' is disabled. No changes are made. Going to return.")
        return

    reference_price_list = get_reference_price_list(price_list_name)
    if not reference_price_list:
        frappe.throw(f"No reference_price_list for '{price_list_name=}'. No changes are made. Going to return.")
        return

    old_general_discount = frappe.get_value("Price List", price_list_name, "general_discount")
    if not old_general_discount:
        frappe.throw(f"Price List '{price_list_name}' has no general discount. No changes are made. Going to return.")
        return
    
    price_list = frappe.get_doc("Price List", price_list_name)
    if not price_list:
        frappe.throw(f"No Price List '{price_list_name}' found. No changes are made. Going to return.")
        return

    customer_item_prices = get_item_prices(price_list_name)
    if not customer_item_prices:
        frappe.throw(f"Price List '{price_list_name}' has no Item Prices. No changes are made. Going to return.")
        return
    
    # dry run
    for item_price in customer_item_prices:
        group = frappe.get_value("Item", item_price.item_code, "item_group")
        if not group:
            # Should never happen since Item.item_group is a mandatory field
            continue
        # The general discount applies only to items of the item group 3.1 and 3.2
        if not ("3.1" in group or "3.2" in group):
            continue

        reference_rate = get_rate_or_none(item_price.item_code, reference_price_list, item_price.min_qty)
        customer_rate = get_rate_or_none(item_price.item_code, price_list_name, item_price.min_qty)
        if reference_rate is None:
            warnings += f"Item {item_price['item_code']}: {item_price['item_name']} with minimum quantity {item_price['min_qty']} is not on the Reference Price List '{reference_price_list}'.<br>"
            continue
        if reference_rate < 0:
            frappe.throw(f"{reference_rate=} < 0 for Item Code {item_price.item_code}. {item_price=} will left unchanged. No changes are made. Going to return.")
            return
        if customer_rate is None:
            frappe.throw(f"customer_rate is None. {item_price=} will left unchanged. No changes are made. Going to return.")
            return

        if item_price.item_code is None:
            frappe.throw(f"item_price.item_code is None. {item_price=} will left unchanged. No changes are made. Going to return.")
            return
        if reference_price_list is None:
            frappe.throw(f"reference_price_list is None. {item_price=} will left unchanged. No changes are made. Going to return.")
            return
        if item_price.min_qty is None:
            frappe.throw(f"item_price.min_qty is None. {item_price=} will left unchanged. No changes are made. Going to return.")
            return

    changes = "item_code;min_qty;old_rate;new_rate"

    for item_price in customer_item_prices:
        group = frappe.get_value("Item", item_price.item_code, "item_group")
        # The general discount applies only to items of the item group 3.1 and 3.2
        if not ("3.1" in group or "3.2" in group):
            continue

        reference_rate = get_rate_or_none(item_price.item_code, reference_price_list, item_price.min_qty)
        customer_rate = get_rate_or_none(item_price.item_code, price_list_name, item_price.min_qty)

        if reference_rate is None:
            continue  # already logged to the variable 'warnings' in the dry run above
        if abs(reference_rate) < 0.0001:  # is possible and happens
            continue  # nothing to do and cannot divide by zero to calculate discount
        if reference_rate <= -0.0001:
            frappe.log_error(f"negative reference rate {reference_rate} for {item_price=}", "pricing_configurator.change_general_discount")
            continue

        calculated_discount = (reference_rate - customer_rate) / reference_rate * 100

        # Calculate a discount tolerance depending on customer and reference rate since rounding the rate
        # to two decimal places can make a difference of several percentage points for small rates
        min_discount_tolerance = 0.2  # Make it user input?
        max_discount_tolerance = 2
        if customer_rate > 0.0001:  # avoid dividing by zero
            discount_tolerance = min(
                    max(
                        1/customer_rate, 
                        1/reference_rate, 
                        min_discount_tolerance),
                    max_discount_tolerance)
        else:  # customer_rate <= 0.0001 is possible and happens
            discount_tolerance = min(
                    max(
                        1/reference_rate,
                        min_discount_tolerance),
                    max_discount_tolerance)

        if abs(old_general_discount - calculated_discount) <= discount_tolerance:
            new_customer_rate = ((100 - new_general_discount) / 100) * reference_rate
            set_rate(item_price.item_code, price_list_name, item_price.min_qty, new_customer_rate)
            changes += f"\n{item_price.item_code};{item_price.min_qty};{customer_rate};{new_customer_rate}"

    # set new general discount
    price_list.general_discount = new_general_discount
    price_list.save()
    if warnings:
        warnings_replaced = warnings.replace('<br>', '\n')
        changes += f"\n\nThe discount could not be changed for the following items:\n{warnings_replaced}"
    changes += f"\n\nThe General Discount was changed from {old_general_discount} to {new_general_discount} for Price List '{price_list_name}' by {user}."
    # log changes by creating a new Item Price Log
    item_price_log = frappe.get_doc({
        'doctype': 'Item Price Log',
        'price_list': price_list_name,
        'user': user,
        'changes': changes
    })
    item_price_log.insert()
    return warnings


def populate_price_lists():
    """
    Go through all price lists and populate missing prices

    Run from bench like
    bench execute microsynth.microsynth.report.pricing_configurator.pricing_configurator.populate_price_lists
    """
    price_lists = frappe.db.sql("""
        SELECT `name`
        FROM `tabPrice List`
        WHERE `reference_price_list` IS NOT NULL
        AND `enabled` = 1;""", as_dict=True)
    count = 0
    start_ts = None
    for p in price_lists:
        count += 1
        start_ts = datetime.now()
        print("Updating {0}... ({1}%)".format(p['name'], int(100 * count / len(price_lists))))
        populate_from_reference(price_list=p['name'])
        print("... {0} sec".format((datetime.now() - start_ts).total_seconds()))
    return


def clean_price_lists():
    """
    Go through all price lists and clean up conflicting prices

    Run from bench like
    bench execute microsynth.microsynth.report.pricing_configurator.pricing_configurator.clean_price_lists
    """
    from microsynth.microsynth.report.pricing_configurator.pricing_configurator import clean_price_list

    price_lists = frappe.db.sql("""
        SELECT `name`
        FROM `tabPrice List`
        WHERE `reference_price_list` IS NOT NULL;""", as_dict=True)
    count = 0
    start_ts = None
    for p in price_lists:
        count += 1
        start_ts = datetime.now()
        print("Updating {0}... ({1}%)".format(p['name'], int(100 * count / len(price_lists))))
        clean_price_list(price_list=p['name'])
        print("... {0} sec".format((datetime.now() - start_ts).total_seconds()))
    return


@frappe.whitelist()
def change_reference_rate(reference_price_list_name, item_code, min_qty, reference_rate, new_reference_rate, user):
    """
    Change the rate (price) of the given combination of Item Code and minimum quantity
    on each customer price list referring to the given reference price list.
    Thereby, the existing discounts are kept and the new rate is calculated
    by applying this calculated discount to the new reference rate.
    """
    start_ts = datetime.now()
    negative_discount_warnings = ""
    try:
        reference_rate = float(reference_rate)
        new_reference_rate = float(new_reference_rate)
    except ValueError:
        msg = f"Cannot convert '{reference_rate}' or '{new_reference_rate}' to a float. Going to return."
        print(msg)
        frappe.log_error(msg, "pricing_configurator.change_reference_rate")
        return negative_discount_warnings

    current_reference_rate = get_rate_or_none(item_code, reference_price_list_name, min_qty)
    if current_reference_rate is None:
        msg = f"No reference rate found for {item_code=}, {reference_price_list_name=}, {min_qty=}. Going to return."
        print(msg)
        frappe.log_error(msg, "pricing_configurator.change_reference_rate")
        return negative_discount_warnings

    if abs(reference_rate - new_reference_rate) < 0.0001:
        #print(f"{reference_rate=} == {new_reference_rate=} -> nothing to do. Going to return.")
        return negative_discount_warnings

    if abs(current_reference_rate - reference_rate) > 0.0001:
        msg = f"{current_reference_rate=} in the ERP is unequals given {reference_rate=}. Going to return."
        print(msg)
        frappe.log_error(msg, "pricing_configurator.change_reference_rate")
        return negative_discount_warnings
    
    if frappe.get_value('Item', item_code, 'disabled'):
        msg = f"Item {item_code} is disabled. Unable to change Item Prices. Going to return."
        print(msg)
        frappe.log_error(msg, "pricing_configurator.change_reference_rate")
        return negative_discount_warnings
     
    changes = "pricelist;old_rate;new_rate"
    counter = 0
    
    sql_query = """
        SELECT `name`
        FROM `tabPrice List`
        WHERE `reference_price_list` = '{reference_price_list_name}'
        AND `enabled` = 1
        ;""".format(reference_price_list_name=reference_price_list_name)
    
    price_lists = frappe.db.sql(sql_query, as_dict=True)

    for price_list in price_lists:
        customer_rate = get_rate_or_none(item_code, price_list['name'], min_qty)
        if customer_rate is None:
            # The combination of item_code and min_qty is not on the customer Price List. Happens.
            # Do not add the combination of item_code and min_qty to the customer Price List.
            continue

        if abs(reference_rate) < 0.0001:  # reference_rate is too close to 0 to calculate the discount (division by 0 issue) -> set Customer Price List rate to 0
            #msg = f"Unable to change customer Price List rate for item {item_code} with {min_qty=} on Price List '{price_list['name']}' since {reference_rate=} is too close to 0 to divide by it for computing the current discount"
            #msg = f"WARNING: {reference_rate=} -> Customer Price List rate is set to 0"
            #frappe.log_error(msg, 'pricing_configurator.change_reference_rate')
            set_rate(item_code, price_list['name'], min_qty, 0)
            counter += 1
            continue

        discount = (reference_rate - customer_rate) / reference_rate * 100

        if discount < 0:
            # "customer_price_list;reference_price_list;item_code;min_qty;customer_rate;reference_rate;discount"
            negative_discount_warnings += f"{price_list['name']};{reference_price_list_name};{item_code};{min_qty};{customer_rate};{reference_rate};{round(discount, 2)}\n"
            #msg = f"WARNING: {discount=} < 0 for item {item_code} with {min_qty=} on Price List '{price_list['name']}' -> new Customer Price List rate will be higher than reference Price List rate"
            #frappe.log_error(msg, 'pricing_configurator.change_reference_rate')
            discount = 0

        new_customer_rate = ((100 - discount) / 100) * new_reference_rate
        try:
            set_rate(item_code, price_list['name'], min_qty, new_customer_rate)
        except Exception as e:
            msg = f"Got the following exception when trying to save the new customer rate {new_customer_rate} for item {item_code} with minimum quantity {min_qty} on Price List '{price_list['name']}':\n{e}"
            print(msg)
            frappe.log_error(msg, 'pricing_configurator.change_reference_rate')
        else:
            changes += f"\n{price_list['name']};{customer_rate};{new_customer_rate}"
            counter += 1

    # set the new reference rate on the reference price list
    set_rate(item_code, reference_price_list_name, min_qty, new_reference_rate)
    # log changes by creating a new Item Price Log
    end_ts = datetime.now()
    changes += f"\n\nChanged {counter}/{len(price_lists)} Price Lists referring to '{reference_price_list_name}' in {round((end_ts - start_ts).total_seconds(), 2)} seconds. If not all Price Lists are changed, the combination of item_code and min_qty was not on the customer Price List or see the Error Log in the ERP for all others."
    max_length = 65_000  # 65_500 is too large
    if len(changes) > max_length:
        msg = f"{len(changes)=} -> string is going to be truncated to {max_length} characters. Please revise architecture. ({user=}; {price_list['name']=}; {reference_price_list_name=}; {item_code=}; {min_qty=}; {customer_rate=}; {reference_rate=};)"
        print(msg)
        frappe.log_error(msg, 'pricing_configurator.change_reference_rate')
    item_price_log = frappe.get_doc({
        'doctype': 'Item Price Log',
        'price_list': reference_price_list_name,
        'item_code': item_code,
        'min_qty': min_qty,
        'original_rate': reference_rate,
        'new_rate': new_reference_rate,
        'user': user,
        'changes': changes[:max_length]
    })
    item_price_log.insert()
    return negative_discount_warnings


def change_rates_from_csv(csv_file, user):
    """
    Change the reference rate and all dependent customer rates for all entries in the given CSV file
    using the function change_reference_rate.
    IMPORTANT: It is expected that the CSV file has a header and exactly the following columns in this order:
    Reference Price List Name, Item Code, Item Name, Minimum Qty, Current Rate, New Rate
    Outputs a CSV file with warnings about negative discounts to the given csv_file path appended by _warnings.csv

    run from bench
    bench execute microsynth.microsynth.report.pricing_configurator.pricing_configurator.change_rates_from_csv --kwargs "{'csv_file': '/mnt/erp_share/JPe/testprices.csv', 'user': 'firstname.lastname@microsynth.ch'}"
    """
    start_ts = datetime.now()
    # Dry run only to check the CSV file (no changes)
    with open(csv_file, 'r') as file:
        print(f"Checking {csv_file} ...")
        csv_reader = csv.reader(file, delimiter=';')
        next(csv_reader)  # skip header
        no_lines = 0
        for line in csv_reader:
            if len(line) != 6:
                print(f"Expected line length 6 but was {len(line)} for the following line:\n{line}\n"
                      f"No Prices are changed. Please correct CSV file and restart. Going to return.")
                return
            if line[0] not in ('Sales Prices CHF', 'Sales Prices EUR', 'Sales Prices SEK', 'Sales Prices USD'):
                print(f"Got unknown reference price list '{line[0]}'. No Prices are changed. "
                      f"Please correct CSV file or add '{line[0]}' here in the code and restart. Going to return.")
                return
            try:
                min_qty = int(line[3])
                reference_rate = float(line[4])
                new_reference_rate = float(line[5])
            except Exception as error:
                print(f"The following exception occurred during type conversion of min_qty, reference_rate or new_reference_rate:\n{error}\n"
                      f"No Prices are changed. Please correct CSV file and restart. Going to return.")
                return
            no_lines += 1

    # header for a CSV file collecting warnings about negative discounts
    negative_discount_warnings = "customer_price_list;reference_price_list;item_code;min_qty;customer_rate;reference_rate;discount\n"

    with open(csv_file, 'r') as file:
        print(f"Changing prices according to {csv_file} ...")
        csv_reader = csv.reader(file, delimiter=';')
        next(csv_reader)  # skip header
        line_counter = 0
        for line in csv_reader:
            reference_price_list_name = line[0]
            item_code = line[1]  # keep as string since leading zeros are removed when converting it to an integer
            # line[2] is Item name and only for human readability
            min_qty = int(line[3])
            reference_rate = float(line[4])
            new_reference_rate = float(line[5])
            warnings = change_reference_rate(reference_price_list_name, item_code, min_qty, reference_rate, new_reference_rate, user)
            negative_discount_warnings += warnings
            line_counter += 1
            print(f"Finished line {line_counter}/{no_lines}: {line}")
    
    with open(csv_file + '_warnings.csv', 'w') as warnings_file:
        warnings_file.write(negative_discount_warnings)
    
    elapsed_time = timedelta(seconds=(datetime.now() - start_ts).total_seconds())
    print(f"Finished after {elapsed_time} hh:mm:ss.")


def change_rates_from_csv_files(user):
    """
    Wrapper to call function change_rates_from_csv with multiple csv files.
    Don't forget to change the hard coded file path if necessary.

    run from bench
    bench execute microsynth.microsynth.report.pricing_configurator.pricing_configurator.change_rates_from_csv_files --kwargs "{'user': 'firstname.lastname@microsynth.ch'}"
    """
    for currency in ['sek', 'usd', 'eur', 'chf']:
        print(f"\n########## Start with {currency} ...")
        change_rates_from_csv(f"/mnt/erp_share/JPe/{currency}.csv", user)


@frappe.whitelist()
def async_change_reference_rate(reference_price_list_name, item_code, min_qty, reference_rate, new_reference_rate, user):
    """
    Wrapper to call function change_reference_rate with a timeout > 120 seconds (here 360 seconds = 6 minutes).
    """        
    frappe.enqueue(method=change_reference_rate, queue='long', timeout=360, is_async=True, job_name='change_reference_rate',
                   reference_price_list_name=reference_price_list_name,
                   item_code=item_code,
                   min_qty=min_qty,
                   reference_rate=reference_rate,
                   new_reference_rate=new_reference_rate,
                   user=user)
