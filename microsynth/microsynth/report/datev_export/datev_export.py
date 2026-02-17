# Copyright (c) 2023-2026, Microsynth, libracore and contributors and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import os
from datetime import datetime
import frappe
from frappe import _
import json
#from erpnextswiss.erpnextswiss.zugferd.zugferd_xml import create_zugferd_xml
from microsynth.microsynth.invoicing import get_microsynth_zugferd_xml as create_zugferd_xml
import re
import html
from 
DATEV_CHARACTER_PATTERNS = {
    'p10040': "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789$%*+-",        # dropped & to prevent xml encing issues
    'p10027': "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ.",
    'p10036': "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789$%*+- ",
}

def strip_str_to_allowed_chars(s, min_length, max_length, allowed_chars):
    out = ""
    if not s and min_length == 0:
        return out
    elif not s:
        #frappe.log_error(f"Got no value for s", "datev_export.strip_str_to_allowed_chars")
        return out
    # append each valid character
    for c in s:
        if c in allowed_chars:
            out += c
    # crop length
    out = out[:max_length]
    # verify min_length
    if len(out) < min_length:
        out += (len(out) - min_length) * allowed_chars[0]
    return out

def execute(filters=None):
    columns = get_columns(filters)
    data = get_data(filters)
    return columns, data

def get_columns(filters):
    columns = []
    if filters.get("version") == "AT":
        columns = [
            {"label": _("satzart"), "fieldname": "entry_type", "fieldtype": "Data", "width": 20},
            {"label": _("External debtor number"), "fieldname": "ext_debitor_number", "fieldtype": "Data", "width": 120},
            {"label": _("gkonto"), "fieldname": "account", "fieldtype": "Data", "width": 80},
            {"label": _("belegnr"), "fieldname": "document", "fieldtype": "Dynamic Link", "options": "document_type", "width": 120},
            {"label": _("belegdatum"), "fieldname": "date", "fieldtype": "Date", "width": 80},
            {"label": _("buchsymbol"), "fieldname": "book_symbol", "fieldtype": "Data", "width": 80},
            {"label": _("buchcode"), "fieldname": "book_code", "fieldtype": "Data", "width": 80},
            {"label": _("prozent"), "fieldname": "vat_percent", "fieldtype": "Percent", "width": 80},
            {"label": _("steuercode"), "fieldname": "vat_code", "fieldtype": "Data", "width": 80},
            {"label": _("betrag"), "fieldname": "gross_amount", "fieldtype": "Float", "width": 100, "precision": 2},
            {"label": _("steuer"), "fieldname": "vat_amount", "fieldtype": "float", "width": 100, "precision": 2},
            {"label": _("text"), "fieldname": "description", "fieldtype": "Data", "width": 120},
            {"label": _("Customer"), "fieldname": "customer", "fieldtype": "Data", "width": 120}
        ]
    return columns

