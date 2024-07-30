# -*- coding: utf-8 -*-
# Copyright (c) 2022-2024, libracore (https://www.libracore.com) and contributors
# For license information, please see license.txt

import os
import re
import frappe
import json
from datetime import datetime, date, timedelta
from frappe.utils import flt, rounded
from frappe.core.doctype.communication.email import make
from erpnextswiss.scripts.crm_tools import get_primary_customer_contact


def get_customer(contact):
    """
    Returns the customer for a contact ID. 
    Logs an error if no customer is linked to the contact.

    run
    bench execute microsynth.microsynth.utils.get_customer --kwargs "{'contact': 215856 }"
    """
    # get contact
    contact = frappe.get_doc("Contact", contact)
    # check links
    customer_id = None
    for l in contact.links:
        if l.link_doctype == "Customer":
            customer_id = l.link_name

    if not customer_id:
        subject = f"Contact '{contact.name}' is not linked to a Customer"
        message = f"Dear Administration,<br><br>this is an automatic email to inform you that Contact '{contact.name}' (created by {contact.owner}) "
        message += f"is not linked to any Customer in the ERP.<br>Please clean up this Contact.<br><br>Best regards,<br>Jens"
        # non_html_message = message.replace("<br>","\n")
        # frappe.log_error(non_html_message, f"{subject} (utils.get_customer)")
        #print(subject + '\n\n' + non_html_message)
        make(
            recipients = "info@microsynth.ch",
            sender = "jens.petermann@microsynth.ch",
            subject = "[ERP] " + subject,
            content = message,
            send_email = True
            )

    return customer_id


# TODO
# Rename get_billing_address to find_billing_address
# New function get_billing_address that pulls from the invoice_to contact of a customer. fall back on find_billing_address below
def get_billing_address(customer_id):
    """
    Returns the primary billing address of a customer specified by its id.

    run
    bench execute "microsynth.microsynth.utils.get_billing_address" --kwargs "{'customer_id':8003}"
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
        frappe.throw("None or multiple billing addresses found for customer '{0}'".format(customer_id),"get_billing_address")


@frappe.whitelist()
def get_webshop_url():
    return frappe.get_value('Microsynth Settings', 'Microsynth Settings', 'webshop_url')


@frappe.whitelist()
def update_address_links_from_contact(address_name, links):
    
    if frappe.db.exists("Address", address_name):
        address = frappe.get_doc("Address", address_name)
        address.links = []
        if type(links) == str:
           links = json.loads(links) 
        for link in links:
            address.append("links", { 
                "link_doctype": link["link_doctype"],
                "link_name": link["link_name"]
            } )
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


def replace_none(input):
    """
    Return an empty string if the input is None, else return the input.
    """
    return input if (input != None) else ""


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


def get_country_express_shipping_item(country_name):
    """
    Return the preferred shipping item for the given country name.
    """

    country = frappe.get_doc("Country", country_name)
    express_items = []

    for item in country.shipping_items:
        if item.preferred_express:
            express_items.append(item)

    if len(express_items) == 0:
        frappe.log_error("No preferred express item found for country '{0}'".format(country_name), "utils.get_country_express_shipping_item")
        None
    if len(express_items) > 0:
        
        if len(express_items) > 1:
            frappe.log_error("Multiple preferred express shipping items found for country '{0}'".format(country_name), "utils.get_country_express_shipping_item")
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
    bench execute microsynth.microsynth.utils.get_express_shipping_item --kwargs "{ 'customer_name': '38480', 'country_name': 'Germany' }"
    """

    customer_express_item = get_customer_express_shipping_item(customer_name)
    if customer_express_item:
        return customer_express_item
    else:
        country_express_item = get_country_express_shipping_item(country_name)
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


