import os
import re
from datetime import datetime
import frappe
from frappe import _
from frappe.utils import flt


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
        frappe.log_error(f"Could not find purchase tax template entry in the Tax Matrix for Sales Tax Template '{sales_tax_template}' targetting {company=}", "taxes.find_purchase_tax_template")
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


def write_pdf(doc, path):
    try:
        pdf_content = frappe.get_print(
            doc.doctype,
            doc.name,
            print_format=doc.doctype,  # assuming that the print format has the same name as the doctype
            as_pdf=True)
        filename = f"{doc.name}.pdf"
        filepath = os.path.join(path, filename)
        with open(filepath, mode='wb') as file:
            file.write(pdf_content)
    except Exception as e:
        msg = f"PDF generation failed for {doc.doctype} {doc.name}: {str(e)}"
        print(msg)
        frappe.log_error(msg, "AT VAT Export")


def write_summary_csv(rows, export_path, filename):
    import csv
    if not rows:
        return  # Nothing to write
    keys = sorted({key for row in rows for key in row.keys()})
    filepath = os.path.join(export_path, filename)

    with open(filepath, mode="w", encoding="utf-8", newline="") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=keys)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in keys})


def replace_placeholders(template: str, values: dict, code: str) -> str:
    """
    Safely replaces placeholders like {company} in the template with values from the dict.
    Logs an error and raises ValueError if any placeholder is missing.
    """
    def replacer(match):
        key = match.group(1)
        if key not in values:
            raise ValueError(f"Missing placeholder '{key}' in AT VAT Declaration for query code {code}")
        return str(values[key])

    pattern = re.compile(r"\{(\w+)\}")
    return pattern.sub(replacer, template)


