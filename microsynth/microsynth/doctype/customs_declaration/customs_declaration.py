# -*- coding: utf-8 -*-
# Copyright (c) 2023, Microsynth, libracore and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document
from frappe.utils import get_url_to_form
from frappe.utils.pdf import get_pdf
from erpnextswiss.erpnextswiss.attach_pdf import save_and_attach, create_folder
from datetime import date


class CustomsDeclaration(Document):
    def on_submit(self):
        # Link Delivery Notes to Customs Declaration
        for dn in self.austria_dns:
            doc = frappe.get_doc('Delivery Note', dn.delivery_note)
            doc.customs_declaration = self.name
            doc.save()

        for dn in self.eu_dns:
            doc = frappe.get_doc('Delivery Note', dn.delivery_note)
            doc.customs_declaration = self.name
            doc.save()

        frappe.db.commit()

        # Create PDF and attach it to the Customs Declaration
        doctype = printformat = "Customs Declaration"
        doctype_folder = create_folder(doctype, "Home")
        title_folder = create_folder(self.name, doctype_folder)
        filecontent = frappe.get_print(doctype, self.name, printformat, doc=None, as_pdf=True, no_letterhead=False)

        save_and_attach(
            content = filecontent,
            to_doctype = doctype,
            to_name = self.name,
            folder = title_folder,
            hashname = None,
            is_private = True
        )


    def before_cancel(self):
        for dn in self.austria_dns:
            doc = frappe.get_doc('Delivery Note', dn.delivery_note)
            doc.customs_declaration = None
            doc.save()

        for dn in self.eu_dns:
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
    """
    bench execute microsynth.microsynth.doctype.customs_declaration.customs_declaration.get_delivery_notes_to_declare
    """
    # TODO: Change total to net_total and base_total to base_net_total?
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
            `tabDelivery Note`.`base_total`,
            IF(`tabDelivery Note`.`currency` != 'EUR',
                ROUND(
                    `tabDelivery Note`.`base_total` / (
                        SELECT `exchange_rate`
                        FROM `tabCurrency Exchange`
                        WHERE `from_currency` = 'EUR'
                        AND `to_currency` = (
                            SELECT `default_currency`
                            FROM `tabCompany`
                            WHERE `name` = `tabDelivery Note`.`company`
                        )
                        ORDER BY `creation` DESC
                        LIMIT 1
                    ), 2
                ),
                `tabDelivery Note`.`total`
            ) as `eur_net_total`,
            IF(`tabDelivery Note`.`currency` != 'EUR',
                ROUND(
                    `tabDelivery Note`.`base_total_taxes_and_charges` / (
                        SELECT `exchange_rate`
                        FROM `tabCurrency Exchange`
                        WHERE `from_currency` = 'EUR'
                        AND `to_currency` = (
                            SELECT `default_currency`
                            FROM `tabCompany`
                            WHERE `name` = `tabDelivery Note`.`company`
                        )
                        ORDER BY `creation` DESC
                        LIMIT 1
                    ), 2
                ),
                `tabDelivery Note`.`total_taxes_and_charges`
            ) as `eur_taxes`,
            IF(`tabDelivery Note`.`currency` != 'EUR',
                ROUND(
                    `tabDelivery Note`.`base_grand_total` / (
                        SELECT `exchange_rate`
                        FROM `tabCurrency Exchange`
                        WHERE `from_currency` = 'EUR'
                        AND `to_currency` = (
                            SELECT `default_currency`
                            FROM `tabCompany`
                            WHERE `name` = `tabDelivery Note`.`company`
                        )
                        ORDER BY `creation` DESC
                        LIMIT 1
                    ), 2
                ),
                `tabDelivery Note`.`grand_total`
            ) as `eur_grand_total`
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
    customs_declaration = frappe.get_doc("Customs Declaration", doc)
    css = frappe.get_value('Print Format', 'Customs Declaration', 'css')
    raw_html = frappe.get_value('Print Format', 'Customs Declaration', 'html')
    # create html
    css_html = f"<style>{css}</style>{raw_html}"
    rendered_html = frappe.render_template(
        css_html,
        {
            'doc': customs_declaration,
            'part': part
        }
    )
    # need to load the styles and tags
    content = frappe.render_template(
        'microsynth/templates/pages/print.html',
        {'html': rendered_html}
    )
    options = {
        'disable-smart-shrinking': ''
    }
    pdf = get_pdf(content, options)
    frappe.local.response.filename = f"Customs_Declaration_{doc}_{part}.pdf"
    frappe.local.response.filecontent = pdf
    frappe.local.response.type = "download"
