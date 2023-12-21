# Copyright (c) 2023, Microsynth, libracore and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.utils import flt
from datetime import datetime


def get_columns(filters):
    return [
        {"label": _("Company"), "fieldname": "company", "fieldtype": "Data", "width": 160 },
        {"label": _("Item Code"), "fieldname": "item_code", "fieldtype": "Link", "options": "Item", "width": 75 },
        {"label": _("Quantity"), "fieldname": "qty", "fieldtype": "Int", "width": 65 },
        #{"label": _("Valuation Rate"), "fieldname": "valuation_rate", "fieldtype": "Currency", "options": "currency", "width": 80 },
        {"label": _("Sum"), "fieldname": "sum", "fieldtype": "Currency", "options": "currency", "width": 125 },
        {"label": _("Currency"), "fieldname": "currency", "fieldtype": "Data", "width": 70 },
        {"label": _("Destination"), "fieldname": "destination", "fieldtype": "Data", "width": 85 },
    ]


def calculate_average_selling_prices(raw_data):
    """
    Calculate the average selling prices according of the given data considering only positive rates.
    """
    summary = {}
    average_selling_prices = {}
    for d in raw_data:
        if d['company'] is None or d['item_code'] is None or flt(d['rate']) < 0.01:
            continue
        company_item = (d['company'], d['item_code'])
        if company_item not in summary:
            summary[company_item] = {'qty': d['count'], 'sum': d['count'] * d['rate']}
        else:
            summary[company_item]['qty'] += d['count']
            summary[company_item]['sum'] += d['count'] * d['rate']

    for company_item, qty_sum in summary.items():
        average_selling_prices[company_item] = qty_sum['sum']/qty_sum['qty']
        print(f"Average selling price of {qty_sum['qty']} x Item {company_item[1]} for {company_item[0]}: "
              f"{round(average_selling_prices[company_item], 2)}")

    return average_selling_prices


def get_rate(company_item_dest, average_selling_prices):
    """
    Return the previously calculated average selling rate if the given Item was sold by the given Company at a rate > 0
    or the rate of the Reference Price List of the default company currency with minimum quantity 1 otherwise.
    """
    company_item = (company_item_dest[0], company_item_dest[1])
    if company_item in average_selling_prices:
        return average_selling_prices[company_item]
    else:
        currency = frappe.get_value("Company", company_item_dest[0], 'default_currency')
        filters={'price_list': f"Sales Prices {currency}", 'item_code': company_item_dest[1], 'min_qty': 1}
        rates = frappe.get_all("Item Price", filters=filters, fields=['price_list_rate'])
        if len(rates) != 1:
            msg = f"{len(rates)=}: There seems to be none or multiple Item Prices with {filters=} -> Unable to take rate for Label Accounting"
            if len(rates) > 1:
                frappe.log_error(msg, 'label_accounting.get_data')
            print(msg)
            return None
        if float(rates[0].price_list_rate) < 0.01:
            return None  # avoid listing non-prepaid labels
        return rates[0].price_list_rate


def identify_unclear_company_assignments(filters):
    """
    Return labels without a Sales Order grouped by company and item code.
    """
    company_condition = ''

    if filters.get('company'):
        company_condition = f"WHERE `raw`.`company` = '{filters.get('company')}' "

    query = f"""
        SELECT `company`,
            `item_code`,
            COUNT(`name`) AS `count`
        FROM (
            SELECT 
                `name`, 
                `item_code`,
                (SELECT `default_company`
                FROM `tabCustomer` 
                WHERE `tabCustomer`.`name` = `base`.`customer`) AS `company`
            FROM (
                SELECT
                    `tabSequencing Label`.`name`,
                    `tabSequencing Label`.`item` AS `item_code`,
                    (SELECT `link_name` 
                    FROM `tabDynamic Link` 
                    WHERE `tabDynamic Link`.`link_doctype` = "Customer"
                    AND `tabDynamic Link`.`parenttype`= "Contact"
                    AND `tabDynamic Link`.`parent` = `tabSequencing Label`.`contact`) AS `customer`
                FROM `tabSequencing Label`
                WHERE `tabSequencing Label`.`status` IN ("unused", "submitted")
                AND `tabSequencing Label`.`sales_order` IS NULL
            ) AS `base`
        )  AS `raw`
        {company_condition}
        GROUP BY CONCAT(`raw`.`company`, ":", `raw`.`item_code`)
        """
    more_details = frappe.db.sql(query, as_dict=True)
    return more_details


