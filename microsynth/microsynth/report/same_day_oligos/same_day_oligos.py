# Copyright (c) 2024, Microsynth, libracore and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
from datetime import datetime


def get_columns():
    return [
        {"label": _("Sales Order"), "fieldname": "name", "fieldtype": "Link", "options": "Sales Order", "width": 125},
        {"label": _("Status"), "fieldname": "status", "fieldtype": "Data", "width": 120},
        {"label": _("Web ID"), "fieldname": "web_order_id", "fieldtype": "Data", "width": 70},
        {"label": _("Customer"), "fieldname": "customer", "fieldtype": "Link", "options": "Customer", "width": 80},
        {"label": _("Customer name"), "fieldname": "customer_name", "fieldtype": "Data", "width": 250},
        {"label": _("Order created"), "fieldname": "creation", "fieldtype": "Date", "width": 130},
        {"label": _("Label printed on"), "fieldname": "label_printed_on", "fieldtype": "Date", "width": 130},
        {"label": _("Same Day fulfilled"), "fieldname": "fulfilled", "fieldtype": "Check", "width": 120}
    ]


def get_holidays():
    """
    Returns a list of public holidays in Balgach from 01.01.2023 till today.
    """
    from erpnextswiss.erpnextswiss.calendar import parse_holidays
    holidays_balgach = []
    for y in range(2023, int(datetime.now().year)+1):
        holidays_balgach += parse_holidays("1903", str(y))
    # Add halfday holidays for 2024 and
    # 27. Dezember 2024: Art. 60 Abs. 1 PersV: "Fällt der Weihnachtstag auf einen Mittwoch, ist der folgende Freitag arbeitsfrei."
    holidays_balgach += [datetime(2024, 12, 24).strftime('%d.%m.%Y'),
                         datetime(2024, 12, 27).strftime('%d.%m.%Y'),
                         datetime(2024, 12, 31).strftime('%d.%m.%Y')]
    return holidays_balgach


def is_workday_before_10am(date_time, holidays):
    """
    Returns true if the given date_time is a workday before 10 am (Monday to Friday and no holiday), otherwise false.
    """
    # https://docs.python.org/3/library/datetime.html#datetime.date.weekday
    if date_time.weekday() < 5 and date_time.strftime('%d.%m.%Y') not in holidays:
        if date_time.hour < 10:  # before 10 am
            return True
    return False


