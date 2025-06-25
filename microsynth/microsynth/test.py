# Copyright (c) 2022, Microsynth, libracore (https://www.libracore.com) and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
import json



def get_item_prices(price_list):
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

def get_data():
    i = 0
    customer_prices = get_item_prices("Pricelist 36966105")
    reference_prices = get_item_prices("Sales Prices EUR")

    mapped_cust_prices = {}
    for p in customer_prices:
        mapped_cust_prices[p.item_code, p.min_qty] = p
        # i += 1
        # if i > 2:
        #     break

    i = 0
    mapped_ref_prices = {}
    for p in reference_prices:
        mapped_ref_prices[p.item_code, p.min_qty] = p
        # i +=1
        # if i > 10: break


    print("-------------------")

    data = []
    for key in mapped_ref_prices:
        if key in mapped_cust_prices:
            customer_rate = mapped_cust_prices[key].rate
            reference_rate = mapped_ref_prices[key].rate
            discount = (reference_rate - customer_rate) / reference_rate * 100
            record = mapped_cust_prices[key].record
        else:
            customer_rate = None # "no rate :-("
            discount = None
            record = None

        # print(key, cust_rate)
        # print(key, mapped_prices[key].rate, (if key in mapped_ref_prices: mapped_ref_prices[key].rate))



        entry = {
            "item_code": mapped_ref_prices[key].item_code,
            "item_name": mapped_ref_prices[key].item_name,
            "item_group": mapped_ref_prices[key].item_group,
            "qty": mapped_ref_prices[key].min_qty,
            "uom": mapped_ref_prices[key].uom,
            "reference_rate": mapped_ref_prices[key].rate,
            "price_list_rate": customer_rate,
            "discount": discount,
            "record": record }

        data.append(entry)

    def sort_key(d):
        return d["item_code"]



    sorted_data =  sorted(data, key=sort_key, reverse=False)

    for x in sorted_data:
        print(x)

    print("-------------------")
    print(mapped_cust_prices[("3200",1)])

    # return sorted_data
    return 42