def get_data(filters):
    """
    Return Sequencing Labels with status unused or submitted grouped by Company and Item Code
    together with quantity sum and sum of rates.
    If there is no rate, the average selling rate as calculated by calculate_average_selling_prices is used instead.

    bench execute microsynth.microsynth.report.label_accounting.label_accounting.get_data --kwargs "{'filters': {'company': 'Microsynth AG'}}"
    """
    company_condition = ''

    if filters.get('company'):
        company_condition = f"WHERE `raw`.`company` = '{filters.get('company')}'"

    sql_query = f"""
        SELECT `company`,
            `item_code`,
            COUNT(`name`) AS `count`,
            `rate`,
            `territory`
        FROM (
            SELECT 
                `name`, 
                `item_code`,
                IFNULL (`company`, 
                    (SELECT `default_company` FROM `tabCustomer` WHERE `tabCustomer`.`name` = `base`.`customer`)) AS `company`,
                `rate`,
                (SELECT `territory` FROM `tabCustomer` WHERE `tabCustomer`.`name` = `base`.`customer`) AS `territory`,
                sales_order
            FROM (
                SELECT
                    `tabSequencing Label`.`name`,

                    `tabSequencing Label`.`item` AS `item_code`,

                    `tabSequencing Label`.`sales_order`,

                    (SELECT `company`
                    FROM `tabSales Order`
                    WHERE `tabSales Order`.`name` = `tabSequencing Label`.`sales_order`) AS `company`,

                    (SELECT `tabSales Order Item`.`base_net_rate`
                    FROM `tabSales Order Item`
                    WHERE `tabSales Order Item`.`parent` = `tabSequencing Label`.`sales_order` 
                    AND `tabSales Order Item`.`item_code` = `tabSequencing Label`.`item`
                    LIMIT 1) AS `rate`,

                    (SELECT `link_name` 
                    FROM `tabDynamic Link` 
                    WHERE `tabDynamic Link`.`link_doctype` = "Customer"
                    AND `tabDynamic Link`.`parenttype`= "Contact"
                    AND `tabDynamic Link`.`parent` = `tabSequencing Label`.`contact`) AS `customer`

                FROM `tabSequencing Label`
                WHERE `tabSequencing Label`.`status` IN ("unused", "submitted")
            ) AS `base`
        )  AS `raw`
        {company_condition}
        GROUP BY CONCAT(`raw`.`company`, ":", `raw`.`item_code`, ":", `raw`.`rate`, ":", `raw`.`territory`)
    """

    raw_data = frappe.db.sql(sql_query, as_dict=True)
    average_selling_prices = calculate_average_selling_prices(raw_data)
    summary = {}

    for d in raw_data:
        if d['company'] is None and d['rate'] is None:
            print(f"Need to identify unclear company assignments: {d=}")
            details = identify_unclear_company_assignments(filters)
            sum = 0

            for det in details:
                if det['count'] is None:
                    continue
                sum += det['count']
                if det['company'] is None:
                    # no company assignment possible -> ignore according to DSc
                    print(f"No company assignment possible: {det=}")
                    continue
                company_item_dest = (det['company'], det['item_code'], None)
                rate = get_rate(company_item_dest, average_selling_prices)
                if rate is None:
                    continue                    
                summary[company_item_dest] = {'qty': det['count'], 'sum': det['count'] * rate}

            if sum != d.count:
                msg = f"Mismatch in the number of Labels without rate and company (no Sales Order): {d['count']=} but {sum=}", 'label_accounting.get_data'
                frappe.log_error(msg)
                print(msg)
            continue

        # if d['rate'] is None:
            # print(f"d.rate is None: {d=}")
        
        # Distinguish territory only for Microsynth Seqlab GmbH
        if d['company'] == 'Microsynth Seqlab GmbH':
            if 'Germany' in d['territory'] or 'Göttingen' in d['territory']:
                destination = 'DE'
            elif 'France' in d['territory'] or d['territory'] == 'Austria' or d['territory'] == 'Rest of Europe':
                destination = 'Europe'  # without DE and CH
            elif d['territory'] == 'Rest of the World':
                destination = 'ROW'
            else:
                print(f"This should be a mistake: {d=}")
                if 'Switzerland' in d['territory']:
                    destination = 'CH'
                else:
                    # This should never happen
                    destination = None
            company_item_dest = (d['company'], d['item_code'], destination)
        else:
            company_item_dest = (d['company'], d['item_code'], None)

        if d['rate'] == 0 or d['rate'] is None:
            # fallback: find rate from average selling rate if available or reference price list rate otherwise
            d['rate'] = get_rate(company_item_dest, average_selling_prices)
            if d['rate'] is None:
                continue

        if company_item_dest not in summary:
            summary[company_item_dest] = {'qty': d['count'], 'sum': d['count'] * d['rate']}
        else:
            summary[company_item_dest]['qty'] += d['count']
            summary[company_item_dest]['sum'] += d['count'] * d['rate']

    data = []

    for company_item_dest, qty_sum in summary.items():
        entry = {
            "company": company_item_dest[0],
            "item_code": company_item_dest[1],
            "qty": qty_sum['qty'],
            #"valuation_rate": get_rate(company_item_dest, average_selling_prices),  # can be confusing because it is not necessary that qty * valuation_rate = sum
            "sum": qty_sum['sum'],
            "currency": frappe.get_cached_value("Company", company_item_dest[0], "default_currency"),
            "destination": company_item_dest[2]
        }
        data.append(entry)

    return data


def execute(filters):
    columns, data = get_columns(filters), get_data(filters)
    return columns, data


def create_csvs(path):
    """
    Create one CSV file per Company except Ecogenics.
    Save the CSV files at the given path.
    Should be run by a cronjob once per month.

    bench execute microsynth.microsynth.report.label_accounting.label_accounting.create_csvs --kwargs "{'path': '/mnt/erp_share/label_accounting/'}"
    """
    companies = frappe.get_all("Company", fields=['name'])
    for comp in companies:
        if 'Ecogenics' in comp['name']:
            continue  # Ecogenics does not sell its own labels
        filters = {'company': comp['name']}
        data = get_data(filters)
        datetime_str = datetime.now().strftime("%Y-%m-%d_%H-%M")
        filepath = path + datetime_str + '_label_accounting_' + (comp['name'].replace(' ', '_')) + '.csv'
        with open(filepath, 'x') as file:  # do not execute the function more than once per minute
            file.write('company;item_code;qty;sum;currency;destination\n')  # header
            for entry in data:
                file.write(f"{entry['company']};{entry['item_code']};{entry['qty']};{round(entry['sum'], 2)};{entry['currency']};{entry['destination']}\n")
