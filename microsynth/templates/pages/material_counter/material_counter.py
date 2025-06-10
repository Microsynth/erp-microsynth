# -*- coding: utf-8 -*-
# Copyright (c) 2025, Microsynth, libracore and contributors
# For license information, please see license.txt

import frappe


@frappe.whitelist(allow_guest=True)
def get_processes():
    """
    return a list of all QM Processes
    TODO: flag those QM Processes that need to use the Material Counter page
    """
    processes = frappe.get_all("QM Process", fields=['name'])
    return [''] + [p['name'] for p in processes]