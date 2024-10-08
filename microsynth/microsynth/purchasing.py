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
        frappe.throw(f"Found {len(addresses)} billing addresses for Supplier '{supplier_id}'", "fetch_billing_address")


def set_default_payable_accounts(supplier, event):
    """
    Set the default payable accounts for the given supplier.

    bench execute microsynth.microsynth.purchasing.set_default_payable_accounts --kwargs "{'supplier': 'S-00001'}"
    """
    if type(supplier) == str:
        supplier = frappe.get_doc("Supplier", supplier)
    companies = frappe.get_all("Company", fields = ['name', 'default_currency'])

    for company in companies:
        print(f"Processing {company['name']} ...")
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
            print(f"appended {entry=}")
    # Do not save since function is called in before_save server hook    


def set_and_save_default_payable_accounts(supplier):
    if type(supplier) == str:
        supplier = frappe.get_doc("Supplier", supplier)
    supplier.save()
    #frappe.db.commit()