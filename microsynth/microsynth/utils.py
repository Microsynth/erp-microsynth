# -*- coding: utf-8 -*-
# Copyright (c) 2022-2024, libracore (https://www.libracore.com) and contributors
# For license information, please see license.txt

import os
import re
import frappe
import json
from datetime import datetime, date, timedelta
from frappe.utils import flt, rounded, get_url_to_form, nowdate
from frappe.core.doctype.communication.email import make
from erpnextswiss.scripts.crm_tools import get_primary_customer_contact


def get_customer(contact):
    """
    Returns the customer ID for a contact ID.

    bench execute microsynth.microsynth.utils.get_customer --kwargs "{'contact': 215856 }"
    """
    # get contact
    contact = frappe.get_doc("Contact", contact)
    # check links
    customer_id = None
    for l in contact.links:
        if l.link_doctype == "Customer":
            customer_id = l.link_name
    return customer_id


def check_contact_to_customer():
    """
    Report non-Disabled Contacts that are not linked to any Customer to the Administration.
    Could be executed by a cronjob, e.g. once per month, but is currently not.

    bench execute microsynth.microsynth.utils.check_contact_to_customer
    """
    contacts = frappe.get_all("Contact", filters={'status': ('!=', 'Disabled')}, fields=['name'])
    counter = 0
    message = f"Dear Administration,<br><br>the following Contacts with a numeric ID are not Disabled and are not linked to any Customer:<br>"
    for c in contacts:
        contact = frappe.get_doc("Contact", c['name'])
        customer_id = None
        for l in contact.links:
            if l.link_doctype == "Customer":
                customer_id = l.link_name
                break
        if not customer_id:
            if not contact.name.isnumeric():
                # disable Contacts with non-numeric IDs that are not linked to a Customer (wish by Administration: "Ja, wir haben es durchdacht")
                # contact.status = 'Disabled'
                # contact.save()
                continue
            if int(contact.name) > 800000:
                # try to find Customer with the same ID
                if frappe.db.exists("Customer", contact.name):
                    my_customer_filters = [['docstatus', '<', '2'], ['customer', '=', contact.name]]
                    customer_quotations = frappe.get_all("Quotation", filters=[['docstatus', '<', '2'], ['party_name', '=', contact.name]], fields=['name'])
                    customer_sales_orders = frappe.get_all("Sales Order", filters=my_customer_filters, fields=['name'])
                    customer_delivery_notes = frappe.get_all("Delivery Note", filters=my_customer_filters, fields=['name'])
                    customer_sales_invoices = frappe.get_all("Sales Invoice", filters=my_customer_filters, fields=['name'])
                    sum_linked_customer_docs = len(customer_quotations) + len(customer_sales_orders) + len(customer_delivery_notes) + len(customer_sales_invoices)
                    if sum_linked_customer_docs:
                        print(f"There exists a Customer '{contact.name}' with {sum_linked_customer_docs} linked documents.")
                    else:
                        print(f"There exists an inactive Customer '{contact.name}'.")
                else:
                    #print(f"There exists no Customer '{contact.name}'.")
                    pass
                #continue
            my_filters = [['docstatus', '<', '2'], ['contact_person', '=', contact.name]]
            #contact_notes = frappe.get_all("Contact Notes", filters=my_filters, fields=['name'])
            quotations = frappe.get_all("Quotation", filters=my_filters, fields=['name'])
            sales_orders = frappe.get_all("Sales Order", filters=my_filters, fields=['name'])
            delivery_notes = frappe.get_all("Delivery Note", filters=my_filters, fields=['name'])
            sales_invoices = frappe.get_all("Sales Invoice", filters=my_filters, fields=['name'])
            sum_linked_docs = len(quotations) + len(sales_orders) + len(delivery_notes) + len(sales_invoices)
            #print(f"Contact '{contact.name}' is not linked to any Customer.")
            url = f"https://erp.microsynth.local/desk#Form/Contact/{contact.name}"
            message += f"<br><a href={url}>{contact.name}</a>: {contact.full_name}, created by {contact.owner} on {contact.creation}, {sum_linked_docs} linked Documents"
            print(f"{url}: {contact.full_name}, created by {contact.owner} on {contact.creation}, {sum_linked_docs} linked Documents")
            counter += 1
    print(f"Found {counter} Contacts that are not Disabled and not linked to any Customer.")
    message += "<br><br>Best regards,<br>Jens"
    make(
        recipients = "info@microsynth.ch",
        sender = "erp@microsynth.ch",
        subject = "[ERP] Contacts that are not linked to any Customer",
        content = message,
        send_email = True
    )


def disable_contacts_without_customers():
    """
    Disable Contacts with a numeric ID that are not linked to any Customer

    bench execute microsynth.microsynth.utils.disable_contacts_without_customers
    """
    contacts = frappe.get_all("Contact", filters={'status': ('!=', 'Disabled')}, fields=['name'])
    counter = 0
    for c in contacts:
        contact = frappe.get_doc("Contact", c['name'])
        customer_id = None
        for l in contact.links:
            if l.link_doctype == "Customer":
                customer_id = l.link_name
                break
        if not customer_id:
            if not contact.name.isnumeric():
                continue
            contact.status = 'Disabled'
            contact.save()
            url = f"https://erp.microsynth.local/desk#Form/Contact/{contact.name}"
            print(f"Disabled {url}: {contact.full_name}, created by {contact.owner} on {contact.creation}")
            counter += 1
    print(f"Disabled {counter} Contacts with a numeric ID that are not linked to any Customer.")


def get_billing_address(customer):
    """
    Returns a dictionary of the Address of the Invoice To Contact of the Customer specified by its ID.

    bench execute "microsynth.microsynth.utils.get_billing_address" --kwargs "{'customer': 8003}"
    """
    if type(customer) == str:
        customer = frappe.get_doc("Customer", customer)
    invoice_to_contact = customer.invoice_to
    if not invoice_to_contact:
        #frappe.log_error(f"Customer '{customer.name}' has no Invoice To Contact.", "utils.get_billing_address")
        return find_billing_address(customer.name)
    billing_address = frappe.get_value("Contact", invoice_to_contact, "address")
    if not billing_address:
        if invoice_to_contact.isnumeric():
            frappe.log_error(f"Contact '{invoice_to_contact}' has no Address.", "utils.get_billing_address")
        return find_billing_address(customer.name)
    addresses = frappe.db.sql(f"""
            SELECT
                `tabAddress`.`name`,
                `tabAddress`.`address_type`,
                `tabAddress`.`overwrite_company`,
                `tabAddress`.`address_line1`,
                `tabAddress`.`address_line2`,
                `tabAddress`.`pincode`,
                `tabAddress`.`city`,
                `tabAddress`.`country`,
                `tabAddress`.`is_shipping_address`,
                `tabAddress`.`is_primary_address`,
                `tabAddress`.`geo_lat`,
                `tabAddress`.`geo_long`,
                `tabAddress`.`customer_address_id`
            FROM `tabAddress`
            WHERE `tabAddress`.`name` = "{billing_address}"
            ;""", as_dict=True)
    if len(addresses) == 1:
        return addresses[0]
    else:
        return find_billing_address(customer.name)


def find_billing_address(customer_id):
    """
    Returns the primary billing address of a customer specified by its id.

    run
    bench execute "microsynth.microsynth.utils.find_billing_address" --kwargs "{'customer_id':8003}"
    """
    addresses = frappe.db.sql(
        """ SELECT
                `tabAddress`.`name`,
                `tabAddress`.`address_type`,
                `tabAddress`.`overwrite_company`,
                `tabAddress`.`address_line1`,
                `tabAddress`.`address_line2`,
                `tabAddress`.`pincode`,
                `tabAddress`.`city`,
                `tabAddress`.`country`,
                `tabAddress`.`is_shipping_address`,
                `tabAddress`.`is_primary_address`,
                `tabAddress`.`geo_lat`,
                `tabAddress`.`geo_long`,
                `tabAddress`.`customer_address_id`
            FROM `tabDynamic Link`
            LEFT JOIN `tabAddress` ON `tabAddress`.`name` = `tabDynamic Link`.`parent`
            WHERE `tabDynamic Link`.`parenttype` = "Address"
              AND `tabDynamic Link`.`link_doctype` = "Customer"
              AND `tabDynamic Link`.`link_name` = "{customer_id}"
              AND (`tabAddress`.`is_primary_address` = 1)
            ;""".format(customer_id=customer_id), as_dict=True)

    if len(addresses) == 1:
        return addresses[0]
    else:
        #frappe.throw("None or multiple billing addresses found for customer '{0}'".format(customer_id), "find_billing_address")
        if customer_id.isnumeric():
            frappe.log_error(f"Found {len(addresses)} billing addresses for Customer '{customer_id}'", "find_billing_address")
        return None


@frappe.whitelist()
def get_webshop_url():
    return frappe.get_value('Microsynth Settings', 'Microsynth Settings', 'webshop_url')


@frappe.whitelist()
def update_address_links_from_contact(address_name, links):
    if not address_name:
        return
    if not frappe.db.exists("Address", address_name):
        frappe.throw(f"Address '{address_name}' does not exist.")

    # Parse links if passed as JSON string
    if isinstance(links, str):
        links = json.loads(links)

    # Step 1: Collect all unique Customers linked to this address (directly or indirectly)
    customer_set = set()
    # 1.1 Customers directly linked to the Address
    direct_customers = frappe.get_all("Dynamic Link", filters={
        "parenttype": "Address",
        "parent": address_name,
        "link_doctype": "Customer"
    }, fields=["link_name"])
    customer_set.update(c.link_name for c in direct_customers)
    # 1.2 Customers linked via Contacts that reference this address
    contacts = frappe.get_all("Contact", filters={
        "address": address_name,
        "status": ["!=", "Inactive"]
    }, fields=["name"])
    for contact in contacts:
        contact_customers = frappe.get_all("Dynamic Link", filters={
            "parenttype": "Contact",
            "parent": contact.name,
            "link_doctype": "Customer"
        }, fields=["link_name"])
        customer_set.update(c.link_name for c in contact_customers)
    # Remove the new Customer from customer_set because it seems to be already set on the Contact
    for l in links:
        if l.get("link_doctype") == "Customer":
            customer_set.discard(l.get("link_name"))

    # Step 2: Throw error if more than one Customer is linked (directly or via contacts)
    if len(customer_set) > 1:
        msg = (
            f"Address '{address_name}' is linked to multiple Customers: {', '.join(customer_set)}.<br>"
            f"Contacts using this Address: {', '.join(c.name for c in contacts)}.<br>"
            f"Cannot safely update Customer link."
        )
        frappe.throw(msg)

    # Step 3: Update the single existing Customer link
    address = frappe.get_doc("Address", address_name)
    customer_links = [l for l in address.links if l.link_doctype == "Customer"]
    if len(customer_links) != 1:
        frappe.throw(f"Expected exactly one Customer link on Address '{address_name}', found {len(customer_links)}.")
    input_customer_links = [l for l in links if l.get("link_doctype") == "Customer"]
    if len(input_customer_links) != 1:
        frappe.throw("Exactly one Customer link must be provided.")
    customer_links[0].link_name = input_customer_links[0].get("link_name")
    customer_links[0].link_title = input_customer_links[0].get("link_title")
    address.save()
    return


def create_oligo(oligo):
    oligo_doc = None
    # check if this oligo is already in the database
    if oligo['web_id']:
        oligo_matches = frappe.get_all("Oligo",
            filters={'web_id': oligo['web_id']}, fields=['name'])
        if len(oligo_matches) > 0:
            # update and return this item
            oligo_doc = frappe.get_doc("Oligo", oligo_matches[0]['name'])
    if not oligo_doc:
        # create oligo
        oligo_doc = frappe.get_doc({
            'doctype': 'Oligo',
            'oligo_name': oligo['name'],
            'web_id': oligo['web_id']
        })
        oligo_doc.insert(ignore_permissions=True)
    # update record
    if 'name' in oligo:
        oligo_doc.oligo_name = oligo['name']
    if 'status' in oligo:
        oligo_doc.status = oligo['status']
    if 'substance_type' in oligo:
        oligo_doc.substance_type = oligo['substance_type']
    if 'sequence' in oligo:
        oligo_doc.sequence = oligo['sequence']
    if 'scale' in oligo:
        oligo_doc.scale = oligo['scale']
    if 'purification' in oligo:
        oligo_doc.purification = oligo['purification']
    if 'phys_cond' in oligo:
        oligo_doc.phys_cond = oligo['phys_cond']
    if 'data_sheet' in oligo:
        oligo_doc.data_sheet = oligo['data_sheet']
    if 'aliquots' in oligo:
        oligo_doc.aliquots = oligo['aliquots']
    # update child table
    if 'items' in oligo:
        oligo_doc.items = []
        for i in oligo['items']:
            oligo_doc.append("items", {
                'item_code': i['item_code'],
                'qty':i['qty']
            })
    oligo_doc.save(ignore_permissions=True)

    return oligo_doc.name


def create_sample(sample):
    sample_doc = None
    # check if this oligo is already in the database
    if sample['sample_web_id']:
        sample_matches = frappe.get_all("Sample",
            filters={'web_id': sample['sample_web_id']}, fields=['name'])
        if len(sample_matches) > 0:
            # update and return this item
            sample_doc = frappe.get_doc("Sample", sample_matches[0]['name'])
    if not sample_doc:
        # fetch sequencing label
        matching_labels = frappe.get_all("Sequencing Label",filters={
            'label_id': sample.get("sequencing_label"),
            'item': sample.get("label_item_code")
        }, fields=['name'])

        if matching_labels and len(matching_labels) == 1:
            label = frappe.get_doc("Sequencing Label", matching_labels[0]["name"])
        else:
            # TODO: activate error logging, when labels are in the ERP
            # frappe.log_error("Sequencing Label for sample with web id '{web_id}' not found: barcode number '{barcode}', item '{item}'".format(
            #     web_id = sample['sample_web_id'],
            #     barcode = sample.get("sequencing_label"),
            #     item =sample.get("label_item_code") ), "utils: create_sample")
            label = None

        # create sample
        web_id = None
        if 'sample_web_id' in sample:
            web_id = sample['sample_web_id']
        elif 'web_id' in sample:
            web_id = sample['web_id']
        sample_doc = frappe.get_doc({
            'doctype': 'Sample',
            'sample_name': sample['name'],
            'web_id': web_id,
            'sequencing_label': label.name if label else None
        })
        sample_doc.insert(ignore_permissions=True)
    # update record
    sample_doc.sample_name = sample['name']
    # update child table
    if 'items' in sample:
        sample_doc.items = []
        for i in sample['items']:
            sample_doc.append("items", {
                'item_code': i['item_code'],
                'qty':i['qty']
            })
    sample_doc.save(ignore_permissions=True)

    return sample_doc.name


def find_label(label_barcode, item):
    """
    Find a Sequencing Label by its barcode and item.
    """

    sql_query = """SELECT `tabSequencing Label`.`name`
        FROM `tabSequencing Label`
        WHERE `tabSequencing Label`.`label_id` = "{label_id}"
        AND `tabSequencing Label`.`item` = "{item}"
    """.format(label_id=label_barcode, item=item)

    labels = frappe.db.sql(sql_query, as_dict=True)

    if len(labels) == 1:
        return labels[0]['name']
    elif len(labels) == 0:
        return None
    else:
        frappe.throw("Multiple labels found for label_barcode '{0}', item '{1}'".format(str(label_barcode),str(item)))


@frappe.whitelist(allow_guest=True)
def login(usr, pwd):
    """
    Create a user session
    """
    from frappe.auth import LoginManager
    lm = LoginManager()
    lm.authenticate(usr, pwd)
    lm.login()
    return frappe.local.session


def replace_none(inpt):
    """
    Return an empty string if the input is None, else return the input.
    """
    return inpt if (inpt != None) else ""


def to_bool(inpt):
    """
    Return the boolean True if the input evaluates to true else return the boolean False.
    """
    if inpt:
        return True
    else:
        return False


def get_name(contact):
    """
    Assembles the first name and last name of a contact
    to a single name string.
    """
    name_elements = []
    if contact.first_name != "-":
        name_elements.append(contact.first_name)
    if contact.last_name:
        name_elements.append(contact.last_name)

    name_line = " ".join(name_elements)

    return name_line


def get_name_line(contact):
    """
    Assembles the first name, last name and designation of a contact
    to a single name line string.
    """
    name_elements = []
    if contact.designation:
        name_elements.append(contact.designation)
    if contact.first_name != "-":
        name_elements.append(contact.first_name)
    if contact.last_name:
        name_elements.append(contact.last_name)

    name_line = " ".join(name_elements)

    return name_line


@frappe.whitelist()
def get_email_ids(contact):
    """
    Return a list of all email_ids of the given contact.
    """
    contact_doc = frappe.get_doc("Contact", contact)
    email_ids = []
    for line in contact_doc.email_ids:
        email_ids.append(line.email_id)
    return email_ids


@frappe.whitelist()
def get_print_address(contact, address, customer=None, customer_name=None):
    if customer and not customer_name:
        customer_name = frappe.get_value("Customer", customer, 'customer_name')

    return frappe.render_template("microsynth/templates/includes/address.html",
        {
            'contact': contact,
            'address': address,
            'customer_name':  customer_name
        })


def get_posting_datetime(document):
    """
    Return the posting timepoint as a datetime object from the given document e.g. Sales Invoice.
    The document must have the fields 'posting_date' and 'posting_time'
    """
    posting = datetime.combine(document.posting_date, (datetime.min + document.posting_time).time())
    return posting


@frappe.whitelist()
def set_order_label_printed(sales_orders):
    if type(sales_orders) == str:
        sales_orders = json.loads(sales_orders)

    for o in sales_orders:
        if frappe.db.exists("Sales Order", o):
            sales_order = frappe.get_doc("Sales Order", o)
            sales_order.label_printed_on = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            sales_order.save()
    frappe.db.commit()
    return


