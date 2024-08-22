# Copyright (c) 2024, Microsynth, libracore and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
from microsynth.microsynth.report.pricing_configurator.pricing_configurator import get_data as pricing_configurator_get_data


def get_columns(filters):
    if filters and filters.get('reference_price_list') and filters.get('price_list'):
        reference_currency = frappe.get_value("Price List", filters.get('reference_price_list'), "currency")
        price_list_currency = frappe.get_value("Price List", filters.get('price_list'), "currency")
        return [
            {"label": _("Item code"), "fieldname": "item_code", "fieldtype": "Link", "options": "Item", "width":60},
            {"label": _("Item name"), "fieldname": "item_name", "fieldtype": "Data", "width": 370},
            {"label": _("Item Group"), "fieldname": "item_group", "fieldtype": "Link", "options": "Item Group", "width": 150},
            {"label": _("Qty"), "fieldname": "qty", "fieldtype": "Int", "width": 60},
            {"label": _("UOM"), "fieldname": "uom", "fieldtype": "Link", "options": "UOM", "width": 50},
            {"label": "{0} [{1}]".format(_("Rate 1"), reference_currency), "fieldname": "reference_rate", "fieldtype": "Float", "precision": 2, "width": 90},
            {"label": "{0} [{1}]".format(_("Rate 2"), price_list_currency), "fieldname": "price_list_rate", "fieldtype": "Float", "precision": 2, "width": 90},
            {"label": _("Difference"), "fieldname": "discount", "fieldtype": "Percent", "precision": 2, "width": 80}
        ]
    else:
        return []


def get_data(filters):
    data = pricing_configurator_get_data(filters)
    for d in data:
        if d['discount']:
            d['discount'] = d['discount'] * (-1)
    return data


def execute(filters=None):
    columns = get_columns(filters)
    data = get_data(filters)
    return columns, data