# -*- coding: utf-8 -*-
# Copyright (c) 2022, libracore (https://www.libracore.com) and contributors
# For license information, please see license.txt

import frappe

NAMING_SERIES_MAP = {
    'Standing Quotation': {
        'Microsynth AG': 'SQ-.YY.#####',
        'Microsynth Seqlab GmbH': 'SQ-.YY.#####',
        'Microsynth Austria GmbH': 'SQ-.YY.#####',
        'Microsynth France SAS': 'SQ-.YY.#####',
        'Ecogenics GmbH': 'SQ-.YY.#####'
    },
    'Quotation': {
        'Microsynth AG': 'QTN-.YY.#####',
        'Microsynth Seqlab GmbH': 'QTN-.YY.#####',
        'Microsynth Austria GmbH': 'QTN-.YY.#####',
        'Microsynth France SAS': 'QTN-.YY.#####',
        'Ecogenics GmbH': 'QTN-.YY.#####'
    },
    'Sales Order': {
        'Microsynth AG': 'SO-BAL-.YY.######',
        'Microsynth Seqlab GmbH': 'SO-GOE-.YY.######',
        'Microsynth Austria GmbH': 'SO-WIE-.YY.######',
        'Microsynth France SAS': 'SO-LYO-.YY.######',
        'Ecogenics GmbH': 'SO-ECO-.YY.######'
    },
    'Delivery Note': {
        'Microsynth AG': 'DN-BAL-.YY.######',
        'Microsynth Seqlab GmbH': 'DN-GOE-.YY.######',
        'Microsynth Austria GmbH': 'DN-WIE-.YY.######',
        'Microsynth France SAS': 'DN-LYO-.YY.######',
        'Ecogenics GmbH': 'DN-ECO-.YY.######'
    },
    'Sales Invoice': {
        'Microsynth AG': 'SI-BAL-.YY.######',
        'Microsynth Seqlab GmbH': 'SI-GOE-.YY.######',
        'Microsynth Austria GmbH': 'SI-WIE-.YY.######',
        'Microsynth France SAS': 'SI-LYO-.YY.######',
        'Ecogenics GmbH': 'SI-ECO-.YY.######'
    },
    'Credit Note': {
        'Microsynth AG': 'CN-BAL-.YY.######',
        'Microsynth Seqlab GmbH': 'CN-GOE-.YY.######',
        'Microsynth Austria GmbH': 'CN-WIE-.YY.######',
        'Microsynth France SAS': 'CN-LYO-.YY.######',
        'Ecogenics GmbH': 'CN-ECO-.YY.######'
    },
    'Material Request': {
        'Microsynth AG': 'MR-.YY.#####',
        'Microsynth Seqlab GmbH': 'MR-.YY.#####',
        'Microsynth Austria GmbH': 'MR-.YY.#####',
        'Microsynth France SAS': 'MR-.YY.#####',
        'Ecogenics GmbH': 'MR-.YY.######'
    },
    'Purchase Order': {
        'Microsynth AG': 'PO-.YY.#####',
        'Microsynth Seqlab GmbH': 'PO-.YY.#####',
        'Microsynth Austria GmbH': 'PO-.YY.#####',
        'Microsynth France SAS': 'PO-.YY.#####',
        'Ecogenics GmbH': 'PO-ECO-.YY.#####'
    },
    'Purchase Receipt': {
        'Microsynth AG': 'PR-.YY.#####',
        'Microsynth Seqlab GmbH': 'PR-.YY.#####',
        'Microsynth Austria GmbH': 'PR-.YY.#####',
        'Microsynth France SAS': 'PR-.YY.#####',
        'Ecogenics GmbH': 'PR-.YY.#####'
    },
    'Purchase Invoice': {
        'Microsynth AG': 'PI-.YY.#####',
        'Microsynth Seqlab GmbH': 'PI-.YY.#####',
        'Microsynth Austria GmbH': 'PI-.YY.#####',
        'Microsynth France SAS': 'PI-.YY.#####',
        'Ecogenics GmbH': 'PI-.YY.#####'
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