def get_country_express_shipping_item(country_name, currency):
    """
    Return the preferred shipping item for the given country name.
    """

    country = frappe.get_doc("Country", country_name)
    express_items = []

    for item in country.shipping_items:
        if item.preferred_express and item.currency == currency:
            express_items.append(item)

    if len(express_items) == 0:
        frappe.log_error(f"No preferred express item found for country '{country_name}' and currency {currency}", "utils.get_country_express_shipping_item")
        return None
    if len(express_items) > 0:

        if len(express_items) > 1:
            frappe.log_error(f"Multiple preferred express shipping items found for country '{country_name}' and currency {currency}", "utils.get_country_express_shipping_item")
        return express_items[0]


def get_customer_express_shipping_item(customer_name):
    """
    Return the preferred express shipping item for the given customer ID.
    """

    customer = frappe.get_doc("Customer", customer_name)
    express_items = []

    for item in customer.shipping_items:
        if item.preferred_express:
            express_items.append(item)

    if len(express_items) == 0:
        return None
    if len(express_items) > 0:
        if len(express_items) > 1:
            frappe.log_error("Multiple preferred express shipping items found for customer '{0}'".format(customer_name), "utils.get_customer_express_shipping_item")
        return express_items[0]


def get_express_shipping_item(customer_name, country_name):
    """
    Return the preferred express shipping item for the given customer ID and country name.

    The shipping items of the customer override those of the country.

    If the customer does not have a preferred express item, the preferred express item of the
    country is returned.

    run
    bench execute microsynth.microsynth.utils.get_express_shipping_item --kwargs "{ 'customer_name': '840574', 'country_name': 'Poland' }"
    """
    customer_express_item = get_customer_express_shipping_item(customer_name)
    if customer_express_item:
        return customer_express_item
    else:
        customer_currency = frappe.get_value("Customer", customer_name, "default_currency")
        country_express_item = get_country_express_shipping_item(country_name, customer_currency)
        return country_express_item


@frappe.whitelist()
def get_export_category(address_name):
    """
    Return the export_code of the Country of the given Address, except Canary Islands (ROW).

    run
    bench execute microsynth.microsynth.utils.get_export_category --kwargs "{'address_name': '817145'}"
    """
    address_doc = frappe.get_doc("Address", address_name)
    for link in address_doc.links:
        if link.link_doctype == "Customer":
            customer = link.link_name
            if frappe.get_value("Customer", customer, "customer_type") == "Individual":
                # do not put private Customers on EU customs declaration
                return 'ROW'
    country = address_doc.country  #frappe.get_value('Address', address_name, 'country')
    if country == "Austria":
        export_category = "AT"
    elif country == "Spain":
        postal_code = frappe.get_value('Address', address_name, 'pincode')
        if not postal_code:
            frappe.log_error(f"Empty postal_code for {address_name=} in Spain.", "utils.get_export_category")
            return frappe.get_value('Country', country, 'export_code')
        try:
            # delete non-numeric characters
            numeric_postal_code = re.sub('\D', '', postal_code)
        except Exception as err:
            frappe.log_error(f"Got the following error when trying to delete non-numeric characters from postal code '{postal_code}' of {address_name=} in Spain:\n{err}", "utils.get_export_category")
            return frappe.get_value('Country', country, 'export_code')
        if not numeric_postal_code:
            frappe.log_error(f"Postal code '{postal_code}' for {address_name=} in Spain does not contain any numbers.", "utils.get_export_category")
            return frappe.get_value('Country', country, 'export_code')
        if len(numeric_postal_code) != 5:
            frappe.log_error(f"Postal code '{postal_code}' for {address_name=} in Spain does not contain five digits.", "utils.get_export_category")
            return frappe.get_value('Country', country, 'export_code')
        pc_prefix = int(numeric_postal_code[:2])
        if pc_prefix == 35 or pc_prefix == 38:
            # "Kanarische Inseln nicht auf EU-Verzollung"
            return 'ROW'
        else:
            return frappe.get_value('Country', country, 'export_code')
    else:
        export_category = frappe.get_value('Country', country, 'export_code')
    return export_category


def get_physical_path(file_name):
    file_url = frappe.get_value("File", file_name, "file_url")     # something like /private/files/myfile.pdf
    base_path = os.path.join(frappe.utils.get_bench_path(), "sites", frappe.utils.get_site_path()[2:])

    return "{0}{1}".format(base_path, file_url)


def get_customer_from_sales_order(sales_order):
    customer_name = frappe.get_value("Sales Order", sales_order, 'customer')
    customer = frappe.get_doc("Customer", customer_name)
    return customer


def get_customer_from_company(company):
    customers = frappe.get_all("Intercompany Settings Company", filters={'company': company}, fields=['customer'])
    if len(customers) > 0:
        return customers[0]['customer']
    else:
        return None


def get_margin_from_company(company):
    margins = frappe.get_all("Intercompany Settings Company", filters={'company': company}, fields=['margin'])
    if len(margins) == 1:
        return margins[0]['margin']
    else:
        frappe.log_error(f"There are {len(margins)} Companies '{company}' in the Intercompany Settings.", "utils.get_margin_from_company")
        return None


def get_margin_from_customer(customer):
    margins = frappe.get_all("Intercompany Settings Company", filters={'customer': customer}, fields=['margin'])
    if len(margins) == 1:
        return margins[0]['margin']
    else:
        frappe.log_error(f"There are {len(margins)} Customers '{customer}' in the Intercompany Settings.", "utils.get_margin_from_company")
        return None


def get_supplier_for_product_type(company, product_type):
    """
    Returns a ['supplier': '..', 'supplier_name': '..', 'manufacturing_company': '..'] dict or None if there is no applicable intercompany supplier
    """
    suppliers = frappe.get_all("Intercompany Settings Supplier",
        filters={
            'company': company,
            'product_type': product_type
        },
        fields=['supplier', 'supplier_name', 'manufacturing_company']
    )
    if len(suppliers) > 0:
        if len(suppliers) > 1:
            frappe.log_error(f"Multiple suitable intercompany suppliers found for {company} and {product_type}", "utils.get_supplier_for_product_type")
        return suppliers[0]
    else:
        return None


@frappe.whitelist()
def has_intercompany_order(sales_order_id, po_no):
    """
    Check if the PO corresponds to an existing Sales Order or
    if there is a submitted Sales Order that has the given sales_order_id as po_no.
    If yes, return the (first) Sales Order ID, else None

    bench execute microsynth.microsynth.utils.has_intercompany_order --kwargs "{'sales_order_id': 'SO-BAL-25017491', 'po_no': 'SO-LYO-25000606'}"
    """
    if po_no and po_no.startswith("SO-"):
        if frappe.db.exists("Sales Order", po_no):
            return po_no
    if sales_order_id:
        sales_orders = frappe.get_all("Sales Order", filters=[['po_no', '=', sales_order_id], ['docstatus', '=', 1]], fields=['name'])
        if len(sales_orders) > 0:
            return sales_orders[0]['name']
        else:
            return None
    else:
        return None


@frappe.whitelist()
def has_intercompany_orders(po_no):
    """
    Check if the PO corresponds to existing Sales Orders.
    If yes, return the a html link list, else None

    bench execute microsynth.microsynth.utils.has_intercompany_orders --kwargs "{'sales_invoice_id': 'SO-BAL-25017491', 'po_no': 'SO-LYO-25000606'}"
    """
    if po_no and po_no.startswith("SO-"):
        html_parts = []
        sales_order_ids = po_no.split(',')
        for so_id in sales_order_ids:
            so_id = so_id.strip()
            if frappe.db.exists("Sales Order", so_id):
                html_parts.append("<a href='/desk#Form/Sales Order/" + so_id + "'>" + so_id + "</a>")
        if len(html_parts) > 0:
            return ', '.join(html_parts)
        else:
            return None
    else:
        return None


def validate_sales_order_status(sales_order):
    """
    Checks if the customer is enabled, the sales order is submitted, has an allowed
    status and has the tax template set.

    run
    bench execute microsynth.microsynth.utils.validate_sales_order_status --kwargs "{'sales_order': ''}"
    """
    customer = get_customer_from_sales_order(sales_order)

    if customer.disabled:
        frappe.log_error("Customer '{0}' of order '{1}' is disabled. Cannot create a delivery note.".format(customer.name, sales_order), "utils.validate_sales_order_status")
        return False

    so = frappe.get_doc("Sales Order", sales_order)

    if so.status in ['Completed', 'Cancelled', 'Closed']:
        user = frappe.get_user().name
        if user == 'bos@microsynth.ch':
            email_template = frappe.get_doc("Email Template", "Unable to create Delivery Note")
            rendered_subject = frappe.render_template(email_template.subject, {'web_order_id': so.web_order_id})
            so_url_string = f"<a href={get_url_to_form('Sales Order', so.name)}>{so.name}</a>"
            rendered_content = frappe.render_template(email_template.response, {'sales_order_id': so_url_string, 'web_order_id': so.web_order_id, 'status': so.status})
            send_email_from_template(email_template, rendered_content, rendered_subject)
            #frappe.log_error(f'Sales Order {so.name} with Web Order ID {so.web_order_id} is in status {so.status}. Cannot create a Delivery Note.\n\nSent an email to {email_template.recipients}.', 'utils.validate_sales_order_status')
        else:
            frappe.log_error(f'Sales Order {so.name} with Web Order ID {so.web_order_id} is in status {so.status}. Cannot create a Delivery Note.\n\n{user=}', 'utils.validate_sales_order_status')
        return False

    if so.docstatus != 1:
        frappe.log_error(f"Sales Order {so.name} is not submitted and has docstatus {so.docstatus}. Cannot create a delivery note.", "utils.validate_sales_order_status")
        return False

    if not so.taxes_and_charges or so.taxes_and_charges == "":
        frappe.log_error(f"Sales Order {so.name} has no Sales Taxes and Charges Template. Cannot create a delivery note.", "utils.validate_sales_order_status")
        return False

    return True


def validate_sales_order(sales_order):
    """
    Checks if the customer is enabled, the sales order is submitted, has an allowed
    status, has the tax template set and there are no delivery notes in status draft, submitted.

    run
    bench execute microsynth.microsynth.utils.validate_sales_order --kwargs "{'sales_order': ''}"
    """

    if not validate_sales_order_status(sales_order):
        return False

    # Check if delivery notes exists. consider also deliver notes with the same web_order_id
    web_order_id = frappe.get_value("Sales Order", sales_order, "web_order_id")
    if web_order_id:
        web_order_id_condition = f" OR `tabDelivery Note`.`web_order_id` = '{web_order_id}' "
    else:
        web_order_id_condition = ""

    delivery_notes = frappe.db.sql(f"""
        SELECT `tabDelivery Note Item`.`parent`
        FROM `tabDelivery Note Item`
        LEFT JOIN `tabDelivery Note` ON `tabDelivery Note`.`name` = `tabDelivery Note Item`.`parent`
        WHERE `tabDelivery Note Item`.`docstatus` < 2
            AND (`tabDelivery Note Item`.`against_sales_order` = '{sales_order}'
                {web_order_id_condition});
        """, as_dict=True)

    if len(delivery_notes) > 0:
        # frappe.log_error("Order '{0}' has already Delivery Notes. Cannot create a delivery note.".format(sales_order), "utils.validate_sales_order")
        return False

    return True


def clean_up_delivery_notes(sales_order_id):
    """
    Deletes all delivery notes in draft mode but the latest one.
    """

    query = """
        SELECT `tabDelivery Note Item`.`parent` AS `delivery_note`
        FROM `tabDelivery Note Item`
        WHERE `tabDelivery Note Item`.`against_sales_order` = "{sales_order}"
        AND `tabDelivery Note Item`.`docstatus` <> 2
        GROUP BY `tabDelivery Note Item`.`parent`
    """.format(sales_order = sales_order_id)
    delivery_notes = frappe.db.sql(query, as_dict = True)

    has_dn = False

    for dn_id in reversed(delivery_notes):
        dn = frappe.get_doc("Delivery Note", dn_id.delivery_note)

        if dn.docstatus == 1:
            if has_dn:
                frappe.log_error("Sales Order '{0}' has delivery notes in submitted and draft mode".format(sales_order_id), "utils.clean_up_delivery_notes")
            # delivery note is submitted. keep it.
            has_dn = True

        elif dn.docstatus == 0 and not has_dn:
            # keep the delivery note with the highest ID (iterate in reversed order)
            has_dn = True

        elif dn.docstatus == 0 and has_dn:
            # delete the delivery note if there is already one to keep
            print("Sales Order '{0}': Delete Delivery Note '{1}'".format(sales_order_id, dn.name))
            dn.delete()

        else:
            frappe.log_error("Delivery Note '{0}' is not in draft status. Cannot delete it. Status: {1}".format(dn.name, dn.docstatus), "utils.clean_up_delivery_notes")

    frappe.db.commit()
    return


def clean_up_all_delivery_notes():
    """
    Finds sales orders with multiple delivery notes that are not cancelled.
    Deletes all delivery notes in draft mode but the latest one.

    run
    bench execute "microsynth.microsynth.utils.clean_up_all_delivery_notes"
    """

    query = """
        SELECT `against_sales_order` AS `name`
        FROM
          (SELECT `against_sales_order`,
                  COUNT(`name`) AS `count`
           FROM `tabDelivery Note Item`
           WHERE `idx` = 1
             AND `docstatus` < 2
           GROUP BY `against_sales_order`) AS `raw`
        WHERE `raw`.`count` > 1
    """

    print("query sales orders with multiple delivery notes...")
    sales_orders = frappe.db.sql(query, as_dict=True)

    print("clean up delivery notes...")

    total = len(sales_orders)
    count = 0

    for so in sales_orders:
        print("process '{0}' - {1}% of total ({2})".format(so.name, int(count/total * 100), total))
        clean_up_delivery_notes(so.name)
        count += 1

    return


def remove_delivery_notes_from_customs_declaration(customs_declaration, delivery_notes):
    """
    Removes Delivery Notes from a Customs Declaration but only if the Delivery Note is in draft.

    run
    bench execute "microsynth.microsynth.utils.remove_delivery_notes_from_customs_declaration" --kwargs "{'customs_declaration': 'CD-23002', 'delivery_notes':['DN-BAL-23048017']}"
    """
    customs_declaration = frappe.get_doc("Customs Declaration", customs_declaration)

    for dn in delivery_notes:
        if frappe.get_value("Delivery Note", dn, "docstatus") == 0:
            for eu_dn in customs_declaration.eu_dns:
                if eu_dn.delivery_note == dn:
                    print("Remove Delivery Note '{0}' (EU)".format(dn))
                    # eu_dn.delete()  # Validation error: Submitted Record cannot be deleted.
                    frappe.db.delete("Customs Declaration Delivery Note", {
                        "name": eu_dn.name
                    })
            for at_dn in customs_declaration.austria_dns:
                if at_dn.delivery_note == dn:
                    print("Remove Delivery Note '{0}' (AT)".format(dn))
                    # at_dn.delete()  # Validation error: Submitted Record cannot be deleted.
                    frappe.db.delete("Customs Declaration Delivery Note", {
                        "name": at_dn.name
                    })
        else:
            print("Cannot remove Delivery Note '{0}'. Delivery Note is not in draft status.".format(dn))
    frappe.db.commit()
    return


def update_shipping_item(item, rate = None, qty = None, threshold = None, preferred_express = None):
    """
    Print out the data for a data import csv-file to update shipping item rate

    Important Note:
    The template includes columns for Webshop Service. This data is currently not
    written to the import data and thus might delete existing Webshop Services!

    Run
    $ bench execute "microsynth.microsynth.utils.update_shipping_item" --kwargs "{'item':'1114', 'rate':42.00}"
    $ bench execute "microsynth.microsynth.utils.update_shipping_item" --kwargs "{'item':'1117', 'preferred_express':1}"
    $ bench execute "microsynth.microsynth.utils.update_shipping_item" --kwargs "{'item':'1117', 'threshold':1000.0}"
    """

    header = """\"Data Import Template"
"Table:","Country"
""
""
"Notes:"
"Please do not change the template headings."
"First data column must be blank."
"If you are uploading new records, leave the ""name"" (ID) column blank."
"If you are uploading new records, ""Naming Series"" becomes mandatory, if present."
"Only mandatory fields are necessary for new records. You can delete non-mandatory columns if you wish."
"For updating, you can update only selective columns."
"You can only upload upto 5000 records in one go. (may be less in some cases)"
""
"DocType:","Country","","~","Webshop Service Link","webshop_service","~","Shipping Item","shipping_items","","","","",""
"Column Labels:","ID","Country Name","","ID","Webshop Service","","ID","Item","Qty","Rate","Threshold","Item name","Preferred express"
"Column Name:","name","country_name","~","name","webshop_service","~","name","item","qty","rate","threshold","item_name","preferred_express"
"Mandatory:","Yes","Yes","","Yes","Yes","","Yes","Yes","Yes","Yes","Yes","No","No"
"Type:","Data","Data","","Data","Link","","Data","Link","Float","Float","Float","Data","Check"
"Info:","","","","","Valid Webshop Service","","","Valid Item","","","","","0 or 1"
"Start entering data below this line\""""
    print(header)

    countries = frappe.get_all("Country")
    # return frappe.get_doc("Country", "Switzerland")

    for country in countries:
        country_doc = frappe.get_doc("Country", country)

        shipping_item_names = []
        for n in country_doc.shipping_items:
            shipping_item_names.append(n.item)

        if item in shipping_item_names:
            i = 0
            for shipping_item in country_doc.shipping_items:
                if i == 0:
                    country_id = "\"\"{0}\"\"".format(country.name)
                    country_name = country.name
                else:
                    country_id = ""
                    country_name = ""

                if shipping_item.item == item:
                    new_qty = qty if qty else 1
                    new_rate = rate if rate else shipping_item.rate
                    new_threshold = threshold if threshold else shipping_item.threshold
                    new_item_name = shipping_item.item_name
                    new_preferred_express = preferred_express if preferred_express else shipping_item.preferred_express
                else:
                    new_qty = shipping_item.qty
                    new_rate = shipping_item.rate
                    new_threshold = shipping_item.threshold
                    new_item_name = shipping_item.item_name
                    new_preferred_express = shipping_item.preferred_express

                print("""\"\",\"{country_id}\","{country_name}","","","","",\"\"\"{shipping_item_id}\"\"\","{item_code}",{qty},{rate},{threshold},\"{item_name}\",{preferred_express}""".format(
                    country_id = country_id,
                    country_name = country_name,
                    shipping_item_id = shipping_item.name,
                    item_code = shipping_item.item,
                    qty = new_qty,
                    rate = new_rate,
                    threshold = new_threshold,
                    item_name = new_item_name,
                    preferred_express = new_preferred_express))

                i += 1


