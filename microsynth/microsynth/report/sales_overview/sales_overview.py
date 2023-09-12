# Copyright (c) 2023, Microsynth, libracore and contributors and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
from datetime import date
from frappe.utils import cint
import calendar
from microsynth.microsynth.utils import get_child_territories

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
NGS_GROUPS = ["3.6 Library Prep", "3.7 NGS"]
GENETIC_ANALSIS_GROUPS = ["3.3 Isolationen", "3.4 Genotyping", "3.5 PCR", "3.6 Library Prep", "3.7 NGS"]
COLOURS = [
    "blue",
    "green",
    "orange",
    "orange",
    "orange",
    "red", 
    "grey"
]
AGGREGATED_COLOURS = [
    "blue",
    "green",
    "red",
    "grey"
]

def get_ngs_groups():
    return NGS_GROUPS

def get_genetic_analysis_groups():
    return GENETIC_ANALSIS_GROUPS
    
def execute(filters=None, debug=False):
    columns = get_columns(filters)
    data = get_data(filters, debug)
    return columns, data

def get_columns(filters):
    if filters.get("reporting_type") == "Qty":
        month_data_type = "Float"
        data_type_options = ""
    else:
        month_data_type = "Float"
        data_type_options = ""
    
    columns = [
        {"label": _(""), "fieldname": "description", "fieldtype": "Data", "width": 120}
    ]
    for m in range(1, 13):
        columns.append(
            {"label": MONTHS[m], "fieldname": "month{0}".format(m), "fieldtype": month_data_type, "options": data_type_options, "width": 100, "precision": "0" }
        )
        
    columns.append(
        {"label": "Year-to-Date", "fieldname": "ytd", "fieldtype": month_data_type, "options": data_type_options, "width": 100, "precision": "0" }
    )
    columns.append(
        {"label": "Forecast", "fieldname": "fc", "fieldtype": month_data_type, "options": data_type_options, "width": 100, "precision": "0" }
    )
    columns.append(
        {"label": "", "fieldname": "blank", "fieldtype": month_data_type, "width": 20}
    )

    return columns

def get_data(filters, debug=False):
    # Allow only 'Credit allocation' that calculates from the invoices.
    filters["customer_credit_revenue"] = "Credit allocation"

    initial_groups = remove_groups_for_overview(get_item_groups())
    # prepare
    #currency = frappe.get_cached_value("Company", filters.company, "default_currency")
    # territory_list = get_territories()
    if filters.get("aggregate_genetic_analyis"):
        group_list = aggregate_groups("Genetic Analysis", GENETIC_ANALSIS_GROUPS, initial_groups)
        colors = AGGREGATED_COLOURS
    else:
        group_list = aggregate_groups("3.67 NGS", NGS_GROUPS, initial_groups)
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
        'currency': filters.get("reporting_type"),
        'group': 'Total'
    }
    for m in range (1, 13):
        key = 'month{0}'.format(m)
        total[key] = 0
    # create matrix
    for group in group_list:
        # skip customer credits in 'Credit allocation' mode to prevent counting revenue twice
        if filters.get("customer_credit_revenue") == "Credit allocation" and group == "Customer Credits":
            continue

        if group == "3.67 NGS":
            query_groups = NGS_GROUPS
        elif group == "Genetic Analysis":
            query_groups = GENETIC_ANALSIS_GROUPS
        else:
            query_groups = [ group ]
        color = colors[group_count if group_count < len(colors) else (len(colors) - 1)]
        group_sums = {
            'description': """<span style="color: {color}; "><b>{group}</b></span>""".format(color=color, group=group),
            'ytd': 0,
            'fc': 0,
            'currency': filters.get("reporting_type"),
            'group': group
        }
        # for territory in filters.get("territory"):
        territory = filters.get("territory")
        _revenue = {
            'description': """<span style="color: {color}; ">{territory}</span>""".format(color=color, territory=territory),
            'group': group
        }
        ytd = 0
        base = 0
        for m in range (1, 13):
            key = 'month{0}'.format(m)
            _revenue[key] = get_revenue(filters, m, query_groups, debug)[filters.get("reporting_type").lower()]
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
    

