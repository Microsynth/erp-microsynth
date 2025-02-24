# -*- coding: utf-8 -*-
# Copyright (c) 2024, Microsynth
# For license information, please see license.txt
# For more details, refer to https://github.com/Microsynth/erp-microsynth/

import frappe
from frappe import _
from frappe.desk.form.assign_to import add, clear
from frappe.core.doctype.communication.email import make
from frappe.utils.password import get_decrypted_password
from frappe.core.doctype.user.user import test_password_strength
from microsynth.microsynth.utils import user_has_role
import json
import csv
import re


def create_pi_from_si(sales_invoice):
    """
    Create a purchase invoice for an internal company from a sales invoice

    bench execute microsynth.microsynth.purchasing.create_pi_from_si  --kwargs "{'sales_invoice': 'SI-BAL-24017171'}"
    """
    from microsynth.microsynth.taxes import find_dated_tax_template
    si = frappe.get_doc("Sales Invoice", sales_invoice)
    # create matching purchase invoice
    pi_company = si.customer_name
    suppliers = frappe.get_all("Supplier", filters={'supplier_name': si.company}, fields=['name'])
    if suppliers and len(suppliers) == 1:
        if len(suppliers) > 1:
            frappe.log_error(f"Found {len(suppliers)} Supplier for Company {si.company} on Sales Invoice {si.name}. Going to take the first one.", "purchasing.create_pi_from_si")
        pi_supplier = suppliers[0]['name']
    else:
        frappe.log_error(f"Found no Supplier for Company {si.company} on Sales Invoice {si.name}. Going to return.", "purchasing.create_pi_from_si")
        return None
    pi_cost_center = frappe.get_value("Company", pi_company, "cost_center")
    # find dated tax template
    if si.product_type == "Oligos" or si.product_type == "Material":
        category = "Material"
    else:
        category = "Service"
    if si.oligos is not None and len(si.oligos) > 0:
        category = "Material"
    pi_tax_template = find_dated_tax_template(pi_company, pi_supplier, si.shipping_address_name, category, si.posting_date)  # TODO: Check carefully
    # create new purchase invoice
    new_pi = frappe.get_doc({
        'doctype': 'Purchase Invoice',
        'company': pi_company,
        'supplier': pi_supplier,
        'bill_no': si.name,
        'bill_date': si.posting_date,
        'due_date': si.due_date,
        'project': si.project,
        'cost_center': pi_cost_center,
        #'taxes_and_charges': pi_tax_template,  # TODO
        'disable_rounded_total': 1
    })
    # add item positions
    for i in si.items:
        new_pi.append('items', {
            'item_code': i.item_code,
            'qty': i.qty,
            'description': i.description,
            'rate': i.rate,
            'cost_center': pi_cost_center
        })
    # apply taxes
    # if pi_tax_template:
    #     pi_tax_details = frappe.get_doc("Purchase Taxes and Charges Template", pi_tax_template)
    #     for t in pi_tax_details.taxes:
    #         new_pi.append('taxes', {
    #             'charge_type': t.charge_type,
    #             'account_head': t.account_head,
    #             'description': t.description,
    #             'rate': t.rate
    #         })
    # insert
    new_pi.insert()
    new_pi.submit()
    return new_pi.name


def fetch_assignee(dt, dn):
    assignees = frappe.db.sql(f"""SELECT `owner`
        FROM `tabToDo`
        WHERE `reference_type`= '{dt}'
            AND `reference_name`= '{dn}'
            AND `status`='Open'
        ;""", as_dict=True)
    if len(assignees) > 0:
        return assignees[0]['owner']
    return None


def is_already_assigned(dt, dn):
    if fetch_assignee(dt, dn):
        return True
    else:
        return False