def set_distributor(customer, distributor, product_type):
    """
    Set the specified distributor for the a product type to the customer. If there is already a distributor set, replace it with the new one.

    run
    bench execute "microsynth.microsynth.utils.set_distributor" --kwargs "{'customer':8003, 'distributor':35914214, 'product_type':'Oligos'}"
    """
    # validate input
    if customer == distributor:
        frappe.log_error("The provided distributor '{0}' is the same as the customer. Cannot set distributor for Customer '{1}' and product type '{2}'.".format(distributor,customer,product_type),"utils.add_distributor")
        return

    if not frappe.db.exists("Customer", distributor):
        frappe.log_error("The provided distributor '{0}' does not exist. Processing Customer '{1}'.".format(distributor,customer),"utils.add_distributor")
        return

    customer = frappe.get_doc("Customer", customer)

    updated = False
    for d in customer.distributors:
        if d.product_type == product_type:
            print("Customer '{0}': Update distributor for '{1}': '{2}' -> '{3}'".format(customer.name, product_type, d.distributor, distributor))
            d.distributor = distributor
            updated = True

    if not updated:
        print("Customer '{0}': Add distributor '{1}' for '{2}'".format(customer.name, distributor, product_type))
        entry = {
            'distributor': distributor,
            'product_type': product_type
        }
        customer.append("distributors",entry)

    customer.save()


def get_webshop_services(customer_id):
    """
    Return a list of the Webshop Services set for the given Customer.

    bench execute microsynth.microsynth.utils.get_webshop_services --kwargs "{'customer_id':'832188'}"
    """
    webshop_services = frappe.get_all("Webshop Service Link",
        filters={'parent': customer_id, 'parenttype': "Customer"},
        fields=['name', 'parent', 'webshop_service']
    )
    return [ws.get('webshop_service') for ws in webshop_services]


def has_webshop_service(customer, service):
    """
    Check if a csutomer has the specified webshop service (e.g. 'EasyRun', 'FullPlasmidSeq')

    bench execute microsynth.microsynth.utils.has_webshop_service --kwargs "{'customer':'832188', 'service':'FullPlasmidSeq'}"
    """
    webshop_services = frappe.get_all("Webshop Service Link",
        filters={'parent': customer, 'parenttype': "Customer", 'webshop_service': service},
        fields=['name', 'parent']
    )
    return len(webshop_services) > 0


def add_webshop_service(customer, service):
    """
    Add the specified webshop service (e.g. 'EasyRun', 'FullPlasmidSeq') to the customer.

    bench execute microsynth.microsynth.utils.add_webshop_service --kwargs "{'customer':'832188', 'service':'FullPlasmidSeq'}"
    """
    customer = frappe.get_doc("Customer", customer)
    has_service = False

    for s in customer.webshop_service:
        if s.webshop_service == service:
            has_service = True

    if not has_service:
        print("Customer '{0}': Add webshop service '{1}'".format(customer.name, service))
        entry = {
            'webshop_service': service
        }
        customer.append("webshop_service", entry)
        customer.save()
    else:
        print("Customer '{0}': Has already webshop service '{1}'".format(customer.name, service))
    return


def add_webshop_service_to_customers(customer_ids, service):
    """
    Wrapper to add the given Webshop Service to all given Customers.

    bench execute microsynth.microsynth.utils.add_webshop_service_to_customers --kwargs "{'customers': ['832188', '8003'], 'service':'InvoiceByDefaultCompany'}"
    """
    for customer_id in customer_ids:
        add_webshop_service(customer_id, service)


def add_webshop_services_for_italy(customer_id):
    """
    Add Webshop services EasyRun and DirectOligoOrders to the Customer if its first shipping address is in Italy.

    bench execute microsynth.microsynth.utils.add_webshop_services_for_italy --kwargs "{'customer_id': '20043'}"
    """
    shipping_address = get_first_shipping_address(customer_id)
    if shipping_address is None:
        frappe.log_error(f"Customer '{customer_id}' has no shipping address.", "utils.add_webshop_services_for_italy")
        return

    country = frappe.get_value("Address", shipping_address, "Country")
    if country == "Italy":
        #add_webshop_service(customer_id, 'EasyRun')  # moved to function set_webshop_services (Italy is part of Territory Rest of Europe (West))
        add_webshop_service(customer_id, 'DirectOligoOrders')


def get_child_territories(territory):
    """
    Returns all child territories for the given territory recursively. Includes the given parent directory and all nodes as well.
    bench execute microsynth.microsynth.utils.get_child_territories --kwargs "{'territory': 'Switzerland'}"
    """
    entries = frappe.db.sql("""select name, lft, rgt, {parent} as parent
            from `tab{tree}` order by lft"""
        .format(tree="Territory", parent="parent_territory"), as_dict=1)

    territory_range = {}
    for d in entries:
        if d.name == territory:
            territory_range['lft'] = d['lft']
            territory_range['rgt'] = d['rgt']

    if 'lft' not in territory_range or 'rgt' not in territory_range:
        frappe.log_error("The provided territory does not exist:\n{0}".format(territory), "utils.get_all_child_territories")
        return []

    territories = []
    for d in entries:
        if territory_range['lft'] <= d['lft'] and d['rgt'] <= territory_range['rgt']:
            territories.append(d.name)

    return territories


def get_debtor_account_currency(company, currency):
    """
    Return the deptor account for a company and the specified currency,

    run
    bench execute microsynth.microsynth.utils.get_debtor_account --kwargs "{'company': 'Microsynth AG', 'currency': 'EUR' }"
    """

    print("get_debtor_accout for '{0}' and '{1}'".format(company, currency))

    query = """
        SELECT `name`
        FROM `tabAccount`
        WHERE `company` = '{company}'
        AND `account_currency` = '{currency}'
        AND `account_type` = 'Receivable'
        AND `disabled` = 0
    """.format(company =company, currency = currency)

    accounts = frappe.db.sql(query, as_dict=True)

    if len(accounts) == 1:
        return accounts[0]
    else:
        frappe.throw("None or multiple debtor accounts for customer '{0}' and curreny '{1}'".format(company, currency), "utils.get_debtor_account_currency")
        return None


def get_account_by_number(company, account_number):
    accounts = frappe.get_all("Account", filters = { 'company': company, 'account_number': account_number, 'account_type': 'Receivable' })

    if len(accounts) == 1:
        # print("{0}: {1}".format(accounts[0].name, accounts[0].currency))
        return accounts[0].name
    else:
        frappe.throw("None or multiple debtor accounts found for company '{0}', account_number '{1}'".format(company, account_number), "utils.get_debtor_account")
        return None


def get_debtor_account(company, currency, country):
    """
    Get the debtor account for customer, currency and country combination.

    run
    bench execute microsynth.microsynth.utils.get_debtor_account --kwargs "{'company': 'Microsynth AG', 'currency': 'CHF', 'country' : 'Switzerland' }"
    """

    company_country = frappe.get_value("Company", company, "country")

    if company == "Microsynth AG":
        if currency == "CHF":
            account = 1100
        elif currency == "EUR":
            account = 1102
        elif currency == "USD":
            account = 1101
        elif currency == "PLN":
            account = 1107
        elif currency == "SEK":
            account = 1104
        # unknown currencies
        else:
            account = 1100

    elif company == "Microsynth Austria GmbH":
        if country == company_country:
            account = 2000
        else:
            account = 2100

    elif company == "Microsynth France SAS":
        if country == company_country:
            account = 4112000
        else:
            account = 4119000

    elif company == "Microsynth Seqlab GmbH":
        if currency == "PLN":
            account = 1403
        elif currency == "SEK":
            account = 1404
        # Note: USD debtor account 1401 is not used because there is no USD bank account
        # USD invoices are assigned to the EUR debtor account 1400
        else:
            account = 1400

    elif company == "Ecogenics GmbH":
        if currency == "EUR":
            account = 1102
        elif currency == "USD":
            account = 1101
        else:
            account = 1100

    return account


def set_debtor_accounts(customer):
    """
    Set the debtor account for customer.

    run
    bench execute microsynth.microsynth.utils.set_debtor_accounts --kwargs "{'customer': 8003 }"
    """

    companies = frappe.get_all("Company", fields = ['name', 'default_currency'])

    default_currencies = {}
    for company in companies:
        default_currencies[company.name] = company.default_currency

    customer = frappe.get_doc("Customer", customer)

    # allow to set specific debtor accounts for intercompany customers
    if customer.invoicing_method == "Intercompany":
        return

    if not customer.default_currency:
        customer.default_currency = default_currencies[customer.default_company]

    address = get_billing_address(customer.name)

    if not address:
        if customer.name.isnumeric():
            frappe.log_error(f"Customer {customer.name} has no Preferred Billing Address. Unable to set Accounts.", "utils.set_debtor_accounts")
        return

    for company in companies:
        account_number =  get_debtor_account(company.name, customer.default_currency, address.country)
        account = get_account_by_number(company.name, account_number)

        entry_exists = False

        for a in customer.accounts:
            if a.company == company.name:
                # update
                a.account = account
                entry_exists = True
                break
        if not entry_exists:
            # create new account entry
            if account:
                entry = {
                    'company': company.name,
                    'account': account
                }
                customer.append("accounts", entry)

    customer.save()
    #TODO Do not commit when using this function when initializing a customer
    frappe.db.commit()
    return


def set_default_language(customer):
    """
    Set the default print language for a customer if it is not yet defined.

    run
    bench execute microsynth.microsynth.utils.set_default_language --kwargs "{'customer':'8003'}"
    """
    customer = frappe.get_doc("Customer", customer)
    if customer.language:
        # early abort if language is already set
        return

    a = get_billing_address(customer)

    if not a:
        frappe.log_error(f"Customer {customer.name} has no Preferred Billing Address. Unable to set default language.", "utils.set_default_language")
        return

    if a.country == "Switzerland":
        try:
            if int(a.pincode) < 3000:
                l = "fr"
            else:
                l = "de"
        except Exception:
            frappe.log_error("Billing address '{0}' of customer '{1}' has the invalid pincode '{2}'.".format(a.name, customer.name, a.pincode), "utils.set_default_language")
            l = "de"
    elif a.country in ("Germany", "Austria"):
        l = "de"
    elif a.country in ("France", "Réunion", "French Guiana"):
        l = "fr"
    else:
        l = "en"

    if customer.language is None:
        customer.language = l
        customer.save()
        # frappe.db.commit()


def set_invoice_to(customer):
    """
    Assert that there is an invoice to set
    """
    doc = frappe.get_doc("Customer", customer)
    if not doc.invoice_to:
        contact = get_primary_customer_contact(customer)
        doc.invoice_to = contact.name
        doc.save()
        frappe.db.commit()
    return


def set_webshop_services(customer_id):
    """
    Set Webshop Service "EasyRun" for all Rest of Europe Territories.
    Set Webshop Service "InvoiceByDefaultCompany" for all French Territories, all German Territories and Austria.
    Set Webshop Service "EcoliNightSeq" if Default Company is NOT Microsynth Austria GmbH.
    """
    customer = frappe.get_doc('Customer', customer_id)

    if customer.territory in ['Rest of Europe (West)', 'Rest of Europe (East)', 'Rest of Europe (PL)']:
        add_webshop_service(customer_id, 'EasyRun')
    elif customer.territory in ['Paris', 'France (Southeast)', 'France (Northwest)', 'Austria', 'Göttingen', 'Germany (Northeast)', 'Germany (South)', 'Germany (Northwest)']:
        add_webshop_service(customer_id, 'InvoiceByDefaultCompany')

    if customer.default_company and customer.default_company != 'Microsynth Austria GmbH':
        add_webshop_service(customer_id, 'EcoliNightSeq')


@frappe.whitelist()
def configure_customer(customer):
    """
    Configures a customer. This function is run upon webshop user registration (webshop.register_user)
    and when saving the customer or an address (customer.js, address.js).
    """
    set_default_language(customer)
    configure_territory(customer)
    configure_sales_manager(customer)
    set_debtor_accounts(customer)
    # set_invoice_to(customer)
    add_webshop_service(customer, 'FullPlasmidSeq')


@frappe.whitelist()
def configure_new_customer(customer):
    """
    Configures a new customer. This function is run upon webshop user registration (webshop.register_user).
    """
    configure_customer(customer)
    set_default_distributor(customer)
    set_default_company(customer)
    add_webshop_services_for_italy(customer)
    set_webshop_services(customer)


def get_alternative_account(account, currency):
    """
    run
    bench execute microsynth.microsynth.utils.get_alternative_account --kwargs "{'account': '2010 - Anzahlungen von Kunden CHF - BAL', 'currency': 'EUR'}"
    """
    query = """
        SELECT `alternative_account`
        FROM `tabAlternative Account`
        WHERE `account` = '{account}'
        AND `currency` = '{currency}'
    """.format(account = account, currency = currency)

    alternative_accounts = frappe.db.sql(query, as_dict=True)

    # TODO: throw an exception if there are multiple entries
    if len(alternative_accounts) > 0:
        return alternative_accounts[0].alternative_account
    else:
        return account


def get_alternative_income_account(account, country):
    """
    Return the first alternative account for a given account and country of a billing address. The company is not used.

    run
    bench execute microsynth.microsynth.utils.get_alternative_income_account --kwargs "{'account': '3200 - 3.1 DNA-Oligosynthese Schweiz - BAL', 'country': 'Switzerland'}"
    """

    if  frappe.get_value("Country", country, "eu"):
        eu_pattern = """ OR `country` = 'EU' """
    else:
        eu_pattern = ""

    query = """
        SELECT `alternative_account`
        FROM `tabAlternative Account`
        WHERE `account` = '{account}'
        AND (`country` = '{country}' OR `country` = '%' {eu_pattern} )
        ORDER BY `idx` ASC
    """.format(account = account, country = country, eu_pattern = eu_pattern)

    records = frappe.db.sql(query, as_dict = True)

    if len(records) > 0:
        return records[0]['alternative_account']
    else:
        return account


def get_alternative_intercompany_income_account(account, customer):
    """
    Return the first alternative intercompany income account for a given account and customer.

    run
    bench execute microsynth.microsynth.utils.get_alternative_intercompany_income_account --kwargs "{'account': '3200 - 3.1 DNA-Oligosynthese Schweiz - BAL', 'customer': '37595596'}"
    """

    query = """
        SELECT `alternative_account`
        FROM `tabIntercompany Settings Alternative Account`
        WHERE `account` = '{account}'
        AND `customer` = '{customer}'
        ORDER BY `idx` ASC
    """.format(account = account, customer = customer)

    records = frappe.db.sql(query, as_dict = True)

    if len(records) > 0:
        return records[0]['alternative_account']
    else:
        return account


def get_customers_for_country(country):
    """
    Look up all addresses (billing and shipping) for the given country and return then linked customer.

    run
    bench execute microsynth.microsynth.utils.get_customers_for_country --kwargs "{'country': 'Hungary'}"
    """
    query = """
        SELECT DISTINCT `tabDynamic Link`.`link_name` as 'name'
        FROM `tabAddress`
        LEFT JOIN `tabDynamic Link` ON `tabDynamic Link`.`parent` = `tabAddress`.`name`
        WHERE `tabAddress`.`country` = '{country}'
        AND `tabDynamic Link`.`link_doctype` = 'Customer'
        AND `tabDynamic Link`.`parenttype` = 'Address'
    """.format(country=country)

    customers = frappe.db.sql(query, as_dict=True)

    return [ c['name'] for c in customers ]


def set_default_company(customer_id):
    """
    Determine the default company according to the shipping address of the given customer_id

    run
    bench execute microsynth.microsynth.utils.set_default_company --kwargs "{'customer': '8003'}"
    """
    query = """
            SELECT
                `tabAddress`.`name`,
                `tabAddress`.`address_type`,
                `tabAddress`.`country`,
                `tabAddress`.`is_shipping_address`,
                `tabAddress`.`is_primary_address`
            FROM `tabDynamic Link`
            LEFT JOIN `tabAddress` ON `tabAddress`.`name` = `tabDynamic Link`.`parent`
            WHERE `tabDynamic Link`.`parenttype` = "Address"
              AND `tabDynamic Link`.`link_doctype` = "Customer"
              AND `tabDynamic Link`.`link_name` = "{customer_id}"
              AND `tabAddress`.`address_type` = "Shipping"
            ;""".format(customer_id=customer_id)

    addresses = frappe.db.sql(query, as_dict=True)

    countries = []
    for a in addresses:
        if not a['country'] in countries:
            countries.append(a['country'])

    customer = frappe.get_doc("Customer", customer_id)

    if len(countries) != 1:
        msg = "Cannot set default company for Customer '{0}': No or multiple countries found ({1})".format(customer.name, len(countries))
        frappe.log_error(msg, "utils.set_default_company")
        from frappe.desk.tags import add_tag
        add_tag(tag="check default company", dt="Customer", dn=customer.name)
        print(msg)
        return

    country_default_company = frappe.db.get_value("Country", countries[0], "default_company")

    if customer.default_company != country_default_company:
        print("Customer '{0}': Set default company '{1}'".format(customer.name, country_default_company))
        customer.default_company = country_default_company
        customer.save()