def get_revenue(filters, month, item_groups, debug=False):
    """
    Fetch a list of documents (Items or Sales Invoices) and calculate the sum.
    """
    details = get_revenue_details(filters, month, item_groups, debug=False)
    
    # create sums per chf and eur to show as total in the report
    revenue = {'eur': 0, 'chf': 0}
    for i in details:
        revenue['chf'] += i['chf']
        revenue['eur'] += i['eur']
        
    if debug:
        print("{year}-{month}: {item_group}, {territory}: CHF {chf}, EUR {eur}".format(
            year=filters.get("fiscal_year"), month=month, item_group=item_groups, territory=filters.get("territory"), 
            chf=revenue['chf'], eur=revenue['eur']))
            
    return revenue


def calculate_chf_eur(exchange_rate, details):
    """
    Add CHF and EUR columns to the raw data. Use the invoice conversion rate for
    CHF → EUR and EUR → CHF conversions.
    """
    company_currency = {}
    for c in frappe.get_all("Company", fields=['name', 'default_currency']):
        company_currency[c['name']] = c['default_currency']

    for i in details:
        if company_currency[i['company']] == "CHF":
            if i['currency'] == "EUR":
                i['chf'] = i['base_net_amount']
                i['eur'] = i['base_net_amount'] / i['conversion_rate']  # conversion_rate: (EUR → CHF); other conversion rates (USD → CHF), (SEK → CHF) cannot be applied
            else:
                i['chf'] = i['base_net_amount']
                i['eur'] = i['base_net_amount'] / exchange_rate         # exchange rate:   (EUR → CHF)
        elif company_currency[i['company']] == "EUR":
            if i['currency'] == "CHF":
                i['chf'] = i['base_net_amount'] / i['conversion_rate']  # conversion_rate: (CHF → EUR); other conversion rates (USD → EUR), (SEK → EUR) cannot be applied
                i['eur'] = i['base_net_amount']
            else:
                i['chf'] = i['base_net_amount'] * exchange_rate         # exchange rate:   (EUR → CHF)
                i['eur'] = i['base_net_amount']
        else:
            frappe.throw(
                title='Company currency error',
                msg=f"Invalid currency {company_currency[i['company']]} of company '{i['company']}'"
            )
        # add currency indicators
        i['currency_chf'] = "CHF"
        i['currency_eur'] = "EUR"
        i['base_currency'] = company_currency[i['company']]
        # add exchange rate for revenue export
        i['exchange_rate'] = exchange_rate

    return details


def get_revenue_details(filters, month, item_groups, debug=False):
    """
    Get raw document list depending on variant including CHF and EUR columns.
    """
    details = get_item_revenues(filters, month, item_groups, debug)
    # details = get_invoice_revenues(filters, month, item_groups, debug)
    
    exchange_rate = get_exchange_rate(filters.get("fiscal_year"), month)

    details = calculate_chf_eur(exchange_rate, details)

    return details


def get_item_revenues(filters, month, item_groups, debug=False):
    """
    Get raw item records for revenue calculation (Sales Invoice Item). Base net amount
    is corrected for additional discounts and includes payments with customer credits.
    Exclude the customer credit item 6100.
    """
    if filters.get("company"):
        company_condition = f"AND `tabSales Invoice`.`company` = '{filters.get('company')}' "
    else:
        company_condition = ""
        
    if filters.get("territory"):
        territory_condition = "AND `tabSales Invoice`.`territory` IN ('{0}')".format("', '".join(get_child_territories(filters.get("territory"))))
    else:
        territory_condition = ""

    last_day = calendar.monthrange(cint(filters.get("fiscal_year")), month)
    group_condition = "'{0}'".format("', '".join(item_groups))
    query = """
            SELECT 
                `tabSales Invoice Item`.`parent` AS `document`,
                IF (`tabSales Invoice`.`total` <> 0,
                    IF (`tabSales Invoice`.`is_return` = 1,
                        (`tabSales Invoice Item`.`amount` * (`tabSales Invoice`.`total`  - (`tabSales Invoice`.`discount_amount` + `tabSales Invoice`.`total_customer_credit`)) / `tabSales Invoice`.`total`) * `tabSales Invoice`.`conversion_rate`,
                        (`tabSales Invoice Item`.`amount` * (`tabSales Invoice`.`total`  - (`tabSales Invoice`.`discount_amount` - `tabSales Invoice`.`total_customer_credit`)) / `tabSales Invoice`.`total`) * `tabSales Invoice`.`conversion_rate`
                    ), 
                    0
                ) AS `base_net_amount`, 
                `tabSales Invoice Item`.`item_group` AS `remarks`,
                `tabSales Invoice`.`currency`,
                `tabSales Invoice`.`conversion_rate` AS `conversion_rate`,
                `tabSales Invoice`.`company`
            FROM `tabSales Invoice Item`
            LEFT JOIN `tabSales Invoice` ON `tabSales Invoice Item`.`parent` = `tabSales Invoice`.`name`
            WHERE 
                `tabSales Invoice`.`docstatus` = 1
                AND `tabSales Invoice Item`.`item_code` <> '6100'
                AND `tabSales Invoice`.`posting_date` BETWEEN "{year}-{month:02d}-01" AND "{year}-{month:02d}-{to_day:02d}"
                {company_condition}
                {territory_condition}
                AND `tabSales Invoice Item`.`item_group` IN ({group_condition})
            ORDER BY `tabSales Invoice`.`posting_date`, `tabSales Invoice`.`posting_time`, `tabSales Invoice`.`name`, `tabSales Invoice Item`.`idx`;
        """.format(company_condition=company_condition, year=filters.get("fiscal_year"), month=month, to_day=last_day[1],
            territory_condition=territory_condition, group_condition=group_condition)
    items = frappe.db.sql(query, as_dict=True)
    
    return items

