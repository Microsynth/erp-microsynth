# Copyright (c) 2023, Microsynth, libracore and contributors and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import os
from datetime import datetime
import frappe
from frappe import _
import json
from erpnextswiss.erpnextswiss.zugferd.zugferd_xml import create_zugferd_xml
import re

def execute(filters=None):
    columns = get_columns(filters)
    data = get_data(filters)
    return columns, data

def get_columns(filters):
    if filters.get("version") == "AT":
        columns = [
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
            {"label": _("Customer"), "fieldname": "customer", "fieldtype": "Data", "width": 120},
            {"label": _("External debtor number"), "fieldname": "ext_debitor_number", "fieldtype": "Data", "width": 120}
        ]
    return columns

def get_data(filters, short=False):
    sql_query = ""
    if filters.get("version") == "AT":
        sql_query = """
        SELECT
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
        if d.get("document_type") == "Sales Invoice":
            create_pdf(path=settings.pdf_export_path, 
                dt=d.get("document_type"), 
                dn=d.get("document"), 
                print_format=settings.pdf_print_format
            )

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
    
def create_datev_xml(path, dt, dn):
    # pre-process document to prevent datev errors
    doc = frappe.get_doc(dt, dn).as_dict()
    for item in doc['items']:
        item['item_name'] = re.sub(r"&([a-z0-9]+|#[0-9]{1,6}|x[0-9a-fA-F]{1,6});", "", item['item_name'])     # drop html entitites from item name, if cropped, they become invalid
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
    path = "{0}/{1}".format(settings.pdf_export_path, date.strftime("%Y-%m-%d_%H-%M"))
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
                'pdf_filename': pdf_file
            })
            
    create_datev_summary_xml(path, document)

    return