def set_customer_default_company_for_country(country):
    """
    run
    bench execute microsynth.microsynth.utils.set_customer_default_company_for_country --kwargs "{'country': 'Austria'}"
    """
    customers = get_customers_for_country(country)
    for c in customers:
        if not frappe.db.get_value("Customer", c, "disabled"):
            set_default_company(c)


TERRITORIES = {
    'lukas.hartl@microsynth.at':                    'Austria',
    'sarah.fajon@microsynth.fr':                    'Paris',
    'agnes.nguyen@microsynth.fr':                   'Lyon',
    'emeraude.hadjattou@microsynth.ch':             'France (without Paris and Lyon)',
    'roderick.lambertz@microsynth.seqlab.de':       'Germany (Northeast)',
    'georg.brenzel@microsynth.ch':                  'Germany (Northwest)',
    'atila.durmus@microsynth.seqlab.de':            'Germany (South)',
    'helena.schwellenbach@microsynth.seqlab.de':    'Göttingen',
    'rupert.hagg@microsynth.ch':                    'Rest of Europe',
    'elges.lardi@microsynth.ch':                    'Rest of the World',
    'philippe.suarez@microsynth.ch':                'Switzerland (French-speaking, Bern, Valais, Ticino)',
    'kirsi.schindler@microsynth.ch':                'Switzerland (German-speaking)',
}  # This dictionary is currently only used in the below function set_territory


def set_territory(customer):
    """
    Set the territory according to the account manager if the current territory is 'All Territories'
    otherwise do not change the territory.
    This function is currently only called in the function migration.set_territory_for_customers.
    The function migration.set_territory_for_customers is currently called nowhere in this repository.

    run
    bench execute microsynth.microsynth.utils.set_territory --kwargs "{'customer': '8003'}"
    """

    customer = frappe.get_doc("Customer", customer)
    if customer.territory == "All Territories":
        customer.territory = TERRITORIES[customer.account_manager]  # TODO: won't work due to duplicate key
        customer.save()


def determine_territory(address_id):
    """
    Determine the territory from an address id.
    Assignment according to \\srvfs\Programm\Dokumente\4_Verkauf\4.1 Sales\SZ_Ungelenkt\Listen\LIST 4.1.0006 Sales Areas and Deputy Arrangements.docx

    run
    bench execute microsynth.microsynth.utils.determine_territory --kwargs "{'address_id': '207692'}"
    """
    try:
        address = frappe.get_doc("Address", address_id)

        if address.country == "Switzerland":
            postal_code = address.pincode
            if postal_code == '':
                #frappe.log_error(f"Empty postal_code for {address_id=} in Switzerland.", "utils.determine_territory")
                return frappe.get_doc("Territory", "Switzerland")
            try:
                numeric_postal_code = re.sub('\D', '', postal_code)
            except Exception as err:
                frappe.log_error(f"Got the following error when trying to delete non-numeric characters from postal code '{postal_code}' of {address_id=}:\n{err}", "utils.determine_territory")
                return frappe.get_doc("Territory", "Switzerland")
            if not numeric_postal_code:
                frappe.log_error(f"Postal Code '{postal_code}' for {address_id=} in Switzerland does not contain any numbers.", "utils.determine_territory")
                return frappe.get_doc("Territory", "Switzerland")
            if len(numeric_postal_code) != 4:
                frappe.log_error(f"Postal code '{postal_code}' for {address_id=} in Switzerland does not contain four digits.", "utils.determine_territory")
                return frappe.get_doc("Territory", "Switzerland")
            pc_int = int(numeric_postal_code)
            if  pc_int < 4000 or \
                6500 <= pc_int < 7000 or \
                4536 <= pc_int <= 4539 or \
                pc_int == 4564 or \
                pc_int == 4704 or \
                4900 <= pc_int <= 4902 or \
                4911 <= pc_int <= 4914 or \
                4916 <= pc_int <= 4917 or \
                pc_int == 4919 or \
                4922 <= pc_int <= 4924 or \
                4932 <= pc_int <= 4938 or \
                4942 <= pc_int <= 4944 or \
                pc_int == 4950 or \
                4952 <= pc_int <= 4955 or \
                6083 <= pc_int <= 6086 or \
                pc_int == 6197:
                return frappe.get_doc("Territory", "Switzerland (French-speaking, Bern, Valais, Ticino)")
            else:
                return frappe.get_doc("Territory", "Switzerland (German-speaking)")

        elif address.country == "Austria":
            return frappe.get_doc("Territory", "Austria")

        elif address.country == "Germany":
            postal_code = address.pincode
            if postal_code == '':
                frappe.log_error(f"Empty postal_code for {address_id=} in Germany.", "utils.determine_territory")
                return frappe.get_doc("Territory", "Germany")
            try:
                numeric_postal_code = re.sub('\D', '', postal_code)
            except Exception as err:
                frappe.log_error(f"Got the following error when trying to delete non-numeric characters from postal code '{postal_code}' of {address_id=}:\n{err}", "utils.determine_territory")
                return frappe.get_doc("Territory", "Germany")
            if not numeric_postal_code:
                frappe.log_error(f"Postal code '{postal_code}' for {address_id=} in Germany does not contain any numbers.", "utils.determine_territory")
                return frappe.get_doc("Territory", "Germany")
            if len(numeric_postal_code) != 5:
                frappe.log_error(f"Postal code '{postal_code}' for {address_id=} in Germany does not contain five digits.", "utils.determine_territory")
                return frappe.get_doc("Territory", "Germany")
            pc_prefix = int(numeric_postal_code[:2])
            if  26 <= pc_prefix <= 29 or \
                32 <= pc_prefix <= 36 or \
                40 <= pc_prefix <= 63 or \
                65 <= pc_prefix <= 69:
                return frappe.get_doc("Territory", "Germany (Northwest)")
            elif pc_prefix < 26 or \
                30 <= pc_prefix <= 31 or \
                38 <= pc_prefix <= 39 or \
                pc_prefix >= 98:  # including invalid 00
                return frappe.get_doc("Territory", "Germany (Northeast)")
            elif pc_prefix == 37:
                return frappe.get_doc("Territory", "Göttingen")
            elif pc_prefix == 64 or \
                70 <= pc_prefix <= 97:
                return frappe.get_doc("Territory", "Germany (South)")
            else:
                frappe.log_error(f"The postal code {postal_code} cannot be assigned to any specific German sales region. "
                                f"Territory is set to Germany (parent Territory).", "utils.determine_territory")
                return frappe.get_doc("Territory", "Germany")

        elif address.country == "France":
            postal_code = address.pincode
            if postal_code == '':
                frappe.log_error(f"Empty postal_code for {address_id=} in France.", "utils.determine_territory")
                return frappe.get_doc("Territory", "France")
            try:
                numeric_postal_code = re.sub('\D', '', postal_code)
            except Exception as err:
                frappe.log_error(f"Got the following error when trying to delete non-numeric characters from postal code '{postal_code}' of {address_id=}:\n{err}", "utils.determine_territory")
                return frappe.get_doc("Territory", "France")
            if not numeric_postal_code:
                frappe.log_error(f"Postal code '{postal_code}' for {address_id=} in France does not contain any numbers.", "utils.determine_territory")
                return frappe.get_doc("Territory", "France")
            if len(numeric_postal_code) != 5:
                frappe.log_error(f"Postal code '{postal_code}' for {address_id=} in France does not contain five digits.", "utils.determine_territory")
                return frappe.get_doc("Territory", "France")
            pc_prefix = numeric_postal_code[:2]
            if pc_prefix in ['01', '04', '05', '06', '07', '13', '26', '30', '34', '38', '42', '43', '69', '73', '74', '83', '84']:
                return frappe.get_doc("Territory", "France (Southeast)")
            elif pc_prefix in ['75', '77', '78', '91', '92', '93', '94', '95']:
                return frappe.get_doc("Territory", "Paris")
            else:
                return frappe.get_doc("Territory", "France (Northwest)")

        elif address.country == "Réunion" or address.country == "French Guiana":
            return frappe.get_doc("Territory", "France (Northwest)")

        elif address.country == "Liechtenstein":
            return frappe.get_doc("Territory", "Switzerland (German-speaking)")

        elif address.country == "Poland":
            return frappe.get_doc("Territory", "Rest of Europe (PL)")

        elif address.country in ("Åland Islands", "Andorra", "Belgium", "Denmark", "Faroe Islands", "Finland", "Gibraltar", "Greenland", "Guernsey",
                                 "Holy See (Vatican City State)", "Iceland", "Ireland", "Isle of Man", "Italy", "Jersey", "Luxembourg", "Monaco",
                                 "Netherlands", "Norway", "Portugal", "San Marino", "Spain", "Sweden", "United Kingdom"):
            return frappe.get_doc("Territory", "Rest of Europe (West)")

        elif address.country in ("Albania", "Armenia", "Belarus", "Bosnia and Herzegovina", "Bulgaria", "Croatia", "Cyprus", "Czech Republic",
                                 "Estonia", "Georgia", "Greece", "Hungary", "Kosovo", "Latvia", "Lithuania", "Macedonia", "Malta", "Moldova, Republic of",
                                 "Montenegro", "Romania", "Serbia", "Slovakia", "Slovenia", "Turkey", "Ukraine"):
            return frappe.get_doc("Territory", "Rest of Europe (East)")

        elif address.country in ("Anguilla", "Antigua and Barbuda", "Argentina", "Aruba", "Bahamas", "Barbados", "Belize", "Brazil", "Canada",
                                 "Cayman Islands", "Chile", "Colombia", "Costa Rica", "Cuba", "Dominica", "Dominican Republic", "Ecuador", "El Salvador",
                                 "Grenada", "Guadeloupe", "Guatemala", "Guyana", "Haiti", "Honduras", "Jamaica", "Martinique", "Mexico", "Montserrat",
                                 "Nicaragua", "Panama", "Paraguay", "Peru", "Puerto Rico", "Saint Kitts and Nevis", "Saint Lucia", "Saint Vincent and the Grenadines",
                                 "Suriname", "Trinidad and Tobago", "United States", "Uruguay"):
            return frappe.get_doc("Territory", "Rest of World (Americas)")
        else:
            return frappe.get_doc("Territory", "Rest of World (Asia, Africa, Australia)")

    except Exception as err:
        msg = f"Could not determine territory from address '{address_id}': {err}"
        print(msg)
        frappe.log_error(msg, "utils.determine_territory")
        return None


def get_first_shipping_address(customer_id):
    """
    Return the ID (name) of the first shipping address of the given Customer
    or None if the given Customer has no shipping address.

    run
    bench execute microsynth.microsynth.utils.get_first_shipping_address --kwargs "{'customer_id': '35475873'}"
    """
    # TODO Webshop update to send the attribute is_shipping_address. Uncomment line 'AND `tabAddress`.`is_shipping_address` <> 0'
    query = f"""
            SELECT
                `tabAddress`.`name`,
                `tabAddress`.`country`,
                `tabAddress`.`is_shipping_address`,
                `tabAddress`.`address_type`
            FROM `tabDynamic Link`
            LEFT JOIN `tabAddress` ON `tabAddress`.`name` = `tabDynamic Link`.`parent`
            WHERE   `tabDynamic Link`.`parenttype` = "Address"
                AND `tabDynamic Link`.`link_doctype` = "Customer"
                AND `tabDynamic Link`.`link_name` = "{customer_id}"
                -- AND `tabAddress`.`is_shipping_address` <> 0
                AND `tabAddress`.`address_type` = "Shipping"
            ;"""
    shipping_addresses = frappe.db.sql(query, as_dict=True)
    if not shipping_addresses:
        #print(f"Customer '{customer_id}' has no shipping address.")
        return None
    # if len(shipping_addresses) > 1:
    #     territories = set()
    #     for a in shipping_addresses:
    #         territories.add(determine_territory(a.name).name)
    #     if len(territories) > 1:
    #         customer_name = frappe.get_value('Customer', customer_id, 'customer_name')
    #         msg = f"Found {len(territories)} different possible Territories for Customer '{customer_name}' ('{customer_id}'): "
    #         for i, ter in enumerate(territories):
    #             if i == 0:
    #                 msg += f"{ter}"
    #             else:
    #                 msg += f", {ter}"
    #         print(msg)
    return shipping_addresses[0]['name']


def configure_territory(customer_id):
    """
    Update a customer given by its ID with a territory derived from
    the shipping address if the territory is "All Territories" (default), empty or None.

    run
    bench execute microsynth.microsynth.utils.configure_territory --kwargs "{'customer_id': '836496'}"
    """
    customer = frappe.get_doc("Customer", customer_id)
    if customer.disabled == 0 and (customer.territory == 'All Territories' or customer.territory == '' or customer.territory is None):
        shipping_address = get_first_shipping_address(customer_id)
        if shipping_address is None:
            email_template = frappe.get_doc("Email Template", "Customer without a Shipping Address")
            if customer.owner == 'webshop@microsynth.ch' or customer.owner == 'Administrator':
                first_name = 'Administration'
                recipient = email_template.recipients
                reason = ''
            else:
                first_name = frappe.get_value("User", customer.owner, "first_name")
                recipient = customer.owner
                reason = 'You are receiving this email because you have created the Customer in the ERP and someone has saved it.<br>'
            customer_href = f"<a href={get_url_to_form('Customer', customer_id)}>{customer_id}</a>"
            rendered_subject = frappe.render_template(email_template.subject, {'customer_id': customer_id})
            rendered_content = frappe.render_template(email_template.response, {'first_name': first_name, 'customer_href': customer_href, 'reason': reason})
            frappe.log_error(rendered_subject + f" Send an email to {recipient}.", "utils.configure_territory")
            send_email_from_template(email_template, rendered_content, rendered_subject=rendered_subject, recipients=recipient)
            return
        territory = determine_territory(shipping_address)
        if territory:
            customer.territory = territory.name
            customer.save()
        else:
            return
        #print(f"Customer '{customer_id}' got assigned Territory '{territory.name}'.")
    #else:
        #print(f"Customer '{customer_id}' has Territory '{customer.territory}'.")


def set_sales_manager(customer):
    """
    Set the sales manager of a customer according to the first shipping address and its country.
    """

    shipping_address = get_first_shipping_address(customer.name)
    if shipping_address is None:
        country = None
    else:
        country = frappe.get_value("Address", shipping_address, "Country")

    if country == "Italy":
        customer.account_manager = "servizioclienticer@dgroup.it"
    # elif country == "Czech Republic" and customer.name not in ("37022785", "36993046"):
    #     customer.account_manager = "allgene@allgene.cz"
    elif country == "Slovakia" and customer.name not in ("11007", "37332309"):
        customer.account_manager = "ktrade@ktrade.sk"
    # elif country == "Cyprus" and customer.name not in ("837936"):
    #     customer.account_manager = ""
    else:
        customer.account_manager = frappe.get_value("Territory", customer.territory, "sales_manager")

    customer.save()


def configure_sales_manager(customer_id):
    """
    Update a customer given by its ID with a sales manager if it is not yet set (default).

    run
    bench execute microsynth.microsynth.utils.configure_sales_manager --kwargs "{'customer_id': '832739'}"
    """
    customer = frappe.get_doc("Customer", customer_id)

    if customer.account_manager is None or customer.account_manager == '' or customer.account_manager == 'null':
        set_sales_manager(customer)
        #print(f"Customer '{customer_id}' got assigned Sales Manager {customer.account_manager}.")


def set_distributor_all_product_types(customer_id, distributor):
    """
    Set the given distributor for all product types for the given customer.

    run
    bench execute microsynth.microsynth.utils.set_distributor_all_product_types --kwargs "{'customer_id': '836446', 'distributor': '840418'}"
    """
    set_distributor(customer_id, distributor, 'Oligos')
    set_distributor(customer_id, distributor, 'Labels')
    set_distributor(customer_id, distributor, 'Sequencing')
    set_distributor(customer_id, distributor, 'FLA')
    set_distributor(customer_id, distributor, 'Genetic Analysis')


def set_distributor_ktrade(customer_id):
    """
    bench execute microsynth.microsynth.utils.set_distributor_ktrade --kwargs "{'customer_id': '838469'}"
    """
    distributor = '11007'
    set_distributor_all_product_types(customer_id, distributor)


def set_distributor_elincou(customer_id):
    """
    bench execute microsynth.microsynth.utils.set_distributor_elincou --kwargs "{'customer_id': '838469'}"
    """
    distributor = '837936'
    set_distributor_all_product_types(customer_id, distributor)


def set_distributor_elincou(customer_id):
    """
    bench execute microsynth.microsynth.utils.set_distributor_elincou --kwargs "{'customer_id': '838469'}"
    """
    distributor = '837936'
    set_distributor_all_product_types(customer_id, distributor)


def set_distributor_allgene(customer_id):
    """
    bench execute microsynth.microsynth.utils.set_distributor_allgene --kwargs "{'customer_id': '836446'}"
    """
    distributor = '840418'
    set_distributor_all_product_types(customer_id, distributor)


