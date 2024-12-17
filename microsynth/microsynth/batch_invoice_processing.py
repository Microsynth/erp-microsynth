# Copyright (c) 2024, libracore, Microsynth and contributors
# License: GNU General Public License v3. See license.txt

import frappe
from frappe.utils import cint, flt, get_link_to_form, get_url_to_form
from frappe.utils.file_manager import save_file
import os
from erpnextswiss.erpnextswiss.zugferd.zugferd import get_xml, get_content_from_zugferd
from erpnextswiss.erpnextswiss.zugferd.qr_reader import find_qr_content_from_pdf, get_content_from_qr
from erpnextswiss.erpnextswiss.zugferd.pdf_reader import find_supplier_from_pdf
from microsynth.microsynth.utils import send_email_from_template


@frappe.whitelist()
def process_files(debug=True):
    """
    Create Purchase Invoices from PDF files in the paths defined in Batch Invoice Processing Settings

    Run by a hourly cronjob from 05:30 to 17:30 if Batch Invoice Processing Settings are enabled:
    30 5-17 * * * cd /home/frappe/frappe-bench && /usr/local/bin/bench --site erp.microsynth.local microsynth.microsynth.batch_invoice_processing.process_files

    bench execute microsynth.microsynth.batch_invoice_processing.process_files
    """
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
    try:
        # try to fetch data from zugferd
        try:
            xml_content = get_xml(file_name)
        except Exception as err:
            if debug:
                print("ERROR: {0}".format(err))
            xml_content = None
        invoice = {}
        supplier = None
        if xml_content:
            if debug:
                print("INFO: electronic invoice detected")
            invoice = get_content_from_zugferd(xml_content)
        else:
            # zugferd failed, fall back to qr-reader
            try:
                qr_content = find_qr_content_from_pdf(file_name)
            except Exception as err:
                if debug:
                    print("ERROR: {0}".format(err))
                qr_content = None

            if qr_content:
                if debug:
                    print("INFO: QR invoice detected")
                invoice = get_content_from_qr(qr_content, company_settings.default_tax, company_settings.default_item, company)
            else:
                if debug:
                    print("INFO: extract supplier from pdf")
                invoice.update({
                    'supplier': find_supplier_from_pdf(file_name, company)
                })
        
        # currency: if so far not defined, get company default currency
        if not invoice:
            invoice = {}
        if 'currency' not in invoice or not invoice.get('currency'):
            if invoice.get("supplier"):
                # use supplier currency
                invoice['currency'] = frappe.get_value("Supplier", invoice.get("supplier"), "default_currency")
            if not invoice.get('currency'):
                # company default currency (last resort)
                invoice['currency'] = frappe.get_value("Company", company, "default_currency")

        # apply price list from supplier
        if invoice.get("supplier"):
            invoice['price_list'] = frappe.get_value("Supplier", invoice.get("supplier"), "default_price_list") 
        
        if debug:
            print("INFO: supplier {0}".format(invoice.get('supplier')))
            
        # create invoice record
        create_invoice(file_name, invoice, company_settings)
    except Exception as err:
        try:
            msg = f"Error: {err}\nFile: {file_name}"
            # Idea: Add an error path to each company setting in Batch Invoice Processing Settings?
            parts = file_name.split("/")
            pdf_name = parts[-1]
            path = "/".join(parts[:(len(parts)-1)]) + "/Error"
            # Move file to error folder
            new_file_name = path + "/" + pdf_name
            os.rename(file_name, new_file_name)
            # Write error
            txt_path = path + "/" + pdf_name[:-4] + ".txt"
            with open(txt_path, 'w') as txt_file:
                txt_file.write(msg)
            frappe.log_error(msg, "Batch processing parse file error")
            # Send an automatic email
            email_template = frappe.get_doc("Email Template", "Batch invoice processing error")
            rendered_content = frappe.render_template(email_template.response, {'file_name': file_name, 'err': err})
            send_email_from_template(email_template, rendered_content)
        except Exception as e:
            frappe.log_error(f"Got the following error during error handling:\n{e}", "Batch processing parse file error")


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

    if invoice.get("price_list"):
        pinv_doc.buying_price_list = invoice.get("price_list")

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
    else:
        # fallback to default taxes
        pinv_doc.taxes_and_charges = settings.get('default_tax')
        taxes_template = frappe.get_doc("Purchase Taxes and Charges Template", pinv_doc.taxes_and_charges)
        for t in taxes_template.taxes:
            pinv_doc.append("taxes", t)
            
    if invoice.get("items"):            # invoice with items (source ZUGFeRD or QR)
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
                        # item not found: try to use the supplier default item and fall back to the settings item
                        item['item_code'] = frappe.get_value("Supplier",  invoice['supplier'], "default_item") or settings.default_item

                        """ 2024-12-10: do not create new items, but use default item
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
                        """
                else:
                    item['item_code'] = item.get('seller_item_code')
            
            pinv_doc.append("items", {
                'item_code': item.get('item_code'),
                'item_name': item.get('item_name'),
                'qty': flt(item.get("qty")),
                'rate': flt(item.get("net_price"))
            })
    else:
        # no items found (PDF- invoices)
        if pinv_doc.supplier:
            # try to use suplier default item
            supplier_default_item = frappe.get_value("Supplier", pinv_doc.supplier, "default_item")
            if supplier_default_item:
                pinv_doc.append("items", {
                    'item_code': supplier_default_item,
                    'qty': 1,
                    'rate': 0
                })
        
        if not pinv_doc.get("items") or len(pinv_doc.items) == 0:
            # use this company's default item (see batch processing settings)
            pinv_doc.append("items", {
                'item_code': settings.get('default_item'),
                'qty': 1,
                'rate': 0
            })
    
    # apply cost center
    cost_center = frappe.get_value("Company", settings.company, "cost_center")
    for i in pinv_doc.items:
        i.cost_center = cost_center
        i.uom = frappe.get_value("Item", i.item_code, "stock_uom")
        if not i.conversion_factor:
            i.conversion_factor = 1
    
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
