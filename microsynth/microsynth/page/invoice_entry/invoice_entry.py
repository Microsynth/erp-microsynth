# Copyright (c) 2024, Microsynth, libracore and contributors
# For license information, please see license.txt

import frappe
from frappe import _
import json
from datetime import datetime, date
from frappe.utils import flt, add_days
from microsynth.microsynth.purchasing import supplier_change_fetches

FORMAT_MAPPER = {
    'dd.mm.yyyy': '%d.%m.%Y',
    'yyyy-mm-dd': '%Y-%m-%d',
    'dd-mm-yyyy': '%d-%m-%Y',
    'dd/mm/yyyy': '%d/%m/%Y',
    'mm/dd/yyyy': '%m/%d/%Y',
    'mm-dd-yyyy': '%m-%d-%Y'
}

@frappe.whitelist()
def get_purchase_invoice_drafts(purchase_invoice=None):
    # find purchase invoice drafts
    purchase_invoice_filter = f""" AND `tabPurchase Invoice`.`name` = "{purchase_invoice}" """ if purchase_invoice else ""
    pinvs = frappe.db.sql(f"""
        SELECT 
            `tabPurchase Invoice`.`name`,
            `tabPurchase Invoice`.`company`,
            `tabPurchase Invoice`.`supplier`,
            `tabPurchase Invoice`.`supplier_name`,
            `tabPurchase Invoice`.`bill_date`,
            `tabPurchase Invoice`.`posting_date`,
            `tabPurchase Invoice`.`due_date`,
            `tabPurchase Invoice`.`net_total`,
            `tabPurchase Invoice`.`total`,
            `tabPurchase Invoice`.`grand_total`,
            `tabPurchase Invoice`.`taxes_and_charges`,
            `tabPurchase Invoice`.`total_taxes_and_charges`,
            `tabPurchase Invoice`.`currency`,
            `tabPurchase Invoice`.`bill_no`,
            `tabPurchase Invoice`.`reject_message`,
            `tabPurchase Invoice Item`.`expense_account`,
            `tabPurchase Invoice Item`.`cost_center`,
            `tabSupplier`.`iban`,
            `tabSupplier`.`esr_participation_number`,
            `tabPurchase Invoice`.`payment_type` AS `default_payment_method`,
            `tabPurchase Invoice`.`approver`,
            `tabPurchase Invoice`.`remarks`,
            CURDATE() AS `curdate`,
            COUNT(`tabPurchase Invoice Item`.`name`) AS `item_count`,
            SUM(`tabPurchase Invoice Item`.`qty`) AS `total_qty`
        FROM `tabPurchase Invoice`
        LEFT JOIN `tabPurchase Invoice Item` ON `tabPurchase Invoice Item`.`parent` = `tabPurchase Invoice`.`name`
        LEFT JOIN `tabSupplier` ON `tabSupplier`.`name` = `tabPurchase Invoice`.`supplier`
        WHERE
            `tabPurchase Invoice`.`docstatus` = 0
            { purchase_invoice_filter } 
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

        # define edit net flag from items and total qty
        if pinv['item_count'] == 1 and pinv['total_qty'] == 1:
            pinv['allow_edit_net_amount'] = 1
        else:
            pinv['allow_edit_net_amount'] = 0
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


def force_set_due_date(purchase_invoice_id, due_date):
    # necessary to circumvent the validation and enable free setting of due_date
    frappe.db.sql(f"""UPDATE `tabPurchase Invoice` 
                     SET `due_date` = '{due_date}' 
                     WHERE `name` = '{purchase_invoice_id}'""")


@frappe.whitelist()
def save_document(doc):
    if type(doc) == str:
        doc = json.loads(doc)

    # date field: parse back from human-friendly format
    date_format = FORMAT_MAPPER[frappe.get_cached_value("System Settings", "System Settings", "date_format")]
    
    d = frappe.get_doc("Purchase Invoice", doc.get('name'))
    if not doc.get('posting_date'):
        doc['posting_date'] = datetime.today().strftime(date_format)
    if not doc.get('bill_date'):
        doc['bill_date'] = doc['posting_date']
    if doc.get('due_date'):
        due_date = datetime.strptime(doc.get('due_date'), date_format).strftime("%Y-%m-%d")
    else:
        due_date = datetime.strptime(doc.get('posting_date'), date_format).strftime("%Y-%m-%d")

    if d.supplier != doc.get('supplier'):
        # Supplier change
        fetches = supplier_change_fetches(doc.get('supplier'), d.company)
        if fetches['default_approver']:
            d.default_approver = fetches['default_approver']
            if not doc.get('approver'):
                doc['approver'] = fetches['default_approver']
        if fetches['taxes_and_charges']:
            d.taxes_and_charges = fetches['taxes_and_charges']
            tax_template = frappe.get_doc("Purchase Taxes and Charges Template", d.taxes_and_charges)
            d.taxes = []
            for tax in tax_template.taxes:
                t = {
                    'category': tax.category,
                    'add_deduct_tax': tax.add_deduct_tax,
                    'charge_type': tax.charge_type,
                    'account_head': tax.account_head,
                    'description': tax.description,
                    'cost_center': tax.cost_center,
                    'rate': tax.rate
                }    
                d.append("taxes", t)
        if len(d.items) == 1:
            if fetches['default_item_code'] and fetches['default_item_name']:
                d.items[0].item_code = fetches['default_item_code']
                d.items[0].item_name = fetches['default_item_name']
            if fetches['expense_account']:
                d.items[0].expense_account = fetches['expense_account']
            if fetches['cost_center']:
                d.items[0].cost_center = fetches['cost_center']
        # define due date based on supplier payment terms (we do not rely on the payment terms copying, because that will prevent free setting of due date
        if d.posting_date and fetches['payment_terms_template']:
            template = frappe.get_doc("Payment Terms Template", fetches['payment_terms_template'])
            if len(template.terms) > 0:
                days = template.terms[0].credit_days
                due_date = add_days(d.posting_date, days)
            else:
                frappe.log_error(f"Payment Terms Template '{d.payment_terms_template}' has no Payment Terms. Please check due_date on Purchase Invoice {doc.get('name')}", "invoice_entry.save_document")

    d.supplier = doc.get('supplier')

    # prepare document fields
    d.set_posting_time = 1
    d.payment_terms_template = None
    d.payment_schedule = []

    target_values = {
        'bill_date': datetime.strptime(doc.get('bill_date'), date_format).strftime("%Y-%m-%d"),
        'posting_date': datetime.strptime(doc.get('posting_date'), date_format).strftime("%Y-%m-%d"),
        #'due_date': due_date,  # update directly in db after all other values are saved with validation to enable free setting
        'bill_no': doc.get('bill_no'),
        'approver': doc.get('approver'),
        'remarks': doc.get('remarks')
    }
    d.update(target_values)

    if doc.get('net_total'):
        rate = flt(doc.get('net_total').replace("'", "").replace(" ", ""))
        #frappe.throw("{0}: {1} from {2}".format(rate, type(rate), doc.get('net_total')))
        target_values['net_total'] = rate
        d.items[0].rate = rate

    try:
        d.save()
        frappe.db.commit()
        force_set_due_date(d.name, due_date)

        deviations = []
        for k,v in target_values.items():
            # convert to string before comparing to circumvent permission issue
            if str(d.get(k) or "") != str(target_values[k]):
                deviations.append(k)
        if len(deviations) > 0:
            frappe.throw("Invalid input detected: {0}".format(deviations) )

        return {'success': True, 'message': 'Saved.'}
    except Exception as err:
        return {'success': False, 'message': err}


@frappe.whitelist()
def delete_document(purchase_invoice_name):    
    doc = frappe.get_doc("Purchase Invoice", purchase_invoice_name)
    try:
        doc.delete()
        frappe.db.commit()
        return f"Deleted {purchase_invoice_name}. Reloading page ..."
    except Exception as err:
        return err
