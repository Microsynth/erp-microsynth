# Copyright (c) 2023, Microsynth, libracore and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _


def get_columns(filters):
    return [
        {"label": _("Note ID"), "fieldname": "note_id", "fieldtype": "Link", "options": "Contact Note", "width": 85 },
        {"label": _("Date"), "fieldname": "date", "fieldtype": "Date", "width": 75 },
        {"label": _("Contact"), "fieldname": "contact", "fieldtype": "Link", "options": "Contact", "width": 65 },
        {"label": _("First Name"), "fieldname": "first_name", "fieldtype": "Data", "width": 80 },
        {"label": _("Last Name"), "fieldname": "last_name", "fieldtype": "Data", "width": 100 },
        {"label": _("Customer Name"), "fieldname": "customer_name", "fieldtype": "Data", "width": 130 },
        {"label": _("Customer ID"), "fieldname": "customer_id", "fieldtype": "Link", "options": "Customer", "width": 90 },
        {"label": _("Sales Manager"), "fieldname": "sales_manager", "fieldtype": "Data", "options": "User", "width": 100 },
        {"label": _("Territory"), "fieldname": "territory", "fieldtype": "Link", "options": "Territory", "width": 135 },
        {"label": _("Country"), "fieldname": "country", "fieldtype": "Data", "width": 75 },
        {"label": _("City"), "fieldname": "city", "fieldtype": "Data", "width": 100 },
        #{"label": _("Institute"), "fieldname": "institute", "fieldtype": "Data", "width": 175 },
        {"label": _("Institute Key"), "fieldname": "institute_key", "fieldtype": "Data", "width": 100 },
        #{"label": _("Department"), "fieldname": "department", "fieldtype": "Data", "width": 125 },
        {"label": _("Group Leader"), "fieldname": "group_leader", "fieldtype": "Data", "width": 100 },
        {"label": _("Creator"), "fieldname": "creator", "fieldtype": "Data", "options": "User", "width": 100 },
        {"label": _("Note Type"), "fieldname": "note_type", "fieldtype": "Data", "width": 80 },
        {"label": _("Notes"), "fieldname": "notes", "fieldtype": "Data", "options": "Notes", "width": 200 },
    ]