def validate_sales_order_status(sales_order):
    """
    Checks if the customer is enabled, the sales order is submitted, has an allowed
    status and has the tax template set.

    run 
    bench execute microsynth.microsynth.utils.validate_sales_order_status --kwargs "{'sales_order': ''}"
    """
    customer = get_customer_from_sales_order(sales_order)

    if customer.disabled:
        frappe.log_error("Customer '{0}' of order '{1}' is disabled. Cannot create a delivery note.".format(customer.name, sales_order), "utils.validate_sales_order")
        return False

    so = frappe.get_doc("Sales Order", sales_order)

    if so.docstatus != 1:
        frappe.log_error(f"Sales Order {so.name} is not submitted. Cannot create a delivery note.", "utils.validate_sales_order")
        return False

    if so.status in ['Completed', 'Canceled', 'Closed']:
        frappe.log_error(f"Sales Order {so.name} is in status '{so.status}'. Cannot create a delivery note.", "utils.validate_sales_order")
        return False

    if not so.taxes_and_charges or so.taxes_and_charges == "":
        frappe.log_error(f"Sales Order {so.name} has not Sales Taxes and Charges Template. Cannot create a delivery note.", "utils.validate_sales_order")
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
        web_order_id_condition = f"OR `tabDelivery Note`.`web_order_id` = {web_order_id}"
    else:
        web_order_id_condition = ""

    delivery_notes = frappe.db.sql(f"""
        SELECT `tabDelivery Note Item`.`parent`
        FROM `tabDelivery Note Item`
        LEFT JOIN `tabDelivery Note` ON `tabDelivery Note`.`name` = `tabDelivery Note Item`.`parent`
        WHERE (`tabDelivery Note Item`.`against_sales_order` = '{sales_order}'
            AND `tabDelivery Note Item`.`docstatus` < 2)
            {web_order_id_condition};
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
    Finds sales orders with multiple delivery notes that are not canceled.
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
    if not frappe.db.exists("Customer", distributor):
        frappe.log_error("The provided distributor '{0}' does not exist. Processing customer '{1}'.".format(distributor,customer),"utils.add_distributor")
        return
    
    customer = frappe.get_doc("Customer", customer)

    updated = False
    for d in customer.distributors:
        if d.product_type == product_type:
            print("Customer '{0}': Update distributor for '{1}': '{2}' -> '{3}'".format(customer.name,product_type, d.distributor,  distributor))
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

    return


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


def add_easy_run_for_italy(customer_id):
    """
    Add Webshop service EasyRun to the Customer if its first shipping address is in Italy.

    bench execute microsynth.microsynth.utils.add_easy_run_for_italy --kwargs "{'customer_id': '20043'}"
    """
    shipping_address = get_first_shipping_address(customer_id)
    if shipping_address is None:
        frappe.log_error(f"Customer '{customer_id}' has no shipping address.", "utils.add_easy_run_for_italy")
        return

    country = frappe.get_value("Address", shipping_address, "Country")
    if country == "Italy":
        add_webshop_service(customer_id, 'EasyRun')


def get_child_territories(territory):
    """
    Returns all child territories for the given territory recursively. Includes the given parent directory and all nodes as well.
    bench execute microsynth.microsynth.utils.get_child_territories --kwargs "{'territory': 'Switzerland'}"
    """

    entries = frappe.db.sql("""select name, lft, rgt, {parent} as parent
            from `tab{tree}` order by lft"""
        .format(tree="Territory", parent="parent_territory"), as_dict=1)
    
    range = {}
    for d in entries:
        if d.name == territory:
            range['lft'] = d['lft']
            range['rgt'] = d['rgt']
    
    if 'lft' not in range or 'rgt' not in range:
        frappe.log_error("The provided territory does not exist:\n{0}".format(territory), "utils.get_all_child_territories")
        return []

    territories = []
    for d in entries:
        if range['lft'] <= d['lft'] and d['rgt'] <= range['rgt']:
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

    if not customer.default_currency:
        customer.default_currency = default_currencies[customer.default_company]

    address = get_billing_address(customer.name)

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
    a = get_billing_address(customer)

    if a.country == "Switzerland":
        try:
            if int(a.pincode) < 3000:
                l = "fr"
            else:
                l = "de"
        except Exception as err:
            frappe.log_error("Billing address '{0}' of customer '{1}' has an invalid pincode".format(a.name, customer), "utils.set_default_language")
            l = "de"
    elif a.country in ("Germany", "Austria"):
        l = "de"
    elif a.country == "France":
        l = "fr"
    else:
        l = "en"

    customer = frappe.get_doc("Customer", customer)
    
    if customer.language is None:
        customer.language = l
        customer.save()
        # frappe.db.commit()

    return


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
    add_easy_run_for_italy(customer)


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
            pc_prefix = int(numeric_postal_code[:2])
            if pc_prefix == 69:
                return frappe.get_doc("Territory", "Lyon")
            elif pc_prefix == 75 or pc_prefix == 77 or pc_prefix == 78 or 91 <= pc_prefix <= 95:
                return frappe.get_doc("Territory", "Paris")
            else:
                return frappe.get_doc("Territory", "France (without Paris and Lyon)")
        
        elif address.country == "Réunion" or address.country == "French Guiana":
            return frappe.get_doc("Territory", "France (without Paris and Lyon)")
        
        elif address.country == "Liechtenstein":
            return frappe.get_doc("Territory", "Switzerland (German-speaking)")
        
        elif address.country == "Poland":
            return frappe.get_doc("Territory", "Rest of Europe (PL)")
        
        elif address.country in ("Åland Islands", "Andorra", "Belgium", "Denmark", "Faroe Islands", "Finland", "Gibraltar", "Greenland", "Guernsey",
                                 "Iceland", "Ireland", "Isle of Man", "Italy", "Jersey", "Luxembourg", "Monaco", "Netherlands",
                                 "Norway", "Portugal", "San Marino", "Spain", "Sweden", "United Kingdom"):
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
        frappe.log_error(f"Could not determine territory from address '{address_id}'\n{err}", "utils.determine_territory")
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
    bench execute microsynth.microsynth.utils.configure_territory --kwargs "{'customer_id': '832739'}"
    """
    customer = frappe.get_doc("Customer", customer_id)
    if customer.territory == 'All Territories' or customer.territory == '' or customer.territory is None:
        shipping_address = get_first_shipping_address(customer_id)
        if shipping_address is None:
            subject = f"Customer '{customer_id}' has no Shipping Address. Can't configure Territory."
            frappe.log_error(subject, "utils.configure_territory")
            message = f"Dear Administration,<br><br>this is an automatic email to inform you that Customer '{customer_id}' has no Shipping Address. " \
                f"Therefore the ERP is unable to determine the Territory of this Customer.<br>" \
                f"Please add a shipping address, Territory and Sales Manager.<br><br>Best regards,<br>Jens"
            make(
                recipients = "info@microsynth.ch",
                sender = "jens.petermann@microsynth.ch",
                subject = "[ERP] " + subject,
                content = message,
                send_email = True
                )
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


def configure_sales_manager(customer_id):
    """
    Update a customer given by its ID with a sales manager if it is not yet set (default).

    run
    bench execute microsynth.microsynth.utils.configure_sales_manager --kwargs "{'customer_id': '832739'}"
    """
    customer = frappe.get_doc("Customer", customer_id)

    if customer.account_manager is None or customer.account_manager == '' or customer.account_manager == 'null':
        shipping_address = get_first_shipping_address(customer_id)
        if shipping_address is None:
            country = None
        else:
            country = frappe.get_value("Address", shipping_address, "Country")

        if country == "Italy":
            customer.account_manager = "servizioclienticer@dgroup.it"
        elif country == "Slovakia":
            if frappe.get_value("Address", shipping_address, "City") in ["Kocice", "Kosice", "Košice", "KOSICE"]:
                # according to an email of Elges from Mi 06.09.2023 16:23
                customer.account_manager = "ktrade@ktrade.sk"
        else:
            customer.account_manager = frappe.get_value("Territory", customer.territory, "sales_manager")
        # TODO: Logic to set Account manager rupert.hagg_agent@microsynth.ch
        customer.save()
        #print(f"Customer '{customer_id}' got assigned Sales Manager {customer.account_manager}.")


def set_default_distributor(customer_id):
    """
    Set the distributors if the Customer has none and its first shipping address is in Italy or Hungary.

    run
    bench execute microsynth.microsynth.utils.set_default_distributor --kwargs "{'customer_id': '35277857'}"
    bench execute microsynth.microsynth.utils.set_default_distributor --kwargs "{'customer_id': '35280995'}"
    """
    # customer = frappe.get_doc("Customer", customer_id)
    # distributors =  frappe.get_value("Customer", customer_id, "distributors")
    # if len(customer.distributors) > 0:
    #     return

    shipping_address = get_first_shipping_address(customer_id)
    if shipping_address is None:
        frappe.log_error(f"Can't set distributor for customer {customer_id} due to the lack of a shipping address.", "utils.set_default_distributor")
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


def check_default_companies():
    """
    run
    bench execute microsynth.microsynth.utils.check_default_companies
    """
    countries = [ "Austria", "Croatia", "Hungary", "Slovakia", "Slovenia", "Kosovo" ]
    for c in countries:
        print(c)
        set_customer_default_company_for_country(c)


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
                'debit': round(amount * current_exchange_rate, 2),
                'exchange_rate': current_exchange_rate
            }
        ]
    })

    # extend invoices
    base_total_debit = flt(amount) * current_exchange_rate
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
            'credit': round((invoice.get('outstanding_amount') or 0) * (exchange_rate or 1), 2)
        })
        base_total_credit += (invoice.get('outstanding_amount') or 0) * (exchange_rate or 1)

    # other currencies: currency deviation
    jv.set_total_debit_credit()
    currency_deviation = rounded(jv.total_debit - jv.total_credit, 2)
    if currency_deviation != 0:
        jv.append('accounts', {
            'account': currency_deviation_account,
            'credit': currency_deviation,
            'account_currency': frappe.get_cached_value("Account", currency_deviation_account, "account_currency")
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
        'doctype': 'Communication',
        'comment_type': "Comment",
        'subject': sales_invoice,
        'content': comment,
        'reference_doctype': "Sales Invoice",
        'status': "Linked",
        'reference_name': sales_invoice
    })
    new_comment.insert()
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
            print(f"Unable to validate Tax ID '{tax_id}'.")
            return False
    return valid