def get_data(filters, short=False):
    sql_query = ""
    if filters.get("version") == "AT":
        if filters.get("transactions") == "Debtors":
            sql_query = """
                SELECT
                    0 AS `entry_type`,
                    (SELECT
                        SUBSTRING(`tabSales Invoice Item`.`income_account`, 1, 4)
                     FROM `tabSales Invoice Item`
                     WHERE `tabSales Invoice Item`.`parent` = `tabSales Invoice`.`name`
                     ORDER BY `tabSales Invoice Item`.`idx` ASC
                     LIMIT 1) AS `account`,
                    "Sales Invoice" AS `document_type`,
                    `tabSales Invoice`.`name` as `document`,
                    `tabSales Invoice`.`posting_date` as `date`,
                    "AR" AS `book_symbol`,
                    "" AS `book_code`,
                    ROUND(100 * `tabSales Invoice`.`total_taxes_and_charges` / `tabSales Invoice`.`net_total`, 1) AS `vat_percent`,
                    `tabSales Invoice`.`grand_total` AS `gross_amount`,
                    (-1) * `tabSales Invoice`.`total_taxes_and_charges` AS `vat_amount`,
                    "Rechnung" AS `description`,
                    `tabSales Invoice`.`customer` AS `customer`,
                    `tabCustomer`.`ext_debitor_number` AS `ext_debitor_number`
                FROM `tabSales Invoice`
                LEFT JOIN `tabCustomer` ON `tabCustomer`.`name` = `tabSales Invoice`.`customer`
                WHERE
                    `tabSales Invoice`.`docstatus` = 1
                    AND `tabSales Invoice`.`company` = "{company}"
                    AND `tabSales Invoice`.`posting_date` >= "{from_date}"
                    AND `tabSales Invoice`.`posting_date` <= "{to_date}"
            """.format(
                company=filters.get("company"),
                from_date=filters.get("from_date"),
                to_date=filters.get("to_date"))

        elif filters.get("transactions") == "Creditors":
            sql_query = """
                SELECT
                    0 AS `entry_type`,
                    (SELECT
                        SUBSTRING(`tabPurchase Invoice Item`.`expense_account`, 1, 4)
                     FROM `tabPurchase Invoice Item`
                     WHERE `tabPurchase Invoice Item`.`parent` = `tabPurchase Invoice`.`name`
                     ORDER BY `tabPurchase Invoice Item`.`idx` ASC
                     LIMIT 1) AS `account`,
                    "Purchase Invoice" AS `document_type`,
                    `tabPurchase Invoice`.`name` as `document`,
                    `tabPurchase Invoice`.`posting_date` as `date`,
                    "ER" AS `book_symbol`,
                    "" AS `book_code`,
                    ROUND(100 * `tabPurchase Invoice`.`total_taxes_and_charges` / `tabPurchase Invoice`.`net_total`, 1) AS `vat_percent`,
                    `tabPurchase Invoice`.`grand_total` AS `gross_amount`,
                    (-1) * `tabPurchase Invoice`.`total_taxes_and_charges` AS `vat_amount`,
                    "Rechnung" AS `description`,
                    `tabPurchase Invoice`.`supplier` AS `customer`,
                    `tabSupplier`.`ext_creditor_id` AS `ext_debitor_number`
                FROM `tabPurchase Invoice`
                LEFT JOIN `tabSupplier` ON `tabSupplier`.`name` = `tabPurchase Invoice`.`supplier`
                WHERE
                    `tabPurchase Invoice`.`docstatus` = 1
                    AND `tabPurchase Invoice`.`company` = "{company}"
                    AND `tabPurchase Invoice`.`posting_date` >= "{from_date}"
                    AND `tabPurchase Invoice`.`posting_date` <= "{to_date}"
            """.format(
                company=filters.get("company"),
                from_date=filters.get("from_date"),
                to_date=filters.get("to_date"))
    data = frappe.db.sql(sql_query, as_dict=True)

    return data

@frappe.whitelist()
def async_pdf_export(filters):
    if type(filters) == str:
        filters = json.loads(filters)

    frappe.enqueue(method=pdf_export, queue='long', timeout=90, is_async=True, filters=filters)
    return

def pdf_export(filters):
    data = get_data(filters)
    settings = frappe.get_doc("Microsynth Settings", "Microsynth Settings")

    for d in data:
        # performance improvement 2026-02-17: use attached pdf instead of creating a new one
        download_pdf(path=settings.pdf_export_path,
            dt=d.get("document_type"),
            dn=d.get("document")
        )
        """
        if d.get("document_type") == "Sales Invoice":
            create_pdf(path=settings.pdf_export_path,
                dt=d.get("document_type"),
                dn=d.get("document"),
                print_format=settings.pdf_print_format
            )
            

        elif d.get("document_type") == "Purchase Invoice":
            download_pdf(path=settings.pdf_export_path,
                dt=d.get("document_type"),
                dn=d.get("document")
            )
        """

    return

@frappe.whitelist()
def async_xml_export(filters):
    if type(filters) == str:
        filters = json.loads(filters)

    frappe.enqueue(method=xml_export, queue='long', timeout=90, is_async=True, filters=filters)
    return

