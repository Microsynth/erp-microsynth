# -*- coding: utf-8 -*-
# Copyright (c) 2022, libracore (https://www.libracore.com) and contributors
# For license information, please see license.txt

import os
import frappe
import json
from datetime import datetime


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
        frappe.log_error("Contact '{0}' is not linked to a Customer".format(contact))

    return customer_id


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
    if 'substance_type' in oligo:
        oligo_doc.substance_type = oligo['substance_type']
    if 'sequence' in oligo:
        oligo_doc.sequence = oligo['sequence']
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


@frappe.whitelist()
def find_tax_template(company, customer, customer_address, category):
    """
    Find the corresponding tax template
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
            return None
    else:
        country = frappe.get_value("Address", customer_address, "country")
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
            return None


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


@frappe.whitelist()
def set_order_label_printed(sales_orders):
    if type(sales_orders) == str:
        sales_orders = json.loads(sales_orders)
    
    for o in sales_orders:
        if frappe.db.exists("Sales Order", o):
            sales_order = frappe.get_doc("Sales Order", o)
            sales_order.label_printed_on = datetime.now()
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
        frappe.log_error("No preferred express item found for country '{0}'".format(country_name))
        None
    if len(express_items) > 0:
        
        if len(express_items) > 1:
            frappe.log_error("Multiple preferred express shipping items found for country '{0}'".format(country_name))
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
            frappe.log_error("Multiple preferred express shipping items found for customer '{0}'".format(customer_name))
        return express_items[0]


def get_express_shipping_item(customer_name, country_name):
    """
    Return the preferred express shipping item for the given customer ID and country name. 
    
    The shipping items of the customer override those of the country.
    
    If the customer does not have a preferred express item, the preferred express item of the
    country is returned.
    """

    customer_express_item = get_customer_express_shipping_item(customer_name)
    if customer_express_item:
        return customer_express_item
    else:
        country_express_item = get_country_express_shipping_item(country_name)
        return country_express_item


def get_export_category(address_name):
    country = frappe.get_value('Address', address_name, 'country')
    if country == "Austria":
        export_category = "AT"
    else:
        export_category = frappe.get_value('Country', country, 'export_code')
    return export_category


def get_physical_path(file_name):
    file_url = frappe.get_value("File", file_name, "file_url")     # something like /private/files/myfile.pdf
    base_path = os.path.join(frappe.utils.get_bench_path(), "sites", frappe.utils.get_site_path()[2:])

    return "{0}{1}".format(base_path, file_url)


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
                frappe.log_error("Sales Order '{0}' has delivery notes in submitted and draft mode".format(sales_order_id), "Migration.clean_up_delivery_notes")
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
            frappe.log_error("Delivery Note '{0}' is not in draft status. Cannot delete it. Status: {1}".format(dn.name, dn.docstatus), "Migration.clean_up_delivery_notes")
    
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


def add_distributor(customer, distributor, product_type):
    """
    Add the specified distributor for the a product type to the customer.
    
    run
    bench execute "microsynth.microsynth.utils.add_distributor" --kwargs "{'customer':8003, 'distributor':35914214, 'product_type':'Oligos'}"
    """       
    # validate input
    if not frappe.db.exists("Customer", distributor):
        frappe.log_error("The provided distributor '{0}' does not exist. Processing customer '{1}'.".format(distributor,customer),"utils.add_distributor")
        return
    
    customer = frappe.get_doc("Customer", customer)

    # TODO: ensure that only 1 distributor is set for a product type

    print("Customer '{0}': Add distributor '{1}' for '{2}'".format(customer.name, distributor, product_type))
    # TODO: check if entry is already there!
    entry = {
        'distributor': distributor,
        'product_type': product_type
    }
    customer.append("distributors",entry)
    customer.save()
    frappe.db.commit()
    return


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
        if currency == "EUR":
            account = 1102
        elif currency == "USD":
            account = 1101
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

    # for account in customer.accounts:
    #     print("{0}\t{1}".format(account.company, account.account))

    def account_exists(company):
        for a in customer.accounts:
            if a.company == company:
                return True
        return False

    for company in companies:
        if not account_exists(company.name):
            account_number =  get_debtor_account(company.name, customer.default_currency, address.country)            
            account = get_account_by_number(company.name, account_number)

            print("{0}, {1}, {2} --> {3}".format(company.name, customer.default_currency, address.country, account))

            if account:
                entry = {
                    'company': company.name,
                    'account': account
                }
                # print(entry)
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
            frappe.log_error("Billing address '{0}' of customer '{1}' has an invalid pincode".format(a.name, customer), "set_default_language")
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