def set_default_distributor(customer_id):
    """
    Set the distributors if the Customer has none and its first shipping address is in a Country with a distributor agreement.

    bench execute microsynth.microsynth.utils.set_default_distributor --kwargs "{'customer_id': '35277857'}"
    bench execute microsynth.microsynth.utils.set_default_distributor --kwargs "{'customer_id': '35280995'}"
    """
    shipping_address = get_first_shipping_address(customer_id)
    if shipping_address is None:
        frappe.log_error(f"Can't set distributor for Customer {customer_id} due to the lack of a shipping address.", "utils.set_default_distributor")
        return

    country = frappe.get_value("Address", shipping_address, "Country")
    if country == "Italy":
        distributor = '35914214'
        set_distributor(customer_id, distributor, 'Sequencing')
        set_distributor(customer_id, distributor, 'Labels')
        set_distributor(customer_id, distributor, 'FLA')

    elif country == "Hungary":
        distributor = '832700'
        set_distributor(customer_id, distributor, 'Oligos')
        set_distributor(customer_id, distributor, 'Labels')
        set_distributor(customer_id, distributor, 'Sequencing')

    elif country == "Slovakia":
        set_distributor_ktrade(customer_id)

    elif country == "Cyprus":
        set_distributor_elincou(customer_id)

    elif country == "Czech Republic":
        set_distributor_allgene(customer_id)


def set_default_distributor_for_customers(customer_ids):
    """
    Set the default distributor for a list of customers.

    run
    bench execute microsynth.microsynth.utils.set_default_distributor_for_customers --kwargs "{'customer_ids': ['35277857', '35280995']}"
    """
    from microsynth.microsynth.credits import has_credits

    customer_count = len(customer_ids)
    for i, customer_id in customer_ids:
        print(f"{int(100 * i / customer_count)} % - process Customer '{customer_id}'")

        if not has_credits(customer_id):
            set_default_distributor(customer_id)
        else:
            print(f"Customer '{customer_id}' has credits. Skip setting default distributor.")


def check_default_companies():
    """
    run
    bench execute microsynth.microsynth.utils.check_default_companies
    """
    countries = [ "Austria", "Croatia", "Hungary", "Slovakia", "Slovenia", "Kosovo" ]
    for c in countries:
        print(c)
        set_customer_default_company_for_country(c)


def update_sales_manager_for_country(country):
    """
    run
    bench execute microsynth.microsynth.utils.update_sales_manager_for_country --kwargs "{'country': 'Slovakia'}"
    """
    customers = get_customers_for_country(country)
    for c in customers:
        customer = frappe.get_doc("Customer", c)

        print(f"process customer {c}: disabled = {customer.disabled}")
        if not customer.disabled:
            set_sales_manager(customer)


@frappe.whitelist()
def exact_copy_sales_invoice(sales_invoice):
    """
    Clone a sales invoice including the no-copy fields (sales_invoice.json: field "no_copy": 1). Set the new document to
    Draft status. Change the owner to the current user ('created this').
    Set the creation time to now.

    run
    bench execute microsynth.microsynth.utils.exact_copy_sales_invoice --kwargs "{'sales_invoice': 'SI-BAL-23001936'}"
    """
    original = frappe.get_doc("Sales Invoice", sales_invoice)
    user = frappe.get_user()

    new = frappe.get_doc(original.as_dict())
    new.name = None
    new.docstatus = 0
    new.set_posting_time = 1
    new.invoice_sent_on = None
    new.creation = datetime.now()
    new.owner = user.name
    new.exported_to_abacus = 0                                          # reset abacus export flag
    new.insert()
    comment_invoice(new.name, "Cloned from {0}<br>by {1}".format(original.name, user.name))
    frappe.db.commit()
    return new.name


def get_tags(dt, dn):
    """
    Return the tags of a document specified by the DocType dt and the Document Name dn.
    run
    bench execute microsynth.microsynth.utils.get_tags --kwargs "{'dt': 'Sales Order', 'dn': 'SO-BAL-23029609'}"
    """
    tags = []
    raw = frappe.db.get_value(dt, dn, "_user_tags")

    if raw is not None:
        for t in raw.split(","):
            if t != "" and t not in tags:
                tags.append(t)

    return tags


def tag_linked_documents(web_order_id, tag):
    """
    Add the specified Tag to all linked Sales Orders, Delivery Notes and Sales Invoices with the given Web Order ID.

    run
    bench execute microsynth.microsynth.utils.tag_linked_documents --kwargs "{ 'web_order_id': 3611777, 'tag': 'my_tag' }"
    """
    from frappe.desk.tags import add_tag

    # find documents by web order id
    sales_order_names = frappe.db.get_all("Sales Order",
        filters={'web_order_id': web_order_id},
        fields=['name'])

    delivery_note_names = frappe.db.get_all("Delivery Note",
        filters={'web_order_id': web_order_id},
        fields=['name'])

    sales_invoice_names = frappe.db.get_all("Sales Invoice",
        filters={'web_order_id': web_order_id},
        fields=['name'])

    sales_orders = []
    for x in sales_order_names:
        if x.name not in sales_orders:
            sales_orders.append(x.name)

    delivery_notes = []
    for x in delivery_note_names:
        if x.name not in delivery_notes:
            delivery_notes.append(x.name)

    sales_invoices = []
    for x in sales_invoice_names:
        if x.name not in sales_invoices:
            sales_invoices.append(x.name)

    # tag sales orders and find linked documents
    for so in sales_orders:
        add_tag(tag = tag, dt = "Sales Order", dn = so )

        # get linked Delivery Notes
        delivery_note_items = frappe.db.get_all("Delivery Note Item",
            filters={'against_sales_order': so },
            fields=['parent'])

        for item in delivery_note_items:
            if item.parent not in delivery_notes:
                delivery_notes.append(item.parent)

        # get linked Sales Invoices
        sales_invoice_items = frappe.db.get_all("Sales Invoice Item",
            filters={'sales_order': so},
            fields=['parent'])

        for item in sales_invoice_items:
            if item.parent not in sales_invoices:
                sales_invoices.append(item.parent)

    # tag delivery notes and find tagged documents
    for dn in delivery_notes:
        add_tag(tag = tag, dt = "Delivery Note", dn = dn )

        # get linked Sales Invoices
        sales_invoice_items = frappe.db.get_all("Sales Invoice Item",
            filters={'delivery_note': dn},
            fields=['parent'])

        for item in sales_invoice_items:
            if item.parent not in sales_invoices:
                sales_invoices.append(item.parent)

    # tag sales invoices
    for si in sales_invoices:
        add_tag(tag = tag, dt = "Sales Invoice", dn = si)

    return


@frappe.whitelist()
def book_avis(company, intermediate_account, currency_deviation_account, invoices, amount, reference, date=None):
    if type(invoices) == str:
        invoices = json.loads(invoices)
    amount = flt(amount)

    # find exchange rate for intermediate account
    intermediate_currency = frappe.get_cached_value("Account", intermediate_account, "account_currency")
    if frappe.get_cached_value("Company", company, "default_currency") == intermediate_currency:
        current_exchange_rate = 1
    else:
        exchange_rates = frappe.db.sql("""
            SELECT `exchange_rate`
            FROM `tabCurrency Exchange`
            WHERE `from_currency` = "{currency}"
            ORDER BY `date` DESC
            LIMIT 1;
            """.format(currency=intermediate_currency), as_dict=True)
        if len(exchange_rates) > 0:
            current_exchange_rate = exchange_rates[0]['exchange_rate']
        else:
            current_exchange_rate = 1

    # get cost center
    cost_center = frappe.get_cached_value("Company", company, "cost_center")

    # create base document
    jv = frappe.get_doc({
        'doctype': 'Journal Entry',
        'posting_date': date if date else datetime.now(),
        'company': company,
        'multi_currency': 1,
        'user_remark': reference,
        'accounts': [
            {
                'account': intermediate_account,
                'account_currency': intermediate_currency,
                'debit_in_account_currency': amount,
                'debit': rounded(amount * current_exchange_rate, 2),
                'exchange_rate': current_exchange_rate,
                'cost_center': cost_center
            }
        ]
    })

    # extend invoices
    #base_total_debit = flt(amount) * current_exchange_rate
    base_total_credit = 0
    for invoice in invoices:
        if not invoice.get('sales_invoice'):
            # skip empty rows (see #14112)
            continue
        debit_account = frappe.get_value("Sales Invoice", invoice.get('sales_invoice'), 'debit_to')
        exchange_rate = frappe.get_value("Sales Invoice", invoice.get('sales_invoice'), 'conversion_rate')
        jv.append('accounts', {
            'account': debit_account,
            'account_currency': intermediate_currency,
            'party_type': 'Customer',
            'party': invoice.get('customer'),
            'exchange_rate': exchange_rate,
            'reference_type': 'Sales Invoice',
            'reference_name': invoice.get('sales_invoice'),
            'credit_in_account_currency': invoice.get('outstanding_amount'),
            'credit': rounded((invoice.get('outstanding_amount') or 0) * (exchange_rate or 1), 2),
            'cost_center': cost_center
        })
        base_total_credit += (invoice.get('outstanding_amount') or 0) * (exchange_rate or 1)

    # other currencies: currency deviation
    jv.set_total_debit_credit()
    currency_deviation = rounded(jv.total_debit - jv.total_credit, 2)
    if currency_deviation != 0:
        jv.append('accounts', {
            'account': currency_deviation_account,
            'credit': currency_deviation,
            'credit_in_account_currency': currency_deviation,
            'account_currency': frappe.get_cached_value("Account", currency_deviation_account, "account_currency"),
            'cost_center': cost_center
        })

        jv.set_total_debit_credit()
    # insert and submit
    jv.flags.ignore_validate = True
    jv.insert()
    jv.submit()

    return jv.name


@frappe.whitelist()
def book_foreign_expense(company, intermediate_account, expense_account,
    currency_deviation_account, foreign_amount, base_amount, reference, date=None):
    """
    This function is used to book a deduction/expense on a foreign currency account, using a journal entry
    """
    foreign_amount = flt(foreign_amount)
    base_amount = flt(base_amount)

    # get cost center
    cost_center = frappe.get_cached_value("Company", company, "cost_center")

    # create base document
    jv = frappe.get_doc({
        'doctype': 'Journal Entry',
        'posting_date': date if date else datetime.now(),
        'company': company,
        'multi_currency': 1,
        'user_remark': reference,
        'accounts': [
            {
                'account': expense_account,
                'account_currency': frappe.get_cached_value("Account", expense_account, "account_currency"),
                'debit_in_account_currency': foreign_amount,
                'debit': base_amount,
                'exchange_rate': base_amount/foreign_amount,
                'cost_center': cost_center
            },
            {
                'account': intermediate_account,
                'account_currency': frappe.get_cached_value("Account", intermediate_account, "account_currency"),
                'credit_in_account_currency': foreign_amount,
                'credit': base_amount,
                'exchange_rate': base_amount/foreign_amount,
                'cost_center': cost_center
            }
        ]
    })

    # other currencies: currency deviation
    jv.set_total_debit_credit()
    currency_deviation = rounded(jv.total_debit - jv.total_credit, 2)
    if currency_deviation != 0:
        jv.append('accounts', {
            'account': currency_deviation_account,
            'credit': currency_deviation,
            'credit_in_account_currency': currency_deviation,
            'account_currency': frappe.get_cached_value("Account", currency_deviation_account, "account_currency"),
            'cost_center': cost_center
        })

        jv.set_total_debit_credit()
    # insert and submit
    jv.flags.ignore_validate = True
    jv.insert()
    jv.submit()

    return jv.name

def comment_invoice(sales_invoice, comment):
    """
    run
    bench execute microsynth.microsynth.utils.comment_invoice --kwargs "{ 'sales_invoice': 'SI-BAL-23016302', 'comment': 'my_comment' }"
    """
    new_comment = frappe.get_doc({
        'doctype': 'Comment',
        'comment_type': "Comment",
        'subject': sales_invoice,
        'content': comment,
        'reference_doctype': "Sales Invoice",
        'status': "Linked",
        'reference_name': sales_invoice
    })
    new_comment.insert(ignore_permissions=True)
    return


@frappe.whitelist()
def fetch_price_list_rates_from_prevdoc(prevdoc_doctype, prev_items):
    if type(prev_items) == str:
        prev_items = json.loads(prev_items)

    prevdoc_price_list_rates = []
    # check each item
    for prev_item in prev_items:
        # check if there is a previous document
        if prev_item:
            prev_doc_price_list_rate = frappe.get_value("{0} Item".format(prevdoc_doctype), prev_item, "price_list_rate")
            prevdoc_price_list_rates.append(prev_doc_price_list_rate)
        else:
            prevdoc_price_list_rates.append(None)

    if len(prevdoc_price_list_rates) != len(prev_items):
        frappe.throw("This can never happen! If not, ask Lars")

    return prevdoc_price_list_rates


@frappe.whitelist()
def deduct_and_close(payment_entry, account, cost_center):
    """
    This function will deduct the unallocated amount to the provided account and submit the payment entry
    """
    doc = frappe.get_doc("Payment Entry", payment_entry)
    if doc.payment_type == "Pay":
        if doc.source_exchange_rate != 1 and (not doc.references or len(doc.references) == 0):
            amount = doc.base_paid_amount;   # use full paid amount, with valuation
        else:
            amount = doc.unallocated_amount or doc.difference_amount or 0
    else:
        amount = ((-1) * doc.unallocated_amount) or doc.difference_amount

    add_deduction(doc, account, cost_center, amount)

    doc.save()
    doc.submit()
    return


def add_deduction(doc, account, cost_center, amount):
    doc.append('deductions', {
        'account': account,
        'cost_center': cost_center,
        'amount': amount
    })
    return


def is_valid_tax_id(tax_id):
    """
    Takes a Tax ID as string.
    Returns whether the given Tax ID is valid.
    Currently only applicable to the European Union (VIES).
    """
    from erpnextaustria.erpnextaustria.utils import check_uid
    try:
        valid = check_uid(tax_id)
        # TODO: Consider to call check_uid with a timeout: https://stackoverflow.com/questions/492519/timeout-on-a-function-call
    except Exception as err:
        try:  # a second time
            valid = check_uid(tax_id)
        except Exception as err:
            print(f"Unable to validate Tax ID '{tax_id}':\n{err}")
            return False
    return valid



# It seems that this function is never called
# def check_tax_id(tax_id, customer_id, customer_name):
#     """
#     Takes a Tax ID with its Customer ID and Customer name and
#     sends an email to the administration if the given Tax ID can be classified as invalid.
#     It is NOT checked if the Tax ID belongs to the given Customer name.
#     """
#     if not tax_id:
#         return
#     if tax_id[:2] in ['CH', 'GB', 'IS', 'NO', 'TR'] and not 'NOT' in tax_id:
#         # unable to check Tax ID from Great Britain, Iceland, Norway or Turkey
#         return
#     if not is_valid_tax_id(tax_id):
#         subject = f"[ERP] Invalid Tax ID '{tax_id}'"
#         vies_url_string = f'<a href="https://ec.europa.eu/taxation_customs/vies/#/vat-validation">https://ec.europa.eu/taxation_customs/vies/#/vat-validation</a>'
#         message = f"Dear Administration,<br><br>this is an automatic email to inform you that the Tax ID '{tax_id}' " \
#                     f"of Customer '{customer_id}' ('{customer_name}') seems to be invalid.<br>" \
#                     f"Please check the Tax ID using {vies_url_string} and correct it if necessary.<br><br>Best regards,<br>Jens"
#         make(
#             recipients = "info@microsynth.ch",
#             sender = "erp@microsynth.ch",
#             subject = subject,
#             content = message,
#             send_email = True
#             )



def check_new_customers_taxid(delta_days=7):
    """
    Check the Tax ID of all new Customers and send one email
    to the administration if there are invalid Tax IDs.
    Run daily by a Cronjob.

    bench execute microsynth.microsynth.utils.check_new_customers_taxid --kwargs "{'delta_days': 20}"
    """
    invalid_tax_ids = []
    start_day = date.today() - timedelta(days = delta_days)
    new_customers = frappe.db.get_all("Customer",
                                      filters=[['creation', '>=', start_day.strftime("%Y-%m-%d")],
                                               ['disabled', '=', '0']],
                                      fields=['name', 'customer_name', 'tax_id'])
    #print(f"Going to check {len(new_customers)} new Customers ...")
    for nc in new_customers:
        if not nc['tax_id']:
            continue
        address = get_first_shipping_address(nc['name']) or get_billing_address(nc['name'])  # second function is only called if first returns falsy value
        if address is None:
            frappe.log_error(f"Customer '{nc['name']}' has no address. Unable to check Tax ID.", "utils.check_new_customers_taxid")
            continue
        country = frappe.get_value("Address", address, "Country")
        if not country in ['Austria', 'Belgium', 'Bulgaria', 'Cyprus', 'Czech Republic', 'Germany', 'Denmark', 'Estonia', 'Greece',
                           'Spain', 'Finland', 'France', 'Croatia', 'Hungary', 'Ireland', 'Italy', 'Lithuania', 'Luxembourg', 'Latvia',
                           'Malta', 'Netherlands', 'Poland', 'Portugal', 'Romania', 'Sweden', 'Slovenia', 'Slovakia']:
            continue
        # if nc['tax_id'][:2] in ['CH', 'GB', 'IS', 'NO', 'TR'] and not 'NOT' in nc['tax_id']:
        #     # unable to check Tax ID from Great Britain, Iceland, Norway or Turkey
        #     continue
        if not is_valid_tax_id(nc['tax_id']):
            invalid_tax_ids.append({'customer_id': nc['name'],
                                    'customer_name': nc['customer_name'],
                                    'tax_id': nc['tax_id']})
    if len(invalid_tax_ids) > 0:
        invalid_tax_id_msg = ""
        for iti in invalid_tax_ids:
            url_string = f"<a href={get_url_to_form('Customer', iti['customer_id'])}>{iti['customer_id']}</a>"
            invalid_tax_id_msg += f"Customer {url_string} ({iti['customer_name']}): Tax ID '{iti['tax_id']}'<br>"

        email_template = frappe.get_doc("Email Template", "Invalid Tax IDs of new Customers")
        rendered_content = frappe.render_template(email_template.response, {'invalid_tax_id_msg': invalid_tax_id_msg, 'delta_days': delta_days })
        send_email_from_template(email_template, rendered_content)


