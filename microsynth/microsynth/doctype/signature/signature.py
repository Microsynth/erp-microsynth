# -*- coding: utf-8 -*-
# Copyright (c) 2022-2024, Microsynth, libracore and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document
from frappe.utils.password import check_password
from frappe import _
from frappe.core.doctype.user.user import test_password_strength
from frappe.utils.password import get_decrypted_password

class Signature(Document):
    def change_approval_password(self, new_pw, retype_new_pw, old_pw=None):
        # compare new PWs
        if new_pw != retype_new_pw:
            return {'error': _("The new passwords differ. Please try again.")}
        
        # surpass old password check for system managers and QMS
        if not user_has_role(frappe.session.user, "System Manager") and not user_has_role(frappe.session.user, "QAU"):
            # verify old password
            db_old_pw = get_decrypted_password("Signature", self.name, "approval_password", False)
            if db_old_pw and db_old_pw != old_pw:
                return {'error': _("The old passwords is not correct. Please try again.")}
        
        # check that approval password does not match login password
        password_match_with_login_pw = True
        try:
            check_password(self.user, new_pw)
        except Exception as err:
            # password failed - this is good, the passwords are different
            password_match_with_login_pw = False
        if password_match_with_login_pw:
            return {'error': _("Your approval password must be different from the login password")}
        
        # check strength
        strength = test_password_strength(new_password=new_pw, old_password=old_pw)
        if not strength['feedback']['password_policy_validation_passed']:
            return {'error': _("The new password does not match the security policy. Please try again.") + " " + (strength['feedback']['warning'] or "")}
        
        # set new password
        self.approval_password = new_pw
        self.save(ignore_permissions=True)
        return {'success': True}


    def reset_approval_password(self, resetting_user):
        if resetting_user != frappe.session.user:
            frappe.throw(f"{resetting_user=} != {frappe.session.user=}. Please tell the IT App group how you did this.")
        if not user_has_role(frappe.session.user, "QAU"):
            frappe.throw(f"Only user with QAU role are allowed to reset the Approval Password.")
        self.approval_password = ""
        self.save()


def user_has_role(user, role):
    """
    Check if a user has a role
    """
    role_matches = frappe.db.sql("""
        SELECT `parent`, `role`
        FROM `tabHas Role`
        WHERE `parent` = "{user}"
          AND `role` = "{role}"
          AND `parenttype` = "User";
        """.format(user=user, role=role), as_dict=True)
    
    if len(role_matches) > 0:
        return True
    else:
        return False


@frappe.whitelist()
def is_password_approval_password(user, password):
    approval_pw = get_decrypted_password("Signature", user, "approval_password", False)
    if password == approval_pw:
        return True
    else:
        return False
    
