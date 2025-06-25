import frappe
from datetime import datetime
from frappe import _


def find_tax_template(company, customer, shipping_address, category):
    """
    Find the corresponding sales tax template in the tax matrix. Does not consider alternative tax templates.

    run
    bench execute microsynth.microsynth.taxes.find_tax_template --kwargs "{'company':'Microsynth France SAS', 'customer':'37662251', 'shipping_address':'230803', 'category':'Material'}"
    """

    # if the customer is "Individual" (B2C), always apply default tax template (with VAT)
    if frappe.get_value("Customer", customer, "customer_type") == "Individual":
        default = frappe.get_all("Sales Taxes and Charges Template",
            filters={'company': company, 'is_default': 1},
            fields=['name']
        )
        if default and len(default) > 0:
            return default[0]['name']
        else:
            frappe.log_error(f"Could not find default tax template for company '{company}'\ncustomer '{customer}' has customer_type='Individual'", "taxes.find_tax_template")
            return None
    else:
        country = frappe.get_value("Address", shipping_address, "country")
        if frappe.get_value("Country", country, "eu"):
            eu_pattern = """ OR `country` = "EU" """
        else:
            eu_pattern = ""
        find_tax_record = frappe.db.sql("""SELECT `sales_taxes_template`
            FROM `tabTax Matrix Entry`
            WHERE `company` = "{company}"
              AND (`country` = "{country}" OR `country` = "%" {eu_pattern})
              AND `category` = "{category}"
            ORDER BY `idx` ASC;""".format(
            company=company, country=country, category=category, eu_pattern=eu_pattern),
            as_dict=True)
        if len(find_tax_record) > 0:
            return find_tax_record[0]['sales_taxes_template']
        else:
            frappe.log_error(f"Could not find sales tax template entry in the Tax Matrix for Customer '{customer}'\n{company=}, {country=}, {category=}, {eu_pattern=}", "taxes.find_tax_template")
            return None


def find_purchase_tax_template(sales_tax_template, company):
    """
    Find the corresponding purchase tax template in the tax matrix. Does not consider alternative tax templates.

    bench execute microsynth.microsynth.taxes.find_purchase_tax_template --kwargs "{'sales_tax_template': 'BAL Export (220) - BAL', 'company':'Microsynth France SAS'}"
    """
    purchase_tax_records = frappe.db.sql(f"""
        SELECT `purchase_tax_template`
        FROM `tabTax Matrix Template Mapping`
        WHERE `purchase_company` = "{company}"
            AND `sales_tax_template` = "{sales_tax_template}"
        ORDER BY `idx` ASC;""", as_dict=True)
    if len(purchase_tax_records) > 0:
        return purchase_tax_records[0]['purchase_tax_template']
    else:
        frappe.log_error(f"Could not find purchase tax template entry in the Tax Matrix for Sales Tax Template '{sales_tax_template} targetting {company=}", "taxes.find_purchase_tax_template")
        return None


def get_alternative_tax_template(tax_template, date):
    """
    run
    bench execute microsynth.microsynth.taxes.get_alternative_tax_template --kwargs "{'tax_template':'BAL CH MwSt 7.7% (302) - BAL'}"
    """
    if type(date) == datetime:
        date = date.strftime("%Y-%m-%d")
    query = """
        SELECT `alternative_tax_template`, `valid_from`
        FROM `tabAlternative Tax Template`
        WHERE `tax_template` = '{tax_template}'
        AND `valid_from` <='{current_date}'
    """.format(tax_template = tax_template, current_date = date)

    alternative_templates = frappe.db.sql(query, as_dict=True)
    if len(alternative_templates) > 0:
        return alternative_templates[0].alternative_tax_template
    else:
        return tax_template


