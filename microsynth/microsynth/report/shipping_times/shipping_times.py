# Copyright (c) 2025, Microsynth, libracore and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
from datetime import datetime
import statistics
import frappe
from frappe import _
from microsynth.microsynth.utils import iterate_dates, is_workday
from microsynth.microsynth.report.same_day_oligos.same_day_oligos import get_holidays


def get_columns(filters):
    return [
        {"label": _("Tracking Code ID"), "fieldname": "name", "fieldtype": "Link", "options": "Tracking Code", "width": 115 },
        {"label": _("Sales Order"), "fieldname": "sales_order", "fieldtype": "Link", "options": "Sales Order", "width": 125 },
        {"label": _("Country"), "fieldname": "country", "fieldtype": "Link", "options": "Country", "width": 110 },
        {"label": _("Shipping Item"), "fieldname": "shipping_item", "fieldtype": "Link", "options": "Item", "width": 350 },
        #{"label": _("Shipping Item Name"), "fieldname": "item_name", "fieldtype": "Data", "width": 170 },
        {"label": _("Tracking Code"), "fieldname": "tracking_code", "fieldtype": "Data", "width": 170 },
        {"label": _("Tracking URL"), "fieldname": "tracking_url", "fieldtype": "HTML", "width": 410 },
        {"label": _("Shipping Date"), "fieldname": "shipping_date", "fieldtype": "Date", "width": 130 },
        {"label": _("Delivery Date"), "fieldname": "delivery_date", "fieldtype": "Date", "width": 130 },
        {"label": _("Business Days"), "fieldname": "shipping_days", "fieldtype": "Data", "width": 110 },
    ]


def get_data(filters):
    """
    Get raw Sales Order records for find tracking code report.
    """
    conditions = ""
    if filters.get('item_code'):
        conditions += f" AND `tabTracking Code`.`shipping_item` = '{filters.get('item_code')}' "
    if filters.get('country'):
        conditions += f" AND `tabAddress`.`country` = '{filters.get('country')}' "
    if filters.get('show_unknown_delivery'):
        pass
    else:
        conditions += f" AND `tabTracking Code`.`delivery_date` IS NOT NULL "

    query = f"""
        SELECT
            `tabTracking Code`.`name`,
            `tabTracking Code`.`sales_order`,
            `tabTracking Code`.`shipping_item`,
            `tabItem`.`item_name`,
            `tabTracking Code`.`tracking_code`,
            CONCAT('<a href="', `tabTracking Code`.`tracking_url`, '">', `tabTracking Code`.`tracking_url`, '</a>') AS `tracking_url`,
            `tabTracking Code`.`shipping_date`,
            `tabTracking Code`.`delivery_date`,
            `tabAddress`.`country`
        FROM `tabTracking Code`
        LEFT JOIN `tabSales Order` ON `tabSales Order`.`name` = `tabTracking Code`.`sales_order`
        LEFT JOIN `tabAddress` ON `tabAddress`.`name` = `tabSales Order`.`shipping_address_name`
        LEFT JOIN `tabItem` ON `tabItem`.`name` = `tabTracking Code`.`shipping_item`
        WHERE `tabTracking Code`.`shipping_date` BETWEEN DATE('{filters.get('from_date')}') AND DATE('{filters.get('to_date')}')
            {conditions}
        ORDER BY `tabTracking Code`.`shipping_date` ASC;
        """
    data = frappe.db.sql(query, as_dict=True)

    #total_days = 0
    counter = 0
    shipping_days_list = []
    holidays = get_holidays()

    for line in data:
        if line['shipping_date'] and line['delivery_date']:
            delivery_date = datetime.date(line['delivery_date'])
            shipping_date = datetime.date(line['shipping_date'])
            shipping_days = (delivery_date - shipping_date).days
            if shipping_days > 0:
                business_days = -1  # alternative to substracting a day afterwards since both the sipping and the delivery date are counted
                for date in iterate_dates(shipping_date, delivery_date):
                    if is_workday(date, holidays):
                        business_days += 1
                line['shipping_days'] = business_days
                shipping_days_list.append(business_days)
                counter += 1
    if counter > 0:
        # add a summary line
        summary_line = {
            'tracking_url': 'Median Business Days:',
            'shipping_days': statistics.median(shipping_days_list)
        }
        data.append(summary_line)
    return data


def execute(filters=None):
    columns, data = get_columns(filters), get_data(filters)
    return columns, data