def xml_export(filters):
    """
    run
    $ bench execute microsynth.microsynth.report.datev_export.datev_export.xml_export --kwargs "{'filters': {'version':'AT', 'company': 'Microsynth Seqlab GmbH', 'from_date':'2023-01-01', 'to_date':'2023-04-14' }}"
    """

    data = get_data(filters)
    settings = frappe.get_doc("Microsynth Settings", "Microsynth Settings")
    path = settings.pdf_export_path + "/" + datetime.now().strftime("%Y-%m-%d__%H-%M")
    if not os.path.exists(path):
        os.mkdir(path)

    for d in data:
        if d.get("document_type") == "Sales Invoice":
            xml = create_zugferd_xml(sales_invoice = d.get("document"), verify = True )

            customer_node = "<ram:ID>{0}</ram:ID>".format(d.get("customer"))
            debtor_node = "<ram:ID>{0}</ram:ID>".format(d.get("ext_debitor_number") if d.get("ext_debitor_number") else 99999)

            content_xml = xml.replace(customer_node, debtor_node)
            file_path = "{0}/{1}.xml".format(path, d.get("document"))
            with open(file_path, mode='w') as file:
                file.write(content_xml)

        elif d.get("document_type") == "Purchase Invoice":
            #xml = create_zugferd_xml(sales_invoice = d.get("document"), verify = True )         # TODO: this will not work for purchase invoices

            supplier_node = "<ram:ID>{0}</ram:ID>".format(d.get("customer"))
            creditor_node = "<ram:ID>{0}</ram:ID>".format(d.get("ext_debitor_number") if d.get("ext_debitor_number") else 99999)

            #content_xml = xml.replace(supplier_node, creditor_node)
            #file_path = "{0}/{1}.xml".format(path, d.get("document"))
            #with open(file_path, mode='w') as file:
            #    file.write(content_xml)

    return

@frappe.whitelist()
def async_package_export(filters):
    if type(filters) == str:
        filters = json.loads(filters)

    frappe.enqueue(method=package_export, queue='long', timeout=120, is_async=True, filters=filters)
    return

def create_pdf(path, dt, dn, print_format):
    content_pdf = frappe.get_print(
        dt,
        dn,
        print_format=print_format,
        as_pdf=True)
    file_name = "{0}.pdf".format(dn)
    content_file_name = "{0}/{1}".format(path, file_name)
    with open(content_file_name, mode='wb') as file:
        file.write(content_pdf)
    return file_name


def download_pdf(path, dt, dn):
    file_name = "{0}.pdf".format(dn)
    content_file_name = "{0}/{1}".format(path, file_name)
    # find attachment and copy to output
    attachments = frappe.get_all(
        "File",
        filters={'attached_to_doctype': dt, 'attached_to_name': dn},
        fields=['name', 'file_url'],
        order_by='creation DESC'
    )
    if attachments and len(attachments) > 0:
        source_file = os.path.join(frappe.utils.get_bench_path(), "sites", frappe.utils.get_site_path()[2:], attachments[0]['file_url'][1:])
        if "\"" in source_file:
            frappe.log_error(f"This file name is less than suboptimal: {dt} {dn}: {source_file}", "datev_export.download_pdf file issue")
        os.system("""cp "{0}" "{1}" """.format(source_file, content_file_name))

    return file_name


def create_datev_xml(path, dt, dn):
    # pre-process document to prevent datev errors
    doc = frappe.get_doc(dt, dn).as_dict()
    for item in doc['items']:
        item['item_name'] = strip_str_to_allowed_chars(item['item_name'], 1, 39, DATEV_CHARACTER_PATTERNS['p10036'])
    doc['party_name'] = strip_str_to_allowed_chars(doc.get('customer_name') or doc.get('supplier_name'), 1, 50, DATEV_CHARACTER_PATTERNS['p10036'])
    if doc['doctype'] == "Sales Invoice":
        customer_address = frappe.get_doc("Address", doc.get("customer_address"))
        doc['party_number'] = frappe.get_value("Customer", doc.customer, "ext_debitor_number")
        doc['address_line1'] = strip_str_to_allowed_chars(customer_address.address_line1, 1, 50, DATEV_CHARACTER_PATTERNS['p10036'])
        doc['pincode'] = customer_address.pincode
        doc['city'] = strip_str_to_allowed_chars(customer_address.city, 1, 11, DATEV_CHARACTER_PATTERNS['p10036'])
    else:
        supplier_address = frappe.get_doc("Address", doc.get("supplier_address"))
        doc['party_number'] = frappe.get_value("Supplier", doc.supplier, "ext_creditor_id")
        doc['address_line1'] = strip_str_to_allowed_chars(supplier_address.address_line1, 1, 50, DATEV_CHARACTER_PATTERNS['p10036'])
        doc['pincode'] = supplier_address.pincode
        doc['city'] = strip_str_to_allowed_chars(supplier_address.city, 1, 11, DATEV_CHARACTER_PATTERNS['p10036'])
    doc['tax_id'] = strip_str_to_allowed_chars(doc.get("tax_id"), 1, 15, DATEV_CHARACTER_PATTERNS['p10027'])
    doc['bill_no'] = strip_str_to_allowed_chars(doc.get("bill_no") or doc.get('name'), 1, 36, DATEV_CHARACTER_PATTERNS['p10040'])

    datev_xml = frappe.render_template("microsynth/microsynth/report/datev_export/invoice.html", {
        'doc': doc
    })
    file_name = "{0}.xml".format(dn)
    content_file_name = "{0}/{1}".format(path, file_name)
    with open(content_file_name, mode='w') as file:
        file.write(datev_xml)
    return file_name

