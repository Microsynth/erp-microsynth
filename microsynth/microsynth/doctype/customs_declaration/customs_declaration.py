# -*- coding: utf-8 -*-
# Copyright (c) 2023, Microsynth, libracore and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document
from frappe.utils import cint, get_url_to_form
from frappe.utils.pdf import get_pdf
from datetime import date

class CustomsDeclaration(Document):
    def on_submit(self):
        for dn in self.austria_dns:
            doc = frappe.get_doc('Delivery Note', dn.delivery_note)
            doc.customs_declaration = self.name
            doc.save()
               
        for dn in self.eu_dns:
            doc = frappe.get_doc('Delivery Note', dn.delivery_note)
            doc.customs_declaration = self.name
            doc.save()

        frappe.db.commit()
        return

    def before_cancel(self):
        for dn in self.austria_dns:
            doc = frappe.get_doc('Delivery Note', dn.delivery_note)
            doc.customs_declaration = None
            doc.save()

        for dn in self.austria_dns:
            doc = frappe.get_doc('Delivery Note', dn.delivery_note)
            doc.customs_declaration = None
            doc.save()
        
        frappe.db.commit()
        return


@frappe.whitelist()
def create_customs_declaration():
    cd = frappe.get_doc({
        'doctype':'Customs Declaration',
        'company': frappe.defaults.get_global_default('company'),
        'date': date.today()
        })
    dns = get_delivery_notes_to_declare()
    for dn in dns:
        if dn['export_category'] == "AT":
            cd.append('austria_dns',dn)
        if dn['export_category'] == "EU":
            cd.append('eu_dns',dn)
    cd.insert(ignore_permissions = True)
    frappe.db.commit()
    return get_url_to_form("Customs Declaration", cd.name)

def get_delivery_notes_to_declare():
    sql_query = """SELECT
            DISTINCT `tabDelivery Note`.`name` as `delivery_note`,
            IF(`tabDelivery Note`.`order_customer` is not null, `tabDelivery Note`.`order_customer`, `tabDelivery Note`.`customer`) as `customer`,
            IF(`tabDelivery Note`.`order_customer` is not null, `tabDelivery Note`.`order_customer_display`, `tabDelivery Note`.`customer_name`) as `customer_name`,
            `tabDelivery Note`.`export_category`,
            `tabDelivery Note`.`shipping_address_name` as `shipping_address`,
            `tabCustomer`.`tax_id` as `tax_id`,
            `tabAddress`.`country` as `country`,
            `tabDelivery Note`.`currency`,
            `tabDelivery Note`.`total` as `net_total`,
            `tabDelivery Note`.`total_taxes_and_charges` as `taxes`,
            `tabDelivery Note`.`grand_total`,
            `tabDelivery Note`.`base_total`
            FROM `tabDelivery Note` 
            JOIN `tabCustomer` ON  `tabCustomer`.`name` = `tabDelivery Note`.`customer`
            JOIN `tabAddress` ON `tabAddress`.`name` = `tabDelivery Note`.`shipping_address_name`
            JOIN `tabDelivery Note Item` ON (`tabDelivery Note Item`.`parent` = `tabDelivery Note`.`name` 
                AND `tabDelivery Note Item`.`item_group` = "Shipping"
                AND `tabDelivery Note Item`.`item_code` NOT IN ("1130", "1133"))
            WHERE `tabDelivery Note`.`export_category` IN ('AT', 'EU')
              AND `tabDelivery Note`.`customs_declaration` is NULL
              AND `tabDelivery Note`.`docstatus` <> 2
              AND `tabDelivery Note`.`total` <> 0
              AND `tabDelivery Note Item`.`name` IS NOT NULL;
        """
    delivery_notes = frappe.db.sql(sql_query, as_dict=True)
    return delivery_notes


@frappe.whitelist()
def create_partial_pdf(doc, part):
    # pdf = frappe.get_print(
    #                 doctype="Customs Declaration",
    #                 name=doc,
    #                 print_format="Customs Declaration",
    #                 as_pdf=True
    #             )
    # file = frappe.get_doc(
    #     {
    #         "doctype": "File",
    #         "file_name": f"{doc}_part_{part}.pdf",
    #         "is_private": 1,
    #         "content": pdf,
    #     })
    # file.save()
    # return file.file_url

    customs_declaration = frappe.get_doc("Customs Declaration", doc)
    content = frappe.render_template(
        "microsynth/microsynth/doctype/customs_declaration/customs_declaration.html",
        {
            'doc': customs_declaration,
            'part': part
        }
    )
    pdf = get_pdf(content)

    frappe.local.response.filename = f"Customs_Declaration_{doc}_{part}.pdf"
    frappe.local.response.filecontent = pdf
    frappe.local.response.type = "download"

    # from erpnextswiss.erpnextswiss.attach_pdf import save_and_attach, create_folder
    # folder = create_folder("Customs Declaration", "Home")
    # save_and_attach(
    #     content = pdf,
    #     to_doctype = "Customs Declaration",
    #     to_name = doc,  
    #     folder = folder,
    #     file_name = f"Customs_Declaration_{doc}_{part}.pdf", 
    #     hashname = None,
    #     is_private = True)
