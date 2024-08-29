# Copyright (c) 2024, Microsynth, libracore and contributors
# For license information, please see license.txt

import frappe
from frappe import _


@frappe.whitelist()
def get_purchase_invoice_drafts():
    # find purchase invoice drafts
    pinvs = frappe.db.sql(f"""
        SELECT 
            `tabPurchase Invoice`.`name`,
            `tabPurchase Invoice`.`supplier`,
            `tabPurchase Invoice`.`supplier_name`,
            `tabPurchase Invoice`.`posting_date`,
            `tabPurchase Invoice`.`due_date`,
            `tabPurchase Invoice`.`net_total`,
            `tabPurchase Invoice`.`grand_total`,
            `tabPurchase Invoice`.`currency`,
            `tabPurchase Invoice`.`bill_no`,
            `tabPurchase Invoice Item`.`expense_account`,
            `tabPurchase Invoice Item`.`cost_center`,
            `tabPurchase Invoice`.`remarks`
        FROM `tabPurchase Invoice`
        LEFT JOIN `tabPurchase Invoice Item` ON `tabPurchase Invoice Item`.`parent` = `tabPurchase Invoice`.`name`
        WHERE
            `tabPurchase Invoice`.`docstatus` = 0
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
        pinv['html'] = frappe.render_template("microsynth/microsynth/page/invoice_entry/document.html", pinv)

    return pinvs


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
