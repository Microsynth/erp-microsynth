# Copyright (c) 2023, Microsynth, libracore and contributors and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import os
from datetime import datetime
import frappe
from frappe import _
import json
from frappe.utils.pdf import get_pdf
from PyPDF2 import PdfFileMerger

def execute(filters=None):
    columns = get_columns(filters)
    data = get_data(filters)
    return columns, data

def get_columns(filters):
    columns = [
        {"label": _("Customer"), "fieldname": "customer", "fieldtype": "Link", "options": "Customer", "width": 80},
        {"label": _("Customer name"), "fieldname": "customer_name", "fieldtype": "Data", "width": 150},
        {"label": _("Address"), "fieldname": "address", "fieldtype": "Data", "width": 150},
        {"label": _("UID"), "fieldname": "tax_id", "fieldtype": "Data", "width": 100},
        {"label": _("Sales Invoice"), "fieldname": "sales_invoice", "fieldtype": "Link", "options": "Sales Invoice", "width": 120},
        {"label": _("Currency"), "fieldname": "currency", "fieldtype": "Data", "width": 80},
        {"label": _("Total amount"), "fieldname": "corrected_total", "fieldtype": "Currency", "options": "currency", "width": 100},
        {"label": _("Net amount"), "fieldname": "net_amount", "fieldtype": "Currency", "options": "currency", "width": 100},
        {"label": _("Tax amount"), "fieldname": "tax_amount", "fieldtype": "Currency", "options": "currency", "width": 100},
        {"label": _("Gross amount"), "fieldname": "gross_amount", "fieldtype": "Currency", "options": "currency", "width": 100},
        {"label": _("EUR net amount"), "fieldname": "eur_net_total", "fieldtype": "Currency", "options": "eur_currency", "width": 100},
        {"label": _("Tax Code"), "fieldname": "tax_code", "fieldtype": "Data", "width": 80}
    ]
    return columns

def get_data(filters, short=False):
    sql_query = """
        SELECT
            `tabSales Invoice`.`customer`,
            `tabSales Invoice`.`customer_name`,
            CONCAT(`tabAddress`.`pincode`, " ", `tabAddress`.`city`) AS `address`,
            `tabCustomer`.`tax_id`,
            `tabSales Invoice`.`name` AS `sales_invoice`,
            `tabSales Invoice`.`currency`,
            IF (`tabSales Invoice`.`is_return` = 1,
                    (`tabSales Invoice`.`total` - (`tabSales Invoice`.`discount_amount` + `tabSales Invoice`.`total_customer_credit`)),
                    (`tabSales Invoice`.`total` - (`tabSales Invoice`.`discount_amount` - `tabSales Invoice`.`total_customer_credit`))
            ) AS corrected_total,
            `tabSales Invoice`.`net_total` AS `net_amount`,
            `tabSales Invoice`.`total_taxes_and_charges` AS `tax_amount`,
            `tabSales Invoice`.`grand_total` AS `gross_amount`,
            IF (`tabSales Invoice`.`currency` = 'EUR',
                `tabSales Invoice`.`net_total`,
                ROUND(`tabSales Invoice`.`base_net_total` / `tabCurrency Exchange`.`exchange_rate`, 2)
            ) AS `eur_net_total`,
            'EUR' AS `eur_currency`,
            `tabSales Invoice`.`taxes_and_charges` AS `tax_code`
        FROM `tabSales Invoice`
        LEFT JOIN `tabAddress` ON `tabAddress`.`name` = `tabSales Invoice`.`customer_address`
        LEFT JOIN `tabCustomer` ON `tabCustomer`.`name` = `tabSales Invoice`.`customer`
        LEFT JOIN `tabCurrency Exchange` ON `tabCurrency Exchange`.`from_currency` = "EUR"
            AND `tabCurrency Exchange`.`to_currency` = "CHF"
            AND SUBSTRING(`tabCurrency Exchange`.`date`, 1, 7) = SUBSTRING(`tabSales Invoice`.`posting_date`, 1, 7)
        WHERE
            `tabSales Invoice`.`docstatus` = 1
            AND `tabSales Invoice`.`company` = "{company}"
            AND `tabSales Invoice`.`posting_date` >= "{from_date}"
            AND `tabSales Invoice`.`posting_date` <= "{to_date}"
            AND `tabSales Invoice`.`taxes_and_charges` LIKE "%(AT0__)%"
            AND NOT EXISTS (
                SELECT `tabSales Invoice Item`.`name`
                FROM `tabSales Invoice Item`
                WHERE `tabSales Invoice Item`.`parent` = `tabSales Invoice`.`name`
                AND `tabSales Invoice Item`.`item_code` = "{credit_item}" )
        ORDER BY `tabCustomer`.`tax_id` ASC, `tabSales Invoice`.`name` ASC
        """.format(
            company = filters.get("company"),
            from_date = filters.get("from_date"),
            to_date = filters.get("to_date"),
            credit_item = frappe.get_value("Microsynth Settings", "Microsynth Settings", "credit_item"))

    data = frappe.db.sql(sql_query, as_dict=True)

    return data

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
def async_package_export(filters):
    if type(filters) == str:
        filters = json.loads(filters)

    frappe.enqueue(method=package_export, queue='long', timeout=120, is_async=True, filters=filters)
    return

