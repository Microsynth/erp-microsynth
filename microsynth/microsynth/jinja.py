# -*- coding: utf-8 -*-
# Copyright (c) 2022, libracore (https://www.libracore.com) and contributors
# For license information, please see license.txt

import frappe
from microsynth.microsynth.report.pricing_configurator.pricing_configurator import get_rate

"""
Jinja endpoint to get pricelist rate and reference rate for an item
"""
def get_price_list_rate(item_code, price_list):
    data = {
        'rate': get_rate(item_code, price_list),
        'reference_rate': get_rate(item_code, frappe.get_value("Price List", price_list, "reference_price_list"))
    }
    return data
