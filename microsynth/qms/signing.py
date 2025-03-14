# -*- coding: utf-8 -*-
# Copyright (c) 2024, Microsynth, libracore and contributors
# For license information, please see license.txt

import frappe
from frappe.utils.password import get_decrypted_password
from frappe.utils.password import check_password
from datetime import datetime
from frappe import _


@frappe.whitelist()
def check_approval_password(user, password):
    if user != frappe.session.user:
        # not allowed to check foreign approval password
        return False

    # verify that approval password is set
    approval_password = get_decrypted_password("Signature", user, "approval_password", False)
    if not approval_password:
        return False
        
    # check password 
    return password == approval_password


@frappe.whitelist()
def sign(dt, dn, user, password, target_field=None, submit=True):
    if user != frappe.session.user:
        frappe.throw( _("Invalid approval user!"), _("Authentication failed") )
        return False
    
    # verify that approval password is set
    approval_password = get_decrypted_password("Signature", user, "approval_password", False)
    if not approval_password:
        frappe.throw( _("Approval password is not set! Please go to Signature and set the approval password."), _("Authentication failed") )
        return False

    # check password 
    if password == approval_password:
        # password correct

        # check that approval password does not match login password
        password_match_with_login_pw = True
        try:
            check_password(user, approval_password)
        except Exception as err:
            # password failed - this is good, the passwords are different
            password_match_with_login_pw = False
        if password_match_with_login_pw:
            frappe.throw( _("Signing failed: Your approval password is identical to your login password.<br>Please change one of them and try again."), _("Authentication failed") )
            return False

        doc = frappe.get_doc(dt, dn)
        if target_field and target_field in doc.as_dict():
            signature = {}
            signature[target_field] = get_signature(user)
            doc.update(signature)
        else:
            doc.signature = get_signature(user)
        doc.save()
        if submit:
            doc.submit()
        frappe.db.commit()
        return True
    else:
        # wrong password
        frappe.throw( _("Invalid approval password!"), _("Authentication failed") )
        return False


def get_signature(user):
    s = "{d}/{u}".format(d=datetime.now(), u=user)
    signature = "{s} ({h})".format(s=s, h=abs(hash(s)))
    return signature
    