def check_tax_id(tax_id, customer_id, customer_name):
    """
    Takes a Tax ID with its Customer ID and Customer name and
    sends an email to the administration if the given Tax ID can be classified as invalid.
    It is NOT checked if the Tax ID belongs to the given Customer name.
    """
    if not tax_id:
        return
    if tax_id[:2] in ['CH', 'GB', 'IS', 'NO', 'TR'] and not 'NOT' in tax_id:
        # unable to check Tax ID from Great Britain, Iceland, Norway or Turkey
        return
    if not is_valid_tax_id(tax_id):
        subject = f"[ERP] Invalid Tax ID '{tax_id}'"
        message = f"Dear Administration,<br><br>this is an automatic email to inform you that the Tax ID '{tax_id}' " \
                    f"of Customer '{customer_id}' ('{customer_name}') seems to be invalid.<br>" \
                    f"Please check the Tax ID and correct it if necessary.<br><br>Best regards,<br>Jens"
        make(
            recipients = "info@microsynth.ch",
            sender = "jens.petermann@microsynth.ch",
            subject = subject,
            content = message,
            send_email = True
            )


def check_new_customers_taxid(delta_days=7):
    """
    Check the Tax ID of all new Customers and send one email
    to the administration if there are invalid Tax IDs.
    Should be run daily by a Cronjob.

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
        shipping_address = get_first_shipping_address(nc['name'])
        if shipping_address is None:
            frappe.log_error(f"Customer '{nc['name']}' has no shipping address.", "utils.check_new_customers_taxid")
            continue
        country = frappe.get_value("Address", shipping_address, "Country")
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
        subject = f"[ERP] Invalid Tax IDs of new Customers"
        message = f"Dear Administration,<br><br>this is an automatic email to inform you that the following " \
                  f"new Customers that are created in the last {delta_days} days seem to have invalid Tax IDs:<br><br>"

        for iti in invalid_tax_ids:
            message += f"Customer {iti['customer_id']} ({iti['customer_name']}): Tax ID '{iti['tax_id']}'<br>"
        
        message += f"<br>Please check the Tax IDs and correct them if necessary.<br><br>Best regards,<br>Jens"
        make(
            recipients = "info@microsynth.ch",
            sender = "jens.petermann@microsynth.ch",
            subject = subject,
            content = message,
            send_email = True
            )
        #print(message.replace('<br>','\n'))


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

    for i, ext_debitor_number in enumerate(ext_debitor_numbers):
        #print(i)
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


def complement_ext_debitor_nr():
    """
    Try to find unique External Debitor Numbers for Customers with default Company
    Microsynth Seqlab GmbH or Microsynth Austria GmbH from Customers with the same Tax ID.
    Should be run by a daily cron job.

    bench execute microsynth.microsynth.utils.complement_ext_debitor_nr
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
    counter = chaos_counter = 0
    print(f"Found {len(customers)} enabled Customers with missing ext_debitor_number and "
          f"Default Company Microsynth Seqlab GmbH or Microsynth Austria GmbH.\n")
    for customer in customers:
        same_tax_id = frappe.db.get_all("Customer",
                                filters=[['ext_debitor_number', '!=', 'NULL'],  # seems not to work
                                         ['tax_id', '=', customer['tax_id']],
                                         ['disabled', '=', '0']],
                                fields=['name', 'customer_name', 'ext_debitor_number'])
        if len(same_tax_id) == 0:
            continue
        first_ext_debitor_nr = None
        for c in same_tax_id:
            if c['ext_debitor_number']:
                first_ext_debitor_nr = c['ext_debitor_number']
        if not first_ext_debitor_nr:
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
            print(f"Going to set External Debitor Number of Customer '{customer['name']}' ('{customer['customer_name']}') to '{first_ext_debitor_nr}' "
                f"from Customer '{same_tax_id[0]['name']}' ('{same_tax_id[0]['customer_name']}') with the same Tax ID '{customer['tax_id']}'.")
            # Set External Debitor Number of customer['name'] to first_ext_debitor_nr
            customer_doc = frappe.get_doc("Customer", customer['name'])
            customer_doc.ext_debitor_number = first_ext_debitor_nr
            customer_doc.save()
            counter += 1
    print(f"\nSet the External Debitor Number of {counter} Customers.")
    print(f"\nThe External Debitor Number of {chaos_counter} Customers was not set, because there are different External Debitor Numbers for the same Tax ID.")
    print(f"\nThere are {len(same_tax_id_diff_ext_dnr)} Tax IDs where the Customers have different External Debitor Numbers:")
    for tax_id, entry in same_tax_id_diff_ext_dnr.items():
        if not tax_id:
            continue
        print(f"\nTax ID '{tax_id}':")
        for cust in entry:
            if cust['ext_debitor_number']:
                print(f"External Debitor Number '{cust['ext_debitor_number']}' for Customer '{cust['name']}' ('{cust['customer_name']}')")


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
    
    message = f"Dear Denise,<br><br>the following new Sales Order(s) with Product Type Oligos or Material "\
              f"has/have a Shipping Address in the EU, but the Customer has no Tax ID in the ERP:<br><br>"
        
    for so in sales_orders:
        message += f"{so['sales_order']} from {so['transaction_date']} with Shipping Address in {so['country']}: Customer {so['customer']} ('{so['customer_name']}')<br>"

    message += f"<br>Please try to add the Tax ID to the Customer before the Sales Invoice is created.<br><br>Best regards,<br>Jens"
    make(
        recipients = "d.schmidheini@microsynth.ch",
        sender = "jens.petermann@microsynth.ch",
        subject = "[ERP] New Sales Order(s) from Customer(s) with missing Tax ID",
        content = message,
        send_email = True
        )
    #print(message.replace('<br>', '\n'))


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


