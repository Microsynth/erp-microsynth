# Copyright (c) 2023, Microsynth, libracore and contributors and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
from microsynth.microsynth.report.sales_overview.sales_overview import get_revenue_details, get_ngs_groups, get_genetic_analysis_groups

def execute(filters=None):
    columns = get_columns(filters)
    data = get_data(filters)
    return columns, data

def get_columns(filters):
    columns = [
        {"label": _("Document"), "fieldname": "document", "fieldtype": "Link", "options": "Sales Invoice", "width": 150},
        {"label": _("Base net amount"), "fieldname": "base_net_amount", "fieldtype": "Currency", "options": "base_currency", "width": 120},
        {"label": _("CHF"), "fieldname": "chf", "fieldtype": "Currency", "options": "currency_chf", "width": 120},
        {"label": _("EUR"), "fieldname": "eur", "fieldtype": "Currency", "options": "currency_eur", "width": 120},
        {"label": _("Company"), "fieldname": "company", "fieldtype": "Link", "options": "Company", "width": 175},
        {"label": _("Remarks"), "fieldname": "remarks", "fieldtype": "Data", "width": 250}
    ]

    return columns

def get_data(filters):
    if filters.get("item_groups") == "3.67 NGS":
        query_groups = get_ngs_groups()
    elif filters.get("item_groups") == "Genetic Analysis":
        query_groups = get_genetic_analysis_groups()
    else:
        query_groups = [ filters.get("item_groups") ]
    data = get_revenue_details(filters, month=filters.get('month'), item_groups=query_groups, debug=False)
    return data
    
