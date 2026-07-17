# -*- coding: utf-8 -*-
# Copyright (c) 2025, libracore (https://www.libracore.com), Microsynth and contributors
# For license information, please see license.txt

import datetime
import json
import frappe
from frappe.utils import rounded


def find_op_deviation_date(start_date, account, company):
    """
    bench execute microsynth.microsynth.troubleshooting.find_op_deviation_date --kwargs "{'company': '', 'account': '', 'start_date': '2025-01-01'}"
    """
    from microsynth.microsynth.report.accounts_receivable_microsynth.accounts_receivable_microsynth import execute

    filters = frappe._dict({
        'company': company,
        'account': account,
        'ageing_based_on': "Posting Date",
        'report_date': start_date,
        'range1': 30,
        'range2': 60,
        'range3': 90,
        'range4': 120
    })

    if type(start_date) == str:
        start_date = datetime.datetime.strptime(start_date, "%Y-%m-%d")

    print(f"Date\tOP\tGL")
    while start_date.date() <= datetime.datetime.today().date():
        filters.report_date = start_date.strftime("%Y-%m-%d")
        _, op_data = execute(filters)
        gl_balance = get_foreign_currency_balance(account, filters.report_date)

        op_foreign_currency = op_data[-1]['doc_outstanding']
        print(f"{filters.report_date}\t{op_foreign_currency}\t{gl_balance}")
        if rounded(op_foreign_currency, 2) != rounded(gl_balance, 2):
            break
        start_date += datetime.timedelta(days=1)

    return


def get_foreign_currency_balance(account, date):
    sql_query = """
        SELECT IFNULL((SUM(`debit_in_account_currency`) - SUM(`credit_in_account_currency`)), 0) AS `balance`
        FROM `tabGL Entry`
        WHERE
            `account` = "{account}"
            AND `posting_date` <= "{date}";
        """.format(account=account, date=date)

    return frappe.db.sql(sql_query, as_dict=True)[0]['balance']


def check_sales_order_item_prices(sales_order):
    """
    run

    bench execute microsynth.microsynth.troubleshooting.check_sales_order_item_prices --kwargs "{'sales_order':'SO-BAL-26028114'}"
    """
    from microsynth.microsynth.webshop import get_item_prices

    so = frappe.get_doc("Sales Order", sales_order)

    query = {}
    query['customer'] = so.customer
    query['currency'] = so.currency
    query['items'] = []

    for item in so.items:
        query_item = {}
        query_item['item_code'] = item.item_code
        query_item['qty'] = item.qty
        query['items'].append(query_item)

    response = get_item_prices(json.dumps(query))
    return_value = True

    if response['success']:
        for so_item in so.items:
            # if so_item.item_group == "Shipping":
            #     print (f"{sales_order}: Skipping shipping item {so_item.item_code}")
            #     continue
            price_found = False
            for item_price in response['item_prices']:
                if so_item.item_code == item_price['item_code'] and so_item.qty == item_price['qty']:
                    price_found = True
                    if so_item.rate == item_price['rate']:
                        print(f"{sales_order}: Price match for {so_item.item_code}: {so_item.rate} == {item_price['rate']}")
                    else:
                        shipping_item_text = " (Shipping)" if so_item.item_group == "Shipping" else ""
                        print(f"{sales_order}: Price mismatch for {so_item.item_code}{shipping_item_text}: {so_item.rate} != {item_price['rate']}{shipping_item_text}")
                        return_value = False
            if not price_found:
                print(f"{sales_order}: Error:No price found for {so_item.item_code} with qty {so_item.qty}")
                return_value = False
    else:
        print(f"Error fetching prices for sales order {sales_order}")

    return return_value


def check_sales_orders_item_prices():
    """
    run

    bench execute microsynth.microsynth.troubleshooting.check_sales_orders_item_prices
    """

    query = """
        SELECT `name`
        FROM `tabSales Order`
        WHERE '2025-07-16 20:00' < `creation` AND `creation` < '2025-07-17 20:00'
        AND `docstatus` = 1
        ORDER BY `creation` ASC
        """
    sales_orders = frappe.db.sql(query, as_dict=True)

    for so in sales_orders:
        check_sales_order_item_prices(so.get('name'))
