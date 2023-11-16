# -*- coding: utf-8 -*-
# Copyright (c) 2023, libracore (https://www.libracore.com) and contributors
# For license information, please see license.txt

import frappe
import socket
import sys
from datetime import datetime

from frappe.model.mapper import get_mapped_doc

@frappe.whitelist()
def make_quotation(contact_name):

    doc = get_mapped_doc(
        "Contact", 
        contact_name, 
        {"Contact": { "doctype": "Quotation"}})

    doc.party_name = "8003"
    doc.contact_person = contact_name
    doc.company = "Microsynth Seqlab GmbH" # Customer.default_company

    return doc