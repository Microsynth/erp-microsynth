# Copyright (c) 2023, Microsynth, libracore and contributors and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
from datetime import date
from frappe.utils import cint
import calendar

MONTHS = {
    1: _("January"),
    2: _("February"),
    3: _("March"),
    4: _("April"),
    5: _("May"),
    6: _("June"),
    7: _("July"),
    8: _("August"),
    9: _("September"),
    10: _("October"),
    11: _("November"),
    12: _("December"),
}
# product type aggregation is currently not used in favour of the item groups
PRODUCT_TYPES = ["Oligos", "Labels", "Sequencing", "NGS", "FLA", "Material", "Service"]
PRODUCT_TYPE_MAP = {
    "Oligo Synthesis": ["Oligos", "Material"],
    "Sanger Sequencing": ["Labels", "Sequencing"],
    "Isolation and Assaying": ["FLA"],
    "Library Prep and NGS": ["NGS"],
    "Ecogenics": ["Service"]
}
GENETIC_ANALSIS_GROUPS = ["3.3 Isolationen", "3.4 Genotyping", "3.5 PCR", "3.6 Library Prep", "3.7 NGS"]
COLOURS = [
    "blue",
    "green",
    "orange",
    "orange",
    "orange",
    "red",
    "red", 
    "grey"
]
AGGREGATED_COLOURS = [
    "blue",
    "green",
    "red",
    "grey"
]

def execute(filters=None, debug=False):
    columns = get_columns(filters)
    data = get_data(filters, debug)
    return columns, data

def get_columns(filters):
    if filters.get("reporting_type") == "Qty":
        month_data_type = "Float"
        data_type_options = ""
    else:
        month_data_type = "Currency"
        data_type_options = "currency"
    
    columns = [
        {"label": _(""), "fieldname": "description", "fieldtype": "Data", "width": 120}
    ]
    for m in range(1, 13):
        columns.append(
            {"label": MONTHS[m], "fieldname": "month{0}".format(m), "fieldtype": month_data_type, "options": data_type_options, "width": 100}
        )
        
    columns.append(
        {"label": "YTD", "fieldname": "ytd", "fieldtype": month_data_type, "options": data_type_options, "width": 100}
    )
    columns.append(
        {"label": "FC", "fieldname": "fc", "fieldtype": month_data_type, "options": data_type_options, "width": 100}
    )
    columns.append(
        {"label": "", "fieldname": "blank", "fieldtype": month_data_type, "width": 20}
    )

    return columns

def get_data(filters, debug=False):
    # prepare
    #currency = frappe.get_cached_value("Company", filters.company, "default_currency")
    # territory_list = get_territories()
    if filters.get("aggregate_genetic_analyis"):
        group_list = aggregate_genetic_analysis(get_item_groups())
        colors = AGGREGATED_COLOURS
    else:
        group_list = get_item_groups()
        colors = COLOURS

    # prepare forcast:
    if cint(date.today().year) > cint(filters.get("fiscal_year")):
        elapsed_month = 12          # the reporting year is complete
    else:
        elapsed_month = date.today().month - 1
    
    output = []
    group_count = 0
    total = {
        'description': "<b>TOTAL</b>",
        'ytd': 0,
        'fc': 0,
        'currency': filters.get("reporting_type")
    }
    for m in range (1, 13):
        key = 'month{0}'.format(m)
        total[key] = 0
    # create matrix
    for group in group_list:
        # skip customer credits in 'Credit allocation' mode to prevent counting revenue twice
        if filters.get("customer_credit_revenue") == "Credit allocation" and group == "Customer Credits":
            continue

        if group == "Genetic Analysis":
            query_groups = GENETIC_ANALSIS_GROUPS
        else:
            query_groups = [ group ]
        color = colors[group_count if group_count < len(colors) else (len(colors) - 1)]
        group_sums = {
            'description': """<span style="color: {color}; "><b>{group}</b></span>""".format(color=color, group=group),
            'ytd': 0,
            'fc': 0,
            'currency': filters.get("reporting_type")
        }
        # for territory in filters.get("territory"):
        territory = filters.get("territory")
        _revenue = {
            'description': """<span style="color: {color}; ">{territory}</span>""".format(color=color, territory=territory)
        }
        ytd = 0
        base = 0
        for m in range (1, 13):
            key = 'month{0}'.format(m)
            if filters.get("customer_credit_revenue") == "Credit deposit":
                _revenue[key] = get_item_revenue(filters, m, query_groups, debug)[filters.get("reporting_type").lower()]
            elif filters.get("customer_credit_revenue") == "Credit allocation":
                _revenue[key] = get_invoice_revenue(filters, m, query_groups, debug)[filters.get("reporting_type").lower()]
            else:
                frappe.throw("Sales Overview.get_data: customer_credit_revenue has invalid value '{0}'".format(filters.get("customer_credit_revenue")))
            if not key in group_sums:
                group_sums[key] = _revenue[key]
            else:
                group_sums[key] += _revenue[key]
            ytd += _revenue[key]
            if m <= elapsed_month:
                base += _revenue[key]
        _revenue['ytd'] = ytd
        _revenue['fc'] = (12 * base / elapsed_month) if elapsed_month > 0 else 0
        _revenue['currency'] = filters.get("reporting_type")
        
        # add each territory
        # output.append(_revenue)
        
        group_sums['ytd'] += _revenue['ytd']
        group_sums['fc'] = _revenue['fc']
            
        # add group sum
        output.append(group_sums)
        
        total['ytd'] += group_sums['ytd']
        total['fc'] += group_sums['fc']
        for m in range (1, 13):
            key = 'month{0}'.format(m)
            total[key] += group_sums[key]
        
        group_count += 1
    
    output.append(total)
    
    return output

