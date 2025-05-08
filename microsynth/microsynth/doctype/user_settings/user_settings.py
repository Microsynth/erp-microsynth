# -*- coding: utf-8 -*-
# Copyright (c) 2024, Microsynth, libracore and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document

class UserSettings(Document):
	pass


@frappe.whitelist()
def disable_user_settings(email):
    if frappe.db.exists("User Settings", email):
        user_settings_doc = frappe.get_doc("User Settings", email)
        if not user_settings_doc.disabled:
             user_settings_doc.disabled = 1
        user_settings_doc.save()
