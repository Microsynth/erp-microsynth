# -*- coding: utf-8 -*-
# Copyright (c) 2024, Microsynth
# For license information, please see license.txt
# For more details, refer to https://github.com/Microsynth/erp-microsynth/

import frappe
from frappe.desk.form.assign_to import add


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


def is_already_assigned(dt, dn):
    if frappe.db.sql(f"""SELECT `owner`
        FROM `tabToDo`
        WHERE `reference_type`= '{dt}'
            AND `reference_name`= '{dn}'
            AND `status`='Open'
        ;""", frappe.local.form_dict):
        return True
    else:
        return False


@frappe.whitelist()
def create_approval_request(assign_to, dt, dn):
    if not is_already_assigned(dt, dn):
        add({
            'doctype': dt,
            'name': dn,
            'assign_to': assign_to,
            'description': f"Please check the {dt} {dn}. Submit {dn} to approve.",
            'notify': True  # Send email
        })
        if dt == "Purchase Invoice":
            purchase_invoice = frappe.get_doc(dt, dn)
            #if (not purchase_invoice.approver) or purchase_invoice.approver == '':
            purchase_invoice.approver = assign_to
            purchase_invoice.in_approval = 1
            purchase_invoice.save()
        return True
    else:
        return False


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


def import_suppliers(file_path, expected_line_length=41):
    """
    bench execute microsynth.microsynth.purchasing.import_suppliers --kwargs "{'file_path': '/mnt/erp_share/JPe/Lieferantenexport_Seqlab.csv'}"
    """
    import csv
    country_code_mapping = {
        'DE': 'Germany',
        'AT': 'Austria',
        'CH': 'Switzerland',
        'UK': 'United Kingdom',
        'US': 'United States',
        'SI': 'Slovenia'
    }
    payment_terms_mapping = {
        '10': '10 days net',
        '30': '30 days net'
    }
    imported_counter = 0
    with open(file_path) as file:
        print(f"Parsing Suppliers from '{file_path}' ...")
        csv_reader = csv.reader((l.replace('\0', '') for l in file), delimiter=";")  # replace NULL bytes (throwing an error)
        next(csv_reader)  # skip header
        for line in csv_reader:
            if len(line) != expected_line_length:
                print(f"Line '{line}' has length {len(line)}, but expected length {expected_line_length}. Going to continue.")
                continue

            # parse values
            ext_customer_id = line[0].strip()  # remove leading and trailing whitespaces
            salutation = line[1].strip()
            first_name = line[2].strip()
            last_name = line[3].strip()
            company = line[4].strip()
            company_addition = line[5].strip()
            post_box = line[6].strip()
            address_line1 = line[7].strip()
            country_code = line[8].strip()
            pincode = line[9].strip()
            city = line[10].strip()
            phone = line[11].strip() + line[12].strip()
            email = line[13].strip()
            web_url = line[14].strip()
            web_username = line[15].strip()
            # web_pwd = line[16].strip()  might be entered directly into a protected field
            supplier_tax_id = line[17].strip()
            skonto = line[18].strip()
            payment_days = str(line[19].strip())
            currency = line[20].strip()
            reliability = line[21].strip()
            phone_note = line[22].strip()
            notes = line[23].strip()
            bic = line[24].strip()
            iban = line[25].strip()
            bank_name = line[26].strip()  # necessary?
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
            ext_debitor_number = line[40].strip()
            print(f"Processing Index {ext_debitor_number} (external debitor number) ...")

            # combine some values
            if company_addition and company:
                company = f"{company} - {company_addition}"
            elif company_addition:
                company = company_addition
            if phone_note and notes:
                notes = f"Phone Note: {phone_note}\n\nNotes: {notes}"
            elif phone_note:
                notes = phone_note
            
            # check some values
            if country_code not in country_code_mapping:
                print(f"Unknown country code '{country_code}', going to skip {ext_debitor_number}.")
                continue
            if payment_days not in payment_terms_mapping:
                print(f"There exists no Payment Terms Template for '{payment_days}', going to skip {ext_debitor_number}.")
                continue
            if len(address_line1) > 140:
                print(f"Column 'Strasse' has {len(address_line1)} > 140 characters, going to skip {ext_debitor_number}.")
                continue
            
            if len(frappe.get_all("Supplier", filters=[['supplier_name', '=', company]], fields=['name'])) > 0:
                print(f"There exists already a Supplier with the Supplier Name '{company}', going to skip {ext_debitor_number}.")
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
                'supplier_details': notes
            })
            new_supplier.insert()
            imported_counter += 1

            if (address_line1 or post_box) and city and country_code:
                address_title = f"{company} - {address_line1 or post_box}"
                if len(address_title) > 100:
                    print(f"The Address Title '{address_title}' is too long, going to skip {ext_debitor_number}.")
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
            else:
                print(f"Missing required information to create an address for Supplier {new_supplier.name} ({ext_debitor_number}).")
            
            if first_name or last_name or phone or email:
                if not (first_name or last_name or company):
                    print(f"Got no first name, no second name and no company for Supplier {new_supplier.name} ({ext_debitor_number}). Unable to import a Contact, going to continue.")
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
            
            create_and_fill_contact(1, contact_person_1, email_1, notes_1)
            create_and_fill_contact(2, contact_person_2, email_2, notes_2)
            create_and_fill_contact(3, contact_person_3, email_3, notes_3)
            print(f"Successfully imported Supplier '{new_supplier.supplier_name}' ({new_supplier.name}).")
        print(f"Successfully imported {imported_counter} Suppliers.")


def create_and_fill_contact(idx, first_name, email, notes, last_name=None):
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
        new_contact.insert()
        if email:
            new_contact.append("email_ids", {
                'email_id': email,
                'is_primary': 1
            })
        if notes:
            new_comment = frappe.get_doc({
                'doctype': 'Comment',
                'comment_type': "Comment",
                'subject': new_contact.name,
                'content': notes,
                'reference_doctype': "Sales Invoice",
                'status': "Linked",
                'reference_name': new_contact.name
            })
            # new_comment.insert(ignore_permissions=True)  # TODO: LinkValidationError: Could not find Reference Name
    elif email:
        print(f"Got the Email {idx} '{email}', but no corresponding Contact name.")
    elif notes:
        print(f"Got the Notes {idx} '{notes}', but no corresponding Contact name.")