def get_exchange_rate(year, month):
    exchange_rate = frappe.db.sql("""
        SELECT IFNULL(`exchange_rate`, 1) AS `exchange_rate`
        FROM `tabCurrency Exchange`
        WHERE `date` LIKE "{year}-{month:02d}-%"
          AND `from_currency` = "EUR"
          AND `to_currency` = "CHF"
        ;
    """.format(year=year, month=month), as_dict=True)
    if len(exchange_rate) > 0:
        exchange_rate = exchange_rate[0]['exchange_rate']
    else:
        exchange_rate = 1
    return exchange_rate
        
def get_item_revenue(filters, month, item_groups, debug=False):
    company = "%"
    if filters.get("company"):
        company = filters.get("company")
    territory = "%"
    if filters.get("territory"):
        territory = filters.get("territory")
    last_day = calendar.monthrange(cint(filters.get("fiscal_year")), month)
    group_condition = "'{0}'".format("', '".join(item_groups))
    query = """
            SELECT 
                `tabSales Invoice Item`.`parent` AS `document`,
                `tabSales Invoice Item`.`base_net_amount` AS `base_net_amount`, 
                `tabSales Invoice Item`.`item_group` AS `remarks`,
                `tabSales Invoice`.`company`
            FROM `tabSales Invoice Item`
            LEFT JOIN `tabSales Invoice` ON `tabSales Invoice Item`.`parent` = `tabSales Invoice`.`name`
            WHERE 
                `tabSales Invoice`.`docstatus` = 1
                AND `tabSales Invoice`.`company` LIKE "{company}"
                AND `tabSales Invoice`.`posting_date` BETWEEN "{year}-{month:02d}-01" AND "{year}-{month:02d}-{to_day:02d}"
                AND `tabSales Invoice`.`territory` LIKE "{territory}"
                AND `tabSales Invoice Item`.`item_group` IN ({group_condition})
            ;
        """.format(company=company, year=filters.get("fiscal_year"), month=month, to_day=last_day[1],
            territory=territory, group_condition=group_condition)
    items = frappe.db.sql(query, as_dict=True)
    
    company_currency = {}
    for c in frappe.get_all("Company", fields=['name', 'default_currency']):
        company_currency[c['name']] = c['default_currency']
    
    exchange_rate = get_exchange_rate(filters.get("fiscal_year"), month)
        
    revenue = {'eur': 0, 'chf': 0}
    for i in items:
        if company_currency[i['company']] == "CHF":
            revenue['chf'] += i['base_net_amount']
            revenue['eur'] += i['base_net_amount'] / exchange_rate
        else:
            revenue['chf'] += i['base_net_amount'] * exchange_rate
            revenue['eur'] += i['base_net_amount'] 
    
    if debug:
        print("{year}-{month}: {item_group}, {territory}: CHF {chf}, EUR {eur}".format(
            year=filters.get("fiscal_year"), month=month, item_group=item_groups, territory=territory, 
            chf=revenue['chf'], eur=revenue['eur']))
            
    return revenue