@frappe.whitelist()
def create_approval_request(assign_to, dt, dn):
    if not is_already_assigned(dt, dn):
        if assign_to == frappe.session.user and not user_has_role(frappe.session.user, "Accounts Manager"):
            frappe.throw(f"You are not allowed to assign the {dt} {dn} to yourself. Please choose another Approver.")
        # create an Assignment without an Email
        add({
            'doctype': dt,
            'name': dn,
            'assign_to': assign_to,
            'description': f'Please check the {dt} {dn} in the <a href="https://erp.microsynth.local/desk#approval-manager">Approval Manager</a>.',
            'notify': False  # Send email
        })
        # create an Email without a direct link to the Document itself
        make(
            recipients = assign_to,
            sender = frappe.session.user,
            subject = f"Approval Request for {dt} {dn}",
            content = f'Please check the {dt} {dn} in the <a href="https://erp.microsynth.local/desk#approval-manager">Approval Manager</a> and approve or reject it.',
            send_email = True
        )
        if dt == "Purchase Invoice":
            purchase_invoice = frappe.get_doc(dt, dn)
            purchase_invoice.approver = assign_to
            purchase_invoice.in_approval = 1
            purchase_invoice.save()
        return True
    else:
        return False


@frappe.whitelist()
def reassign_purchase_invoice(assign_to, dt, dn):
    if not is_already_assigned(dt, dn):
        frappe.throw(f"{dt} {dn} is not already assigned. Unable to reassign.")
        return False
    assignee = fetch_assignee(dt, dn)
    approver = frappe.get_value(dt, dn, "approver")
    if assignee != approver:
        frappe.throw(f"{dt} {dn} has Approver '{approver}', but is assigned to '{assignee}'. Unable to reassign.")
        return False
    # clear assignment
    clear(dt, dn)
    # create new assignment and notify new Approver
    if create_approval_request(assign_to, dt, dn):
        # notify original Approver about reassignment
        make(
                recipients = approver,
                sender = frappe.session.user,
                subject = f"{dt} {dn} was reassigned",
                content = f"{dt} {dn} was originally assigned to you, but {frappe.session.user} reassigned it to {assign_to}.",
                send_email = True
            )
        return True
    return False


def reset_in_approval(purchase_invoice, event):
    if type(purchase_invoice) == str:
        purchase_invoice = frappe.get_doc("Purchase Invoice", purchase_invoice)
    purchase_invoice.in_approval = 0
    purchase_invoice.save()


def assign_purchase_invoices():
    """
    Get all Draft Purchase Invoices with an approver.
    Assign those that are not yet assigned to the specified approver.

    Should be executed daily by a cronjob.

    bench execute microsynth.microsynth.purchasing.assign_purchase_invoices
    """
    sql_query = """
        SELECT `tabPurchase Invoice`.`name`,
            `tabPurchase Invoice`.`approver`
        FROM `tabPurchase Invoice`
        WHERE `tabPurchase Invoice`.`docstatus` = 0
            AND `tabPurchase Invoice`.`approver` IS NOT NULL;
        """
    purchase_invoices = frappe.db.sql(sql_query, as_dict=True)
    for pi in purchase_invoices:
        assigned = create_approval_request(pi['approver'], "Purchase Invoice", pi['name'])
        if assigned:
            print(f"Assigned {pi['name']} to {pi['approver']}.")


