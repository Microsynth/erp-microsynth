# Copyright (c) 2023, Microsynth, libracore and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.utils import cint
import calendar
from microsynth.microsynth.utils import get_child_territories
from microsynth.microsynth.report.sales_overview.sales_overview import get_exchange_rate, get_item_groups


def get_month_number(month):
    months = {
        "January": 1,
        "February": 2,
        "March": 3,
        "April": 4,
        "May": 5,
        "June": 6,
        "July": 7,
        "August": 8, 
        "September": 9,
        "October": 10, 
        "November": 11,
        "December": 12
    }
    return months[month]


def get_columns(filters):
    return [
        {"label": _("Sales Invoice"), "fieldname": "sales_invoice", "fieldtype": "Link", "options": "Sales Invoice", "width": 130 },
        {"label": _("Item"), "fieldname": "item_code", "fieldtype": "Link", "options": "Item", "width": 75 },
        {"label": _("Item Group"), "fieldname": "item_group", "fieldtype": "Link", "options": "Item Group", "width": 100 },
        {"label": _("Quantity"), "fieldname": "qty", "fieldtype": "Float", "options": "", "precision": "0", "width": 75 },
        {"label": _("Base net amount"), "fieldname": "base_net_amount", "fieldtype": "Currency", "options": "base_currency", "width": 120},
        {"label": _("CHF"), "fieldname": "chf", "fieldtype": "Currency", "options": "currency_chf", "width": 120},
        {"label": _("EUR"), "fieldname": "eur", "fieldtype": "Currency", "options": "currency_eur", "width": 120},
        {"label": _("Invoice Conversion Rate"), "fieldname": "conversion_rate", "fieldtype": "Float", "precision": "6", "width": 120},
        {"label": _("Monthly Currency Exchange"), "fieldname": "exchange_rate", "fieldtype": "Float", "precision": "6", "width": 120},
        {"label": _("Company"), "fieldname": "company", "fieldtype": "Link", "options": "Company", "width": 175},
        {"label": _("Group Leader"), "fieldname": "group_leader", "fieldtype": "Data", "width": 120},
        {"label": _("Institute Key"), "fieldname": "institute_key", "fieldtype": "Data", "width": 120},
    ]


def get_item_revenue(filters, month, item_groups, debug=False):
    company = "%"
    if filters.get("company"):
        company = filters.get("company")

    if filters.get("territory"):
        territory_condition = "IN ('{0}')".format("', '".join(get_child_territories(filters.get("territory"))))
    else:
        territory_condition = "LIKE '%'"

    
    last_day = calendar.monthrange(cint(filters.get("fiscal_year")), month)
    group_condition = "'{0}'".format("', '".join(item_groups))

    # TODO: replace base_net_amount by a discount-corrected version 'discounted item amount in company currency'
    #     (`tabSales Invoice Item`.`amount` * (`tabSales Invoice`.`total`  - (`tabSales Invoice`.`discount_amount` - `tabSales Invoice`.`total_customer_credit`)) / `tabSales Invoice`.`total`) * `tabSales Invoice`.`conversion_rate` AS `discounted item amount in company currency`,

    # TODO: unify with implementation on Sales Overview, consider Month, Item Group and Territory
    

    query = """
            SELECT 
                `tabSales Invoice Item`.`parent` AS `document`,
                `tabSales Invoice Item`.`base_net_amount` AS `base_net_amount`, 
                `tabSales Invoice Item`.`item_group` AS `item_group`,
                `tabSales Invoice Item`.`item_group` AS `remarks`,
                `tabSales Invoice`.`company`,
                `tabSales Invoice`.`conversion_rate` AS `conversion_rate`,
                `tabContact`.`group_leader` AS `group_leader`,
                `tabContact`.`institute_key` AS `institute_key`
            FROM `tabSales Invoice Item`
            LEFT JOIN `tabSales Invoice` ON `tabSales Invoice Item`.`parent` = `tabSales Invoice`.`name`
            LEFT JOIN `tabContact` ON `tabContact`.`name` = `tabSales Invoice`.`contact_person`
            WHERE 
                `tabSales Invoice`.`docstatus` = 1
                AND `tabSales Invoice`.`company` LIKE "{company}"
                AND `tabSales Invoice`.`posting_date` BETWEEN "{year}-{month:02d}-01" AND "{year}-{month:02d}-{to_day:02d}"
                AND `tabSales Invoice`.`territory` {territory_condition}
                AND `tabSales Invoice Item`.`item_group` IN ({group_condition})
            ;
        """.format(company=company, year=filters.get("fiscal_year"), month=month, to_day=last_day[1],
            territory_condition=territory_condition, group_condition=group_condition)
    items = frappe.db.sql(query, as_dict=True)
    
    return items


def get_revenue_details(filters, debug=False):
    if filters.get("item_group"):
        item_groups = [ filters.get("item_group") ]
    else:
        # TODO get_item_groups does not include shipping
        item_groups = get_item_groups()

    if filters.get("month"): 
        m = get_month_number(filters.get("month"))
        details = get_item_revenue(filters, m, item_groups, debug)
    else:
        details = []
        for m in range(1, 12 + 1):
            details += get_item_revenue(filters, month = m, item_groups=item_groups, debug=debug)

    # add chf and eur columns
    company_currency = {}
    for c in frappe.get_all("Company", fields=['name', 'default_currency']):
        company_currency[c['name']] = c['default_currency']
    
    # TODO use month to get exchange rate
    exchange_rate = get_exchange_rate(filters.get("fiscal_year"), 7)

    for i in details:
        i['sales_invoice'] = i['document']
        if company_currency[i['company']] == "CHF":
            i['chf'] = i['base_net_amount']
            i['eur'] = i['base_net_amount'] / exchange_rate
        else:
            i['chf'] = i['base_net_amount'] * exchange_rate
            i['eur'] = i['base_net_amount']
        # add currency indicators
        i['currency_chf'] = "CHF"
        i['currency_eur'] = "EUR"
        i['base_currency'] = company_currency[i['company']]
        
    return details


def get_data(filters):
    data = []
    element = { 
        "sales_invoice": "SI-BAL-23021267",
        "item_code": "0010",
        "qty": 42 }
    data.append(element)
    data = get_revenue_details(filters)
    return data


def execute(filters=None):
    columns, data = get_columns(filters), get_data(filters)
    return columns, data
