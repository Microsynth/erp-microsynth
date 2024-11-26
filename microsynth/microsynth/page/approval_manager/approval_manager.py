# -*- coding: utf-8 -*-
# Copyright (c) 2023, libracore and contributors
# License: AGPL v3. See LICENCE

import frappe
from frappe import _
from frappe.desk.form.assign_to import add, clear
from frappe.utils import cint


@frappe.whitelist()
def get_approvals(user):
    # find assigned purchase invoices
    pinvs = frappe.db.sql(f"""
        SELECT 
            `tabPurchase Invoice`.`name`,
            `tabPurchase Invoice`.`supplier`,
            `tabPurchase Invoice`.`supplier_name`,
            `tabPurchase Invoice`.`posting_date`,
            `tabPurchase Invoice`.`due_date`,
            `tabPurchase Invoice`.`net_total`,
            `tabPurchase Invoice`.`grand_total`,
            `tabPurchase Invoice`.`total_taxes_and_charges`,
            `tabPurchase Invoice`.`currency`,
            `tabPurchase Invoice`.`bill_no`,
            `tabPurchase Invoice Item`.`expense_account`,
            `tabPurchase Invoice Item`.`cost_center`,
            `tabPurchase Invoice`.`remarks`
        FROM `tabToDo`
        LEFT JOIN `tabPurchase Invoice` ON `tabPurchase Invoice`.`name` = `tabToDo`.`reference_name`
        LEFT JOIN `tabPurchase Invoice Item` ON `tabPurchase Invoice Item`.`parent` = `tabPurchase Invoice`.`name`
        WHERE `tabPurchase Invoice`.`docstatus` = 0
            AND `tabToDo`.`owner` = "{user}"
            AND `tabToDo`.`reference_type` = "Purchase Invoice"
            AND `tabToDo`.`status` = "Open"
        GROUP BY `tabPurchase Invoice`.`name`
        ORDER BY `tabPurchase Invoice`.`due_date` ASC, `tabPurchase Invoice`.`name` ASC
        ;
        """, as_dict=True)

    # extend attachments
    for pinv in pinvs:
        pinv['attachments'] = frappe.db.sql("""
            SELECT *
            FROM `tabFile`
            WHERE 
                `attached_to_doctype` = "Purchase Invoice"
                AND `attached_to_name` = "{pinv}"
            ;""".format(pinv=pinv['name']), as_dict=True)
        # reformat values for output
        pinv['posting_date'] = frappe.utils.get_datetime(pinv['posting_date']).strftime("%d.%m.%Y")
        pinv['due_date'] = frappe.utils.get_datetime(pinv['due_date']).strftime("%d.%m.%Y")
        pinv['net_total'] = "{:,.2f}".format(pinv['net_total']).replace(",", "'")
        pinv['grand_total'] = "{:,.2f}".format(pinv['grand_total']).replace(",", "'")

        # render html
        pinv['html'] = frappe.render_template("microsynth/microsynth/page/approval_manager/document.html", pinv)

    return pinvs


@frappe.whitelist()
def approve(pinv, user):
    # clear assignment
    clear("Purchase Invoice", pinv)
    # submit document
    pinv_doc = frappe.get_doc("Purchase Invoice", pinv)
    # check if supplier has LSV/direct debit enabled, if so, mark invoice to not propose it for payment
    if cint(frappe.get_value("Supplier", pinv_doc.supplier, "direct_debit_enabled")):
        pinv_doc.is_proposed = 1
        pinv_doc.save()
    pinv_doc.submit()
    add_comment(pinv, _("Approval"), _("Approved"), user)
    frappe.db.commit()


@frappe.whitelist()
def reassign(pinv, user, reason, new_assignee):
    add_comment(pinv, _("Reassign"), reason, user)
    # clear assignment
    clear("Purchase Invoice", pinv)
    pinv_doc = frappe.get_doc("Purchase Invoice", pinv)
    pinv_doc.approver = new_assignee
    pinv_doc.save()
    description = f"Reason: {reason}" if reason else ""
    add({
            'doctype': "Purchase Invoice",
            'name': pinv,
            'assign_to': new_assignee,
            'description': f'{description}\nPlease check it in the <a href="https://erp.microsynth.local/desk#approval-manager">Approval Manager</a>.',
            'notify': True
        })


@frappe.whitelist()
def reject(pinv, user, reason):
    add_comment(pinv, _("Reject"), reason, user)
    # clear assignment
    clear("Purchase Invoice", pinv)
    pinv_doc = frappe.get_doc("Purchase Invoice", pinv)
    pinv_doc.reject_message = reason
    pinv_doc.save()
    return


def add_comment(pinv, subject, comment, user):
    new_comment = frappe.get_doc({
        'doctype': "Comment",
        'comment_type': "Comment",
        'subject': subject,
        'content': comment,
        'reference_doctype': "Purchase Invoice",
        'reference_name': pinv,
        'modified_by': user,
        'owner': user
    })
    new_comment.insert(ignore_permissions=True)
    frappe.db.commit()