def get_data(filters=None):
    conditions = ""
    
    if filters.get('customer'):
        conditions += f"AND `tabSales Order`.`customer` = '{filters.get('customer')}'"
    if filters.get('customer_name'):
        conditions += f"AND `tabSales Order`.`customer_name` LIKE '%{filters.get('customer_name')}%'"
    if filters.get('city'):
        conditions += f"AND `tabAddress`.`city` LIKE '{filters.get('city')}'"

    sql_query = f"""
        SELECT *
        FROM (
            SELECT DISTINCT
                `tabSales Order`.`name`,
                `tabSales Order`.`status`,
                `tabSales Order`.`web_order_id`,
                `tabSales Order`.`customer`,
                `tabSales Order`.`customer_name`,
                `tabSales Order`.`creation`,
                `tabSales Order`.`transaction_date`,
                `tabSales Order`.`label_printed_on`,
                (SELECT COUNT(`tabOligo`.`name`)
                 FROM `tabOligo`
                 WHERE `tabOligo`.`parent` = `tabSales Order`.`name`
                ) AS `oligo_number`
            FROM `tabSales Order`
            LEFT JOIN `tabAddress` ON `tabAddress`.`name` = `tabSales Order`.`customer_address`
            LEFT JOIN `tabSales Order Item` ON `tabSales Order Item`.`parent` = `tabSales Order`.`name`
            LEFT JOIN `tabOligo` ON `tabOligo`.`parent` = `tabSales Order`.`name`
            WHERE
            `tabSales Order`.`docstatus` = 1
            AND `tabSales Order`.`status` NOT IN ('Draft', 'Cancelled', 'Closed')
            AND `tabSales Order`.`product_type` = 'Oligos'
            AND `tabSales Order`.`customer` != '8003'
            AND `tabSales Order`.`transaction_date` >= DATE('{filters.get('from_date')}')
            AND `tabSales Order`.`transaction_date` <= DATE('{filters.get('to_date')}')
            AND `tabSales Order Item`.`item_code` IN ('0010', '0050', '0100', '1100', '1101', '1102')
            {conditions}
            ORDER BY `tabSales Order`.`transaction_date`
        ) AS `raw`
        WHERE `raw`.`oligo_number` < 20
        """
    query_results = frappe.db.sql(sql_query, as_dict=True)
    same_day_orders = []
    #print(f"There are {len(query_results)} SQL query results.")
    holidays = get_holidays()
    should_be_same_day = is_same_day = 0

    for result in query_results:
        sales_order = frappe.get_doc("Sales Order", result['name'])
        # the same day criteria only applies to Sales Orders with less than 20 Oligos
        if len(sales_order.oligos) >= 20:
            #frappe.log_error(f"This should never happen: Sales Order {result['name']}", "oh no")
            continue
        unallowed_items = False
        for i in sales_order.items:
            if i.item_code not in ('0010', '0050', '0100', '1100', '1101', '1102'):
                unallowed_items = True
                break
        if not unallowed_items:
            oligo_too_complicated = False
            for oligo_link in sales_order.oligos:
                oligo = frappe.get_doc("Oligo", oligo_link.oligo)
                if len(oligo.items) != 1:  # exclude Oligos with modifications (more than one item) and Oligos without any items
                    if len(oligo.items) == 0:
                        #print(f"WARNING: {len(oligo.items)=} for {sales_order.name}, Web Order ID {sales_order.web_order_id}. Going to take sequence length instead")
                        if not oligo.sequence:
                            #print(f"Oligo {oligo.name} from Sales Order {sales_order.name} has no items and no sequence. Going to skip this Sales Order.")
                            oligo_too_complicated = True
                            break
                        if len(oligo.sequence) <= 25:  # check if oligo is longer than 25 nt
                            continue
                        else:
                            oligo_too_complicated = True
                            break
                    else:
                        #print(f"{len(oligo.items)=} for {sales_order.name}, Web Order ID {sales_order.web_order_id}")
                        oligo_too_complicated = True
                        break
                if oligo.items[0].qty > 25:  # check if oligo is longer than 25 nt
                    oligo_too_complicated = True
                    break
            if not oligo_too_complicated:
                creation_time = sales_order.creation
                creation_date = str(creation_time).split(' ')[0]
                if creation_date != str(sales_order.transaction_date):
                    #print(f"creation_date != sales_order.transaction_date for {sales_order.name}, Web Order ID {sales_order.web_order_id}. Going to skip this Sales Order.")
                    continue
                if is_workday_before_10am(sales_order.creation, holidays):
                    if not sales_order.label_printed_on:
                        #print(f"There is no Label printed on date on {sales_order.name}, Web Order ID {sales_order.web_order_id}. Going to skip this Sales Order.")
                        continue
                    should_be_same_day += 1
                    same_day_fulfilled = (sales_order.creation.day == sales_order.label_printed_on.day) and (sales_order.label_printed_on.hour < 18)
                    if same_day_fulfilled:
                        is_same_day += 1
                        result['fulfilled'] = '1'
                    same_day_orders.append(result)
    summary_line = {
        'web_order_id': "Summary",
        'customer_name': f"{is_same_day}/{should_be_same_day} fulfilled ({((is_same_day/should_be_same_day)*100):.2f} %)"
    }
    same_day_orders.append(summary_line)
    return same_day_orders


def execute(filters=None):
    columns = get_columns()
    data = get_data(filters)
    return columns, data
