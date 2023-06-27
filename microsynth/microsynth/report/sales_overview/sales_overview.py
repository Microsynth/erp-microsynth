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
COLOURS = [
    "blue",
    "green",
    "grey",
    "red",
    "orange",
    "grey"
]

def execute(filters=None):
    columns = get_columns(filters)
    data = get_data(filters)
    return columns, data

def get_columns(filters):
    if filters.reporting_type == "Qty":
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

def get_data(filters):
    # prepare
    #currency = frappe.get_cached_value("Company", filters.company, "default_currency")
    territory_list = get_territories()
    group_list = get_item_groups()
    # prepare forcast:
    if cint(date.today().year) > cint(filters.fiscal_year):
        elapsed_month = 12          # the reporting year is complete
    else:
        elapsed_month = date.today().month - 1
    
    output = []
    group_count = 0
    total = {
        'description': "<b>TOTAL</b>",
        'ytd': 0,
        'fc': 0
    }
    for m in range (1, 13):
        key = 'month{0}'.format(m)
        total[key] = 0
    # create matrix
    for group in group_list:
        color = COLOURS[group_count if group_count < len(COLOURS) else (len(COLOURS) - 1)]
        group_sums = {
            'description': """<span style="color: {color}; "><b>{group}</b></span>""".format(color=color, group=group),
            'ytd': 0,
            'fc': 0,
            'currency': filters.reporting_type
        }
        for territory in territory_list:
            _revenue = {
                'description': """<span style="color: {color}; ">{territory}</span>""".format(color=color, territory=territory)
            }
            ytd = 0
            base = 0
            for m in range (1, 13):
                key = 'month{0}'.format(m)
                _revenue[key] = get_revenue(filters, m, territory, group)[filters.reporting_type.lower()]
                if not key in group_sums:
                    group_sums[key] = _revenue[key]
                else:
                    group_sums[key] += _revenue[key]
                ytd += _revenue[key]
                if m <= elapsed_month:
                    base += _revenue[key]
            _revenue['ytd'] = ytd
            _revenue['fc'] = (12 * base / elapsed_month) if elapsed_month > 0 else 0
            _revenue['currency'] = filters.reporting_type
            
            # add each territory
            output.append(_revenue)
            
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
        
def get_revenue(filters, month, territory, item_group):
    company = "%"
    if filters.company:
        company = filters.company
    first_last_day = calendar.monthrange(cint(filters.fiscal_year), month)
    invoices = frappe.db.sql("""
            SELECT 
                `tabSales Invoice Item`.`base_net_amount`, 
                `tabSales Invoice`.`company`
            FROM `tabSales Invoice Item`
            LEFT JOIN `tabSales Invoice` ON `tabSales Invoice Item`.`parent` = `tabSales Invoice`.`name`
            WHERE 
                `tabSales Invoice`.`docstatus` = 1
                AND `tabSales Invoice`.`company` LIKE "{company}"
                AND `tabSales Invoice`.`posting_date` BETWEEN "{year}-{month:02d}-{from_day:02d}" AND "{year}-{month:02d}-{to_day:02d}"
                AND `tabSales Invoice`.`territory` = "{territory}"
                AND `tabSales Invoice Item`.`item_group` = "{item_group}"
            ;
        """.format(company=company, year=filters.fiscal_year, month=month, from_day=first_last_day[0], to_day=first_last_day[1],
            territory=territory, item_group=item_group)
        , as_dict=True)
    
    exchange_rate = frappe.db.sql("""
        SELECT IFNULL(`exchange_rate`, 1) AS `exchange_rate`
        FROM `tabCurrency Exchange`
        WHERE `date` LIKE "{year}-{month:02d}-%"
          AND `from_currency` = "EUR"
          AND `to_currency` = "CHF"
        ;
    """.format(year=filters.fiscal_year, month=month), as_dict=True)
    if len(exchange_rate) > 0:
        exchange_rate = exchange_rate[0]['exchange_rate']
    else:
        exchange_rate = 1
    
    company_currency = {}
    for c in frappe.get_all("Company", fields=['name', 'default_currency']):
        company_currency[c['name']] = c['default_currency']
        
    revenue = {'eur': 0, 'chf': 0}
    for i in invoices:
        if company_currency[i['company']] == "CHF":
            revenue['chf'] += i['base_net_amount']
            revenue['eur'] += i['base_net_amount'] * exchange_rate
        else:
            revenue['chf'] += i['base_net_amount'] / exchange_rate
            revenue['eur'] += i['base_net_amount'] 
    
    return revenue

def get_territories():
    terr = frappe.get_all("Territory", filters={'is_group': 0}, fields=['name'])
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
            group_list.append(g['name'])
    group_list.sort()
    return group_list