"""
Export the complete sales invoice package with pdf, xml and document overview
"""
def package_export(filters):
    """
    run
    $ bench execute microsynth.microsynth.report.fiscal_representation_export.fiscal_representation_export.package_export --kwargs "{'filters': {'company': 'Microsynth Seqlab GmbH', 'from_date':'2023-01-01', 'to_date':'2023-04-14' }}"
    """

    data = get_data(filters)
    settings = frappe.get_doc("Microsynth Settings", "Microsynth Settings")
    date = datetime.now()
    path = "{0}/FiscRep_{1}".format(settings.pdf_export_path, date.strftime("%Y-%m-%d_%H-%M"))
    if not os.path.exists(path):
        os.mkdir(path)

    # pdf_at = []             # collect pdf file names AT
    # pdf_ig = []             # collect pdf file names IG
    sum_at = {}             # summary data AT
    sum_ig = {}             # summary data IG
    data_at = []
    data_ig = []

    for d in data:
        key = (d.get("tax_id") or "-")
        if "AT022" in d.get("tax_code"):            # AT
            # pdf_at.append(pdf_file)
            subdirectory = "{0}/{1}".format(path, "AT")
            data_at.append(d)
            if key in sum_at:
                sum_at[key]['count'] += 1
                sum_at[key]['gross_amount'] += d.get('gross_amount')
            else:
                sum_at[key] = {
                    'count': 1,
                    'gross_amount': d.get('gross_amount'),
                    'address': d.get('customer_name'),
                    'uid': d.get('tax_id')
                }
        else:                                       # IG
            # pdf_ig.append(pdf_file)
            subdirectory = "{0}/{1}".format(path, "EU")
            data_ig.append(d)
            if key in sum_ig:
                sum_ig[key]['count'] += 1
                sum_ig[key]['gross_amount'] += d.get('gross_amount')
            else:
                sum_ig[key] = {
                    'count': 1,
                    'gross_amount': d.get('gross_amount'),
                    'address': d.get('customer_name'),
                    'uid': d.get('tax_id')
                }
        # create pdf
        if not os.path.exists(subdirectory):
            os.mkdir(subdirectory)

        create_pdf(path=subdirectory,
            dt="Sales Invoice",
            dn=d.get("sales_invoice"),
            print_format=settings.pdf_print_format
        )

    # bind all pdfs
    # merge_pdfs(path, "AUS", pdf_at, filters.get('from_date'), filters.get('to_date'))
    # merge_pdfs(path, "EU", pdf_ig, filters.get('from_date'), filters.get('to_date'))

    # create summary pdf
    create_summary_pdf(path, "AUS", data_at, filters.get('from_date'), filters.get('to_date'))
    create_summary_pdf(path, "EU", data_ig, filters.get('from_date'), filters.get('to_date'))

    # create summary csv
    create_summary_csv(path, "AUS", sum_at, filters.get('from_date'), filters.get('to_date'))
    create_summary_csv(path, "EU", sum_ig, filters.get('from_date'), filters.get('to_date'))

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

def create_summary_csv(path, code, summary_data, from_date, to_date):
    summary_csv = frappe.render_template("microsynth/microsynth/report/fiscal_representation_export/summary_csv.html", {'data': summary_data} )
    file_name = "UID_{code}_{from_date}_{to_date}.csv".format(code=code, from_date=from_date, to_date=to_date)
    content_file_name = "{0}/{1}".format(path, file_name)
    with open(content_file_name, mode='w') as file:
        file.write(summary_csv)
    return file_name

def create_summary_pdf(path, code, data, from_date, to_date):
    summary_html = frappe.render_template("microsynth/microsynth/report/fiscal_representation_export/summary_pdf.html", {'data': data, 'from_date': from_date, 'to_date': to_date} )
    pdf = get_pdf(summary_html)
    file_name = "Sammelauszug_{code}_{from_date}_{to_date}.pdf".format(code=code, from_date=from_date, to_date=to_date)
    content_file_name = "{0}/{1}".format(path, file_name)
    with open(content_file_name, mode='wb') as file:
        file.write(pdf)
    return file_name

def merge_pdfs(path, code, files, from_date, to_date):
    merger = PdfFileMerger()

    for pdf in files:
        merger.append("{0}/{1}".format(path, pdf))
        # clean up single invoice pdf
        os.remove("{0}/{1}".format(path, pdf))

    file_name = "UID_{code}_{from_date}_{to_date}.pdf".format(code=code, from_date=from_date, to_date=to_date)
    content_file_name = "{0}/{1}".format(path, file_name)
    merger.write(content_file_name)
    merger.close()
    return file_name