def get_data(filters):
    """
    Get raw Contact Notes records for find notes report.
    """
    filter_conditions = ''

    if filters:
        if filters.get('contact'):
            filter_conditions += f"AND `tabContact Note`.`contact_person` = '{filters.get('contact')}'"
        if filters.get('first_name'):
            filter_conditions += f"AND `tabContact Note`.`first_name` LIKE '{filters.get('first_name')}'"
        if filters.get('last_name'):
            filter_conditions += f"AND `tabContact Note`.`last_name` LIKE '{filters.get('last_name')}'"
        if filters.get('customer_name'):
            filter_conditions += f"AND `tabCustomer`.`customer_name` LIKE '%{filters.get('customer_name')}%'"
        if filters.get('sales_manager'):
            filter_conditions += f"AND `tabCustomer`.`account_manager` LIKE '%{filters.get('sales_manager')}%'"
        if filters.get('territory'):
            filter_conditions += f"AND `tabCustomer`.`territory` = '{filters.get('territory')}'"
        if filters.get('country'):
            filter_conditions += f"AND `tabAddress`.`country` LIKE '%{filters.get('country')}%'"
        if filters.get('city'):
            filter_conditions += f"AND `tabAddress`.`city` LIKE '%{filters.get('city')}%'"
        if filters.get('pincode'):
            filter_conditions += f"AND `tabAddress`.`pincode` = '{filters.get('pincode')}'"
        if filters.get('street'):
            filter_conditions += f"AND `tabAddress`.`address_line1` LIKE '%{filters.get('street')}%'"
        #if filters.get('institute'):
        #    filter_conditions += f"AND `tabContact`.`institute` LIKE '%{filters.get('institute')}%'"
        if filters.get('institute_key'):
            filter_conditions += f"AND `tabContact`.`institute_key` LIKE '%{filters.get('institute_key')}%'"
        #if filters.get('department'):
        #    filter_conditions += f"AND `tabContact`.`department` LIKE '%{filters.get('department')}%'"
        if filters.get('group_leader'):
            filter_conditions += f"AND `tabContact`.`group_leader` LIKE '%{filters.get('group_leader')}%'"
        if filters.get('from_date'):
            filter_conditions += f"AND `tabContact Note`.`date` >= DATE('{filters.get('from_date')}')"
        if filters.get('to_date'):
            filter_conditions += f"AND `tabContact Note`.`date` <= DATE('{filters.get('to_date')}')"

    query = """
            SELECT
                `tabContact Note`.`name` AS `note_id`,
                `tabContact Note`.`date`,
                `tabContact Note`.`contact_person` AS `contact`,
                `tabContact Note`.`first_name`,
                `tabContact Note`.`last_name`,
                `tabCustomer`.`customer_name`,
                `tabCustomer`.`name` AS `customer_id`,
                `tabCustomer`.`account_manager` AS `sales_manager`,
                `tabCustomer`.`territory`,
                `tabAddress`.`country`,
                `tabAddress`.`city`,
                `tabContact`.`institute`,
                `tabContact`.`institute_key`,
                `tabContact`.`department`,
                `tabContact`.`group_leader`,
                `tabContact Note`.`owner` AS `creator`,
                `tabContact Note`.`contact_note_type` AS `note_type`,
                `tabContact Note`.`notes`
            FROM `tabContact Note`
            LEFT JOIN `tabContact` ON `tabContact`.`name` = `tabContact Note`.`contact_person`
            LEFT JOIN `tabDynamic Link` AS `tDLA` ON `tDLA`.`parent` = `tabContact`.`name` 
                                              AND `tDLA`.`parenttype`  = "Contact" 
                                              AND `tDLA`.`link_doctype` = "Customer"
            LEFT JOIN `tabCustomer` ON `tabCustomer`.`name` = `tDLA`.`link_name`
            LEFT JOIN `tabAddress` ON `tabAddress`.`name` = `tabContact`.`address`
            WHERE TRUE
                {filter_conditions}
            ORDER BY `tabContact Note`.`date` DESC
        """.format(filter_conditions=filter_conditions)

    return frappe.db.sql(query, as_dict=True)


def execute(filters=None):
    columns, data = get_columns(filters), get_data(filters)
    return columns, data


@frappe.whitelist()
def create_pdf(filters):
    """
    Get Contact Notes matching the given filters, create and append their print formats and return the URL to the merged PDF.
 
    bench execute microsynth.microsynth.report.find_notes.find_notes.create_pdf --kwargs "{'filters': {'sales_manager': 'atila.durmus@microsynth.seqlab.de', 'from_date':'2024-06-01', 'to_date':'2024-06-30'}}"
    """
    import io
    import json
    from datetime import datetime
    from PyPDF2 import PdfFileMerger, PdfFileReader  # JPe: I've checked that PyPDF is available on the server. It was also used in microsynth/report/fiscal_representation_export/fiscal_representation_export.py

    if type(filters) == str:
        filters = json.loads(filters)
    data = get_data(filters)
    merger = PdfFileMerger()

    for note in data:
        #contact_note = frappe.get_doc("Contact Note", note['note_id'])
        pdf = frappe.get_print(
                    doctype="Contact Note",
                    name=note['note_id'],
                    print_format="Contact Note",
                    as_pdf=True
                )
        merger.append(PdfFileReader(io.BytesIO(pdf)))
    # https://gist.github.com/vijaywm/d6b7d1a54274838cd25acd1e3dd31740#pypdf2-pdffilemerger-to-merge-pdfs
    out = io.BytesIO()
    merger.write(out)
    file = frappe.get_doc(
        {
            "doctype": "File",
            "file_name": f"customer_contact_report_{datetime.now()}.pdf",
            "is_private": 1,
            "content": out.getvalue(),
        })
    file.save()
    merger.close()
    #return file.name
    return file.file_url
