# -*- coding: utf-8 -*-
# Copyright (c) 2022, libracore (https://www.libracore.com) and contributors
# For license information, please see license.txt

import frappe

NAMING_SERIES_MAP = {
    'Sales Order': {
		'Microsynth AG': 'SO-BAL-.YY.######',
		'Microsynth Seqlab GmbH': 'SO-GOE-.YY.######',
		'Microsynth Austria GmbH': 'SO-WIE-.YY.######',
		'Microsynth France SAS': 'SO-LYO-.YY.######',
		'Ecogenics GmbH': 'SO-ECO-.YY.######'
	}
}

"""
Returns the naming series according to doctype and optionally company 
"""
@frappe.whitelist()
def get_naming_series(doctype, company=None):
	if company:
		return NAMING_SERIES_MAP[doctype][company]
	else:
		return NAMING_SERIES_MAP[doctype]
