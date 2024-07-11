# -*- coding: utf-8 -*-
# Copyright (c) 2024, Microsynth
# For license information, please see license.txt
# For more details, refer to https://github.com/Microsynth/erp-microsynth/

import frappe


def is_already_assigned(dt, dn):
    if frappe.db.sql(f"""SELECT `owner`
        FROM `tabToDo`
        WHERE `reference_type`= '{dt}'
            AND `reference_name`= '{dn}'
            AND `status`='Open'
        ;""", frappe.local.form_dict):
        return True
    else:
        return False


@frappe.whitelist()
def create_approval_request(approver, dt, dn):
    from frappe.desk.form.assign_to import add
    if not is_already_assigned(dt, dn):
        add({
            'doctype': dt,
            'name': dn,
            'assign_to': approver,
            'description': f"Please check the Purchase Invoice {dn}. Submit {dn} to approve.",
            'notify': True
        })
        return True
    else:
        return False