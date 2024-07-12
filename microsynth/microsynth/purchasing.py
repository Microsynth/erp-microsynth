# -*- coding: utf-8 -*-
# Copyright (c) 2024, Microsynth
# For license information, please see license.txt
# For more details, refer to https://github.com/Microsynth/erp-microsynth/

import frappe
from frappe.desk.form.assign_to import add


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
def create_approval_request(assign_to, dt, dn):
    if not is_already_assigned(dt, dn):
        add({
            'doctype': dt,
            'name': dn,
            'assign_to': assign_to,
            'description': f"Please check the {dt} {dn}. Submit {dn} to approve.",
            'notify': True  # Send email
        })
        if dt == "Purchase Invoice":
            purchase_invoice = frappe.get_doc(dt, dn)
            #if (not purchase_invoice.approver) or purchase_invoice.approver == '':
            purchase_invoice.approver = assign_to
            purchase_invoice.in_approval = 1
            purchase_invoice.save()
        return True
    else:
        return False


def assign_purchase_invoices():
    """
    Get all Draft Purchase Invoices with an approver.
    Assign those that are not yet assigned to the specified approver.

    Should be executed daily by a cronjob.

    bench execute microsynth.microsynth.purchasing.assign_purchase_invoices
    """
    sql_query = """
        SELECT `tabPurchase Invoice`.`name`,
            `tabPurchase Invoice`.`approver`
        FROM `tabPurchase Invoice`
        WHERE `tabPurchase Invoice`.`docstatus` = 0
            AND `tabPurchase Invoice`.`approver` IS NOT NULL;
        """
    purchase_invoices = frappe.db.sql(sql_query, as_dict=True)
    for pi in purchase_invoices:
        assigned = create_approval_request(pi['approver'], "Purchase Invoice", pi['name'])
        if assigned:
            print(f"Assigned {pi['name']} to {pi['approver']}.")