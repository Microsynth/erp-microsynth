# -*- coding: utf-8 -*-
# Copyright (c) 2022-2024, Microsynth, libracore and contributors and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document
from frappe.utils.password import check_password
from frappe import _

class Signature(Document):
    def validate(self):
        # if the password has not been updated, skip check
        if self.approval_password.startswith("***"):
            return
        
        password_match_with_login_pw = True
        try:
            check_password(self.user, self.approval_password)
        except Exception as err:
            # password failed - this is good, the passwords are different
            password_match_with_login_pw = False
            
        if password_match_with_login_pw:
            frappe.throw( _("Your approval password must be different from the login password"), _("Validation") )

        return

