# Copyright (c) 2023, Microsynth, libracore and contributors and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _

def execute(filters=None):
    columns = get_columns(filters)
    data = get_data(filters)
    return columns, data

def get_columns(filters):
    columns = [
        {"label": _("Month"), "fieldname": "month", "fieldtype": "Int", "width": 80},
        {"label": filters.fiscal_year_1, "fieldname": "year_1", "fieldtype": "Currency", "options": "currency", "width": 150},
        {"label": filters.fiscal_year_2, "fieldname": "year_2", "fieldtype": "Currency", "options": "currency", "width": 150},
        {"label": _("Total"), "fieldname": "total", "fieldtype": "Currency", "options": "currency", "width": 150},
        {"label": _("Currency"), "fieldname": "currency", "fieldtype": "Data", "hidden": 1, "width": 50},
        {"label": "", "fieldname": "blank", "fieldtype": "Data", "width": 20}
    ]
    return columns

def get_data(filters):
    currency = frappe.get_cached_value("Company", filters.company, "default_currency")
    output = []

    for month in range(1, 13):
        revenue_year_1 = get_revenue(filters, filters.fiscal_year_1, month)
        revenue_year_2 = get_revenue(filters, filters.fiscal_year_2, month)
        output.append({
            'month': month,
            'year_1': revenue_year_1,
            'year_2': revenue_year_2,
            'total': revenue_year_1 + revenue_year_2,
            'currency': currency
        })

    return output

def get_revenue(filters, year, month):
    conditions = ""
    if filters.territory:
        conditions += """ AND `tabSales Invoice`.`territory` = "{territory}" """.format(territory=filters.territory)
    if filters.account_manager:
        conditions += """ AND `tabCustomer`.`account_manager` = "{manager}" """.format(manager=filters.account_manager)
    if filters.product_type:
        conditions += """ AND `tabSales Invoice`.`product_type` = "{product_type}" """.format(product_type=filters.product_type)

    sql_query = """
        SELECT IFNULL(SUM(`base_net_total`), 0) AS `revenue`
        FROM `tabSales Invoice`
        LEFT JOIN `tabCustomer` ON `tabCustomer`.`name` = `tabSales Invoice`.`customer`
        WHERE
            `tabSales Invoice`.`docstatus` = 1
            AND `tabSales Invoice`.`company` = "{company}"
            AND `tabSales Invoice`.`posting_date` LIKE "{year}-{month:02d}-%"
            {conditions}
        ;
    """.format(company=filters.company, year=year, month=month, conditions=conditions)

    revenue = frappe.db.sql(sql_query, as_dict=True)[0]['revenue']

    return revenue