def new_french_customers(delta_hours=24):
    """
    Notify the administration daily about new Customers with a french billing address.
    Run daily by a Cronjob at 15:55.

    bench execute microsynth.microsynth.utils.new_french_customers --kwargs "{'delta_hours': 24}"
    """
    sql_query = f"""
        SELECT DISTINCT `tabCustomer`.`name` AS `customer_id`,
            `tabCustomer`.`customer_name`
        FROM `tabCustomer`
        LEFT JOIN `tabContact` ON `tabContact`.`name` = `tabCustomer`.`invoice_to`
        LEFT JOIN `tabAddress` ON `tabAddress`.`name` = `tabContact`.`address`
        WHERE `tabCustomer`.`creation` BETWEEN "{datetime.now() - timedelta(hours=delta_hours)}" AND "{datetime.now()}"
            AND `tabAddress`.`country` = "France"
            AND `tabAddress`.`address_type` = 'Billing'
            AND `tabAddress`.`disabled` = 0
            AND `tabContact`.`status` != "Disabled"
            AND `tabCustomer`.`disabled` = 0
        ;"""
    new_customers = frappe.db.sql(sql_query, as_dict=True)
    if len(new_customers) > 0:
        customer_details = ""
        for new_customer in new_customers:
            customer_details += f"<a href={get_url_to_form('Customer', new_customer['customer_id'])}>{new_customer['customer_id']} ({new_customer['customer_name']})</a><br>"
        email_template = frappe.get_doc("Email Template", "New French Customers")
        rendered_content = frappe.render_template(email_template.response, {'customer_details': customer_details })
        send_email_from_template(email_template, rendered_content)


def new_sanofi_contacts(delta_hours=24):
    """
    Notify the administration daily about new Contacts of Customers with "Sanofi" in their name.
    Should be run daily by a Cronjob:
    # Notify the administration about new Sanofi Contacts
    50 15 * * * cd /home/frappe/frappe-bench && /usr/local/bin/bench --site erp.microsynth.local execute microsynth.microsynth.utils.new_sanofi_contacts --kwargs "{'delta_hours': 24}"

    bench execute microsynth.microsynth.utils.new_sanofi_contacts --kwargs "{'delta_hours': 24}"
    """
    sql_query = f"""
        SELECT DISTINCT `tabContact`.`name` AS `contact_id`,
            `tabContact`.`first_name`,
            `tabContact`.`last_name`,
            `tabCustomer`.`name` AS `customer_id`,
            `tabCustomer`.`customer_name`
        FROM `tabContact`
        LEFT JOIN `tabDynamic Link` ON `tabDynamic Link`.`parent` = `tabContact`.`name`
        LEFT JOIN `tabCustomer` ON `tabCustomer`.`name` = `tabDynamic Link`.`link_name`
        WHERE `tabDynamic Link`.`parenttype` = "Contact"
            AND `tabDynamic Link`.`link_doctype` = "Customer"
            AND `tabCustomer`.`customer_name` LIKE "%Sanofi%"
            AND `tabContact`.`creation` BETWEEN "{datetime.now() - timedelta(hours=delta_hours)}" AND "{datetime.now()}"
            AND `tabContact`.`status` != 'Disabled'
        ;"""
    new_contacts = frappe.db.sql(sql_query, as_dict=True)
    if len(new_contacts) > 0:
        contact_details = ""
        for new_contact in new_contacts:
            contact_details += f"<a href={get_url_to_form('Contact', new_contact['contact_id'])}>{new_contact['contact_id']} ({new_contact['first_name']} {new_contact['last_name']})</a> of Customer <a href={get_url_to_form('Customer', new_contact['customer_id'])}>{new_contact['customer_id']} ({new_contact['customer_name']})</a><br>"
        email_template = frappe.get_doc("Email Template", "New Sanofi Contacts")
        rendered_content = frappe.render_template(email_template.response, {'contact_details': contact_details })
        send_email_from_template(email_template, rendered_content)


def find_same_ext_dnr_diff_taxid():
    """
    For each External Debitor Number: If there are Customers with this External Debitor Number but different Tax IDs,
    the Tax IDs get printed together with the Customer ID and Customer Name.

    bench execute microsynth.microsynth.utils.find_same_ext_dnr_diff_taxid
    """
    sql_query = """
        SELECT `tabCustomer`.`name`,
            `tabCustomer`.`customer_name`,
            `tabCustomer`.`ext_debitor_number`,
            `tabCustomer`.`tax_id`
        FROM `tabCustomer`
        WHERE `tabCustomer`.`default_company` IN ('Microsynth Seqlab GmbH', 'Microsynth Austria GmbH')
            AND `tabCustomer`.`disabled` = 0;
    """
    customers = frappe.db.sql(sql_query, as_dict=True)
    ext_debitor_numbers = set()
    same_ext_dnr_diff_taxid = {}
    chaos_counter = 0

    for c in customers:
        if c['ext_debitor_number']:
            ext_debitor_numbers.add(c['ext_debitor_number'])

    print(f"There are {len(ext_debitor_numbers)} different External Debitor Numbers of enabled Customers "
          f"with Default Company Microsynth Seqlab GmbH or Microsynth Austria GmbH.")

    for ext_debitor_number in ext_debitor_numbers:
        same_ext_debitor_number = frappe.db.get_all("Customer",
                                                    filters=[['ext_debitor_number', '=', ext_debitor_number],
                                                            ['disabled', '=', '0']],
                                                    fields=['name', 'customer_name', 'tax_id', 'ext_debitor_number'])
        if len(same_ext_debitor_number) == 0:
            continue
        first_tax_id = None
        for c in same_ext_debitor_number:
            if c['tax_id']:
                first_tax_id = c['tax_id']
        if not first_tax_id:
            continue

        for c in same_ext_debitor_number:
            if c['tax_id'] and c['tax_id'] != first_tax_id:
                if not ext_debitor_number in same_ext_dnr_diff_taxid:
                    same_ext_dnr_diff_taxid[ext_debitor_number] = same_ext_debitor_number
                    chaos_counter += 1
                break

    for ext_deb_nr, entry in same_ext_dnr_diff_taxid.items():
        if not ext_deb_nr:
            continue
        print(f"\nExternal Debitor Number '{ext_deb_nr}':")
        for cust in entry:
            if cust['tax_id']:
                print(f"Tax ID '{cust['tax_id']}' for Customer '{cust['name']}' ('{cust['customer_name']}')")

    print(f"\nThere are {chaos_counter}/{len(ext_debitor_numbers)} External Debitor Numbers "
          f"({(chaos_counter / len(ext_debitor_numbers)) * 100:.2f} %) "
          f"where the Customers have different Tax IDs.")


def complement_ext_debitor_nr(dry_run=True):
    """
    Try to find unique External Debitor Numbers for Customers with default Company
    Microsynth Seqlab GmbH or Microsynth Austria GmbH from Customers with the same Tax ID.
    Should be run by a daily cron job.

    bench execute microsynth.microsynth.utils.complement_ext_debitor_nr --kwargs "{'dry_run': True}"
    """
    sql_query = """SELECT `tabCustomer`.`name`,
            `tabCustomer`.`customer_name`,
            `tabCustomer`.`tax_id`
        FROM `tabCustomer`
        WHERE `tabCustomer`.`default_company` IN ('Microsynth Seqlab GmbH', 'Microsynth Austria GmbH')
            AND `tabCustomer`.`ext_debitor_number` IS NULL
            AND `tabCustomer`.`disabled` = 0;
    """
    customers = frappe.db.sql(sql_query, as_dict=True)
    same_tax_id_diff_ext_dnr = {}
    counter = chaos_counter = unique_tax_id = no_ext_deb_nr = 0
    print(f"Found {len(customers)} enabled Customers with missing ext_debitor_number and "
          f"Default Company Microsynth Seqlab GmbH or Microsynth Austria GmbH.\n")
    for customer in customers:
        same_tax_id = frappe.db.get_all("Customer",
                                filters=[['ext_debitor_number', '!=', 'NULL'],  # seems not to work
                                         ['tax_id', '=', customer['tax_id']],
                                         ['disabled', '=', '0']],
                                fields=['name', 'customer_name', 'ext_debitor_number'])
        if len(same_tax_id) == 0:
            unique_tax_id += 1
            continue
        first_ext_debitor_nr = None
        for c in same_tax_id:
            if c['ext_debitor_number']:
                first_ext_debitor_nr = c['ext_debitor_number']
        if not first_ext_debitor_nr:
            no_ext_deb_nr += 1
            continue
        same_ext_debitor_number = True
        for c in same_tax_id:
            if c['ext_debitor_number'] and c['ext_debitor_number'] != first_ext_debitor_nr:
                if not customer['tax_id'] in same_tax_id_diff_ext_dnr:
                    same_tax_id_diff_ext_dnr[customer['tax_id']] = same_tax_id
                same_ext_debitor_number = False
                chaos_counter += 1
                break
        if same_ext_debitor_number and first_ext_debitor_nr:
            print(f"{'Could' if dry_run else 'Going to'} set External Debitor Number of Customer '{customer['name']}' "
                  f"('{customer['customer_name']}') to '{first_ext_debitor_nr}' from Customer '{same_tax_id[0]['name']}' "
                  f"('{same_tax_id[0]['customer_name']}') with the same Tax ID '{customer['tax_id']}'.")
            if not dry_run:
                # Set External Debitor Number of customer['name'] to first_ext_debitor_nr
                customer_doc = frappe.get_doc("Customer", customer['name'])
                customer_doc.ext_debitor_number = first_ext_debitor_nr
                customer_doc.save()
            counter += 1
    print(f"\nThere are {len(same_tax_id_diff_ext_dnr)} Tax IDs where the Customers have different External Debitor Numbers:")
    for tax_id, entry in same_tax_id_diff_ext_dnr.items():
        if not tax_id:
            continue
        print(f"\nTax ID '{tax_id}':")
        for cust in entry:
            if cust['ext_debitor_number']:
                print(f"External Debitor Number '{cust['ext_debitor_number']}' for Customer '{cust['name']}' ('{cust['customer_name']}')")
    print(f"\n\nThere are {len(same_tax_id_diff_ext_dnr)} Tax IDs where the Customers have different External Debitor Numbers.\n")
    print(f"\n{len(customers)} enabled Customers with missing ext_debitor_number and "
          f"Default Company Microsynth Seqlab GmbH or Microsynth Austria GmbH break down as follows:")
    print(f"\nCould have set the External Debitor Number of {counter} Customers. (There is at least one Customer with the same Tax ID "
          f"and an External Debitor Number and all Customers with the same Tax ID have the same non-empty External Debitor Number.)")
    print(f"\nThe External Debitor Number of {unique_tax_id + no_ext_deb_nr + chaos_counter} Customers was not set, because ...")
    print(f"\n{unique_tax_id} Customers have a unique Tax ID (no other Customer with the same Tax ID).")
    print(f"\nFor {no_ext_deb_nr} Customers, at least one other Customer with the same Tax ID was found but none of them has an External Debitor Number.")
    print(f"\nThere are {chaos_counter} Customers where the Customers with the same Tax ID have different External Debitor Numbers.")


def find_orders_with_missing_tax_id():
    """
    Find new Sales Orders to be delivered outside of Switzerland whose Customers have no Tax ID and notify DSc.
    Should be executed by a daily cronjob.

    bench execute microsynth.microsynth.utils.find_orders_with_missing_tax_id
    """
    sql_query = f"""
        SELECT
            `tabSales Order`.`name` AS `sales_order`,
            `tabSales Order`.`customer`,
            `tabSales Order`.`customer_name`,
            `tabCustomer`.`tax_id`,
            `tabAddress`.`country`,
            `tabSales Order`.`transaction_date`,
            `tabSales Order`.`status`
        FROM `tabSales Order`
        LEFT JOIN `tabAddress` ON `tabAddress`.`name` = `tabSales Order`.`shipping_address_name`
        LEFT JOIN `tabCustomer` ON `tabCustomer`.`name` = `tabSales Order`.`customer`
        WHERE `tabSales Order`.`docstatus` = 1
            AND `tabSales Order`.`product_type` IN ('Oligos', 'Material')
            AND `tabAddress`.`country` IN ('Austria', 'Belgium', 'Bulgaria', 'Cyprus', 'Czech Republic', 'Germany', 'Denmark', 'Estonia', 'Greece',
                                        'Spain', 'Finland', 'France', 'Croatia', 'Hungary', 'Ireland', 'Italy', 'Lithuania', 'Luxembourg', 'Latvia',
                                        'Malta', 'Netherlands', 'Poland', 'Portugal', 'Romania', 'Sweden', 'Slovenia', 'Slovakia')
            AND `tabCustomer`.`tax_id` IS NULL
            AND `tabSales Order`.`transaction_date` >= DATE_ADD(NOW(), INTERVAL -1 DAY)
        ORDER BY `tabSales Order`.`transaction_date` DESC;
        """
    sales_orders = frappe.db.sql(sql_query, as_dict=True)

    if len(sales_orders) == 0:
        return  # early abort

    sales_order_details = ""
    for so in sales_orders:
        sales_order_details += f"{so['sales_order']} from {so['transaction_date']} with Shipping Address in {so['country']}: Customer {so['customer']} ('{so['customer_name']}')<br>"

    email_template = frappe.get_doc("Email Template", "New Sales Orders from Customers with missing Tax ID")
    rendered_content = frappe.render_template(email_template.response, {'sales_order_details': sales_order_details })
    send_email_from_template(email_template, rendered_content)


def get_yearly_order_volume(customer_id):
    """
    Returns the total volume of all Sales Orders of the given customer_id from the current year
    and the total volume from last year. Used in the Customer print format.

    bench execute microsynth.microsynth.utils.get_yearly_order_volume --kwargs "{'customer_id': '37765217'}"
    """
    if not customer_id or not frappe.db.exists("Customer", customer_id):
        frappe.throw("Please provide a valid Customer ID.")
    # get current year as int
    current_year = datetime.now().year
    yearly_order_volume = []
    for year in range(current_year, current_year-2, -1):
        data = frappe.db.sql(f"""
                        SELECT SUM(`base_net_total`) AS `total`, `currency`
                        FROM `tabSales Order`
                        WHERE `customer` = '{customer_id}'
                        AND `docstatus` = 1
                        AND `transaction_date` BETWEEN DATE('{year}-01-01') AND DATE('{year}-12-31')
                        GROUP BY `currency`
                    """, as_dict=True)
        if len(data) > 1:
            frappe.log_error(f"There seem to be {len(data)} different currencies on Sales Orders of Customer '{customer_id}' from {year}.", "utils.get_yearly_order_volume")
            yearly_order_volume.append({
                'volume': sum((entry.total or 0) for entry in data),
                'currency': 'different'
            })
        elif len(data) > 0:
            yearly_order_volume.append({
                'volume': data[0].total or 0,
                'currency': data[0].currency
            })
        else:
            yearly_order_volume.append({
                'volume': 0,
                'currency': 'CHF'  # if there are no data, the currency should not matter
            })
    return yearly_order_volume


@frappe.whitelist()
def apply_item_group_defaults(item_group):
    """
    Apply the item_group_defaults of the given Item Group to all Items of this Item Group.

    bench execute microsynth.microsynth.utils.apply_item_group_defaults --kwargs "{'item_group': '3.6 Library Prep'}"
    """
    item_group = frappe.get_doc("Item Group", item_group)
    items = frappe.db.get_all("Item", filters={'item_group': item_group.name}, fields=['name'])
    for item in items:
        print(f"Going to process Item {item['name']} ...")
        overwrite_item_defaults(item['name'])


def update_item_defaults(item):
    """
    Update the item defaults of the Item object based on its Item Group defaults.
    """
    item_group = frappe.get_doc("Item Group", item.item_group)
    for group_default in item_group.item_group_defaults:
        found_company = False
        for item_default in item.item_defaults:
            if group_default.company == item_default.company:
                found_company = True
                item_default.income_account = group_default.income_account
                item_default.default_warehouse = group_default.default_warehouse
                item_default.expense_account = group_default.expense_account
                item_default.selling_cost_center = group_default.selling_cost_center
                item_default.buying_cost_center = group_default.buying_cost_center
                item_default.default_supplier = group_default.default_supplier
                item_default.default_price_list = group_default.default_price_list
                break  # only from the inner for loop
        if not found_company:
            item.append('item_defaults', {
                'company': group_default.company,
                'default_warehouse': group_default.default_warehouse,
                'expense_account': group_default.expense_account,
                'income_account': group_default.income_account,
                'selling_cost_center': group_default.selling_cost_center,
                'buying_cost_center': group_default.buying_cost_center,
                'default_supplier': group_default.default_supplier,
                'default_price_list': group_default.default_price_list
            })


def overwrite_item_defaults(item):
    """
    Overwrite item.item_defaults of the item defined by its item name with item_group_defaults from Item Group.

    bench execute microsynth.microsynth.utils.overwrite_item_defaults --kwargs "{'item': '3100'}"
    """
    item = frappe.get_doc("Item", item)
    update_item_defaults(item)
    item.save()


def item_before_save(item, event):
    update_item_defaults(item)


@frappe.whitelist()
def force_cancel(dt, dn):
    """
    This function allows to move a document from draft directly to cancelled

    Parameters:
        dt      Doctype Name, e.g. "Quotation"
        dn      Record Name, e.g. "QTN-01234"

    It will only work from docstatus 0/Draft, because valid documents might need actions on cancel (GL Entry, ...)
    """
    try:
        # check if this doctype has a status field
        meta = frappe.get_meta(dt)
        if meta.has_field('status'):
            status_update = """, `status` = "Cancelled" """
            set_record_cancelled(dt, dn, status_update=status_update, key="name")
        else:
            set_record_cancelled(dt, dn, status_update="", key="name")

        # recurse into child tables
        for f in meta.fields:
            if f.fieldtype == "Table":
                set_record_cancelled(f.options, dn, status_update="", key="parent", parent_dt=dt)

        frappe.db.commit()
    except Exception as err:
        frappe.log_error(err, "Force cancel failed on {dt}:{dn}".format(dt=dt, dn=dn) )
    else:
        # TODO: If dn has not docstatus 0, it will not be set to docstatus 2, but will be commented:
        new_comment = frappe.get_doc({
            'doctype': 'Comment',
            'comment_type': "Comment",
            'subject': dn,
            'content': f'Force cancelled by {frappe.get_user().name}',
            'reference_doctype': dt,
            'status': "Linked",
            'reference_name': dn
        })
        new_comment.insert(ignore_permissions=True)
    return