def set_alternative_tax_template(self, event):
    """
    Replace the tax template according to Tax Matrix.alternative_tax_templates.
    Does not change the tax template of credit notes to prevent differences.

    triggered by document events and called through hooks
    """

    if not self.taxes_and_charges:
        # Do not try to change taxes_and_charges if it is not set at all.
        # Webshop.get_item_prices creates a temporaty sales order without tax template.
        return

    if self.doctype == "Quotation":
        template_name = get_alternative_tax_template(
            tax_template = self.taxes_and_charges,
            date = self.transaction_date )

    elif self.doctype == "Sales Order":
        template_name = get_alternative_tax_template(
            tax_template = self.taxes_and_charges,
            date = self.delivery_date)

    elif self.doctype == "Delivery Note":
        template_name = get_alternative_tax_template(
            tax_template = self.taxes_and_charges,
            date = self.posting_date)

    elif self.doctype == "Sales Invoice":
        if self.is_return:
            return
        template_name = get_alternative_tax_template(
            tax_template = self.taxes_and_charges,
            date = self.posting_date)
    else:
        frappe.log_error (f"Cannot process doctype '{self.doctype}'", "taxes.set_alternative_tax_template")
        return

    tax_template = frappe.get_doc("Sales Taxes and Charges Template", template_name)
    self.taxes_and_charges = tax_template.name
    self.taxes = []

    for tax in tax_template.taxes:
        new_tax = { 'charge_type': tax.charge_type,
                    'account_head': tax.account_head,
                    'description': tax.description,
                    'cost_center': tax.cost_center,
                    'rate': tax.rate }
        self.append("taxes", new_tax)

    self.calculate_taxes_and_totals()

    return


@frappe.whitelist()
def find_dated_tax_template(company, customer, shipping_address, category, date):
    """
    Find the corresponding tax template in the tax matrix while considering alternative tax templates.
    Category must be 'Material' or 'Service'.

    run
    bench execute microsynth.microsynth.taxes.find_dated_tax_template --kwargs "{'company':'Microsynth AG', 'customer':'23057', 'shipping_address':'237472', 'category':'Material', 'date': '2024-01-09'}"
    """
    template = find_tax_template(company, customer, shipping_address, category)
    alternative_template = get_alternative_tax_template(template, date)
    return alternative_template


def sales_order_before_save(doc, event):
    """
    This is a wrapper function for the hooked Sales Order:before save trigger
    """
    update_taxes(doc, event)
    set_alternative_tax_template(doc, event)
    return


def quotation_before_save(doc, event):
    """
    This is a wrapper function for the hooked Quotation:before save trigger
    """
    update_taxes(doc, event)
    set_alternative_tax_template(doc, event)
    return


def update_taxes(doc, event=None):
    """
    This function will update the tax template and child table of a Quotation, Sales Order to assure they correspond to the stored templates

    It is triggered from the document hook.
    """

    # parametrisation from the document
    if doc.doctype == "Sales Order":
        customer = doc.customer
        address = doc.shipping_address_name
        date = doc.delivery_date
    elif doc.doctype == "Quotation":
        if not doc.shipping_address_name:
            frappe.msgprint(_("Check shipping address"), _("Quotation"))
            return            # cannot determine tax template without the destination address
        customer = doc.party_name
        address = doc.shipping_address_name
        date = doc.transaction_date
    else:
        frappe.throw(f"For this doctype {doc.doctype} this is not yet implemented")
        return  # to satisfy linter

    if doc.get('product_type') in ["Oligos", "Material"]:
        category = "Material"
    else:
        category = "Service"

    if doc.get('oligos') and len(doc.get('oligos')) > 0:
        category = "Material"

    taxes = find_dated_tax_template(
        company=doc.company,
        customer=customer,
        shipping_address=address,
        category=category,
        date=date
    )

    doc.taxes_and_charges = taxes

    tax_template = frappe.get_doc("Sales Taxes and Charges Template", taxes)

    doc.taxes = []
    for t in tax_template.taxes:
        doc.append("taxes", {
            'charge_type': t.charge_type,
            'account_head': t.account_head,
            'description': t.description,
            'cost_center': t.cost_center,
            'rate': t.rate,
        })

    return
