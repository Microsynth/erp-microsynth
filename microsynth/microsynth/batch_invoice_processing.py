# Copyright (c) 2024, libracore, Microsynth and contributors
# License: GNU General Public License v3. See license.txt

import frappe
from frappe.utils import cint, flt, get_link_to_form, get_url_to_form
from frappe.utils.file_manager import save_file
import os
from erpnextswiss.erpnextswiss.zugferd.zugferd import get_xml, get_content_from_zugferd
from erpnextswiss.erpnextswiss.zugferd.qr_reader import find_qr_content_from_pdf, get_content_from_qr

def process_files():
    settings = frappe.get_doc("Batch Invoice Processing Settings", "Batch Invoice Processing Settings")
    if cint(settings.enabled) == 0:
        return
    
    if not settings.company_settings:
        return
        
    for company in settings.company_settings:
        read_company(company.company, company.input_path, company)
    return

def read_company(company, input_path, company_settings):
    if not input_path:
        return
    
    for f in os.listdir(input_path):
        if f.lower().endswith(".pdf"):
            parse_file(os.path.join(input_path, f), company, company_settings)
    
    return

def parse_file(file_name, company, company_settings):
    # try to fetch data from zugferd
    xml_content = get_xml(file_name)
    invoice = {}
    if xml_content:
        invoice = get_content_from_zugferd(xml_content)
    else:
        # zugferd failed, fall back to qr-reader
        qr_content = find_qr_content_from_pdf(file_name)
        if qr_content:
            invoice = get_content_from_qr(qr_content, company_settings.default_tax, company_settings.default_item, company)
        # TODO: QR-reader failed also, try to get text-content from PDF and parse for UID
        
    # create invoice record
    create_invoice(file_name, invoice, company_settings)
    
    return
    
def create_invoice(file_name, invoice, settings):
    
    if not invoice.get('supplier'):
        invoice['supplier'] = settings.fallback_supplier

    # create purchase invoice
    pinv_doc = frappe.get_doc({
        'doctype': 'Purchase Invoice',
        'company': settings.company,
        'supplier': invoice.get('supplier'),
        'currency': invoice.get('currency'),
        'bill_no': invoice.get('doc_id'),
        'terms': invoice.get('terms')
    })

    pinv_doc.bill_date = invoice.get('posting_date')
    pinv_doc.due_date = invoice.get('due_date')
        
    if invoice.get('esr_reference'):
        pinv_doc.esr_reference_number = invoice.get('esr_reference')
        pinv_doc.payment_type = "ESR"
        
    # find taxes and charges
    taxes_and_charges_template = frappe.db.sql("""
        SELECT `tabPurchase Taxes and Charges Template`.`name`
        FROM `tabPurchase Taxes and Charges`
        LEFT JOIN `tabPurchase Taxes and Charges Template` ON `tabPurchase Taxes and Charges Template`.`name` = `tabPurchase Taxes and Charges`.`parent`
        WHERE 
            `tabPurchase Taxes and Charges Template`.`company` = "{company}"
            AND `tabPurchase Taxes and Charges`.`rate` = {tax_rate}
        ;""".format(company=settings.company, tax_rate=flt(invoice.get('tax_rate'))), as_dict=True)
    if len(taxes_and_charges_template) > 0:
        pinv_doc.taxes_and_charges = taxes_and_charges_template[0]['name']
        taxes_template = frappe.get_doc("Purchase Taxes and Charges Template", taxes_and_charges_template[0]['name'])
        for t in taxes_template.taxes:
            pinv_doc.append("taxes", t)
            
    for item in invoice.get("items"):
        if not item.get('item_code'):
            # get item from seller_item_code
            if not frappe.db.exists("Item", item.get('seller_item_code')):
                # try to find item by supplier item
                supplier_item_matches = frappe.db.sql("""
                    SELECT `parent`
                    FROM `tabItem Supplier`
                    WHERE 
                        `supplier` = "{supplier}"
                        AND `supplier_part_no` = "{supplier_item}"
                    ;""".format(supplier=pinv_doc.supplier, supplier_item=item.get('seller_item_code')), as_dict=True)
                if len(supplier_item_matches) > 0:
                    item['item_code'] = supplier_item_matches[0]['parent']
                else:
                    # create new item
                    _item = {
                        'doctype': "Item",
                        'item_code': item.get('seller_item_code'),
                        'item_name': item.get('item_name'),
                        'item_group': frappe.get_value("ZUGFeRD Settings", "ZUGFeRD Settings", "item_group")
                    }
                    # apply default values
                    for d in settings.defaults:
                        if d.dt == "Item":
                            _item[d.field] = d.value
                    item_doc = frappe.get_doc(_item)
                    item_doc.insert()
                    item['item_code'] = item_doc.name
            else:
                item['item_code'] = item.get('seller_item_code')
        
        pinv_doc.append("items", {
            'item_code': item.get('item_code'),
            'item_name': item.get('item_name'),
            'qty': flt(item.get("qty")),
            'rate': flt(item.get("net_price"))
        })
    
    pinv_doc.flags.ignore_mandatory = True
    pinv_doc.insert()
    frappe.db.commit()
    
    # attach file
    f = open(file_name, "rb")
    content = f.read()
    f.close()
    save_file(
        fname=os.path.basename(file_name),
        content=content,
        dt=pinv_doc.doctype,
        dn=pinv_doc.name,
        is_private=True
    )
    
    # remove file
    os.remove(file_name)
    
    return {
        'name': pinv_doc.name, 
        'url': get_url_to_form("Purchase Invoice", pinv_doc.name),
        'link': get_link_to_form("Purchase Invoice", pinv_doc.name)
    }
