import frappe
from datetime import datetime


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
    # frappe.throw(len(alternative_templates))
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

    if self.doctype == "Sales Order":
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
        # frappe.throw(template_name)
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