def set_record_cancelled(dt, dn, status_update="", key="name", parent_dt=None):
    frappe.db.sql("""
        UPDATE `tab{dt}`
        SET
            `docstatus` = 2
            {status}
        WHERE
            `{key}` = "{dn}"
            AND `docstatus` = 0
            {parent};
    """.format(
        dt=dt,
        dn=dn,
        status=status_update,
        key=key,
        parent=""" AND `parenttype` = "{0}" """.format(parent_dt) if parent_dt else "")
    )
    return


def user_has_role(user, role):
    """
    Check if a user has a given role
    """
    role_matches = frappe.db.sql(f"""
        SELECT `parent`, `role`
        FROM `tabHas Role`
        WHERE `parent` = "{user}"
          AND `role` = "{role}"
          AND `parenttype` = "User";
        """, as_dict=True)

    return len(role_matches) > 0


# def user_has_roles(user, roles):
#     """
#     Check if a given user has at least one of the given roles.

#     bench execute microsynth.microsynth.utils.user_has_roles --kwargs "{'user': 'rolf.suter@microsynth.ch', 'roles': ['Robot', 'Blogger']}"
#     """
#     role_matches = frappe.db.sql(f"""
#         SELECT `parent`, `role`
#         FROM `tabHas Role`
#         WHERE `parent` = "{user}"
#           AND `role` IN ({get_sql_list(roles)})
#           AND `parenttype` = "User";
#         """, as_dict=True)

#     return len(role_matches) > 0


@frappe.whitelist()
def get_potential_contact_duplicates(contact_id):
    """
    bench execute microsynth.microsynth.utils.get_potential_contact_duplicates --kwargs "{'contact_id': '215856'}"
    """
    contact = frappe.get_doc("Contact", contact_id)
    address_type = frappe.get_value("Address", contact.address, "address_type")
    contacts = frappe.db.sql(f"""
        SELECT `tabContact`.`name`,
            `tabContact`.`first_name`,
            `tabContact`.`last_name`,
            `tabContact`.`institute`
        FROM `tabContact`
        LEFT JOIN `tabAddress` ON `tabContact`.`address` = `tabAddress`.`name`
        WHERE `tabContact`.`status` != 'Disabled'
            AND (`tabContact`.`email_id` = '{contact.email_id}'
                OR (`tabContact`.`first_name` = '{contact.first_name}'
                    AND `tabContact`.`last_name` = '{contact.last_name}'
                )
            )
            AND `tabAddress`.`address_type` = '{address_type}'
            AND `tabContact`.`name` != '{contact.name}'
        """, as_dict=True)
    return contacts


def set_module_for_one_user(module, user):
    """
    bench execute microsynth.microsynth.utils.set_module_for_one_user --kwargs "{'module': 'QMS', 'user': 'firstname.lastname@microsynth.ch'}"
    """
    #home_settings = frappe.cache().hget('home_settings', user)
    home_settings = frappe.db.get_value('User', user, 'home_settings')
    if home_settings:
        home_settings = json.loads(home_settings)
    else:
        home_settings = None
    inserted = False
    if not home_settings:
        print(f"Found no home_settings for user '{user}'. Going to take those from the Administrator.")
        home_settings = frappe.cache().hget('home_settings', 'Administrator')
        if not home_settings:
            home_settings = json.loads(frappe.db.get_value('User', 'Administrator', 'home_settings'))
            if not home_settings:
                print("Found no home_settings for Administrator. Going to return.")
                return
        modules = home_settings['modules_by_category']['Modules']
        if module in modules:
            inserted = True
    modules = home_settings['modules_by_category']['Modules']
    if not module in modules and 'Microsynth' in modules:
        for i in range(len(modules)):
            if modules[i] == 'Microsynth':
                modules.insert(i+1, module)
                inserted = True
                break
    if inserted:
        home_settings['modules_by_category']['Modules'] = modules
        s = frappe.parse_json(home_settings)
        frappe.cache().hset('home_settings', user, s)                                       # update cached value (s as dict)
        frappe.db.set_value('User', user, 'home_settings', json.dumps(home_settings))       # also update database value
        print(f"Added module '{module}' to home_settings of user '{user}'.")
    else:
        print(f"Module '{module}' is already in home_settings of user '{user}'.")


def set_module_for_all_users(module):
    """
    bench execute microsynth.microsynth.utils.set_module_for_all_users --kwargs "{'module': 'QMS'}"
    """
    users = frappe.get_all("User", fields=['name'])
    for user in users:
        set_module_for_one_user(module, user['name'])


def set_module_according_to_role(user, role_module_mapping):
    """
    bench execute microsynth.microsynth.utils.set_module_according_to_role --kwargs "{'user': 'firstname.lastname@microsynth.ch', 'role_module_mapping': {}}"
    """
    # exclude some roles
    if user_has_role(user, 'System Manager'):
        print(f"User {user} has role System Manager. Not going to change modules.")
        return
    if type(role_module_mapping) == str:
        role_module_mapping = json.loads(role_module_mapping)
    has_any_given_role = False
    modules = set()
    for role in role_module_mapping.keys():
        if user_has_role(user, role):
            has_any_given_role = True
            for module in role_module_mapping[role]:
                modules.add(module)
    if not has_any_given_role:
        print(f"User {user} has none of the given roles. Not going to change modules.")
        return
    home_settings = {'modules_by_category': {'Administration': [], 'Modules': list(modules), 'Places': [], 'Domains': []}}
    s = frappe.parse_json(home_settings)
    frappe.cache().hset('home_settings', user, s)  # update cached value (s as dict)
    old_home_settings = frappe.db.get_value('User', user, 'home_settings')
    frappe.db.set_value('User', user, 'home_settings', json.dumps(home_settings))  # also update database value
    print(f"Changed the home_settings of user {user} from {old_home_settings} to {home_settings}.")


def set_modules_for_all_users(role_module_mapping):
    """
    role_module_mapping has to be a dictionary or its string representation mapping roles (strings) to a list of modules (list of strings) each.

    bench execute microsynth.microsynth.utils.set_modules_for_all_users --kwargs "{'role_module_mapping': {'QM User': ['QMS'], 'QM Reader': ['QMS'], 'QAU': ['Microsynth', 'QMS'], 'Microsynth User': ['Microsynth', 'QMS'], 'NGS Lab User': ['Microsynth', 'QMS'], 'Accounts User': ['Microsynth', 'QMS', 'Accounting']}}"
    """
    if isinstance(role_module_mapping, str):
        try:
            role_module_mapping = json.loads(role_module_mapping)
        except json.JSONDecodeError:
            frappe.throw("Invalid role_module_mapping format. Must be a valid JSON string.")
    elif not isinstance(role_module_mapping, dict):
        frappe.throw("Invalid role_module_mapping format. Must be a dictionary.")

    for role, modules in role_module_mapping.items():
        if not isinstance(role, str) or not isinstance(modules, list):
            frappe.throw(f"Invalid role-module mapping for role '{role}'. Modules must be a list of strings.")

    enabled_users = frappe.get_all("User", filters={'enabled': 1}, fields=['name'])
    for user in enabled_users:
        set_module_according_to_role(user['name'], role_module_mapping)


@frappe.whitelist()
def has_distributor(customer, product_type):
    """
    Checks if the given Customer has a Distributor for the given Product Type.

    bench execute microsynth.microsynth.utils.has_distributor --kwargs "{'customer': '832547', 'product_type': 'Genetic Analysis'}"
    """
    customer_doc = frappe.get_doc("Customer", customer)
    for distributor in customer_doc.distributors:
        if distributor.product_type == product_type:
            return True
    return False


def has_items_delivered_by_supplier(sales_order_id):
    """
    Checks if there are any Sales Order Items for the given Sales Order ID
    with the flag "Supplier delivers to Customer" set.

    bench execute microsynth.microsynth.utils.has_items_delivered_by_supplier --kwargs "{'sales_order_id': 'SO-GOE-25011431'}"
    """
    items_delivered_by_supplier = frappe.db.sql(f"""
        SELECT `tabSales Order Item`.`name`
        FROM `tabSales Order Item`
        WHERE `tabSales Order Item`.`parent` = '{sales_order_id}'
            AND `tabSales Order Item`.`delivered_by_supplier` = 1
        ;""", as_dict=True)
    return len(items_delivered_by_supplier) > 0


def print_users_without_role(role):
    """
    bench execute microsynth.microsynth.utils.print_users_without_role --kwargs "{'role': 'Microsynth User'}"
    """
    users = frappe.get_all("User", fields=['name'])
    for user in users:
        if not user_has_role(user['name'], role):
            print(user['name'])


def fetch_quotation(sales_order):
    """
    Checks if there is a Quotation linked against the given Sales Order.
    If yes, return it. If no, return None.

    bench execute microsynth.microsynth.utils.fetch_quotation --kwargs "{'sales_order': 'SO-BAL-24041373'}"
    """
    sales_order_doc = frappe.get_doc("Sales Order", sales_order)
    for item in sales_order_doc.items:
        if item.prevdoc_docname:
            return item.prevdoc_docname
    return None


def check_sales_order(sales_order, event):
    if not sales_order.customer_address or \
       not sales_order.invoice_to or \
       not sales_order.contact_person or \
       not sales_order.shipping_address_name:
        frappe.throw("The following fields are mandatory to submit:<ul><li>Billing Address Name</li><li>Shipping Address Name</li><li>Invoice To</li><li>Contact Person</li></ul>Please check the section <b>Address and Contact</b>.")


def validate_sales_order_items(sales_order_doc, event=None):
    """
    Validate the Sales Order (server-side validation trigger).
    Validate that no Item on the Sales Order has Sales Status "In Preparation" or "Discontinued".
    """
    invalid_items = []

    for item in sales_order_doc.items:
        sales_status = frappe.get_value("Item", item.item_code, "sales_status")
        if sales_status in ["In Preparation", "Discontinued"]:
            invalid_items.append((item.item_code, item.item_name, sales_status))

    if invalid_items:
        # Build HTML table
        html = """
        <p>The following Items are not allowed to be on this Sales Order:</p>
        <table class="table table-bordered">
            <thead>
                <tr>
                    <th>Item</th>
                    <th>Sales Status</th>
                </tr>
            </thead>
            <tbody>
        """
        for item_code, item_name, status in invalid_items:
            html += f"<tr><td>{item_code}: {item_name}</td><td>{status}</td></tr>"

        html += """
            </tbody>
        </table>
        <p><b>Please remove or replace these Items.</b></p>
        """
        if frappe.session.user == "webshop@microsynth.ch":
            frappe.log_error(f"The Webshop tried to save Sales Order {sales_order_doc.name} with invalid items: {invalid_items}", "Invalid Items on Webshop Sales Order")
            return
        frappe.throw(html, title="Invalid Items")


def report_therapeutic_oligo_sales(from_date=None, to_date=None):
    """
    Run by a monthly cronjob on the first of each month at 0:40:
    40 0 1 * * cd /home/frappe/frappe-bench && /usr/local/bin/bench --site erp.microsynth.local execute microsynth.microsynth.utils.report_therapeutic_oligo_sales

    bench execute microsynth.microsynth.utils.report_therapeutic_oligo_sales --kwargs "{'from_date': '2025-09-01', 'to_date': '2025-09-30'}"
    """
    start_ts = datetime.now()

    intercompany_customers = frappe.get_all("Intercompany Settings Company", fields=['customer'])
    intercompany_customer_list = [entry['customer'] for entry in intercompany_customers]

    si_rna_item_codes = set(['0672', '0673', '0674', '0677', '0678', '0679', '0830', '0831', '0832', '0833', '0834', '0835', '0836', '0837', '0458', '0459', '0740', '0741'])
    aso_item_codes = set(['0456', '0457', '0728', '0729', '0730', '0731', '0732', '0733', '0734', '0735', '0736', '0737', '0738', '0739', '0820', '0821', '0870', '0871', '0872', '0873', '0876', '0877', '0878', '0879', '0882', '0883', '0884', '0885', '0888', '0889', '0890'])

    asos = []
    sirnas = []
    neither_counter = 0

    currencies = ['CHF', 'EUR', 'USD', 'SEK', 'PLN']
    sirna_totals = {'CHF': 0, 'EUR': 0, 'USD': 0, 'SEK': 0, 'PLN': 0}
    aso_totals = {'CHF': 0, 'EUR': 0, 'USD': 0, 'SEK': 0, 'PLN': 0}

    yesterday = datetime.now() - timedelta(days=1)
    if not from_date:
        from_date = f"{yesterday.year}-{yesterday.month}-01"
    if not to_date:
        to_date = f"{yesterday.year}-{yesterday.month}-{yesterday.day}" # yesterday.date()
    print(f"{from_date=}; {to_date=}")

    item_query = f"""
        SELECT
            `tabSales Invoice`.`name`,
            `tabSales Invoice Item`.`base_amount` AS `total`,
            `tabSales Invoice`.`currency` AS `currency`,
            `tabSales Invoice`.`posting_date` AS `date`,
            `tabSales Invoice`.`web_order_id`,
            `tabSales Invoice`.`customer`,
            `tabSales Invoice`.`customer_name`,
            `tabSales Invoice`.`contact_person`,
            `tabSales Invoice`.`company`,
            `tabSales Invoice`.`product_type`,
            `tabSales Invoice Item`.`item_code` AS `items`,
            `tabSales Invoice Item`.`delivery_note`,
            `tabCustomer`.`account_manager` AS `sales_manager`
        FROM `tabSales Invoice Item`
        LEFT JOIN `tabSales Invoice` ON `tabSales Invoice Item`.`parent` = `tabSales Invoice`.`name`
        LEFT JOIN `tabCustomer` ON `tabCustomer`.`name` = `tabSales Invoice`.`customer`
        WHERE
            `tabSales Invoice`.`docstatus` = 1
            AND `tabSales Invoice Item`.`docstatus` = 1
            AND `tabSales Invoice Item`.`item_code` IN ('0640', '0650', '0660', '0670', '0671', '0652', '0653', '0655', '0665')
            AND `tabSales Invoice`.`posting_date` BETWEEN DATE('{from_date}') AND DATE('{to_date}')
            AND `tabSales Invoice`.`customer` NOT IN ({get_sql_list(intercompany_customer_list)})
        """
    si_rna_items = frappe.db.sql(item_query, as_dict=True)

    for si_rna_item in si_rna_items:
        sirnas.append(si_rna_item)
        si_rna_item['items'] = set([si_rna_item['items']])
        si_rna_item['delivery_notes'] = set([si_rna_item['delivery_note']])
        sirna_totals[si_rna_item['currency']] += si_rna_item['total']

    query = f"""
            SELECT
                `tabSales Invoice`.`name`,
                `tabSales Invoice`.`base_total` AS `total`,
                `tabSales Invoice`.`currency` AS `currency`,
                `tabSales Invoice`.`posting_date` AS `date`,
                `tabSales Invoice`.`web_order_id`,
                `tabSales Invoice`.`customer`,
                `tabSales Invoice`.`customer_name`,
                `tabSales Invoice`.`contact_person`,
                `tabSales Invoice`.`company`,
                `tabSales Invoice`.`product_type`,
                `tabCustomer`.`account_manager` AS `sales_manager`
            FROM `tabSales Invoice Item`
            LEFT JOIN `tabSales Invoice` ON `tabSales Invoice Item`.`parent` = `tabSales Invoice`.`name`
            LEFT JOIN `tabCustomer` ON `tabCustomer`.`name` = `tabSales Invoice`.`customer`
            WHERE
                `tabSales Invoice`.`docstatus` = 1
                AND `tabSales Invoice Item`.`item_code` IN ('0352', '0353', '0354', '0355', '0372', '0373', '0374', '0379', '0380', '0381', '0382', '0383', '0448', '0449', '0450', '0451', '0452', '0453', '0454', '0455', '0570', '0571', '0572', '0573', '0574', '0575', '0576', '0600', '0601', '0602', '0605', '0606', '0607', '0608', '0672', '0673', '0674', '0677', '0678', '0679', '0820', '0821', '0830', '0831', '0832', '0833', '0834', '0835', '0836', '0837', '0845', '0860', '0861', '0870', '0871', '0872', '0873', '0876', '0877', '0878', '0879', '0882', '0883', '0884', '0885', '0888', '0889', '0890' )
                AND `tabSales Invoice`.`posting_date` BETWEEN DATE('{from_date}') AND DATE('{to_date}')
                AND `tabSales Invoice`.`customer` NOT IN ({get_sql_list(intercompany_customer_list)})
            GROUP BY `tabSales Invoice`.`name`
            """
    potential_sales_invoices = frappe.db.sql(query, as_dict=True)
    print(f"{datetime.now()}: Going to distinguish between siRNA, ASO and neither for {len(potential_sales_invoices)} Sales Invoices.")

    for si in potential_sales_invoices:
        si_doc = frappe.get_doc("Sales Invoice", si['name'])
        items = set()
        delivery_notes = set()
        # add items to a set
        for item in si_doc.items:
            items.add(item.item_code)
            delivery_notes.add(item.delivery_note)
        si['items'] = items
        si['delivery_notes'] = delivery_notes
        # search for siRNA first
        if '0651' in items or '0661' in items:
            # potential siRNA
            if '0379' in items or '0372' in items or '0373' in items or '0374' in items:
                sirnas.append(si)
                continue
            elif '0605' in items or '0606' in items or '0607' in items or '0608' in items:
                sirnas.append(si)
                continue
            elif '0375' in items or '0376' in items or '0377' in items or '0378' in items:
                sirnas.append(si)
                continue
            elif '0380' in items or '0381' in items or '0382' in items or '0383' in items:
                sirnas.append(si)
                continue
            elif '0448' in items or '0449' in items or '0450' in items or '0451' in items:
                sirnas.append(si)
                continue
            elif '0452' in items or '0453' in items or '0454' in items or '0455' in items:
                sirnas.append(si)
                continue
            # it could still be an ASO
        if ('0662' in items or '0663' in items) and ('0379' in items or '0372' in items or '0373' in items or '0374' in items):
            sirnas.append(si)
            continue
        elif len(items.intersection(si_rna_item_codes)) > 0:
            sirnas.append(si)
            continue
        # search for ASOs
        elif '0860' in items or '0861' in items:
            asos.append(si)
            continue
        elif '0820' in items or '0821' in items:
            asos.append(si)
            continue
        elif len(items.intersection(aso_item_codes)) > 0:
            asos.append(si)
            continue
        elif '0380' in items or '0381' in items or '0382' in items or '0383' in items:
            asos.append(si)
            continue
        elif '0600' in items or '0601' in items or '0602' in items:
            # potential ASO
            if '0352' in items or '0353' in items or '0354' in items or '0355' in items:
                asos.append(si)
                continue
            elif '0605' in items or '0606' in items or '0607' in items or '0608' in items:
                asos.append(si)
                continue
            elif '0375' in items or '0376' in items or '0377' in items or '0378' in items:
                asos.append(si)
                continue
            elif '0379' in items or '0372' in items or '0373' in items or '0374' in items:
                asos.append(si)
                continue
            else:
                neither_counter += 1
        else:
            neither_counter += 1

    print(f"\n{len(sirnas)=}, {len(asos)=}, {neither_counter=}, total={len(sirnas) + len(asos) + neither_counter}\n")

    file_content = "classification;name;total;currency;date;web_order_id;customer;customer_name;contact_person;sales_manager;company;product_type;items;is_collective\n"

    for si in sirnas:
        sirna_totals[si['currency']] += si['total']
        is_collective = len(si['delivery_notes']) > 1
        items_string = ",".join(list(si['items']))
        file_content += f"siRNA;{si['name']};{si['total']};{si['currency']};{si['date']};{si['web_order_id']};{si['customer']};{si['customer_name']};{si['contact_person']};{si['sales_manager']};{si['company']};{si['product_type']};{items_string};{is_collective}\n"

    for si in asos:
        aso_totals[si['currency']] += si['total']
        is_collective = len(si['delivery_notes']) > 1
        items_string = ",".join(list(si['items']))
        file_content += f"ASO;{si['name']};{si['total']};{si['currency']};{si['date']};{si['web_order_id']};{si['customer']};{si['customer_name']};{si['contact_person']};{si['sales_manager']};{si['company']};{si['product_type']};{items_string};{is_collective}\n"

    summary = ""
    for c in currencies:
        total_string = f"{sirna_totals[c]:,.2f}".replace(",", "'")
        summary += f"<br>siRNA: {total_string} {c}"
        total_string = f"{aso_totals[c]:,.2f}".replace(",", "'")
        summary += f"<br>ASO: {total_string} {c}<br>"

    print(summary)
    elapsed_time = timedelta(seconds=(datetime.now() - start_ts).total_seconds())
    print(f"\n{datetime.now()}: Finished calculate_therapeutic_oligo_sales after {elapsed_time} hh:mm:ss.")

    _file = frappe.get_doc(
        {
            "doctype": "File",
            "file_name": f"ASO_siRNA_sales_from_{from_date}_to_{to_date}_created_{datetime.now().strftime('%Y-%m-%d_%H-%M')}.csv",
            "is_private": 1,
            "content": file_content,
        })
    _file.save()
    frappe.db.commit()
    email_template = frappe.get_doc("Email Template", "ASO and siRNA Sales Export")
    rendered_content = frappe.render_template(email_template.response, {'from_date': from_date, 'to_date': to_date, 'summary': summary})
    send_email_from_template(email_template, rendered_content, rendered_subject=None, attachments=[{'fid': _file.name}])