def get_invoice_revenue(filters, month, item_groups, debug=False):
    company = "%"
    if filters.get("company"):
        company = filters.get("company")
    territory = "%"
    if filters.get("territory"):
        territory = filters.get("territory")
    last_day = calendar.monthrange(cint(filters.get("fiscal_year")), month)
    group_condition = "'{0}'".format("', '".join(item_groups))

    # Define the Item Group of an invoice by the item with the highest amount. 
    # Use the absolute value of the base_amount due to credit notes/returns and 
    # customer credits. 
    # Ignore 'Shipping' items. 
    # Important Note: 
    # This excludes invoices with only 'Shipping' items. Though, these are usually
    # intercompany invoices.

    query = """
            SELECT DISTINCT 
                `tabSales Invoice`.`name` AS `document`,
                IF (`tabSales Invoice`.`is_return` = 1,
                  `tabSales Invoice`.`base_total` - (`tabSales Invoice`.`base_discount_amount` + `tabSales Invoice`.`total_customer_credit` * `tabSales Invoice`.`conversion_rate`),
                  `tabSales Invoice`.`base_total` - (`tabSales Invoice`.`base_discount_amount` - `tabSales Invoice`.`total_customer_credit` * `tabSales Invoice`.`conversion_rate`)
                  ) AS `base_net_amount`,
                CONCAT("Customer credit: ", `tabSales Invoice`.`total_customer_credit`) AS `remarks`,
                `tabSales Invoice`.`company`
            FROM `tabSales Invoice`
            WHERE 
                `tabSales Invoice`.`docstatus` = 1
                AND `tabSales Invoice`.`company` LIKE "{company}"
                AND `tabSales Invoice`.`posting_date` BETWEEN "{year}-{month:02d}-01" AND "{year}-{month:02d}-{to_day:02d}"
                AND `tabSales Invoice`.`territory` LIKE "{territory}"
                AND (
                    SELECT `tabSales Invoice Item`.`item_group`
                    FROM `tabSales Invoice Item` 
                    WHERE `tabSales Invoice Item`.`parent` = `tabSales Invoice`.`name`
                    ORDER BY 
                        IF (`tabSales Invoice Item`.`item_group` = 'Shipping', 
                            -1,
                            ABS(`tabSales Invoice Item`.`base_amount`)) DESC
                    LIMIT 1
                ) IN ({group_condition})
            ;
        """.format(company=company, year=filters.get("fiscal_year"), month=month, to_day=last_day[1],
            territory=territory, group_condition=group_condition)
    invoices = frappe.db.sql(query, as_dict=True)
    
    company_currency = {}
    for c in frappe.get_all("Company", fields=['name', 'default_currency']):
        company_currency[c['name']] = c['default_currency']
    
    exchange_rate = get_exchange_rate(filters.get("fiscal_year"), month)

    revenue = {'eur': 0, 'chf': 0}
    for i in invoices:        
        if company_currency[i['company']] == "CHF":
            revenue['chf'] += i['base_net_amount']
            revenue['eur'] += i['base_net_amount'] / exchange_rate
        else:
            revenue['chf'] += i['base_net_amount'] * exchange_rate
            revenue['eur'] += i['base_net_amount'] 

    if debug:
        print("{year}-{month}: {item_groups}, {territory}: CHF {chf}, EUR {eur}".format(
            year=filters.get("fiscal_year"), month=month, item_groups=item_groups, territory=territory, 
            chf=revenue['chf'], eur=revenue['eur']))
        print("--")
        for i in invoices:
            print("{0}\t{1}".format(i['name'].ljust(20), i['base_total']))

    return revenue

def get_territories():
    terr = frappe.get_all("Territory", fields=['name'])
    territory_list = []
    for t in terr:
        territory_list.append(t['name'])
    territory_list.sort()
    return territory_list
    
def get_item_groups():
    groups = frappe.get_all("Item Group", filters={'is_group': 0}, fields=['name'])
    group_list = []
    for g in groups:
        #if cint(g['name'][0]) > 0:                     # only use numeric item groups, like 3.1 Oligo
        if g['name'] not in ['ShippingThreshold', 'Financial Accounting', 'Internal Invoices']:
            group_list.append(g['name'])
    group_list.sort()
    return group_list

def aggregate_genetic_analysis(groups):
    new_groups = []
    for group in groups:
        if group in GENETIC_ANALSIS_GROUPS:
            if "Genetic Analysis" not in new_groups:
                new_groups.append("Genetic Analysis") 
            else:
                continue
        else:
            new_groups.append(group)
    return new_groups

def debug():
    filters = {
        'fiscal_year': date.today().year,
        'reporting_type': "CHF"
    }
    execute(filters, debug=True)

def test():
    """
    bench execute microsynth.microsynth.report.sales_overview.sales_overview.test
    """
    filters = {
        'company': None,
        'territory': None,
        'fiscal_year': date.today().year,
        'reporting_type': "CHF"
    }    
    item_groups = ["Shipping"]
    return get_invoice_revenue(filters, month = 3, item_groups=item_groups, debug=True)
