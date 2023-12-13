# Copyright (c) 2023, Microsynth, libracore and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _


def get_columns(filters):
    return [
        {"label": _("Company"), "fieldname": "company", "fieldtype": "Data", "width": 160 },
        {"label": _("Item Code"), "fieldname": "item_code", "fieldtype": "Link", "options": "Item", "width": 75 },
        #{"label": _("Item Name"), "fieldname": "item_name", "fieldtype": "Data", "width": 150 },
        {"label": _("Quantity"), "fieldname": "qty", "fieldtype": "Int", "width": 75 },
        {"label": _("Sum"), "fieldname": "sum", "fieldtype": "Currency", "width": 125 },
        #{"label": _("Currency"), "fieldname": "currency", "fieldtype": "Data", "width": 75 },
    ]


def identify_unclear_company_assignments(filters):
    company_condition = ''

    if filters and filters.get('company'):
        company_condition = f"AND `raw`.`company` = '{filters.get('company')}' "

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
        WHERE TRUE
        {company_condition}
        GROUP BY CONCAT(`raw`.`company`, ":", `raw`.`item_code`)
        """
    more_details = frappe.db.sql(query, as_dict=True)

    return more_details


def get_data(filters=None):
    """
    bench execute microsynth.microsynth.report.label_accounting.label_accounting.get_data
    """
    company_condition = ''
    hasFilters = False

    if filters and filters.get('company'):
        company_condition = f"AND `raw`.`company` = '{filters.get('company')}'"
        hasFilters = True

    data = []

    if hasFilters:
        query = f"""
            SELECT `company`,
                `item_code`,
                COUNT(`name`) AS `count`,
                `rate`
            FROM (
                SELECT 
                    `name`, 
                    `item_code`,
                    IFNULL (`company`, 
                        (SELECT `default_company` FROM `tabCustomer` WHERE `tabCustomer`.`name` = `base`.`customer`)) AS `company`,
                    `rate`
                FROM (
                    SELECT
                        `tabSequencing Label`.`name`,

                        `tabSequencing Label`.`item` AS `item_code`,

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
            WHERE TRUE
            {company_condition}
            GROUP BY CONCAT(`raw`.`company`, ":", `raw`.`item_code`, ":", `raw`.`rate`)
        """
        raw_data = frappe.db.sql(query, as_dict=True)

        average_selling_prices = dict()
        for d in raw_data:
            if d.company is None or d.rate is None or d.rate == 0 or d.item_code is None:
                continue
            company_item_pair = (d.company, d.item_code)
            if company_item_pair not in average_selling_prices:
                average_selling_prices[company_item_pair] = {'qty': d.count, 'sum': d.count * d.rate}
            else:
                average_selling_prices[company_item_pair]['qty'] += d.count
                average_selling_prices[company_item_pair]['sum'] += d.count * d.rate
        for company_item_pair, qty_sum in average_selling_prices.items():
            average_selling_prices[company_item_pair] = qty_sum['sum']/qty_sum['qty']
            print(f"Average selling price of {qty_sum['qty']} x Item {company_item_pair[1]} for {company_item_pair[0]}: {round(average_selling_prices[company_item_pair], 2)}")

        summary = dict()
        for d in raw_data:
            if d.company is None and d.rate is None:
                print(f"{d=}")
                details = identify_unclear_company_assignments(filters)
                sum = 0

                for det in details:
                    if det.count is None:
                        continue
                    sum += det.count
                    if det.company is None:
                        print(f"{det=}")
                        # TODO: What to do with these?
                        continue
                    if company_item_pair not in average_selling_prices:
                        continue
                    rate = average_selling_prices[company_item_pair]

                    company_item_pair = (det.company, det.item_code)
                    summary[company_item_pair] = {'qty': det.count, 'sum': det.count * rate}

                if sum != d.count:
                    msg = f'{d.count=} but {sum=}', 'label_accounting.get_data'
                    frappe.log_error(msg)
                    print(msg)

                continue

            if d.rate is None:
                print(f"d.rate is None: {d=}")

            company_item_pair = (d.company, d.item_code)
            if d.rate == 0 or d.rate is None:
                if company_item_pair not in average_selling_prices:
                    continue
                rate = average_selling_prices[company_item_pair]
            else:
                rate = d.rate

            if company_item_pair not in summary:
                summary[company_item_pair] = {'qty': d.count, 'sum': d.count * rate}
            else:
                summary[company_item_pair]['qty'] += d.count
                summary[company_item_pair]['sum'] += d.count * rate

        for company_item_pair, qty_sum in summary.items():
            entry = {
                "company": company_item_pair[0],
                "item_code": company_item_pair[1],
                "qty": qty_sum['qty'],
                "sum": qty_sum['sum']  # TODO: Consider currency
            }
            data.append(entry)

    return data


def execute(filters=None):
    columns, data = get_columns(filters), get_data(filters)
    return columns, data