def send_email_from_template(email_template, rendered_content, rendered_subject=None, attachments=None, recipients=None):
    """
    Takes an Email Template object, the rendered content (message) and optionally a rendered subjects
    and triggers the sending of the corresponding email.
    """
    make(
            recipients = recipients if recipients else email_template.recipients,
            cc = email_template.cc_recipients,
            sender = email_template.sender,
            sender_full_name = email_template.sender_full_name,
            subject = rendered_subject if rendered_subject else email_template.subject,
            content = rendered_content,
            attachments = attachments,
            send_email = True
        )


@frappe.whitelist()
def set_xml_version(xml_version):
    try:
        settings = frappe.get_doc("ERPNextSwiss Settings", "ERPNextSwiss Settings")
        settings.xml_version = xml_version
        settings.save(ignore_permissions=True)
    except Exception as err:
        return {'success': False, 'message': err}
    return {'success': True, 'message': 'OK'}


def find_unsend_communications(from_date_time, to_date_time):
    """
    bench execute microsynth.microsynth.utils.find_unsend_communications --kwargs "{'from_date_time': '2025-03-10 20:00:00', 'to_date_time': '2025-03-11 12:00:00'}"
    """
    query = f"""
            SELECT
                `tabCommunication`.`name`,
                `tabCommunication`.`creation`,
                `tabCommunication`.`status`
            FROM `tabCommunication`
            LEFT JOIN `tabEmail Queue` ON `tabEmail Queue`.`communication` = `tabCommunication`.`name`
            WHERE
                `tabCommunication`.`communication_type` = "Communication"
                AND `tabCommunication`.`creation` >= '{from_date_time}'
                AND `tabCommunication`.`creation` <= '{to_date_time}'
                -- AND `tabCommunication`.`status` = "Linked"
                AND `tabCommunication`.`sent_or_received` = "Sent"
                AND `tabEmail Queue`.`name` IS NULL
            ORDER BY `creation`
            """
    communications = frappe.db.sql(query, as_dict=True)

    for c in communications:
        print(f"{c['name']}    {c['creation']}    {c['status']}" )

    print(f"number of communications: {len(communications)}")

    return communications


def send_communication(communication_id):
    """
    bench execute microsynth.microsynth.utils.send_communication --kwargs "{'communication_id': 'e6ab3eee0e'}"
    """
    communication = frappe.get_doc("Communication", communication_id)
    communication.send()


def send_unsend_communications(from_date_time, to_date_time):
    """
    bench execute microsynth.microsynth.utils.send_unsend_communications --kwargs "{'from_date_time': '2025-03-10 20:00:00', 'to_date_time': '2025-03-11 12:00:00'}"
    """
    communications = find_unsend_communications(from_date_time, to_date_time)
    for c in communications:
        send_communication(c['name'])


def iterate_dates(start_date, end_date):
    """
    Yield all dates from the given start_date to and including the given end_date
    """
    current_date = start_date
    while current_date <= end_date:
        yield current_date
        current_date += timedelta(days=1)


def is_workday(date_time, holidays):
    """
    Returns true if the given date_time is a workday (Monday to Friday and no holiday), otherwise false.
    """
    # https://docs.python.org/3/library/datetime.html#datetime.date.weekday
    if date_time.weekday() < 5 and date_time.strftime('%d.%m.%Y') not in holidays:
        return True
    return False


def add_workdays(date, workdays):
    """
    Calculates the date that is exactly :param workdays in the future from the given date.
    The existence of public holidays is ignored.
    """
    if type(date) == str:
        current_date = datetime.strptime(date, "%Y-%m-%d").date()
    else:
        current_date = date
    workdays_needed = workdays

    # Go forwards until we have found two workdays
    while workdays_needed > 0:
        current_date += timedelta(days=1)
        if current_date.weekday() < 5:  # 0-4 are Monday to Friday (workdays)
            workdays_needed -= 1

    return current_date


def get_sql_list(raw_list):
    if raw_list:
        return (','.join('"{0}"'.format(e) for e in raw_list))
    else:
        return '""'


def with_url(doctype, docs):
    return [
        {
            **doc,
            "url": get_url_to_form(doctype, doc["name"])
        }
        for doc in docs
    ]


@frappe.whitelist()
def get_open_documents_for_item(item_code):
    """
    Returns open documents that reference the given Item.
    """
    result = {
        "Quotation": [],
        "Sales Order": [],
        "Delivery Note": [],
        "Sales Invoice": []
    }

    # Quotations (open & valid)
    qt_items = frappe.get_all("Quotation Item",
        filters={
            "item_code": item_code,
            "docstatus": 1,
            "parenttype": "Quotation"
        },
        fields=["parent"],
        distinct=True
    )
    if qt_items:
        quotations = frappe.get_all("Quotation",
            filters={
                "name": ["in", [d.parent for d in qt_items]],
                "status": "Open",
                "valid_till": [">=", nowdate()],
                "docstatus": 1
            },
            fields=["name", "transaction_date", "valid_till"]
        )
        result["Quotation"] = with_url("Quotation", quotations)

    # Sales Orders (not closed / not fully delivered)
    so_items = frappe.get_all("Sales Order Item",
        filters={
            "item_code": item_code,
            "docstatus": 1,
            "parenttype": "Sales Order"
        },
        fields=["parent"],
        distinct=True
    )
    if so_items:
        sales_orders = frappe.get_all("Sales Order",
            filters={
                "name": ["in", [d.parent for d in so_items]],
                "status": ["!=", "Closed"],
                "per_delivered": ["<", 100],
                "docstatus": 1
            },
            fields=["name", "transaction_date"]
        )
        result["Sales Order"] = with_url("Sales Order", sales_orders)

    # Delivery Notes (not fully billed)
    dn_items = frappe.get_all("Delivery Note Item",
        filters={
            "item_code": item_code,
            "docstatus": 1,
            "parenttype": "Delivery Note"
        },
        fields=["parent"],
        distinct=True
    )
    if dn_items:
        delivery_notes = frappe.get_all("Delivery Note",
            filters={
                "name": ["in", [d.parent for d in dn_items]],
                "status": ["!=", "Closed"],
                "per_billed": ["<", 100],
                "docstatus": 1
            },
            fields=["name", "posting_date"]
        )
        result["Delivery Note"] = with_url("Delivery Note", delivery_notes)

    # Sales Invoices (with outstanding amount)
    si_items = frappe.get_all("Sales Invoice Item",
        filters={
            "item_code": item_code,
            "docstatus": 1,
            "parenttype": "Sales Invoice"
        },
        fields=["parent"],
        distinct=True
    )

    if si_items:
        invoices = frappe.get_all("Sales Invoice",
            filters={
                "name": ["in", [d.parent for d in si_items]],
                "outstanding_amount": [">", 0],
                "docstatus": 1
            },
            fields=["name", "posting_date", "outstanding_amount"]
        )
        result["Sales Invoice"] = with_url("Sales Invoice", invoices)

    return result


@frappe.whitelist()
def get_open_documents_for_customer(customer_id):
    """
    Returns a dictionary of open documents linked directly to a Customer,
    including form URLs for each entry.

    Usage:
    bench execute microsynth.microsynth.utils.get_open_documents_for_customer --kwargs "{'customer_id': '37545653'}"
    """
    result = {
        "Sales Invoice": [],
        "Delivery Note": [],
        "Sales Order": [],
        "Quotation": []
    }
    # Sales Invoices with outstanding amount
    invoices = frappe.get_all("Sales Invoice",
        filters={
            "customer": customer_id,
            "docstatus": 1,
            "outstanding_amount": [">", 0]
        },
        fields=["name", "posting_date", "outstanding_amount"]
    )
    result["Sales Invoice"] = with_url("Sales Invoice", invoices)

    # Delivery Notes not fully billed
    delivery_notes = frappe.get_all("Delivery Note",
        filters={
            "customer": customer_id,
            "docstatus": 1,
            "status": ["!=", "Closed"],
            "per_billed": 0
        },
        fields=["name", "posting_date", "per_billed"]
    )
    result["Delivery Note"] = with_url("Delivery Note", delivery_notes)

    # Sales Orders not fully delivered
    sales_orders = frappe.get_all("Sales Order",
        filters={
            "customer": customer_id,
            "docstatus": 1,
            "status": ["!=", "Closed"],
            "per_delivered": ["<", 100],
        },
        fields=["name", "transaction_date", "per_delivered"]
    )
    result["Sales Order"] = with_url("Sales Order", sales_orders)

    # Open and valid Quotations
    quotations = frappe.get_all("Quotation",
        filters={
            "party_name": customer_id,
            "docstatus": 1,
            "status": "Open",
            "valid_till": [">=", nowdate()]
        },
        fields=["name", "transaction_date", "valid_till"]
    )
    result["Quotation"] = with_url("Quotation", quotations)

    return result


def is_contact_safe_to_disable(contact_id):
    """
    bench execute microsynth.microsynth.utils.is_contact_safe_to_disable --kwargs "{'contact_id': '247270'}"
    """
    # 1. Linked to Sales Invoices
    invoice = frappe.db.exists({
        "doctype": "Sales Invoice",
        "contact_person": contact_id,
        "docstatus": 1,
        "outstanding_amount": [">", 0]
    })
    if invoice:
        return False

    # 2. Linked to Delivery Notes
    dn = frappe.db.exists({
        "doctype": "Delivery Note",
        "contact_person": contact_id,
        "docstatus": 1,
        "status": ["!=", "Closed"],
        "per_billed": 0
    })
    if dn:
        return False

    # 3. Used by another Customer (invoice_to or reminder_to)
    customer_id = get_customer(contact_id)
    other_customers = frappe.db.sql("""
        SELECT name FROM `tabCustomer`
        WHERE name != %s
            AND (invoice_to = %s OR reminder_to = %s)
            AND disabled = 0
        LIMIT 1
    """, (customer_id, contact_id, contact_id))
    if other_customers:
        return False

    # 4. Linked on Sales Orders
    so = frappe.db.exists({
        "doctype": "Sales Order",
        "contact_person": contact_id,
        "docstatus": 1,
        "status": ["!=", "Closed"],
        "per_delivered": 0
    })
    if so:
        return False

    # 5. Linked on Quotations
    quotation = frappe.db.exists({
        "doctype": "Quotation",
        "contact_person": contact_id,
        "docstatus": 1,
        "status": 'Open',
        "valid_till": [">=", frappe.utils.nowdate()]
    })
    if quotation:
        return False

    return True


def is_address_safe_to_disable(address_id):
    """
    bench execute microsynth.microsynth.utils.is_address_safe_to_disable --kwargs "{'address_id': '247270'}"
    """
    # 1. Linked to submitted Sales Invoices
    invoice = frappe.db.exists({
        "doctype": "Sales Invoice",
        "customer_address": address_id,
        "docstatus": 1,
        "outstanding_amount": [">", 0]
    })
    if invoice:
        return False

    # 2. Linked to Delivery Notes
    dn = frappe.db.exists({
        "doctype": "Delivery Note",
        "shipping_address_name": address_id,
        "docstatus": 1,
        "status": ["!=", "Closed"],
        "per_billed": 0
    })
    if dn:
        return False

    # 3. Linked on Sales Orders
    so = frappe.db.exists({
        "doctype": "Sales Order",
        "shipping_address_name": address_id,
        "docstatus": 1,
        "status": ["!=", "Closed"],
        "per_delivered": 0
    })
    if so:
        return False

    # 4. Linked on Quotations
    quotation = frappe.db.exists({
        "doctype": "Quotation",
        "shipping_address_name": address_id,
        "docstatus": 1,
        "status": 'Open',
        "valid_till": [">=", frappe.utils.nowdate()]
    })
    if quotation:
        return False

    return True


@frappe.whitelist()
def check_linked_contacts_addresses(customer_id):
    """
    bench execute microsynth.microsynth.utils.check_linked_contacts_addresses --kwargs "{'customer_id': '37545653'}"
    """
    customer = frappe.get_doc("Customer", customer_id)

    to_disable = []
    not_to_disable = []

    # Check Contacts
    contacts = frappe.get_all("Contact",
        filters={
            "link_doctype": "Customer",
            "link_name": customer.name,
            "status": ["!=", "Disabled"]
        },
        fields=["name"],
        distinct=True
    )
    for c in contacts:
        if is_contact_safe_to_disable(c.name):
            to_disable.append({"doctype": "Contact",
                               "name": c.name,
                               "url": get_url_to_form("Contact", c.name)})
        else:
            not_to_disable.append({"doctype": "Contact",
                                   "name": c.name,
                                   "url": get_url_to_form("Contact", c.name)})

    # Check Addresses
    addresses = frappe.get_all("Address",
        filters={"link_doctype": "Customer", "link_name": customer.name, "disabled": 0},
        fields=["name"], distinct=True
    )
    for a in addresses:
        if is_address_safe_to_disable(a.name):
            to_disable.append({"doctype": "Address",
                               "name": a.name,
                               "url": get_url_to_form("Address", a.name)})
        else:
            not_to_disable.append({"doctype": "Address",
                                   "name": a.name,
                                   "url": get_url_to_form("Address", a.name)})

    return {"to_disable": to_disable, "not_to_disable": not_to_disable}


@frappe.whitelist()
def disable_linked_contacts_addresses(links):
    import json
    links = json.loads(links) if isinstance(links, str) else links

    for entry in links:
        doc = frappe.get_doc(entry["doctype"], entry["name"])
        if doc.doctype == "Contact":
            doc.status = "Disabled"
        elif doc.doctype == "Address":
            doc.disabled = 1
        doc.save(ignore_permissions=True)

    frappe.db.commit()