@frappe.whitelist()
def overwrite_item_defaults(item):
    """
    Overwrite item.item_defaults with item_group_defaults from Item Group.

    bench execute microsynth.microsynth.utils.overwrite_item_defaults --kwargs "{'item': '3100'}"
    """
    item = frappe.get_doc("Item", item)
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
    item.save()


@frappe.whitelist()
def force_cancel(dt, dn):
    """
    This function allows to move a document from draft directly to cancelled
    
    Parameters:
        dt		Doctype Name, e.g. "Quotation"
        dn		Record Name, e.g. "QTN-01234"
        
    It will only work from docstatus 0/Draft, because valid documents might need actions on cancel (GL Entry, ...)
    """
    try:
        frappe.db.sql("""
            UPDATE `tab{dt}`
            SET 
                `docstatus` = 2,
                `status` = "Cancelled"
            WHERE
                `name` = "{dn}"
                AND `docstatus` = 0;
        """.format(dt=dt, dn=dn))
        frappe.db.commit()
    except Exception as err:
        frappe.log_error(err, "Force cancel failed on {dt}:{dn}".format(dt=dt, dn=dn) )
    else:
        new_comment = frappe.get_doc({
            'doctype': 'Communication',
            'comment_type': "Comment",
            'subject': dn,
            'content': f'Force cancelled by {frappe.get_user().name}',
            'reference_doctype': dt,
            'status': "Linked",
            'reference_name': dn
        })
        new_comment.insert()


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


@frappe.whitelist()
def get_potential_contact_duplicates(contact_id):
    """
    bench execute microsynth.microsynth.utils.get_potential_contact_duplicates --kwargs "{'contact_id': '215856'}"
    """
    contact = frappe.get_doc("Contact", contact_id)
    address = frappe.get_doc("Address", contact.address)
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
            AND `tabAddress`.`address_type` = '{address.address_type}'
            AND `tabContact`.`name` != '{contact.name}'
        """, as_dict=True)
    return contacts


def set_module_for_one_user(module, user):
    """
    bench execute microsynth.microsynth.utils.set_module_for_one_user --kwargs "{'module': 'QMS', 'user': 'firstname.lastname@microsynth.ch'}"
    """
    home_settings = frappe.cache().hget('home_settings', user)
    inserted = False
    if not home_settings:
        print(f"Found no home_settings for user '{user}'. Going to take those from the Administrator.")
        home_settings = frappe.cache().hget('home_settings', 'Administrator')
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