def get_invoice_revenues(filters, month, item_groups, debug=False):
    """
    Get raw invoice records for revenue calculation (Sales Invoice)
    """
    if filters.get("company"):
        company_condition = f"AND `tabSales Invoice`.`company` = '{filters.get('company')}' "
    else:
        company_condition = ""
        
    if filters.get("territory"):
        territory_condition = "AND `tabSales Invoice`.`territory` IN ('{0}')".format("', '".join(get_child_territories(filters.get("territory"))))
    else:
        territory_condition = ""

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
                CONCAT("Customer credit: ", `tabSales Invoice`.`currency`, " ", ROUND(`tabSales Invoice`.`total_customer_credit`, 2)) AS `remarks`,
                `tabSales Invoice`.`currency`,
                `tabSales Invoice`.`conversion_rate` AS `conversion_rate`,
                `tabSales Invoice`.`company`
            FROM `tabSales Invoice`
            WHERE 
                `tabSales Invoice`.`docstatus` = 1
                AND `tabSales Invoice`.`posting_date` BETWEEN "{year}-{month:02d}-01" AND "{year}-{month:02d}-{to_day:02d}"
                {company_condition}
                {territory_condition}
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
        """.format(company_condition=company_condition, year=filters.get("fiscal_year"), month=month, to_day=last_day[1],
            territory_condition=territory_condition, group_condition=group_condition)
    invoices = frappe.db.sql(query, as_dict=True)

    return invoices

def get_territories():
    terr = frappe.get_all("Territory", fields=['name'])
    territory_list = []
    for t in terr:
        territory_list.append(t['name'])
    territory_list.sort()
    return territory_list


def get_item_groups():
    """
    Return a list of item groups that are used to show on Sales Overview and also Revenue Export.
    """
    groups = frappe.get_all("Item Group", filters={'is_group': 0}, fields=['name'])
    group_list = []
    for g in groups:
        #if cint(g['name'][0]) > 0:                     # only use numeric item groups, like 3.1 Oligo
        if g['name'] not in ['ShippingThreshold', 'Financial Accounting', 'Internal Invoices']:
            group_list.append(g['name'])
    group_list.sort()
    return group_list


def remove_groups_for_overview(groups):
    """
    Remove item groups that should not be shown in the Sales Overview.
    """
    new_groups = []
    for g in groups:
        if g not in new_groups and g not in ["Shipping", "Andere"]:
            new_groups.append(g)

    return new_groups


def aggregate_groups(group_name, target_groups, groups):
    new_groups = []
    for group in groups:
        if group in target_groups:
            if group_name not in new_groups:
                new_groups.append(group_name) 
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
        'territory': "Switzerland",
        'fiscal_year': date.today().year,
        'reporting_type': "CHF",
        'customer_credit_revenue': "Credit allocation"
    }    
    item_groups = ["Shipping"]
    return get_revenue(filters, month = 3, item_groups=item_groups, debug=True)
