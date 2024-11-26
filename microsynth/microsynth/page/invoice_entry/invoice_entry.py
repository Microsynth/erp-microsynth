# Copyright (c) 2024, Microsynth, libracore and contributors
# For license information, please see license.txt

import frappe
from frappe import _
import json
from datetime import datetime

FORMAT_MAPPER = {
    'dd.mm.yyyy': '%d.%m.%Y',
    'yyyy-mm-dd': '%Y-%m-%d',
    'dd-mm-yyyy': '%d-%m-%Y',
    'dd/mm/yyyy': '%d/%m/%Y',
    'mm/dd/yyyy': '%m/%d/%Y',
    'mm-dd-yyyy': '%m-%d-%Y'
}

@frappe.whitelist()
def get_purchase_invoice_drafts():
    # find purchase invoice drafts
    pinvs = frappe.db.sql(f"""
        SELECT 
            `tabPurchase Invoice`.`name`,
            `tabPurchase Invoice`.`company`,
            `tabPurchase Invoice`.`supplier`,
            `tabPurchase Invoice`.`supplier_name`,
            `tabPurchase Invoice`.`posting_date`,
            `tabPurchase Invoice`.`due_date`,
            `tabPurchase Invoice`.`net_total`,
            `tabPurchase Invoice`.`total`,
            `tabPurchase Invoice`.`grand_total`,
            `tabPurchase Invoice`.`taxes_and_charges`,
            `tabPurchase Invoice`.`total_taxes_and_charges`,
            `tabPurchase Invoice`.`currency`,
            `tabPurchase Invoice`.`bill_no`,
            `tabPurchase Invoice Item`.`expense_account`,
            `tabPurchase Invoice Item`.`cost_center`,
            `tabSupplier`.`iban`,
            `tabSupplier`.`esr_participation_number`,
            `tabSupplier`.`default_payment_method`,
            `tabPurchase Invoice`.`approver`,
            `tabPurchase Invoice`.`remarks`
        FROM `tabPurchase Invoice`
        LEFT JOIN `tabPurchase Invoice Item` ON `tabPurchase Invoice Item`.`parent` = `tabPurchase Invoice`.`name`
        LEFT JOIN `tabSupplier` ON `tabSupplier`.`name` = `tabPurchase Invoice`.`supplier`
        WHERE
            `tabPurchase Invoice`.`docstatus` = 0
            AND `tabPurchase Invoice`.`name` NOT IN (
                SELECT `tabToDo`.`reference_name`
                FROM `tabToDo`
                WHERE 
                    `tabToDo`.`reference_type` = "Purchase Invoice"
                    AND `tabToDo`.`status` = "Open"
            )
        GROUP BY `tabPurchase Invoice`.`name`
        ORDER BY `tabPurchase Invoice`.`name` ASC
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


@frappe.whitelist()
def save_document(doc):
    if type(doc) == str:
        doc = json.loads(doc)
    
    d = frappe.get_doc("Purchase Invoice", doc.get('name'))
    d.supplier = doc.get('supplier')
    # date field: parse back from human-friendly format
    date_format = FORMAT_MAPPER[frappe.get_cached_value("System Settings", "System Settings", "date_format")]
    # prepare document fields
    d.set_posting_time = 1
    d.payment_terms_template = None
    d.payment_schedule = []
    
    target_values = {
        'posting_date': datetime.strptime(doc.get('posting_date'), date_format).strftime("%Y-%m-%d"),
        'due_date': datetime.strptime(doc.get('due_date'), date_format).strftime("%Y-%m-%d"),
        'bill_no': doc.get('bill_no'),
        'approver': doc.get('approver'),
        'remarks': doc.get('remarks')
    }
    d.update(target_values)
    
    try:
        d.save()
        frappe.db.commit()
        
        deviations = []
        for k,v in target_values.items():
            if (d.get(k) or "") != target_values[k]:
                deviations.append(k)
        if len(deviations) > 0:
            frappe.throw("Invalid input detected: {0}".format(deviations) )
            
        return "Saved."
    except Exception as err:
        return err


@frappe.whitelist()
def delete_document(purchase_invoice_name):    
    doc = frappe.get_doc("Purchase Invoice", purchase_invoice_name)
    try:
        doc.delete()
        frappe.db.commit()
        return f"Deleted {purchase_invoice_name}. Reloading page ..."
    except Exception as err:
        return err