@frappe.whitelist()
def at_vat_package_export(declaration_name, debug=False):
    """
    Export documents related to the AT VAT Declaration as PDF files and one summary CSV.
    The export path is configured in Microsynth Settings.

    bench execute microsynth.microsynth.taxes.at_vat_package_export --kwargs "{'declaration_name': '2025-08', 'debug': True}"
    """
    from erpnextaustria.erpnextaustria.doctype.at_vat_declaration.at_vat_declaration import create_uva_pdf

    if debug:
        start_ts = datetime.now()
        print(f"{start_ts.strftime('%Y-%m-%d %H:%M:%S')} Starting package export for AT VAT Declaration {declaration_name}")
    declaration = frappe.get_doc("AT VAT Declaration", declaration_name)
    if not declaration:
        frappe.throw(f"AT VAT Declaration {declaration_name} not found.")

    base_path = frappe.get_value("Microsynth Settings", "Microsynth Settings", "at_vat_export_path") or "/tmp/at_vat_exports"
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    folder_name = f"{timestamp}_AT_VAT_Declaration_{declaration.name}"
    export_path = os.path.join(base_path, folder_name)
    os.makedirs(export_path, exist_ok=True)

    # Generate and save XML file
    try:
        # Ensure start_date and end_date are strings for downstream compatibility
        if hasattr(declaration, "start_date") and declaration.start_date and not isinstance(declaration.start_date, str):
            declaration.start_date = declaration.start_date.strftime("%Y-%m-%d")
        if hasattr(declaration, "end_date") and declaration.end_date and not isinstance(declaration.end_date, str):
            declaration.end_date = declaration.end_date.strftime("%Y-%m-%d")
        xml_result = declaration.generate_transfer_file()
        xml_content = xml_result.get('content') if xml_result else None
        if xml_content:
            xml_filename = f"AT_VAT_Declaration_{declaration.name}.xml"
            xml_filepath = os.path.join(export_path, xml_filename)
            with open(xml_filepath, mode="w", encoding="utf-8") as xmlfile:
                xmlfile.write(xml_content)
            if debug:
                print(f"XML file written: {xml_filepath}")
    except Exception as e:
        msg = f"Failed to generate or write XML: {str(e)}"
        frappe.log_error(msg, "AT VAT Export")
        if debug:
            print(msg)
        frappe.throw(msg)

    # Generate and save PDF file
    try:
        generated_pdf_path = create_uva_pdf(declaration.name)
        pdf_filename = f"AT_VAT_Declaration_{declaration.name}.pdf"
        pdf_filepath = os.path.join(export_path, pdf_filename)
        with open(generated_pdf_path, mode='rb') as src_file:
            pdf_data = src_file.read()
        with open(pdf_filepath, mode='wb') as dest_file:
            dest_file.write(pdf_data)
        if debug:
            print(f"PDF file written: {pdf_filepath}")
    except Exception as e:
        msg = f"Failed to generate or write PDF: {str(e)}"
        frappe.log_error(msg, "AT VAT Export")
        if debug:
            print(msg)
        frappe.throw(msg)

    summary_document_map = {}
    fields = declaration.meta.fields
    declaration_dict = declaration.as_dict()

    start_date = declaration_dict.get("start_date")
    end_date = declaration_dict.get("end_date")

    if not (start_date and end_date):
        msg = f"Missing start_date or end_date in AT VAT Declaration"
        frappe.log_error(msg, "AT VAT Export")
        if debug:
            print(msg)
        frappe.throw(msg)

    code_pattern = re.compile(r"\b(\d{3})\b")  # Match 3-digit codes
    if debug:
        print(f"Export path: {export_path}")
        print(f"\nDeclaration data: {declaration_dict}")
        print(f"\nProcessing fields: {[(df.label, df.fieldname) for df in fields if df.label and df.fieldtype == 'Float']}")

    for df in fields:
        if df.fieldtype != "Float":
            continue

        value = declaration.get(df.fieldname)
        if not flt(value):
            continue

        # Label of fields contains the 3-digit code matching AT VAT queries
        match = code_pattern.search(df.label or "")
        if not match:
            continue

        code = match.group(1)

        # Find corresponding AT VAT query
        vat_query = frappe.get_all("AT VAT query", filters={"code": code}, fields=["query"])
        if not vat_query:
            continue

        raw_query = vat_query[0]["query"]

        try:
            if debug:
                print(f"\n\n\nProcessing code {code} with raw query:\n{raw_query}")
            query = replace_placeholders(raw_query, declaration_dict, code)
            if debug:
                print(f"\n\nFinal query for code {code}:\n{query}")
        except ValueError as e:
            msg = f"Placeholder error in query for code {code}: {str(e)}"
            frappe.log_error(msg, "AT VAT Export")
            if debug:
                print(msg)
            continue

        try:
            # Wrap the entire query in an outer SELECT to apply the posting_date filter
            wrapped_query = f"""
                SELECT *
                FROM ({query}) AS s
                WHERE s.posting_date >= '{start_date}'
                  AND s.posting_date <= '{end_date}'
            """
            results = frappe.db.sql(wrapped_query, as_dict=True)
            if debug:
                print(f"\n{len(results)} query results for code {code}.")
        except Exception as e:
            msg = f"SQL error executing wrapped query for code {code}: {str(e)}"
            frappe.log_error(msg, "AT VAT Export")
            if debug:
                print(msg)
            continue

        query_document_map = {}

        for row in results:
            doctype = row.get("doctype")
            name = row.get("name")
            if doctype and name:
                key = (doctype, name)
                # Add a column with the file name of the exported PDF
                row['filename'] = f"{name}.pdf"
                if key not in query_document_map:
                    query_document_map[key] = row
                if key not in summary_document_map:
                    # Add a column with the query code to each row
                    row['codes'] = [code]
                    summary_document_map[key] = row
                else:
                    # Document already exists from a previous query, just append the code
                    summary_document_map[key]['codes'].append(code)

        if query_document_map:
            # Write one CSV per query/code/field
            try:
                filename = f"AT_VAT_Declaration_{declaration.name}_Code_{code}.csv"
                write_summary_csv(query_document_map.values(), export_path, filename)
            except Exception as e:
                msg = f"Failed to write summary CSV for code {code}: {str(e)}"
                frappe.log_error(msg, "AT VAT Export")
                if debug:
                    print(msg)
            if debug:
                print(f"\nSummary CSV for code {code} written.\n")

    if debug:
        list_to_export = list(summary_document_map.keys())
        list_length = len(list_to_export)
        print(f"\n\n{list_length} documents to export.\n")

    # Write overall summary CSV
    try:
        filename = f"AT_VAT_Declaration_{declaration_name}_summary.csv"
        write_summary_csv(summary_document_map.values(), export_path, filename)
    except Exception as e:
        msg = f"Failed to write summary CSV: {str(e)}"
        frappe.log_error(msg, "AT VAT Export")
        if debug:
            print(msg)
    if debug:
        print(f"\nSummary CSV written.\n")

    # Write PDFs
    export_count = 0
    for (doctype, name), row in summary_document_map.items():
        try:
            doc = frappe.get_doc(doctype, name)
            write_pdf(doc, export_path)
            export_count += 1
            if debug:
                print(f"{export_count}/{list_length}. Exported {doctype} {name} to PDF.")
        except Exception as e:
            msg = f"Failed to export {doctype} {name}: {str(e)}"
            frappe.log_error(msg, "AT VAT Export")
            if debug:
                print(msg)

    if debug:
        end_ts = datetime.now()
        duration = (end_ts - start_ts).total_seconds()
        print(f"\nExported {export_count} PDFs and one summary CSV to {export_path} in {duration:.2f} seconds.\n")


@frappe.whitelist()
def async_at_vat_package_export(declaration_name):
    frappe.enqueue(method=at_vat_package_export, queue='long', timeout=600, declaration_name=declaration_name)