def fetch_billing_address(supplier_id):
    """
    Returns the primary billing address of a supplier specified by its id.

    bench execute "microsynth.microsynth.purchasing.fetch_billing_address" --kwargs "{'supplier_id': 'S-00001'}"
    """
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
            `tabAddress`.`is_primary_address`
        FROM `tabDynamic Link`
        LEFT JOIN `tabAddress` ON `tabAddress`.`name` = `tabDynamic Link`.`parent`
        WHERE `tabDynamic Link`.`parenttype` = "Address"
            AND `tabDynamic Link`.`link_doctype` = "Supplier"
            AND `tabDynamic Link`.`link_name` = "{supplier_id}"
            AND (`tabAddress`.`is_primary_address` = 1)
        ;""", as_dict=True)

    if len(addresses) == 1:
        return addresses[0]
    else: 
        return None # frappe.throw(f"Found {len(addresses)} billing addresses for Supplier '{supplier_id}'", "fetch_billing_address")


def set_purchase_invoice_title(purchase_invoice, event):
    """
    Set the title of the given Purchase Invoice to the Supplier Name if present
    """
    if type(purchase_invoice) == str:
        purchase_invoice = frappe.get_doc("Purchase Invoice", purchase_invoice)
    if purchase_invoice.supplier_name and purchase_invoice.title != purchase_invoice.supplier_name:
        purchase_invoice.title = purchase_invoice.supplier_name
    # Do not save since function is called in before_save server hook


def set_default_payable_accounts(supplier, event):
    """
    Set the default payable accounts for the given supplier.

    bench execute microsynth.microsynth.purchasing.set_default_payable_accounts --kwargs "{'supplier': 'S-00001'}"
    """
    if type(supplier) == str:
        supplier = frappe.get_doc("Supplier", supplier)
    companies = frappe.get_all("Company", fields = ['name', 'default_currency'])

    for company in companies:
        #print(f"Processing {company['name']} ...")
        if company['name'] == "Microsynth Seqlab GmbH":
            account = "1600 - Verb. aus Lieferungen und Leistungen - GOE"
        elif company['name'] == "Microsynth France SAS":
            account = "4191000 - Clients acptes s/com - LYO"
        elif company['name'] == "Microsynth AG":
            if supplier.default_currency and supplier.default_currency == "EUR":
                account = "2005 - Kreditoren EUR - BAL"
            elif supplier.default_currency and supplier.default_currency == "USD":
                account = "2003 - Kreditoren USD - BAL"
            else:
                account = "2000 - Kreditoren - BAL"
        elif company['name'] == "Microsynth Austria GmbH":
            billing_address = fetch_billing_address(supplier.name)
            if not billing_address:
                continue
            country = billing_address['country']
            country_doc = frappe.get_doc("Country", country)
            if country_doc.name == "Austria":
                account = "3300 - Lieferverbindlichkeiten Inland - WIE"
            elif country_doc.eu:
                account = "3360 - Lieferverbindlichkeiten EU - WIE"
            else:
                account = "3370 - Lieferverbindlichkeiten sonstiges Ausland - WIE"
        else:
            continue
        if not frappe.db.exists("Account", account):
            msg = f"Account '{account}' does not exist. Please check if it was renamed."
            frappe.log_error(msg, "set_default_payable_accounts")
            frappe.throw(msg)
            continue
        entry_exists = False    
        for a in supplier.accounts:
            if a.company == company['name']:
                # update
                a.account = account
                entry_exists = True
                break
        if not entry_exists:
            # create new account entry
            entry = {
                'company': company['name'],
                'account': account
                # set_default_payable_accounts should not set the default_tax_template.
                # An algorithm cannot be defined to set the default value. (requires classification of the supplier)
            }
            supplier.append("accounts", entry)
            #print(f"appended {entry=}")
    # Do not save since function is called in before_save server hook    


def set_and_save_default_payable_accounts(supplier):
    if type(supplier) == str:
        supplier = frappe.get_doc("Supplier", supplier)
    supplier.save()
    #frappe.db.commit()


def remove_control_characters(input_string):
    """
    Removes all control characters (ASCII 0-31 and 127-159) and returns the cleaned string.
    """
    return re.sub(r'[\x00-\x1F\x7F-\x9F]', '', input_string)


def import_supplier_items(input_filepath, output_filepath, supplier_mapping_file, company='Microsynth AG', expected_line_length=28):
    """
    bench execute microsynth.microsynth.purchasing.import_supplier_items --kwargs "{'input_filepath': '/mnt/erp_share/JPe/2025-02-24_Lieferantenartikel.csv', 'output_filepath': '/mnt/erp_share/JPe/2025-02-24_supplier_item_mapping.txt', 'supplier_mapping_file': '/mnt/erp_share/JPe/2025-02-24_supplier_mapping.txt'}"
    """
    supplier_mapping = {}
    with open(supplier_mapping_file) as sm_file:
        print(f"INFO: Parsing Supplier Mapping from '{supplier_mapping_file}' ...")
        csv_reader = csv.reader((l.replace('\0', '') for l in sm_file), delimiter=";")  # replace NULL bytes (throwing an error)
        for line in csv_reader:
            if len(line) != 2:
                print(f"ERROR: Line '{line}' has length {len(line)}, but expected length 2. Going to continue.")
                continue
            supplier_id = line[0]
            index = line[1]
            if index in supplier_mapping:
                print(f"ERROR: Supplier Index {index} was already mapped to {supplier_mapping[index]} but should now be mapped to {supplier_id}. Going to continue.")
            supplier_mapping[index] = supplier_id
    total_counter = 0
    imported_counter = 0
    with open(input_filepath) as file:
        print(f"INFO: Parsing Supplier Items from '{input_filepath}' ...")
        csv_reader = csv.reader((l.replace('\0', '') for l in file), delimiter=";")  # replace NULL bytes (throwing an error)
        next(csv_reader)  # skip header
        for line in csv_reader:
            if len(line) != expected_line_length:
                print(f"ERROR: Line '{line}' has length {len(line)}, but expected length {expected_line_length}. Going to continue.")
                continue
            total_counter += 1
            # parse values
            supplier_index = line[0].strip()  # remove leading and trailing whitespaces
            auftraggeber = line[1].strip()
            lk = line[2].strip()
            internal_code = line[3].strip()  # if given, Item should have "Maintain Stock"
            supplier_item_id = line[4].strip()
            item_name = remove_control_characters(line[5].strip().replace('\n', ' ').replace('  ', ' '))  # replace newlines and double spaces
            unit_size = line[6].strip()
            currency = line[7].strip()
            supplier_quote = line[8].strip()
            list_price = line[9].strip()
            purchase_price = line[10].strip()
            customer_discount = line[11].strip()
            content_quantity = line[12].strip()
            item_group = line[13].strip()
            group = line[14].strip()
            account = line[15].strip()
            storage_localtion = line[16].strip()  # warehouse
            annual_consumption_budget = line[17].strip()
            order_quantity_6mt = line[18].strip()
            threshold = line[19].strip()
            shelf_life  = line[20].strip()  # Haltbarkeit
            process_critical = line[21].strip()
            quality_control = line[22].strip()
            quality_list = line[23].strip()
            subgroup = line[24].strip()
            time_limit = line[25].strip()
            quantity_supplier = line[26].strip()
            item_id = line[27].strip()  # Datensatznummer

            if not item_name:
                print(f"ERROR: Item with Index {item_id} has no Item name. Going to continue with the next supplier item.")
                continue
            if not item_id:
                print(f"ERROR: Item '{item_name}' has no Index (Datensatznummer). Going to continue with the next supplier item.")
                continue
            if not supplier_index:
                print(f"ERROR: Item with Index {item_id} ('{item_name}') has no Supplier Index. Going to continue with the next supplier item.")
                continue
            if account:
                accounts = frappe.get_all("Account", filters={'account_number': account, 'company': company}, fields=['name'])
                if len(accounts) != 1:
                    print(f"ERROR: There are {len(accounts)} Accounts with Account Number '{account}' for Company {company}: {','.join(a['name'] for a in accounts)}. Unable to import Item '{item_name}' with Index {item_id}. Going to continue with the next supplier item.")
                    continue
                else:
                    account_name = accounts[0]['name']  # TODO: Should this be the Default Expense Account in the Item Defaults table on the Item?
            else:
                print(f"ERROR: No account number given for Item with Index {item_id} ('{item_name}'). Going to continue with the next supplier item.")
                continue

            if currency == "£":
                currency = "GBP"

            if len(item_name) > 140:
                print(f"WARNING: Item name '{item_name}' has {len(item_name)} characters. Going to shorten it to 140 characters.")
            
            item_code = f"P{int(item_id):0{5}d}"

            item = frappe.get_doc({
                'doctype': "Item",
                'item_code': item_code,
                'item_name': item_name[:140],
                'item_group': 'Purchasing',
                'stock_uom': 'Pcs',
                'is_stock_item': 1 if internal_code else 0,
                'description': item_name,
                'is_purchase_item': 1,
                'is_sales_item': 0
            })
            item.insert()
            imported_counter += 1

            # write mapping of ERP Item ID to FM Index (Datensatznummer) to a file
            with open(output_filepath, 'a') as txt_file:
                txt_file.write(f"{item.name};{item_id}\n")

            if not supplier_index in supplier_mapping:
                print(f"WARNING: Found no Supplier with Index {supplier_index}. Unable to link a Supplier on Item with Index {item_id} ({item.item_name}). Going to continue.")
                continue
            item.append("supplier_items", {
                'supplier': supplier_mapping[supplier_index],
                'supplier_part_no': supplier_item_id,
                'substitute_status': ''
            })
            #if account:
                # item.append("item_defaults", {
                #     'company': company,
                #     'expense_account': account_name,
                #     'default_supplier': supplier_mapping[supplier_index]
                # })  # TODO: Error: "Cannot set multiple Item Defaults for a company."
            item.save()
            print(f"INFO: Successfully imported Item '{item.item_name}' ({item.name}).")
            if imported_counter % 1000 == 0:
                frappe.db.commit()
        print(f"INFO: Successfully imported {imported_counter}/{total_counter} Items.")


def import_suppliers(input_filepath, output_filepath, our_company='Microsynth AG', expected_line_length=41, update_countries=False, add_ext_creditor_id=False):
    """
    bench execute microsynth.microsynth.purchasing.import_suppliers --kwargs "{'input_filepath': '/mnt/erp_share/JPe/2025-02-17_Lieferanten_Microsynth_AG.csv', 'output_filepath': '/mnt/erp_share/JPe/2025-02-24_supplier_mapping.txt'}"
    """
    country_code_mapping = {'UK': 'United Kingdom'}
    payment_terms_mapping = {
        '10': '10 days net',
        '20': '20 days net',
        '30': '30 days net'
    }
    total_counter = 0
    imported_counter = 0
    with open(input_filepath) as file:
        print(f"INFO: Parsing Suppliers from '{input_filepath}' ...")
        csv_reader = csv.reader((l.replace('\0', '') for l in file), delimiter=";")  # replace NULL bytes (throwing an error)
        next(csv_reader)  # skip header
        for line in csv_reader:
            if len(line) != expected_line_length:
                print(f"ERROR: Line '{line}' has length {len(line)}, but expected length {expected_line_length}. Going to continue.")
                continue
            total_counter += 1
            # parse values
            ext_customer_id = line[0].strip()  # remove leading and trailing whitespaces
            salutation = line[1].strip()
            first_name = line[2].strip()
            last_name = line[3].strip()
            company = line[4].strip()
            company_addition = line[5].strip()
            post_box = line[6].strip()
            address_line1 = line[7].strip()
            country_code = line[8].strip().upper()
            pincode = line[9].strip()
            city = line[10].strip()
            phone = line[11].strip() + line[12].strip()
            email = line[13].strip()
            web_url = line[14].strip()
            web_username = line[15].strip()
            web_pwd = line[16].strip()
            supplier_tax_id = line[17].strip()
            skonto = line[18].strip()  # will be imported manually
            payment_days = str(line[19].strip())
            currency = line[20].strip()
            reliability = line[21].strip()  # import later
            phone_note = line[22].strip()
            notes = line[23].strip()
            bic = line[24].strip()
            iban = line[25].strip()
            bank_name = line[26].strip()  # do not import
            contact_person_1 = line[27].strip()
            email_1 = line[28].strip()
            notes_1 = line[29].strip()
            contact_person_2 = line[30].strip()
            email_2 = line[31].strip()
            notes_2 = line[32].strip()
            contact_person_3 = line[33].strip()
            email_3 = line[34].strip()
            notes_3 = line[35].strip()
            discount = line[36].strip()
            threshold = line[37].strip()
            small_qty_surcharge = line[38].strip()
            transportation_costs = line[39].strip()
            ext_creditor_number = line[40].strip()
            #print(f"INFO: Processing Supplier with Index {ext_creditor_number} (external creditor number) ...")

            # combine/edit some values
            if company_addition and company:
                company = f"{company} - {company_addition}"
            elif company_addition:
                company = company_addition
            company = company.replace('\n', ' ').replace('\r', '')
            details = ""
            if phone_note:
                details += f"Phone Note: {phone_note}\n"
            if notes:
                details += f"Notes: {notes}"
            if discount:
                details += f"\nKundenrabatt: {discount}"
            if threshold:
                details += f"\nKleinmengenzuschlag bis Bestellwert {threshold}"
            if small_qty_surcharge:
                details += f"\nKleinmengenzuschlag (Betrag): {small_qty_surcharge}"
            if transportation_costs:
                details += f"\nTransportkosten: {transportation_costs}"
            if post_box and not "Postfach" in post_box:
                post_box = f"Postfach {post_box}"
            if currency == '£':
                currency = 'GBP'
            
            # check some values
            if salutation and salutation not in ('Frau', 'Herr', 'Ms.', 'Mr.', 'Mme', 'M.'):
                #print(f"WARNING: Salutation '{salutation}' is not in the list of allowed salutations ('Frau', 'Herr', 'Ms.', 'Mr.', 'Mme', 'M.'), going to ignore salutation of {ext_creditor_number}.")
                salutation = None
            if country_code not in country_code_mapping:
                countries = frappe.get_all("Country", filters={'code': country_code}, fields=['name'])
                if len(countries) == 0:
                    print(f"ERROR: Unknown country code '{country_code}', going to skip {ext_creditor_number}.")
                    continue
                elif len(countries) > 1:
                    print(f"ERROR: Found the following {len(countries)} Countries for country code '{country_code}' in the ERP, going to skip {ext_creditor_number}: {countries}")
                    continue
                else:
                    country = countries[0]['name']
                    country_code_mapping[country_code] = country
            if payment_days not in payment_terms_mapping:
                print(f"ERROR: There exists no Payment Terms Template for '{payment_days}', going to skip {ext_creditor_number}.")
                continue
            if len(address_line1) > 140:
                print(f"ERROR: Column 'Strasse' has {len(address_line1)} > 140 characters, going to skip {ext_creditor_number}.")
                continue
            if not company:
                print(f"ERROR: Column 'Firma' is mandatory, going to skip {ext_creditor_number}.")
                continue
            #company = f"{company} 2"  # Only for testing
            existing_suppliers = frappe.get_all("Supplier", filters=[['supplier_name', '=', company]], fields=['name', 'ext_creditor_id'])
            if existing_suppliers and (not (update_countries or add_ext_creditor_id)) and len(existing_suppliers) > 0:
                print(f"ERROR: There exists already {len(existing_suppliers)} Supplier with the Supplier Name '{company}' and it has the External Creditor ID {','.join((s['ext_creditor_id'] or 'None') for s in existing_suppliers)}. Going to skip {ext_creditor_number}.")
                continue

            if add_ext_creditor_id:
                suppliers = frappe.get_all("Supplier", filters=[['supplier_name', '=', company]], fields=['name'])
                if len(suppliers) != 1:
                    print(f"ERROR: Found {len(suppliers)} Suppliers with Supplier Name '{company}', going to skip {ext_creditor_number}.")
                    continue
                supplier_doc = frappe.get_doc("Supplier", suppliers[0]['name'])
                if supplier_doc.ext_creditor_id and supplier_doc.ext_creditor_id != ext_creditor_number:
                    print(f"ERROR: Supplier {supplier_doc.name} has External Creditor ID {supplier_doc.ext_creditor_id}, but should now be {ext_creditor_number}. Going to skip.")
                    continue
                elif supplier_doc.ext_creditor_id and supplier_doc.ext_creditor_id == ext_creditor_number:
                    print(f"ERROR: Supplier {supplier_doc.name} already has External Creditor ID {supplier_doc.ext_creditor_id}. Going to skip.")
                    continue
                supplier_doc.ext_creditor_id = ext_creditor_number
                supplier_doc.save()
                print(f"INFO: Supplier {supplier_doc.name}: Added External Creditor ID {ext_creditor_number}.")
                continue

            if update_countries:
                suppliers = frappe.get_all("Supplier", filters=[['supplier_name', '=', company]], fields=['name'])
                if len(suppliers) != 1:
                    print(f"ERROR: Found {len(suppliers)} with Supplier Name '{company}', going to skip {ext_creditor_number}.")
                    continue
                supplier_doc = frappe.get_doc("Supplier", suppliers[0]['name'])
                old_country = supplier_doc.country
                supplier_doc.country = country_code_mapping[country_code]
                supplier_doc.save()
                print(f"INFO: Supplier {supplier_doc.name} (Index {ext_creditor_number}): Changed country from {old_country} to {supplier_doc.country}.")
                continue

            new_supplier = frappe.get_doc({
                'doctype': 'Supplier',
                'supplier_name': company,
                'supplier_group': 'All Supplier Groups',  # TODO?
                'website': web_url,
                'tax_id': supplier_tax_id,
                'default_currency': currency,
                'payment_terms': payment_terms_mapping[payment_days],
                'bic': bic,
                'iban': iban,
                'supplier_details': details,
                'country': country_code_mapping[country_code]
            })
            new_supplier.insert()
            new_supplier.append("supplier_shops", {
                'company': our_company,
                'webshop_url': web_url,
                'customer_id': ext_customer_id,
                'username': web_username,
                'password': web_pwd
            })
            imported_counter += 1

            # write mapping of ERP Supplier ID to FM Index to a file
            with open(output_filepath, 'a') as txt_file:
                txt_file.write(f"{new_supplier.name};{ext_creditor_number}\n")

            if (address_line1 or post_box) and city and country_code and country_code in country_code_mapping:
                address_title = f"{company} - {address_line1 or post_box}"
                if len(address_title) > 100:
                    print(f"ERROR: The Address Title '{address_title}' is too long, unable to create any Address or Contact for {ext_creditor_number}. Please shorten 'Strasse' or 'Firma' so that they sum up to less than 98 characters.")
                    continue
                new_address = frappe.get_doc({
                    'doctype': 'Address',
                    'address_title': address_title,
                    'is_primary_address': 1,
                    'address_type': 'Billing',
                    'address_line1': address_line1 or post_box,
                    'country': country_code_mapping[country_code],
                    'pincode': pincode,
                    'city': city
                })
                new_address.insert()
                new_address.append("links", {
                    'link_doctype': 'Supplier',
                    'link_name': new_supplier.name
                })
                new_address.save()
                new_supplier.save()  # necessary to trigger set_default_payable_accounts (if country is Austria)
            elif city or pincode or address_line1 or post_box:
                print(f"WARNING: Ort, PLZ, Strasse or Postfach given, but missing required information (Land, Ort, Stasse oder Postfach) to create an address for Supplier with Index {ext_creditor_number} (external debitor number).")
            
            if first_name or last_name or phone or email:
                if not (first_name or last_name or company):
                    print(f"WARNING: Got no first name, no second name and no company for Supplier with Index {ext_creditor_number} (external debitor number). Unable to import a Contact, going to continue.")
                    continue
                new_contact = frappe.get_doc({
                    'doctype': 'Contact',
                    'first_name': first_name or last_name or company,
                    'last_name': last_name if first_name else None,
                    'salutation': salutation
                })
                new_contact.insert()
                new_contact.append("links", {
                    'link_doctype': 'Supplier',
                    'link_name': new_supplier.name
                })
                if phone:
                    new_contact.append("phone_nos", {
                        'phone': phone,
                        'is_primary_phone': 1
                    })
                if email:
                    new_contact.append("email_ids", {
                        'email_id': email,
                        'is_primary': 1
                    })
                new_contact.save()
            
            create_and_fill_contact(new_supplier.name, 1, contact_person_1, email_1, notes_1, ext_creditor_number)
            create_and_fill_contact(new_supplier.name, 2, contact_person_2, email_2, notes_2, ext_creditor_number)
            create_and_fill_contact(new_supplier.name, 3, contact_person_3, email_3, notes_3, ext_creditor_number)
            print(f"INFO: Successfully imported Supplier '{new_supplier.supplier_name}' ({new_supplier.name}).")
        print(f"INFO: Successfully imported {imported_counter}/{total_counter} Suppliers.")


def create_and_fill_contact(supplier_id, idx, first_name, email, notes, ext_creditor_number, last_name=None):
    if first_name:
        if last_name:
            new_contact = frappe.get_doc({
                'doctype': 'Contact',
                'first_name': first_name,
                'last_name': last_name
            })
        else:
            new_contact = frappe.get_doc({
                'doctype': 'Contact',
                'first_name': first_name
            })
        new_contact.append("links", {
            'link_doctype': 'Supplier',
            'link_name': supplier_id
        })
        if email:
            new_contact.append("email_ids", {
                'email_id': email,
                'is_primary': 1
            })
        try:
            new_contact.insert()
        except Exception as err:
            print(f"ERROR: Got the following error while trying to insert 'Ansprechpartner {idx}' of Supplier with Index {ext_creditor_number}: {err}")
            return
        if notes:
            if not frappe.db.exists("Contact", new_contact.name):
                frappe.throw(f"Contact '{new_contact.name}' does not exist.")
            new_comment = frappe.get_doc({
                'doctype': 'Comment',
                'comment_type': "Comment",
                'subject': new_contact.name,
                'content': notes,
                'reference_doctype': "Contact",
                'status': "Linked",
                'reference_name': new_contact.name
            })
            new_comment.insert(ignore_permissions=True)
    elif email:
        print(f"WARNING: Got the Email {idx} '{email}' for Supplier with Index {ext_creditor_number}, but no corresponding Contact name ('Ansprechpartner {idx}' required). Unable to create a Contact.")
    elif notes:
        print(f"WARNING: Got the Notes {idx} '{notes}' for Supplier with Index {ext_creditor_number}, but no corresponding Contact name ('Ansprechpartner {idx}' required). Unable to create a Contact.")


def validate_purchase_invoice(doc, event):
    validate_unique_bill_no(doc)
    return


def validate_unique_bill_no(doc):
    if type(doc) == str:
        doc = json.load(doc)

    # validate unique exstance of bill_no
    if doc.get("bill_no") and doc.get('supplier'):
        same_bill_nos = frappe.get_all("Purchase Invoice",
            filters=[
                ['supplier', '=', doc.get('supplier')],
                ['bill_no', '=', doc.get('bill_no')],
                ['docstatus', '<', 2]
            ],
            fields=['name']
        )
        for pinv in same_bill_nos:
            if pinv['name'] != doc.get('name'):
                frappe.throw("The supplier invoice number '{0}' is already recorded in {1}.<br><br>No changes were saved.".format(doc.get("bill_no"), pinv['name']) )
    return


@frappe.whitelist()
def supplier_change_fetches(supplier_id, company):
    """
    bench execute microsynth.microsynth.purchasing.supplier_change_fetches --kwargs "{'supplier_id': 'S-00003', 'company': 'Microsynth AG'}"
    """
    supplier_doc = frappe.get_doc("Supplier", supplier_id)
    expense_account = ""
    cost_center = ""
    if supplier_doc.default_item:
        item_doc = frappe.get_doc("Item", supplier_doc.default_item)
        for item_default in item_doc.item_defaults:
            if item_default.company == company:
                expense_account = item_default.expense_account
                cost_center = item_default.buying_cost_center or frappe.get_value("Company", company, "cost_center")
                break
    default_tax_template = ""
    for row in supplier_doc.accounts:
        if row.company == company:
            default_tax_template = row.default_tax_template
            break
    if (not default_tax_template) and company:
        # fetch company specific default Purchase Taxes and Charges Template
        tax_templates = frappe.get_all("Purchase Taxes and Charges Template", filters={'company': company, 'is_default': 1}, fields=['name'])
        if len(tax_templates) == 1:
            default_tax_template = tax_templates[0]['name']
        else:
            frappe.log_error(f"There are {len(tax_templates)} default Purchase Taxes and Charges Templates for Company {company}.", "purchasing.supplier_change_fetches")
    return {'taxes_and_charges': default_tax_template,
            'payment_terms_template': supplier_doc.payment_terms,
            'default_item_code': supplier_doc.default_item,
            'default_item_name': supplier_doc.item_name,
            'expense_account': expense_account,
            'cost_center': cost_center,
            'default_approver': supplier_doc.default_approver}


@frappe.whitelist()
def decrypt_access_password(cdn):
    """
    Decrypt access password
    """
    password = get_decrypted_password("Supplier Shop", cdn, "password", False)
    if not password:
        return {'password': password, 'warning': "Please set a password and save the Supplier before using the button 'Copy password'."}
    strength = test_password_strength(new_password=password)
    if 'microsynth' in password.lower() or not strength['feedback']['password_policy_validation_passed']:
        return {'password': password, 'warning': f"The password does not match our security policy. Please change it to a strong password. {strength['feedback']['warning'] or ''}"}
    else:
        return {'password': password, 'warning': None}


@frappe.whitelist()
def check_supplier_shop_password(password):
    """
    bench execute microsynth.microsynth.purchasing.check_supplier_shop_password --kwargs "{'new_password': 'microsynth-1'}"
    """
    # check strength
    strength = test_password_strength(new_password=password)
    if 'microsynth' in password.lower() or not strength['feedback']['password_policy_validation_passed']:
        return {'error': _("The new password does not match the security policy. Please try again with a strong password.") + " " + (strength['feedback']['warning'] or "")}
    else:
        return {'success': True}