def create_datev_summary_xml(path, document):
    datev_summary_xml = frappe.render_template("microsynth/microsynth/report/datev_export/document.html", document)
    file_name = "document.xml"
    content_file_name = "{0}/{1}".format(path, file_name)
    with open(content_file_name, mode='w') as file:
        file.write(datev_summary_xml)
    return file_name

"""
Export the complete sales invoice package with pdf, xml and document overview
"""
def package_export(filters):
    """
    run
    $ bench execute microsynth.microsynth.report.datev_export.datev_export.package_export --kwargs "{'filters': {'version':'AT', 'company': 'Microsynth Seqlab GmbH', 'from_date':'2023-01-01', 'to_date':'2023-04-14' }}"
    """

    data = get_data(filters)
    settings = frappe.get_doc("Microsynth Settings", "Microsynth Settings")
    date = datetime.now()
    path = "{0}/{1}_{2}".format(settings.pdf_export_path, date.strftime("%Y-%m-%d_%H-%M"), filters.get("transactions"))
    if not os.path.exists(path):
        os.mkdir(path)

    document = {
        'date': date,
        'title': 'DATEV Export',
        'documents': []
    }
    for d in data:
        if d.get("document_type") == "Sales Invoice" and d.get("gross_amount") != 0:
            # create pdf
            pdf_file = create_pdf(path=path,
                dt=d.get("document_type"),
                dn=d.get("document"),
                print_format=settings.pdf_print_format
            )
            xml_file = create_datev_xml(path=path,
                dt=d.get("document_type"),
                dn=d.get("document")
            )

            document['documents'].append({
                'xml_filename': xml_file,
                'pdf_filename': pdf_file,
                'document_type': d.get("document_type")
            })

        elif d.get("document_type") == "Purchase Invoice" and d.get("gross_amount") != 0:
            # create pdf
            pdf_file = download_pdf(path=path,
                dt=d.get("document_type"),
                dn=d.get("document")
            )
            xml_file = create_datev_xml(path=path,
                dt=d.get("document_type"),
                dn=d.get("document")
            )

            document['documents'].append({
                'xml_filename': xml_file,
                'pdf_filename': pdf_file,
                'document_type': d.get("document_type")
            })

    create_datev_summary_xml(path, document)

    return

def escape_and_safe_truncate(input_string, max_length=50):
    # Escape the HTML string
    escaped_string = html.escape(input_string)

    # Early return if the string is already short enough
    if len(escaped_string) <= max_length:
        return escaped_string

    # Use a regex to extract valid parts of the string without breaking entities
    result = []
    current_length = 0
    # Regex to match entities or single characters
    entity_or_char_pattern = re.compile(r'&[a-zA-Z0-9#]+;|.')
    # Iterate through matches while keeping track of length
    for match in entity_or_char_pattern.finditer(escaped_string):
        part = match.group(0)
        part_length = len(part)
        if current_length + part_length > max_length:
            break # Stop before exceeding the max length

        result.append(part)
        current_length += part_length

    # Join the result to form the safely truncated string
    return ''.join(result)
