# -*- coding: utf-8 -*-
# Copyright (c) 2024, Microsynth, libracore and contributors
# For license information, please see license.txt

import frappe
from frappe.utils.password import get_decrypted_password
import hashlib
from datetime import datetime
from frappe import _


@frappe.whitelist()
def sign(dt, dn, user, password):
    if user != frappe.session.user:
        frappe.throw( _("Invalid approval user!"), _("Authentication failed") )
        return False
    # check password 
    if password == get_decrypted_password("Signature", user, "approval_password", False):
        # password correct
        doc = frappe.get_doc(dt, dn)
        doc.signature = get_signature(user)
        doc.save()
        doc.submit()
        return True
    else:
        # wrong password
        frappe.throw( _("Invalid approval password!"), _("Authentication failed") )
        return False


def get_signature(user):
    s = "{d}/{u}".format(d=datetime.now(), u=user)
    signature = "{s} ({h})".format(s=s, h=abs(hash(s)))
    return signature
    
