import frappe
from datetime import datetime


@frappe.whitelist()
def find_tax_template(company, customer, shipping_address, category):
    """
    Find the corresponding tax template
    run
    bench execute microsynth.microsynth.utils.find_tax_template --kwargs "{'company':'Microsynth France SAS', 'customer':'37662251', 'shipping_address':'230803', 'category':'Material'}"
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
            frappe.log_error(f"Could not find default tax template for company '{company}'\ncustomer '{customer}' has customer_type='Individual'", "utils.find_tax_template")
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
            frappe.log_error(f"Could not find tax template entry in the Tax Matrix for customer '{customer}'\n{company=}, {country=}, {category=}, {eu_pattern=}", "utils.find_tax_template")
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

    return