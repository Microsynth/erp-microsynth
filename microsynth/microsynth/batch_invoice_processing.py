# Copyright (c) 2024, libracore, Microsynth and contributors
# License: GNU General Public License v3. See license.txt
#
# Run using (also for cron; note: enable in batch processing settings)
#
#  $ bench execute microsynth.microsynth.batch_invoice_processing.process_files
#
import frappe
from frappe.utils import cint, flt, get_link_to_form, get_url_to_form
from frappe.utils.file_manager import save_file
import os
from erpnextswiss.erpnextswiss.zugferd.zugferd import get_xml, get_content_from_zugferd
from erpnextswiss.erpnextswiss.zugferd.qr_reader import find_qr_content_from_pdf, get_content_from_qr
from erpnextswiss.erpnextswiss.zugferd.pdf_reader import find_supplier_from_pdf

def process_files(debug=True):
    settings = frappe.get_doc("Batch Invoice Processing Settings", "Batch Invoice Processing Settings")
    if cint(settings.enabled) == 0:
        return
    if not settings.company_settings:
        return
    for company in settings.company_settings:
        read_company(company.company, company.input_path, company, debug)


def read_company(company, input_path, company_settings, debug=True):
    if not input_path:
        return
    for f in os.listdir(input_path):
        if f.lower().endswith(".pdf"):
            parse_file(os.path.join(input_path, f), company, company_settings, debug)


def parse_file(file_name, company, company_settings, debug=True):
    if debug:
        print("INFO: Parsing {0} for {1}...".format(file_name, company))
    # try to fetch data from zugferd
    xml_content = get_xml(file_name)
    invoice = {}
    supplier = None
    if xml_content:
        if debug:
            print("INFO: electronic invoice detected")
        invoice = get_content_from_zugferd(xml_content)
    else:
        # zugferd failed, fall back to qr-reader
        qr_content = find_qr_content_from_pdf(file_name)
        if qr_content:
            if debug:
                print("INFO: QR invoice detected")
            invoice = get_content_from_qr(qr_content, company_settings.default_tax, company_settings.default_item, company)
        else:
            if debug:
                print("INFO: extract supplier from pdf")
            invoice.update({
                'supplier': find_supplier_from_pdf(file_name),
                'items': [{
                    'item_code': company_settings.default_item,
                    'qty': 1,
                    'rate': 0
                }]
            })
    
    if debug:
        print("INFO: supplier {0}".format(invoice['supplier']))
        
    # create invoice record
    create_invoice(file_name, invoice, company_settings)


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
    # prio 1: supplier default tax
    supplier_default_taxes = frappe.db.sql("""
        SELECT `default_tax_template`
        FROM `tabParty Account`
        WHERE
            `parentfield` = "accounts"
            AND `parenttype` = "Supplier"
            AND `parent` = "{supplier}"
            AND `company` = "{company}";
        """.format(supplier=invoice.get('supplier'), company=settings.company), as_dict=True)
    if len(supplier_default_taxes) > 0:
        pinv_doc.taxes_and_charges = supplier_default_taxes[0]['default_tax_template']
    else:
        # prio 2: find tax template by tax rate
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
    if pinv_doc.taxes_and_charges:
        taxes_template = frappe.get_doc("Purchase Taxes and Charges Template", pinv_doc.taxes_and_charges)
        for t in taxes_template.taxes:
            pinv_doc.append("taxes", t)
    
    if invoice.get("items"):
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


def read_folder(folder):
    """
    bench execute microsynth.microsynth.batch_invoice_processing.read_folder  --kwargs "{'folder': '/mnt/erp_share/JPe/test_invoices/seqlab'}"
    """
    counter = 0
    success_counter = 0
    for file in os.listdir(folder):
        if file.lower().endswith(".pdf"):
            file_path = os.path.join(folder, file)
            print(file_path)
            invoice = process_file(file_path)
            counter += 1
            if invoice:
                success_counter += 1
    print(f"success rate: {round((success_counter/counter) * 100, 2)} % ({success_counter}/{counter})")


def process_file(file_path):
    # try to fetch data from zugferd
    try:
        xml_content = get_xml(file_path)
        invoice = None
        settings = frappe.get_doc("ZUGFeRD Wizard", "ZUGFeRD Wizard")
        if xml_content:
            invoice = get_content_from_zugferd(xml_content)
        else:
            # zugferd failed, fall back to qr-reader
            qr_content = find_qr_content_from_pdf(file_path)
            if qr_content:
                invoice = get_content_from_qr(qr_content, settings.default_tax, settings.default_item)
        print("{0}".format(invoice))
        return invoice
    except Exception as err:
        print(err)
        return None
