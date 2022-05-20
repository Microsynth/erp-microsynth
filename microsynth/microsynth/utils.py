# -*- coding: utf-8 -*-
# Copyright (c) 2022, libracore (https://www.libracore.com) and contributors
# For license information, please see license.txt

import frappe

def create_oligo(oligo):
    # check if this oligo is already in the database
    if oligo['oligo_web_id']:
        oligo_matches = frappe.get_all("Oligo", 
            filters={'web_id': oligo['oligo_web_id']}, fields=['name'])
        if len(oligo_matches) > 0:
            # update and return this item
            oligo_doc = frappe.get_doc("Oligo", oligo_matches[0]['name'])
            oligo_doc.oligo_name = oligo['name']
            oligo_doc.save(ignore_permissions=True)
            return oligo_doc.name
    # create oligo
    oligo_doc = frappe.get_doc({
        'doctype': 'Oligo',
        'oligo_name': oligo['name'],
        'web_id': oligo['oligo_web_id']
    })
    oligo_doc.insert(ignore_permissions=True)
    return oligo_doc.name
