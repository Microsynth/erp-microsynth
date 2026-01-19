# -*- coding: utf-8 -*-
# Copyright (c) 2024, Microsynth
# For license information, please see license.txt
# For more details, refer to https://github.com/Microsynth/erp-microsynth/

import json
import csv
import re
from datetime import datetime

import frappe
from frappe import _
from frappe.desk.form.assign_to import add, clear
from frappe.core.doctype.communication.email import make
from frappe.utils import get_url_to_form, flt, getdate
from frappe.utils.data import today
from frappe.utils.password import get_decrypted_password
from frappe.core.doctype.user.user import test_password_strength
from microsynth.microsynth.utils import user_has_role
from microsynth.microsynth.taxes import find_purchase_tax_template
from microsynth.microsynth.naming_series import get_next_purchasing_item_id

from microsynth.microsynth.report.material_request_overview.material_request_overview import get_data as get_requested_items

SUPPORTED_BUYING_CURRENCIES = ['CHF', 'EUR', 'USD', 'GBP']


def create_pi_from_si(sales_invoice):
    """
    Create a purchase invoice for an internal company from a sales invoice

    bench execute microsynth.microsynth.purchasing.create_pi_from_si  --kwargs "{'sales_invoice': 'SI-BAL-24017171'}"
    """
    si = frappe.get_doc("Sales Invoice", sales_invoice)
    # create matching purchase invoice
    pi_company = frappe.get_all("Intercompany Settings Company", filters={'customer': si.customer}, fields=['company'])
    if len(pi_company) == 0:
        frappe.log_error(f"Company for customer {si.customer} is not available, but was requested in the intercompany invoicing of {sales_invoice}. Please check the Intercompany Settings.", "purchasing.create_pi_from_si")
        return None
    else:
        pi_company = pi_company[0]['company']
    if not frappe.db.exists("Company", pi_company):
        frappe.log_error(f"Company {pi_company} is not available, but was requested in the intercompany invoicing of {sales_invoice}.", "purchasing.create_pi_from_si")
        return None
    suppliers = frappe.get_all("Supplier", filters={'supplier_name': si.company}, fields=['name'])
    if suppliers and len(suppliers) == 1:
        if len(suppliers) > 1:
            frappe.log_error(f"Found {len(suppliers)} Supplier for Company {si.company} on Sales Invoice {si.name}. Going to take the first one.", "purchasing.create_pi_from_si")
        pi_supplier = suppliers[0]['name']
    else:
        frappe.log_error(f"Found no Supplier for Company {si.company} on Sales Invoice {si.name}. Going to return.", "purchasing.create_pi_from_si")
        return None
    pi_cost_center = frappe.get_value("Company", pi_company, "cost_center")
    # find tax template based on sales invoice taxes
    pi_tax_template = find_purchase_tax_template(si.taxes_and_charges, pi_company)
    if not pi_tax_template:
        frappe.log_error(f"Cannot create purchase invoice, because no purchase tax template was found for {sales_invoice}. Going to return.", "purchasing.create_pi_from_si")
        return None

    expense_account = frappe.get_all("Intercompany Settings Supplier",
                                        filters={
                                            'supplier': pi_supplier,
                                            'product_type': si.product_type,
                                            'company': pi_company},
                                        fields=['expense_account'])

    if len(expense_account) == 0 or not expense_account[0]['expense_account']:
        frappe.log_error(f"Sales Invoice {sales_invoice}: No expense account was found for supplier {pi_supplier} and product type {si.product_type} for company {pi_company}. Using company default settings. Go and configure Intercompany Settings.", "purchasing.create_pi_from_si")
        expense_account = frappe.get_value("Company", pi_company, "default_expense_account")
    else:
        expense_account = expense_account[0]['expense_account']

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
        'currency': si.currency,
        'additional_discount_percentage': si.additional_discount_percentage,
        'taxes_and_charges': pi_tax_template,
        'disable_rounded_total': 1
    })
    # add item positions
    for i in si.items:
        new_pi.append('items', {
            'item_code': i.item_code,
            'item_name': i.item_name,
            'qty': i.qty,
            'description': i.description,
            'rate': i.rate,
            'cost_center': pi_cost_center,
            'expense_account': expense_account
        })
    # apply taxes
    if pi_tax_template:
        pi_tax_details = frappe.get_doc("Purchase Taxes and Charges Template", pi_tax_template)
        for t in pi_tax_details.taxes:
            new_pi.append('taxes', {
                'charge_type': t.charge_type,
                'account_head': t.account_head,
                'description': t.description,
                'rate': t.rate
            })
    # insert
    new_pi.insert()
    new_pi.submit()

    # Link attachment of sales invoice (duplication record of tabFile)
    # Get the list of attachments linked to the Sales Invoice
    attachments = frappe.get_all('File', filters={'attached_to_doctype': 'Sales Invoice', 'attached_to_name': sales_invoice})

    # Loop through the attachments and add them to the Purchase Invoice
    for attachment in attachments:
        file_record = frappe.get_doc('File', attachment['name'])
        new_file = frappe.get_doc({
            'doctype': 'File',
            'file_name': file_record.file_name,
            'file_url': file_record.file_url,
            'attached_to_doctype': 'Purchase Invoice',
            'attached_to_name': new_pi.name,
            'is_private': file_record.is_private
        })
        new_file.insert(ignore_permissions=True)
    new_pi.save()
    return new_pi


def _compute_total_quantity_by_item(material_request_rows):
    """Compute total qty per item_code from the list of material-request rows."""
    totals = {}
    for row in material_request_rows:
        key = row.get('item_code') or '-'
        totals[key] = totals.get(key, 0.0) + flt(row.get('qty') or 0)
    return totals


def _select_quotation_for_item(item_code, consolidated_total_qty, supplier_doc, currency, today_date, original_rate, company):
    """Select cheapest valid Supplier Quotation Item or fallback to price list rate.

    Returns a dict: {
        'supplier_quotation': name or None,
        'supplier_quotation_item': name or None,
        'rate': float,
        'external_reference': str or None,
        'warnings': [str]
    }
    """
    selection = {
        'supplier_quotation': None,
        'supplier_quotation_item': None,
        'rate': original_rate,  # use original MR rate as default
        'external_reference': None,
        'warnings': []
    }

    # Query Supplier Quotation Items
    supplier_quotation_rows = frappe.db.sql(
        """
        SELECT
            `tabSupplier Quotation`.`name` AS `supplier_quotation`,
            `tabSupplier Quotation`.`external_reference` AS `external_reference`,
            `tabSupplier Quotation Item`.`name` AS `supplier_quotation_item`,
            IFNULL(`tabSupplier Quotation Item`.`qty`, 0) AS `min_qty`,
            IFNULL(`tabSupplier Quotation Item`.`rate`, 0) AS `rate`,
            IFNULL(`tabSupplier Quotation`.`valid_from`, '1900-01-01') AS `valid_from`,
            IFNULL(`tabSupplier Quotation`.`valid_till`, '9999-12-31') AS `valid_till`
        FROM `tabSupplier Quotation Item`
        JOIN `tabSupplier Quotation` ON `tabSupplier Quotation Item`.`parent` = `tabSupplier Quotation`.`name`
        WHERE `tabSupplier Quotation`.`docstatus` = 1
            AND `tabSupplier Quotation`.`supplier` = %s
            AND `tabSupplier Quotation Item`.`item_code` = %s
        ORDER BY `tabSupplier Quotation Item`.`rate` ASC
        """,
        (supplier_doc.name, item_code), as_dict=True
    )

    valid_supplier_quotations = []
    expired_supplier_quotations = []
    for sq_row in (supplier_quotation_rows or []):
        try:
            valid_from_date = getdate(sq_row.get('valid_from'))
            valid_till_date = getdate(sq_row.get('valid_till'))
        except Exception:
            valid_from_date = None
            valid_till_date = None
        is_valid_now = True
        if valid_from_date and valid_from_date > today_date:
            is_valid_now = False
        if valid_till_date and valid_till_date < today_date:
            is_valid_now = False
        if is_valid_now:
            valid_supplier_quotations.append(sq_row)
        else:
            expired_supplier_quotations.append(sq_row)

    if valid_supplier_quotations:
        chosen = valid_supplier_quotations[0]
        selection['rate'] = flt(chosen.get('rate') or selection['rate'])
        selection['supplier_quotation'] = chosen.get('supplier_quotation')
        selection['supplier_quotation_item'] = chosen.get('supplier_quotation_item')
        selection['external_reference'] = chosen.get('external_reference')
        if flt(chosen.get('min_qty') or 0) > consolidated_total_qty:
            selection['warnings'].append(
                f"Item {item_code}: chosen Supplier Quotation {chosen.get('supplier_quotation')} requires minimum quantity {chosen.get('min_qty')}, consolidated qty {consolidated_total_qty}."
            )
    else:
        if expired_supplier_quotations:
            selection['warnings'].append(
                f"Item {item_code}: found Supplier Quotations but none are currently valid."
            )
        # Fallback: try to derive a rate from supplier's default price list
        from erpnext.stock.get_item_details import get_item_details

        conversion_rate = 1
        if supplier_doc.default_currency != currency:
            conversion_rate = frappe.get_value(
                "Currency Exchange",
                {"from_currency": supplier_doc.default_currency, "to_currency": currency},
                "exchange_rate"
            )
        item_details = get_item_details({
            "item_code": item_code,
            "qty": consolidated_total_qty,
            "price_list": supplier_doc.default_price_list,
            "supplier": supplier_doc.name,
            "company": company,
            "buying": 1,
            "currency": currency,
            "conversion_rate": conversion_rate,
            "doctype": "Purchase Order",
        })
        if item_details and item_details.get("rate") is not None:
            selection['rate'] = flt(item_details.get("rate"))
        else:
            selection['warnings'].append(
                f"Item {item_code}: no valid Item Price found in price list {supplier_doc.default_price_list}."
            )

    return selection


def _create_po_document_for_items(material_request_rows, total_quantity_by_item_code, supplier_doc, filters, currency):
    """Create a Purchase Order document and append PO items for each material request row.

    Returns: (po_doc, used_supplier_quotations, purchase_warnings)
    """
    po_doc = frappe.get_doc({
        'doctype': 'Purchase Order',
        'supplier': filters.get('supplier'),
        'company': filters.get('company'),
        'currency': currency,
        'buying_price_list': supplier_doc.default_price_list
    })

    today_date = getdate(today())
    used_supplier_quotations = []
    purchase_warnings = []
    quotation_choice_cache = {}

    # Ensure rows are sorted by item_code so identical items are consecutive
    rows_sorted = sorted(material_request_rows, key=lambda r: (r.get('item_code') or ''))

    for original_row in rows_sorted:
        original_item_code = original_row.get('item_code')
        item_code_key = original_item_code or '-'
        consolidated_total_qty = flt(total_quantity_by_item_code.get(item_code_key, 0.0))
        original_rate = flt(original_row.get('rate') or 0.0)

        # reuse cached selection or compute it
        if item_code_key in quotation_choice_cache:
            selection = quotation_choice_cache[item_code_key]
            if selection.get('external_reference'):
                used_supplier_quotations.append(
                    f"{selection.get('supplier_quotation')} ({selection.get('external_reference')})"
                )
            if selection.get('warnings'):
                purchase_warnings.extend(selection.get('warnings'))
        else:
            selection = _select_quotation_for_item(
                item_code_key, consolidated_total_qty, supplier_doc, currency, today_date, original_rate, filters.get('company')
            )
            quotation_choice_cache[item_code_key] = selection
            if selection.get('external_reference'):
                used_supplier_quotations.append(
                    f"{selection.get('supplier_quotation')} ({selection.get('external_reference')})"
                )
            if selection.get('warnings'):
                purchase_warnings.extend(selection.get('warnings'))

        # UOM & conversion checks
        chosen_item_stock_uom = None
        chosen_item_purchase_uom = None
        chosen_item_conversion_factor = 1
        if original_item_code and frappe.db.exists('Item', original_item_code):
            try:
                item_document = frappe.get_doc('Item', original_item_code)
                chosen_item_stock_uom = item_document.get('stock_uom') or None
                chosen_item_purchase_uom = item_document.get('purchase_uom') or chosen_item_stock_uom
                if chosen_item_purchase_uom and chosen_item_stock_uom and chosen_item_purchase_uom != chosen_item_stock_uom:
                    conv = frappe.db.get_value(
                        'UOM Conversion Detail',
                        {'parent': original_item_code, 'uom': chosen_item_purchase_uom},
                        'conversion_factor'
                    )
                    if conv:
                        chosen_item_conversion_factor = flt(conv)
                    else:
                        purchase_warnings.append(
                            f"Item {item_code_key}: missing UOM conversion from {chosen_item_purchase_uom} to {chosen_item_stock_uom} on Item record. Please verify UOM conversions."
                        )
            except Exception as err:
                purchase_warnings.append(f"Unable to fetch Item {original_item_code} for UOM checks: {err}")

        # warn on conversion factor issues
        if chosen_item_purchase_uom and chosen_item_stock_uom and chosen_item_purchase_uom != chosen_item_stock_uom:
            if not chosen_item_conversion_factor or chosen_item_conversion_factor <= 0 or chosen_item_conversion_factor == 1:
                purchase_warnings.append(
                    f"Item {item_code_key}: invalid or missing conversion factor '{chosen_item_conversion_factor}' between purchase UOM '{chosen_item_purchase_uom}' and stock UOM '{chosen_item_stock_uom}'."
                )

        # build PO item row
        po_item_row = {
            'item_code': original_item_code,
            'item_name': original_row.get('item_name'),
            'schedule_date': getdate(original_row.get('schedule_date') or today_date),
            'qty': flt(original_row.get('qty') or 0),
            'rate': flt(selection.get('rate') or original_rate),
            'uom': chosen_item_purchase_uom or original_row.get('uom') or chosen_item_stock_uom,
            'stock_uom': chosen_item_stock_uom,
            'conversion_factor': chosen_item_conversion_factor,
            'material_request': original_row.get('material_request'),
            'material_request_item': original_row.get('material_request_item'),
            'external_quotation_reference': selection.get('external_reference')
        }
        # set supplier quotation link only once
        already_used_sq_item = quotation_choice_cache[item_code_key].get('sq_item_used')
        if not already_used_sq_item:
            po_item_row.update({
                'supplier_quotation': selection.get('supplier_quotation'),
                'supplier_quotation_item': selection.get('supplier_quotation_item')
            })
            quotation_choice_cache[item_code_key]['sq_item_used'] = True

        po_doc.append('items', po_item_row)

    return po_doc, used_supplier_quotations, purchase_warnings


@frappe.whitelist()
def create_po_from_open_mr(filters):
    """
    create_po_from_open_mr
    """
    if type(filters) == str:
        filters = json.loads(filters)
    items = get_requested_items(filters)
    currencies = {item.get('currency') for item in items if item.get('currency') is not None}
    supplier_doc = frappe.get_doc('Supplier', filters.get('supplier'))
    if len(currencies) > 1:
        frappe.throw(
            _("The selected Material Requests contain items with different currencies ({0}). Please create separate Purchase Orders for each currency.").format(
                ", ".join(currencies)
            )
        )
    elif len(currencies) == 1:
        currency = currencies.pop() or supplier_doc.default_currency
        if currency != supplier_doc.default_currency:
            frappe.throw(
                f"The selected Supplier has default currency {supplier_doc.default_currency}, but the Material Requests are in {currency}. Unable to create Purchase Order.",
                "Currency Mismatch"
            )
    else:
        currency = supplier_doc.default_currency

    # Check for existing Draft POs and exit if there are some drafts
    existing_po_drafts = frappe.get_all(
        'Purchase Order',
        filters={
            'supplier': filters.get('supplier'),
            'company': filters.get('company'),
            'docstatus': 0
        },
        fields=['name']
    )
    if existing_po_drafts:
        links = [
            f'<li><a href="{get_url_to_form("Purchase Order", po["name"])}" target="_blank">{po["name"]}</a></li>'
            for po in existing_po_drafts
        ]
        frappe.throw(
            f"There are the following existing Purchase Order Drafts for the Supplier "
            f"{filters.get('supplier')} and Company {filters.get('company')}:"
            f"<ul>{''.join(links)}</ul>"
            f"Please review them before creating a new Purchase Order."
        )

    # Consolidate totals and create PO
    total_quantity_by_item_code = _compute_total_quantity_by_item(items)
    po_doc, used_supplier_quotations, purchase_warnings = _create_po_document_for_items(
        items, total_quantity_by_item_code, supplier_doc, filters, currency
    )

    # add inbound freight item
    last_schedule_date = getdate(today())
    if po_doc.items:
        try:
            last_schedule_date = getdate(po_doc.items[-1].schedule_date or today())
        except Exception:
            last_schedule_date = getdate(today())
    po_doc.append('items', {
        'item_code': get_inbound_freight_item(),
        'item_name': 'Inbound Freight',
        'qty': 1,
        'rate': 0.0,
        'schedule_date': last_schedule_date,
    })
    # taxes
    po_doc.taxes_and_charges = get_purchase_tax_template(po_doc.supplier, po_doc.company or 'Microsynth AG')
    if po_doc.taxes_and_charges:
        taxes_template = frappe.get_doc("Purchase Taxes and Charges Template", po_doc.taxes_and_charges)
        for tax_row in taxes_template.taxes:
            po_doc.append("taxes", tax_row)

    po_doc.insert()

    # Deduplicate lists
    unique_used_supplier_quotations = list(dict.fromkeys(used_supplier_quotations))
    unique_purchase_warnings = list(dict.fromkeys(purchase_warnings))

    if unique_purchase_warnings:
        # TODO: How to best show warnings to user on the UI side?
        frappe.log_error(f"Created Purchase Order {po_doc.name} from Material Requests. Used Supplier Quotations: {unique_used_supplier_quotations}. Warnings: {unique_purchase_warnings}", "purchasing.create_po_from_open_mr")

    return po_doc.name


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
def book_as_deposit(purchase_invoice_id):
    """
    bench execute microsynth.microsynth.purchasing.assign_purchase_invoices --kwargs "{'purchase_invoice_id': 'PI-2500612'}"
    """
    pi_doc = frappe.get_doc("Purchase Invoice", purchase_invoice_id)
    jv = frappe.get_doc({
        'doctype': 'Journal Entry',
        'posting_date': datetime.now(),
        'company': pi_doc.company,
        'user_remark': 'Transfer posting as a deposit for later deduction from an purchase invoice',
        'accounts': [
            {
                'account': pi_doc.credit_to,
                'account_currency': pi_doc.currency,
                'credit_in_account_currency': abs(pi_doc.grand_total),
                'cost_center': pi_doc.items[0].cost_center,
                'reference_type': 'Purchase Invoice',
                'reference_name': pi_doc.name,
                'party_type': 'Supplier',
                'party': pi_doc.supplier
            },
            # TODO: How to set balance (Account Balance)?
            {
                'account': pi_doc.credit_to,
                'account_currency': pi_doc.currency,
                'debit_in_account_currency': abs(pi_doc.grand_total),
                'cost_center': pi_doc.items[0].cost_center,
                'party_type': 'Supplier',
                'party': pi_doc.supplier,
                'is_advance': 'Yes'
            }
        ]
    })
    jv.insert(ignore_permissions=True)
    jv.submit()
    # frappe.db.commit()
    return jv.name


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

    # allow to set specific debtor accounts for intercompany customers
    intercompany_suppliers = set()
    for s in frappe.get_all("Intercompany Settings Supplier", fields = ['supplier']):
        intercompany_suppliers.add(s['supplier'])

    if supplier.name in intercompany_suppliers or supplier.supplier_name in ['Microsynth Seqlab GmbH', 'Microsynth Austria GmbH', 'Microsynth France SAS']:  # TODO remove fallback to supplier_name once they are all entered in the supplier settings
        return

    for company in companies:
        #print(f"Processing {company['name']} ...")
        if company['name'] == "Microsynth Seqlab GmbH":
            account = "1600 - Verb. aus Lieferungen und Leistungen - GOE"
        elif company['name'] == "Microsynth France SAS":
            account = "4010000 - Fournisseurs - LYO"  # TODO check this account!
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


COMPANY_CITY_MAPPING = {
    'Microsynth AG': 'Balgach',
    'Microsynth Seqlab GmbH': 'Göttingen',
    'Microsynth Austria GmbH': 'Wien',
    'Microsynth France SAS': 'Lyon'
}

FLOOR_MAPPING_PER_COMPANY = {
    'Microsynth AG': {
        '10': 'Ground Floor',
        '11': '1st Floor',
        '12': '2nd Floor',
        '13': '3rd Floor',
        '14': '4th Floor'
    },
    'Microsynth Seqlab GmbH': {
        '00': 'Ground Floor Seqlab',
        '01': '1st Floor Seqlab',
        '02': '2nd Floor Seqlab'
    }
}


def _get_or_create_single_location(location_name, parent_location, is_group=True):
    """
    Helper: Get or create a single Location under the given parent.
    Returns the Location name.
    """
    existing = frappe.db.exists("Location", {"location_name": location_name, "parent_location": parent_location})
    if existing:
        # ensure correct group flag
        if frappe.db.get_value("Location", existing, "is_group") != int(is_group):
            frappe.db.set_value("Location", existing, "is_group", int(is_group))
        return existing

    loc = frappe.get_doc({
        "doctype": "Location",
        "location_name": location_name,
        "parent_location": parent_location,
        "is_group": 1 if is_group else 0
    })
    loc.insert()
    frappe.db.commit()
    return loc.name


def get_or_create_location(floor, room, destination, fridge_rack, company='Microsynth AG'):
    """
    Returns the final Location document (creates any missing lower-level locations).

    Hierarchy: All Locations → CITY → FLOOR → ROOM → DESTINATION → FRIDGE_RACK

    - 'All Locations', city, floor, and room must already exist.
    - Room lookup matches 'floor-room-*' exactly (e.g. '11-03-' for floor=11, room=03).
    - Creates missing DESTINATION or FRIDGE_RACK if necessary.
    """
    FLOOR_MAPPING = FLOOR_MAPPING_PER_COMPANY[company]
    city = COMPANY_CITY_MAPPING.get(company)
    if not city:
        frappe.throw(f"Unknown company mapping for {company}")

    # City
    city_location = frappe.db.exists("Location", {"location_name": city})
    if not city_location:
        frappe.throw(f"City location '{city}' not found under 'All Locations'.")
    if not floor:
        return frappe.get_doc("Location", city)

    # Floor
    if not floor in FLOOR_MAPPING:
        frappe.throw(f"Got unknown floor '{floor}'.")
    floor_name = FLOOR_MAPPING.get(str(floor), '')
    floor_location = frappe.db.exists("Location", {"location_name": floor_name, "parent_location": city_location})
    if not floor_location:
        frappe.throw(f"Floor '{floor_name}' not found under city '{city}'.")
    if not room:
        return frappe.get_doc("Location", floor_name)

    # Room - exact structured match
    floor_str = str(floor).strip()
    room_str = str(room).strip()

    # Validate that floor and room are exactly two digits
    if not (floor_str.isdigit() and len(floor_str) == 2):
        frappe.throw(f"Invalid floor '{floor}': must be exactly two digits (e.g. '10', '11').")
    if not (room_str.isdigit() and len(room_str) == 2) and room_str != '14c':
        frappe.throw(f"Invalid room '{room}': must be exactly two digits (e.g. '03', '20').")

    if company == 'Microsynth Seqlab GmbH':
        pattern = f"{floor_str}.{room_str}%"
    else:
        pattern = f"{floor_str}-{room_str}%"

    room_doc = frappe.db.sql("""
        SELECT `name`
        FROM `tabLocation`
        WHERE `parent_location` = %s
          AND `location_name` LIKE %s
    """, (floor_location, pattern), as_dict=True)

    if len(room_doc) == 0:
        frappe.throw(f"No room matching pattern '{pattern}' found under floor '{floor_name}' in '{city}'.")
    elif len(room_doc) > 1:
        frappe.throw(f"Multiple rooms matching pattern '{pattern}' found under floor '{floor_name}' in '{city}'.")

    room_location = room_doc[0].name
    parent_location = room_location

    # Optional deeper levels (Destination, Fridge Rack)
    for i, level_name in enumerate([destination, fridge_rack]):
        if not level_name:
            continue
        level_name = str(level_name).strip()
        is_last = (i == 1 or not fridge_rack)  # last if fridge_rack is None or this is fridge_rack
        # ensure parent is a group before adding children
        parent_doc = frappe.get_doc("Location", parent_location)
        if not parent_doc.is_group:
            parent_doc.is_group = 1
            parent_doc.save()
        # create or fetch the child
        parent_location = _get_or_create_single_location(
            level_name,
            parent_location,
            is_group=not is_last
        )
    # Return final location
    final_doc = frappe.get_doc("Location", parent_location)
    return final_doc


def import_supplier_items(input_filepath, output_filepath, supplier_mapping_file, company='Microsynth AG', expected_line_length=43, update_existing_items=False):
    """
    Seqlab:
    bench execute microsynth.microsynth.purchasing.import_supplier_items --kwargs "{'input_filepath': '/mnt/erp_share/JPe/2026-01-15_Lieferantenartikel_Seqlab.csv', 'output_filepath': '/mnt/erp_share/JPe/2025-11-27_DEV_supplier_item_mapping_Seqlab.txt', 'supplier_mapping_file': '/mnt/erp_share/JPe/2025-11-27_2_supplier_mapping_Seqlab_DEV-ERP.txt', 'company': 'Microsynth Seqlab GmbH', 'update_existing_items': False}"

    AG:
    bench execute microsynth.microsynth.purchasing.import_supplier_items --kwargs "{'input_filepath': '/mnt/erp_share/Migration/Purchasing/2025-12-01_Lieferantenartikel_Microsynth_AG.csv', 'output_filepath': '/mnt/erp_share/Migration/Purchasing/2025-12-01_supplier_item_mapping_Microsynth_AG.txt', 'supplier_mapping_file': '/mnt/erp_share/Migration/Purchasing/2025-12-01_supplier_mapping_Microsynth_AG.txt', 'company': 'Microsynth AG', 'update_existing_items': True}"
    """
    # TODO: Refactor code
    known_uoms = [uom['name'] for uom in frappe.get_all("UOM", fields=['name'])]
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
            #auftraggeber = line[1].strip()
            #lk = line[2].strip()  # Lagerkontrolle -> all Items get "Maintain Stock"
            internal_code = line[3].strip()  # if given, Item should have "Maintain Stock"
            supplier_item_id = line[4].strip()
            item_name = remove_control_characters(line[5].strip().replace('\n', ' ').replace('  ', ' '))  # replace newlines and double spaces
            unit_size = line[6].strip()  # "Einheit besteht aus", e.g. 4 for Item "Oxidizer 4 x4.0 L"
            currency = line[7].strip()
            supplier_quote = line[8].strip()
            #list_price = line[9].strip()
            purchase_price = line[10].strip()
            #customer_discount = line[11].strip()
            #content_quantity = line[12].strip()  # "Inhaltsmenge_Angabe" -> split into pack_size and pack_uom
            #item_group = line[13].strip()
            #group = line[14].strip()
            account = line[15].strip()
            #storage_location = line[16].strip()  # "Lagerort" -> split into floor, room, destination, fridge_rack
            #annual_consumption_budget = line[17].strip()
            #order_quantity_6mt = line[18].strip()
            safety_stock = line[19].strip()  # "Schwellenwert"
            shelf_life_in_years  = line[20].strip()  # Haltbarkeit
            #process_critical = line[21].strip()
            #quality_control = line[22].strip()
            #quality_list = line[23].strip()
            #subgroup = line[24].strip()
            #time_limit = line[25].strip()
            #quantity_supplier = line[26].strip()
            material_code = line[27]  # Kurzname
            item_id = line[28].strip()  # Datensatznummer
            # line[29]..line[32]: order quantities 2021..2024
            # last_order_date = line[33].strip()
            to_import = line[34].strip().lower()  # Export ERP (Ja/nein)
            purchase_uom = line[35].strip()
            stock_uom = line[36].strip()
            pack_uom = line[37].strip()
            pack_size = line[38].strip()
            floor = line[39].strip()
            room = line[40].strip()
            destination = line[41].strip()
            fridge_rack = line[42].strip()

            if to_import not in ['ja', 'nein']:
                print(f"ERROR: Item with Index {item_id} has invalid value '{to_import}' in column 'Export ERP'. Going to continue with the next supplier item.")
                continue
            if to_import == 'nein':
                continue
            # check if item was ordered from 2021 to 2025
            # try:
            #     ordered_2021_2025 = sum([int(line[29].strip() or 0), int(line[30].strip() or 0), int(line[31].strip() or 0), int(line[32].strip() or 0)])
            # except ValueError as err:
            #     print(f"ERROR: Item with Index {item_id} has the following non-integer order quantities: {line[29:33]} ({err}). Going to continue with the next supplier item.")
            #     continue
            # if ordered_2021_2025 == 0 and not line[33].strip() and not internal_code:
            #     # do not import Items that were not ordered from 2021 to 2024 and have no "EAN"
            #     print(f"INFO: Item with Index {item_id} was not ordered from 2021 to 2024 and has no 'EAN'. Going to continue with the next supplier item.")
            #     continue

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

            if purchase_uom in ['ul', 'ug', 'umol']:
                purchase_uom = purchase_uom.replace('u', 'µ')  # replace micro symbol
            if stock_uom in ['ul', 'ug', 'umol']:
                stock_uom = stock_uom.replace('u', 'µ')  # replace micro symbol
            if pack_uom in ['ul', 'ug', 'umol']:
                pack_uom = pack_uom.replace('u', 'µ')  # replace micro symbol
            if purchase_uom and purchase_uom not in known_uoms:
                print(f"ERROR: Item with Index {item_id} has unknown Purchase UOM '{purchase_uom}'. Going to continue with the next supplier item.")
                continue
            if stock_uom and stock_uom not in known_uoms:
                print(f"ERROR: Item with Index {item_id} has unknown Stock UOM '{stock_uom}'. Going to continue with the next supplier item.")
                continue
            if pack_uom == 'Units':
                pack_uom = 'Reaction Units'
            if pack_uom and pack_uom not in known_uoms:
                print(f"ERROR: Item with Index {item_id} has unknown Pack UOM '{pack_uom}'. Going to continue with the next supplier item.")
                continue
            if purchase_uom and stock_uom and purchase_uom != stock_uom:
                if not unit_size:
                    print(f"ERROR: Item with Index {item_id} has different Purchase UOM '{purchase_uom}' and Stock UOM '{stock_uom}', but no Unit Size given. Going to continue with the next supplier item.")
                    continue
                try:
                    unit_size = float(unit_size)
                except Exception as err:
                    print(f"ERROR: Item with Index {item_id} ('{item_name}'): Unable to convert {unit_size=} to a float ({err}). Going to continue with the next supplier item.")
                    continue
                if unit_size <= 0:
                    print(f"ERROR: Item with Index {item_id} ('{item_name}'): Invalid {unit_size=} <= 0. Going to continue with the next supplier item.")
                    continue

            if currency == "£":
                currency = "GBP"
            if purchase_price:
                try:
                    purchase_price = float(purchase_price)
                except Exception as err:
                    print(f"ERROR: Item with Index {item_id} ('{item_name}'): Unable to convert {purchase_price=} to a float ({err}). Going to continue with the next supplier item.")
                    continue
            if pack_size:
                try:
                    pack_size = float(pack_size)
                except Exception as err:
                    print(f"ERROR: Item with Index {item_id} ('{item_name}'): Unable to convert {pack_size=} to a float ({err}). Going to continue with the next supplier item.")
                    continue
            if pack_uom and not pack_size or pack_size and not pack_uom:
                print(f"WARNING: Got Pack Size '{pack_size}' but Pack UOM '{pack_uom}' for Item with Index {item_id} ('{item_name}').")
            if pack_uom and pack_size and pack_size != 1.0 and pack_uom in (stock_uom, purchase_uom):
                print(f"WARNING: Pack UOM {pack_uom} equals stock UOM {stock_uom} or purchase UOM {purchase_uom}, but Pack Size is {pack_size} for Item with Index {item_id} ('{item_name}').")
            try:
                location = get_or_create_location(floor, room, destination, fridge_rack, company=company)
            except Exception as err:
                print(f"ERROR: Item with Index {item_id} ('{item_name}'): Unable to get or create Location for {floor=}, {room=}, {destination=}, {fridge_rack=} ({err}). Going to continue with the next supplier item.")
                continue

            if len(item_name) > 140:
                print(f"WARNING: Item name '{item_name}' has {len(item_name)} characters. Going to shorten it to 140 characters.")

            shelf_life_in_days = None
            if shelf_life_in_years:
                try:
                    shelf_life_in_years = float(shelf_life_in_years)
                    shelf_life_in_days = int(shelf_life_in_years * 365)
                except Exception as err:
                    print(f"ERROR: Unable to convert {shelf_life_in_years=} into days ({err}).")

            if safety_stock:
                try:
                    safety_stock = float(safety_stock)
                except Exception as err:
                    print(f"ERROR: Item {item_id}: Unable to convert {safety_stock=} to a float.")

            if internal_code:
                item_code = f"P00{int(internal_code):0{4}d}"
            else:
                item_code = f"P01{int(item_id):0{4}d}"

            if frappe.db.exists("Item", item_code):
                existing_item_doc = frappe.get_doc("Item", item_code)
                existing_item_name = existing_item_doc.item_name
                if not update_existing_items:
                    if internal_code:
                        print(f"ERROR: Item with internal code {internal_code} and Supplier {supplier_index} already exists as Item {item_code} ('{existing_item_name}'). Going to skip import of Item with Index {item_id} ('{item_name}').")
                        continue
                    else:
                        print(f"ERROR: Item with 'Datensatznummer' {item_id} ('{item_name}') and Supplier {supplier_index} already exists as Item {item_code} ('{existing_item_name}'). Going to skip import.")
                        continue
                else:
                    # Update existing item fields as necessary
                    if stock_uom and existing_item_doc.stock_uom != stock_uom:
                        existing_item_doc.stock_uom = stock_uom
                        try:
                            existing_item_doc.save()
                        except Exception as err:
                            print(f"WARNING: Unable to update stock_uom of existing Item {item_code} for Item with Index {item_id} ('{item_name}'): {err}. Trying to update all other fields.")
                        finally:
                            existing_item_doc = frappe.get_doc("Item", item_code)  # re-fetch to avoid error "document has been modified after you have opened it"
                    if existing_item_doc.item_name != item_name:
                        existing_item_doc.item_name = item_name[:140]
                    if pack_size and existing_item_doc.pack_size != pack_size:
                        existing_item_doc.pack_size = pack_size
                    if pack_uom and existing_item_doc.pack_uom != pack_uom:
                        existing_item_doc.pack_uom = pack_uom
                    if purchase_uom and existing_item_doc.purchase_uom != purchase_uom:
                        existing_item_doc.purchase_uom = purchase_uom
                        if purchase_uom and stock_uom and purchase_uom != stock_uom and unit_size:
                            # add UOM conversion
                            existing_item_doc.append("uoms", {
                                'uom': purchase_uom,
                                'conversion_factor': unit_size
                            })
                    if existing_item_doc.description != item_name:
                        existing_item_doc.description = item_name
                    if existing_item_doc.shelf_life_in_days != shelf_life_in_days:
                        existing_item_doc.shelf_life_in_days = shelf_life_in_days
                    if safety_stock and existing_item_doc.safety_stock != safety_stock:
                        existing_item_doc.safety_stock = safety_stock
                    if material_code and existing_item_doc.material_code != material_code:
                        existing_item_doc.material_code = material_code
                    if supplier_quote and not existing_item_doc.internal_note:
                        existing_item_doc.internal_note = f"Supplier Quotation ID: {supplier_quote}"
                    if location and location.name:
                        # Check if location.name is already in Table MultiSelect field existing_item_doc.storage_locations with Options "Location Link".
                        # If not, add it. DocType "Location Link" has a Link field "location".
                        existing_locations = [row.location for row in existing_item_doc.get("storage_locations") or [] ]
                        # Add only if not present
                        if location.name not in existing_locations:
                            existing_item_doc.append("storage_locations", {
                                "location": location.name
                            })
                    # Check if there is already a matching Item Price. If not, create one
                    if purchase_price and currency and currency in SUPPORTED_BUYING_CURRENCIES:
                        existing_item_prices = frappe.get_all("Item Price", filters={
                                                        'item_code': item_code,
                                                        'price_list': f"Standard Buying {currency}",
                                                        'currency': currency,
                                                        'buying': 1
                                                    }, fields=['name'])
                        if len(existing_item_prices) == 0:
                            price_list_name = f"Standard Buying {currency}"
                            item_price = frappe.get_doc({
                                'doctype': "Item Price",
                                'item_code': item_code,
                                'price_list': price_list_name,
                                'price_list_rate': purchase_price,
                                'currency': currency,
                                # 'reference': supplier_quote,       # gets deleted on insert
                                # 'reference_name': supplier_quote,  # gets deleted on insert
                                'buying': 1
                            })
                            try:
                                item_price.insert()
                            except Exception as err:
                                print(f"ERROR: Unable to insert Price List Rate for Item with Index {item_id} ('{item_name}') in Price List '{price_list_name}' ({err}).")
                    try:
                        existing_item_doc.save()
                    except Exception as err:
                        print(f"ERROR: Unable to update existing Item {item_code} for Item with Index {item_id} ('{item_name}') ({err}). Going to continue with the next supplier item.")
                        continue
                    if not currency:
                        print(f"ERROR: Item with Index {item_id} ('{item_name}') has no currency. Unable to create an Item Price.")
                        continue
                    imported_counter += 1
                    print(f"INFO: Successfully updated existing Item '{existing_item_doc.item_name}' ({existing_item_doc.name}).")
                    if imported_counter % 1000 == 0:
                        frappe.db.commit()
                    continue

            item = frappe.get_doc({
                'doctype': "Item",
                'item_code': item_code,
                'item_name': item_name[:140],
                'item_group': 'Purchasing',
                'stock_uom': stock_uom or 'Pcs',
                'pack_size': pack_size or 1,
                'pack_uom': pack_uom or 'Pcs',
                'purchase_uom': purchase_uom or stock_uom or 'Pcs',
                'is_stock_item': 1,
                'description': item_name,
                'shelf_life_in_days': shelf_life_in_days,
                'safety_stock': safety_stock or 0.0,
                'is_purchase_item': 1,
                'is_sales_item': 0,
                'material_code': material_code or None,
                'internal_note': f"Supplier Quotation ID: {supplier_quote}" if supplier_quote else None
            })
            if location and location.name:
                # Add Location location.name to Table MultiSelect storage_locations
                item.append("storage_locations", {
                    "location": location.name
                })
            if supplier_index not in supplier_mapping:
                # Search for an existing Supplier with the supplier_index as external creditor number?
                existing_suppliers = frappe.get_all("Supplier", filters={'ext_creditor_id': supplier_index}, fields=['name'])
                if len(existing_suppliers) == 1:
                    print(f"WARNING: Found no Supplier with Index {supplier_index} in the supplier mapping file, but found one Supplier {existing_suppliers[0]['name']} with the same external creditor number. Going to use this Supplier for Item with Index {item_id} ({item.item_name}).")
                    supplier_mapping[supplier_index] = existing_suppliers[0]['name']
                elif len(existing_suppliers) > 1:
                    print(f"WARNING: Found no Supplier with Index {supplier_index} in the supplier mapping file, but found {len(existing_suppliers)} Suppliers with the same external creditor number. Unable to link a Supplier on Item with Index {item_id} ({item.item_name}).")
                else:
                    print(f"WARNING: Found no Supplier with Index {supplier_index}. Unable to link a Supplier on Item with Index {item_id} ({item.item_name}).")
            if supplier_index in supplier_mapping:
                item.append("supplier_items", {
                    'supplier': supplier_mapping[supplier_index],
                    'supplier_part_no': supplier_item_id,
                    'substitute_status': ''
                })
                if account:
                    item.item_defaults = []
                    item.append("item_defaults", {
                        'company': company,
                        'expense_account': account_name,
                        'default_supplier': supplier_mapping[supplier_index]
                    })
            if purchase_uom and stock_uom and purchase_uom != stock_uom and unit_size:
                # add UOM conversion
                item.append("uoms", {
                    'uom': purchase_uom,
                    'conversion_factor': unit_size
                })
            try:
                item.insert()
            except Exception as err:
                print(f"ERROR: Unable to insert Item with Index {item_id} ('{item_name}') ({err}). Going to continue with the next supplier item.")
                continue
            imported_counter += 1

            if purchase_price:
                if currency in SUPPORTED_BUYING_CURRENCIES:
                    # add it to the Price List "Standard Buying ..."
                    price_list_name = f"Standard Buying {currency}"
                    item_price = frappe.get_doc({
                        'doctype': "Item Price",
                        'item_code': item.item_code,
                        'price_list': price_list_name,
                        'price_list_rate': purchase_price,
                        'currency': currency,
                        # 'reference': supplier_quote,       # gets deleted on insert
                        # 'reference_name': supplier_quote,  # gets deleted on insert
                        'buying': 1
                    })
                    try:
                        item_price.insert()
                    except Exception as err:
                        print(f"ERROR: Unable to insert Price List Rate for Item with Index {item_id} ('{item_name}') in Price List '{price_list_name}' ({err}).")
                else:
                    print(f"ERROR: Item with Index {item_id} ('{item_name}'): Currency '{currency}' is not supported. Going to skip the creation of an Item Price.")

            # write mapping of ERP Item ID to FM Index (Datensatznummer) to a file
            with open(output_filepath, 'a') as txt_file:
                txt_file.write(f"{item.name};{item_id}\n")
            print(f"INFO: Successfully imported Item '{item.item_name}' ({item.name}).")
            if imported_counter % 1000 == 0:
                frappe.db.commit()
        print(f"INFO: Successfully imported {imported_counter}/{total_counter} Items.")


def import_suppliers(input_filepath, output_filepath, our_company='Microsynth AG', expected_line_length=41, update_countries=False, add_ext_creditor_id=False):
    """
    Seqlab:
    bench execute microsynth.microsynth.purchasing.import_suppliers --kwargs "{'input_filepath': '/mnt/erp_share/JPe/Supplier/20241105_Lieferantenexport_Seqlab.csv', 'output_filepath': '/mnt/erp_share/JPe/2025-11-27_2_supplier_mapping_Seqlab_DEV-ERP.txt', 'our_company': 'Microsynth Seqlab GmbH'}"

    AG:
    bench execute microsynth.microsynth.purchasing.import_suppliers --kwargs "{'input_filepath': '/mnt/erp_share/Migration/Purchasing/2025-12-01_Lieferanten_Adressen_Microsynth_AG.csv', 'output_filepath': '/mnt/erp_share/Migration/Purchasing/2025-12-01_supplier_mapping_Microsynth_AG.txt', 'our_company': 'Microsynth AG'}"
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
            skonto = line[18].strip()  # imported as text into "Supplier Details"
            payment_days = str(line[19].strip())
            currency = line[20].strip()
            reliability = line[21].strip()  # imported as text into "Supplier Details"
            phone_note = line[22].strip()  # imported as text into "Supplier Details"
            notes = line[23].strip()  # imported as text into "Supplier Details"
            bic = line[24].strip()
            iban = line[25].strip()
            #bank_name = line[26].strip()  # do not import
            contact_person_1 = line[27].strip()
            email_1 = line[28].strip()
            notes_1 = line[29].strip()
            contact_person_2 = line[30].strip()
            email_2 = line[31].strip()
            notes_2 = line[32].strip()
            contact_person_3 = line[33].strip()
            email_3 = line[34].strip()
            notes_3 = line[35].strip()
            discount = line[36].strip()  # imported as text into "Supplier Details"
            threshold = line[37].strip()  # imported as text into "Supplier Details"
            small_qty_surcharge = line[38].strip()  # imported as text into "Supplier Details"
            transportation_costs = line[39].strip()  # imported as text into "Supplier Details"
            ext_creditor_number = line[40].strip()
            #print(f"INFO: Processing Supplier with Index {ext_creditor_number} (external creditor number) ...")

            # combine/edit some values
            if company_addition and company:
                company = f"{company} - {company_addition}"
            elif company_addition:
                company = company_addition
            company = company.replace('\n', ' ').replace('\r', '')
            details = ""
            if reliability:
                details += f"Zuverlässigkeit: {reliability}\n"
            if phone_note:
                details += f"Phone Note: {phone_note}\n"
            if notes:
                details += f"Notes: {notes}"
            if discount:
                details += f"\nKundenrabatt: {discount}"
            if skonto:
                details += f"\nSkonto: {skonto}"
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
            if salutation:
                if salutation == 'Frau':
                    salutation = 'Ms.'
                elif salutation == 'Herr':
                    salutation = 'Mr.'
                if salutation not in ('Ms.', 'Mr.'):
                    print(f"WARNING: Salutation '{salutation}' is not in the list of allowed salutations ('Frau', 'Herr', 'Ms.', 'Mr.'), going to ignore salutation of {ext_creditor_number}.")
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
            if currency not in SUPPORTED_BUYING_CURRENCIES:
                print(f"WARNING: There is no Standard Buying Price List in Currency '{currency}'. Not going to set a default Price List for {ext_creditor_number}.")
            existing_suppliers = frappe.get_all("Supplier", filters=[['supplier_name', '=', company]], fields=['name', 'ext_creditor_id'])
            if existing_suppliers and (not (update_countries or add_ext_creditor_id)) and len(existing_suppliers) > 0:
                # TODO: Try to update existing Supplier?
                print(f"ERROR: There exists already {len(existing_suppliers)} Supplier {','.join(s['name'] for s in existing_suppliers)} with the Supplier Name '{company}' and it has the External Creditor ID {','.join((s['ext_creditor_id'] or 'None') for s in existing_suppliers)}. Going to skip {ext_creditor_number}.")
                if len(existing_suppliers) == 1:
                    # write mapping of existing ERP Supplier ID to FM Index to a file
                    with open(output_filepath, 'a') as txt_file:
                        txt_file.write(f"{existing_suppliers[0]['name']};{ext_creditor_number}\n")
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

            if not web_url.startswith('http'):
                web_url = f'https://{web_url}'

            new_supplier = frappe.get_doc({
                'doctype': 'Supplier',
                'supplier_name': company,
                'supplier_group': 'All Supplier Groups',  # TODO?
                'website': web_url,
                'tax_id': supplier_tax_id,
                'default_currency': currency,
                'default_price_list': f'Standard Buying {currency}' if currency in SUPPORTED_BUYING_CURRENCIES else None,
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
                try:
                    new_address.insert()
                except Exception as err:
                    print(f"ERROR: Unable to insert an Address for Supplier with Index {ext_creditor_number}, skipping: {err}")
                else:
                    new_address.append("links", {
                        'link_doctype': 'Supplier',
                        'link_name': new_supplier.name
                    })
                    new_address.save()
                new_supplier.save()  # necessary to trigger set_default_payable_accounts (if country is Austria)
            elif city or pincode or address_line1 or post_box:
                print(f"WARNING: Ort, PLZ, Strasse or Postfach given, but missing required information (Land and Ort and Strasse or Postfach) to create an address for Supplier with Index {ext_creditor_number}.")

            if first_name or last_name or phone or email:
                if not (first_name or last_name or company):
                    print(f"WARNING: Got no first name, no second name and no company for Supplier with Index {ext_creditor_number}. Unable to import a Contact, going to continue.")
                    continue
                new_contact = frappe.get_doc({
                    'doctype': 'Contact',
                    'first_name': first_name or last_name or company,
                    'last_name': last_name if first_name else None,
                    'salutation': salutation
                })
                try:
                    new_contact.insert()
                except Exception as err:
                    print(f"ERROR: Unable to insert a Contact for Supplier with Index {ext_creditor_number}, skipping: {err}")
                else:
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
        return {'password': password, 'warning': f"The password does not match our security policy. Please change it to a strong password. Please do not use the company name inside the password. {strength['feedback']['warning'] or ''}"}
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
        return {'error': _("The new password does not match the security policy. Please try again with a strong password. Please do not use the company name inside the password.") + " " + (strength['feedback']['warning'] or "")}
    else:
        return {'success': True}


def mark_purchase_invoice_as_proposed(purchase_invoice):
    """
    bench execute microsynth.microsynth.purchasing.mark_purchase_invoices_as_proposed --kwargs "{'payment_proposal_id':'e9b1a13027'}"
    """

    pi = frappe.get_doc("Purchase Invoice", purchase_invoice)
    pi.is_proposed = True
    pi.save()
    print(f"Set {pi.name} to 'is proposed'")


def mark_purchase_invoices_as_proposed(payment_proposal_id):
    """
    bench execute microsynth.microsynth.purchasing.mark_purchase_invoices_as_proposed --kwargs "{'payment_proposal_id':'e9b1a13027'}"
    """
    payment_proposal = frappe.get_doc("Payment Proposal", payment_proposal_id)
    for i in payment_proposal.purchase_invoices:
        mark_purchase_invoice_as_proposed(i.purchase_invoice)


def mark_purchase_invoices_of_payment_propsals_as_proposed(payment_proposal_ids):
    """
    bench execute microsynth.microsynth.purchasing.mark_purchase_invoices_of_payment_propsals_as_proposed --kwargs "{'payment_proposal_ids':['e9b1a13027', 'e9b1a13027']}"
    """
    for pp_id in payment_proposal_ids:
        print(f"Process Payment Proposal {pp_id}")
        mark_purchase_invoices_as_proposed(pp_id)


@frappe.whitelist()
def get_batch_items(purchase_receipt):
    purchase_receipt_doc = frappe.get_doc("Purchase Receipt", purchase_receipt)
    batch_items = []

    for item in purchase_receipt_doc.items:
        item_doc = frappe.get_doc("Item", item.item_code)
        if item_doc.has_batch_no:
            batch_items.append({
                "idx": item.idx,
                "item_code": item.item_code,
                "item_name": item.item_name,
                "qty": item.qty,
                "existing_batch": item.batch_no,
                "new_batch_id": "",
                "new_batch_expiry": ""
            })
    return batch_items


@frappe.whitelist()
def create_batches_and_assign(purchase_receipt, batch_data):
    batch_data = json.loads(batch_data) if isinstance(batch_data, str) else batch_data
    purchase_receipt_doc = frappe.get_doc("Purchase Receipt", purchase_receipt)

    for row in batch_data:
        batch_no = row.get('existing_batch')
        if not batch_no and row.get('new_batch_id'):
            batch = frappe.new_doc("Batch")
            batch.batch_id = row['new_batch_id']
            batch.item = row['item_code']
            if row.get('new_batch_expiry'):
                batch.expiry_date = row['new_batch_expiry']
            batch.insert()
            batch_no = batch.name

        for item in purchase_receipt_doc.items:
            if str(item.idx) == str(row['idx']):
                item.batch_no = batch_no

    purchase_receipt_doc.save()


def import_supplier_prices(price_list_name, currency, column_assignment, input_filepath, expected_line_length=4, create_new_items=False, supplier_id=None, dry_run=True):
    """
    bench execute microsynth.microsynth.purchasing.import_supplier_prices --kwargs "{'price_list_name': 'PUR_Merck', 'currency': 'CHF', 'column_assignment': {'supplier_part_no': 0, 'item_name': 1, 'rate': 3}, 'input_filepath': '/mnt/erp_share/JPe/2025-06-04_PUR_Merck_prices.csv'}"
    """
    if type(column_assignment) == str:
        column_assignment = json.loads(column_assignment)
    if not 'supplier_part_no' in column_assignment or not 'rate' in column_assignment:
        print("Please provide the column index of supplier_part_no and rate in the column_assignment.")
        return
    if not frappe.db.exists('Price List', price_list_name):
        if dry_run:
            print(f"Would create enabled Buying Price List '{price_list_name}' with Currency {currency}.")
        else:
            price_list_doc = frappe.get_doc({
                'doctype': 'Price List',
                'price_list_name': price_list_name,
                'buying': 1,
                'selling': 0,
                'enabled': 1,
                'currency': currency
            }).insert()
            print(f"Create enabled Buying Price List '{price_list_doc.name}' with Currency {currency}.")
    else:
        print(f"Price List '{price_list_name}' already exists. Going to extend it.")
    with open(input_filepath) as file:
        print(f"INFO: Parsing Supplier prices from '{input_filepath}' ...")
        csv_reader = csv.reader(file, delimiter=";")
        next(csv_reader)  # skip header
        for line in csv_reader:
            if len(line) != expected_line_length:
                print(f"ERROR: Line '{line}' has length {len(line)}, but expected length {expected_line_length}. Going to continue.")
                continue
            supplier_part_no = line[int(column_assignment.get('supplier_part_no'))].strip()
            item_name = line[int(column_assignment.get('item_name'))].strip()
            rate = float(line[int(column_assignment.get('rate'))].strip().replace('’', ''))
            # try to find Item according to Supplier Part Number
            item_codes = frappe.get_all(
                "Item Supplier",
                filters={"supplier_part_no": supplier_part_no},
                fields=["parent"],  # 'parent' is the Item code
                distinct=True
            )
            # Extract the item codes from result
            item_code_list = [row["parent"] for row in item_codes]
            if len(item_code_list) == 0:
                if create_new_items:
                    if not dry_run:
                        item = frappe.get_doc({
                            'doctype': 'Item',
                            'item_code': get_next_purchasing_item_id(),
                            'item_name': item_name[:140],
                            'item_group': 'Purchasing',
                            'stock_uom': 'Pcs',
                            'is_stock_item': 1,
                            'description': item_name,
                            'is_purchase_item': 1,
                            'is_sales_item': 0,
                        })
                        if supplier_id:
                            item.append('supplier_items', {
                                'supplier': supplier_id,
                                'supplier_part_no': supplier_part_no,
                                'substitute_status': ''
                            })
                        item.insert()
                        item_code = item.item_code
                        print(f"Created the new Item {item_code} for the given Supplier Part Number '{supplier_part_no}' ({item_name[:140]})")
                    else:
                        print(f"Would create a new Item for the given Supplier Part Number '{supplier_part_no}' ({item_name[:140]})")
                else:
                    print(f"Found no Item for the given Supplier Part Number '{supplier_part_no}' and {create_new_items=}. Going to continue.")
                    continue
            elif len(item_code_list) > 1:
                print(f"Found the following {len(item_code_list)} Items for the given Supplier Part Number '{supplier_part_no}': {item_code_list}. Going to continue.")
                continue
            elif len(item_code_list) == 1:
                item_code = item_code_list[0]
            if dry_run:
                print(f"Would create an Item Price with the following properties: {item_code=}, {price_list_name=}, min_qty=1, {rate=}, {currency=}")
            else:
                item_price_doc = frappe.get_doc({
                    'doctype': 'Item Price',
                    'item_code': item_code,
                    'min_qty': 1,
                    'price_list': price_list_name,
                    'buying': 0,
                    'selling': 1,
                    'currency': currency,
                    'price_list_rate': rate
                })
                item_price_doc.insert()
                print(f"Created Item Price {item_price_doc.name} with the following properties: {item_code=}, {price_list_name=}, min_qty=1, {rate=}, {currency=}")


def get_customer_id_from_supplier(supplier_id, company):
    """
    bench execute microsynth.microsynth.purchasing.get_customer_id_from_supplier --kwargs "{'supplier_id': 'S-00631', 'company': 'Microsynth Seqlab GmbH'}"
    """
    supplier_doc = frappe.get_doc("Supplier", supplier_id)

    for shop in supplier_doc.supplier_shops:
        if shop.company == company:
            return shop.customer_id
    return None


def payment_proposal_after_insert(payment_proposal, event):
    update_required = False
    for p in payment_proposal.purchase_invoices:

        if p.grand_total != p.amount:
            query = """
                SELECT `reference_type`, `reference_name`
                FROM `tabPurchase Invoice Advance`
                WHERE `parent` = %(purchase_invoice)s
                AND `reference_type` = "Journal Entry"
                """
            advances = frappe.db.sql(query, { "purchase_invoice": p.purchase_invoice }, as_dict=True)

            if len(advances) > 0:
                for a in advances:
                    jv_query = """
                        SELECT
                            `tabJournal Entry Account`.`reference_name`,
                            `tabPurchase Invoice`.`bill_no`
                        FROM `tabJournal Entry Account`
                        LEFT JOIN `tabPurchase Invoice` ON `tabPurchase Invoice`.`name` = `tabJournal Entry Account`.`reference_name`
                        WHERE `tabJournal Entry Account`.`parent` = %(journal_entry)s
                        AND `tabJournal Entry Account`.`reference_name` <> %(purchase_invoice)s
                        AND `tabJournal Entry Account`.`reference_type` = "Purchase Invoice"
                        """
                    references = frappe.db.sql(jv_query, {"journal_entry": a.get('reference_name'), "purchase_invoice": p.purchase_invoice}, as_dict=True)
                    if len(references) > 0:
                        p.external_reference = p.external_reference + "," + ",".join( [r.get("bill_no") for r in (references or []) ] )
                        update_required = True

    if update_required:
        payment_proposal.save()


@frappe.whitelist()
def has_available_advances(purchase_invoice_id):
    """
    Returns true if there are advances available for the given Purchase Invoice ID or the given Purchase Invoice ID is an advance itself.

    bench execute microsynth.microsynth.purchasing.has_available_advances --kwargs "{'purchase_invoice_id': 'PI-2500770'}"
    """
    try:
        pi = frappe.get_doc("Purchase Invoice", purchase_invoice_id)

        advances = pi.get_advance_entries()

        return len(advances) > 0

    except Exception as err:
        frappe.log_error(f"{err}\n\n{frappe.get_traceback()}", "purchasing.has_available_advances")
        return False


@frappe.whitelist()
def get_purchasing_items(item_name_part=None, material_code=None, supplier_name=None, supplier_part_no=None):
    # List to build WHERE clause conditions
    filters = []
    values = {}

    # Filter: partial match on item_name
    if item_name_part:
        filters.append('`tabItem`.`item_name` LIKE %(item_name_part)s')
        values['item_name_part'] = f'%{item_name_part}%'

    # Filter: partial match on material_code
    if material_code:
        filters.append('`tabItem`.`material_code` LIKE %(material_code)s')
        values['material_code'] = f'%{material_code}%'

    # Filter: partial match on supplier_name
    if supplier_name:
        filters.append('`tabSupplier`.`supplier_name` LIKE %(supplier_name)s')
        values['supplier_name'] = f'%{supplier_name}%'

    # Filter: partial match on supplier_part_no
    if supplier_part_no:
        filters.append('`tabItem Supplier`.`supplier_part_no` LIKE %(supplier_part_no)s')
        values['supplier_part_no'] = f'%{supplier_part_no}%'

    # Only include active items from 'Purchasing' item group
    filters.append('`tabItem`.`item_group` = "Purchasing"')
    filters.append('`tabItem`.`disabled` = 0')

    # Combine all WHERE conditions
    where_clause = ' AND '.join(filters)

    # SQL query joins Item with Supplier and Item Supplier tables
    # Aggregates supplier data per item (MIN used to get the first entry per group)
    query = f"""
        SELECT
            `tabItem`.`name`,
            `tabItem`.`item_name`,
            `tabItem`.`pack_size`,
            `tabItem`.`pack_uom`,
            `tabItem`.`stock_uom`,
            `tabItem`.`purchase_uom`,
            `tabItem`.`lead_time_days`,
            ROUND(`tabItem`.`last_purchase_rate`, 2) AS `last_purchase_rate`,
            CASE
                WHEN `tabItem`.`stock_uom` IS NOT NULL
                    AND `tabItem`.`purchase_uom` IS NOT NULL
                    AND `tabItem`.`stock_uom` <> `tabItem`.`purchase_uom`
                THEN (
                    SELECT `tabUOM Conversion Detail`.`conversion_factor`
                    FROM `tabUOM Conversion Detail`
                    WHERE
                        `tabUOM Conversion Detail`.`parent` = `tabItem`.`name`
                        AND `tabUOM Conversion Detail`.`uom` = `tabItem`.`purchase_uom`
                    LIMIT 1
                )
                ELSE 1
            END AS `conversion_factor`,
            `tabItem`.`material_code`,
            MIN(`tabItem Supplier`.`supplier`) AS `supplier`,
            MIN(`tabSupplier`.`supplier_name`) AS `supplier_name`,
            MIN(`tabItem Supplier`.`supplier_part_no`) AS `supplier_part_no`,
            last_po.last_order_date AS last_order_date
        FROM `tabItem`
        LEFT JOIN `tabItem Supplier` ON `tabItem Supplier`.`parent` = `tabItem`.`name`
        LEFT JOIN `tabSupplier` ON `tabSupplier`.`name` = `tabItem Supplier`.`supplier`
        LEFT JOIN (
            SELECT
                poi.item_code,
                MAX(po.transaction_date) AS last_order_date
            FROM `tabPurchase Order Item` poi
            INNER JOIN `tabPurchase Order` po
                ON po.name = poi.parent
            WHERE po.docstatus = 1
            GROUP BY poi.item_code
        ) last_po
            ON last_po.item_code = `tabItem`.`name`
        WHERE {where_clause}
        GROUP BY `tabItem`.`name`
        LIMIT 10
    """
    items = frappe.db.sql(query, values, as_dict=True)
    return items


def send_material_request_owner_emails(doc, event=None):
    """
    Send emails to each Material Request owner listing items received on this Purchase Receipt.
    Priority for effective owner:
      1. Material Request.requested_by
      2. Item Request.owner
      3. Material Request.owner
    """
    owner_map = {}

    # Collect unique material requests from items
    material_requests = list({item.material_request for item in doc.items if item.material_request})
    if not material_requests:
        return

    # Fetch Material Requests and their requested_by + owner
    mr_owners = frappe.get_all('Material Request',
        filters={'name': ['in', material_requests]},
        fields=['name', 'requested_by', 'owner'])
    mr_owner_map = {mr.name: {'requested_by': mr.requested_by, 'owner': mr.owner} for mr in mr_owners}

    # Fetch Item Requests linked to those Material Requests
    item_requests = frappe.get_all('Item Request',
        filters={'material_request': ['in', material_requests]},
        fields=['material_request', 'owner'])

    # Build Item Request owner map: Material Request → Item Request Owner
    item_request_owner_map = {ir.material_request: ir.owner for ir in item_requests}

    # Determine effective owner using priority: requested_by → Item Request.owner → MR.owner
    effective_owner_map = {}
    for mr in material_requests:
        mr_info = mr_owner_map.get(mr, {})
        requested_by = mr_info.get('requested_by')
        mr_owner = mr_info.get('owner')
        item_request_owner = item_request_owner_map.get(mr)
        # Priority: requested_by > item_request_owner > mr_owner
        effective_owner_map[mr] = requested_by or item_request_owner or mr_owner

    # Group items by effective owner
    for item in doc.items:
        mr = item.material_request
        if not mr:
            continue
        owner = effective_owner_map.get(mr)
        if not owner:
            continue
        if owner not in owner_map:
            owner_map[owner] = []
        owner_map[owner].append(item)

    # Send email to each effective owner
    for mr_owner, items in owner_map.items():
        if doc.owner == mr_owner:
            # Skip sending email to the owner of the Purchase Receipt
            continue
        user = frappe.get_doc("User", mr_owner)
        email = user.email or mr_owner
        # TODO: Create Email Template later
        subject = f"Items Received for Your Request(s) - Purchase Receipt {doc.name}"
        message = f"<p>Dear {user.full_name or mr_owner},</p>"
        message += f"<p>The following items from your Item or Material Request(s) have been received in Purchase Receipt <a href='{get_url_to_form('Purchase Receipt', doc.name)}'>{doc.name}</a>:</p><ul>"
        for i in items:
            message += f"<li><b>{i.item_name or '-'}</b> ({i.item_code or '-'}) - Quantity: {i.qty}</li>"
        message += "</ul><p>Best regards,<br>Your ERP System</p>"

        # Send email
        make(
            recipients=[email],
            sender=frappe.session.user,
            subject=subject,
            content=message,
            send_email=True
        )


@frappe.whitelist()
def create_material_request(item_code, qty, schedule_date, company, item_name=None, rate=0, currency=None, comment=None, requested_by=None):
    if not (item_code and qty and schedule_date and company):
        frappe.throw("Required parameters missing")
    mr = frappe.new_doc("Material Request")
    mr.material_request_type = "Purchase"
    mr.transaction_date = today()
    mr.schedule_date = schedule_date
    mr.company = company
    mr.comment = comment
    mr.requested_by = requested_by
    # get default supplier from Item and its default currency
    supplier = None
    supplier_currency = None
    item_doc = frappe.get_doc("Item", item_code)
    if len(item_doc.supplier_items) == 1:
        entry = item_doc.supplier_items[0]
        supplier = entry.supplier
        supplier_currency = frappe.get_value("Supplier", supplier, "default_currency")
    elif len(item_doc.supplier_items) > 1:
        for entry in item_doc.supplier_items:
            if not entry.substitute_status or (entry.substitute_status and entry.substitute_status == "Verified"):
                supplier = entry.supplier
                supplier_currency = frappe.get_value("Supplier", supplier, "default_currency")
                break
        if not supplier:
            entry = item_doc.supplier_items[0]
            supplier = entry.supplier
            supplier_currency = frappe.get_value("Supplier", supplier, "default_currency")
            frappe.log_error(f"Item {item_code} has multiple suppliers but none marked as 'Verified'. Using first supplier {supplier}.", "purchasing.create_material_request")
    else:
        frappe.throw(f"Item {item_code} is not assigned to any Supplier, unable to create a Material Request. Please contact the purchasing department.")
    if (not currency or not rate) and supplier_currency:
        currency = supplier_currency
    elif supplier and supplier_currency and currency and supplier_currency != currency:
        frappe.throw(f"Currency mismatch: Item {item_code} belongs to Supplier {supplier} with currency {supplier_currency} and cannot be purchased in currency {currency}.")
    elif not currency:
        currency = frappe.get_value("Company", company, "default_currency")
    mr.append("items", {
        "item_code": item_code,
        "item_name": item_name,
        "qty": qty,
        "schedule_date": schedule_date,
        "rate": rate,
        "item_request_currency": currency
    })
    mr.insert()
    mr.submit()
    return mr.name


@frappe.whitelist()
def create_mr_from_item_request(item_request_id, item):
    """
    Create a Material Request from an Item Request.
    Link the created Material Request on the Item Request.
    Set the status of the Item Request to 'Done'.
    """
    try:
        item = frappe._dict(json.loads(item))
        mr_id = create_material_request(item.item_code, item.qty, item.schedule_date, item.company, item_name=item.item_name, rate=item.rate, currency=item.currency, comment=item.comment, requested_by=item.requested_by)
        # Link back to Item Request
        ir = frappe.get_doc('Item Request', item_request_id)
        ir.material_request = mr_id
        ir.material_request_item = item.item_code
        ir.status = 'Done'
        ir.save()
        return mr_id
    except Exception as err:
        frappe.log_error(f"{err}\n\n{frappe.get_traceback()}", "purchasing.create_mr_from_item_request")
        frappe.throw(f"Error creating Material Request from Item Request {item_request_id}: {err}")


@frappe.whitelist()
def check_unbatched_items(item_codes):
    """
    Returns a list of item codes where:
    - has_batch_no = 0
    - AND they were never submitted on a Purchase Receipt
    """
    if isinstance(item_codes, str):
        try:
            item_codes = json.loads(item_codes)
        except json.JSONDecodeError:
            frappe.throw("Invalid item_codes format. Must be JSON list.")

    items_to_confirm = []

    for item_code in item_codes:
        if not item_code:
            continue  # skip empty item codes

        # Use get_value instead of get_doc to avoid DoesNotExistError
        has_batch_no = frappe.db.get_value("Item", item_code, "has_batch_no")

        if has_batch_no is None:
            # Item does not exist — optionally skip or log
            frappe.log_error(f"Item not found: {item_code}", "Batch Validation")
            continue  # or raise exception if strict

        if has_batch_no:
            continue  # batching already enabled, skip

        # Check if it was ever submitted
        submitted = frappe.db.exists({
            "doctype": "Purchase Receipt Item",
            "item_code": item_code,
            "docstatus": 1
        })

        if not submitted:
            items_to_confirm.append(item_code)

    return items_to_confirm


@frappe.whitelist()
def get_inbound_freight_item():
    """
    Returns the Item Code for the Inbound Freight Item.
    """
    item_code = frappe.get_value("Microsynth Settings", "Microsynth Settings", "inbound_freight_item")
    if not item_code:
        frappe.throw("No Inbound Freight Item found. Please set it in the Microsynth Settings.")
    return item_code


@frappe.whitelist()
def get_purchase_tax_template(supplier, company):
    """
    bench execute microsynth.microsynth.purchasing.get_purchase_tax_template --kwargs "{'supplier': 'S-01460', 'company': 'Microsynth AG'}"
    """
    # TODO implement fallback, see also batch_invoice_processing.create_invoice (settings --> Batch Invoice Process Settings)
    # Algorithmus
    # * Assumption: use for materials because it's in the long process with material requests
    # * check first if there is a setting on the supplier
    # * else use tax matrix
    #    * Material/Service <- Item.is_stock_item (use first item, validate the item group?)
    tax_templates = frappe.get_all("Party Account",
        filters={
            'parent': supplier,
            'parenttype': "Supplier",
            'company': company
        },
        fields=['name', 'default_tax_template']
    )
    if len(tax_templates) > 0:
        return tax_templates[0]['default_tax_template']
    else:
        return None


@frappe.whitelist()
def check_po_item_prices(purchase_order_name):
    """
    Return suggested item prices to add or update based on PO data.
    """
    po = frappe.get_doc("Purchase Order", purchase_order_name)
    precision = int(frappe.db.get_single_value("System Settings", "currency_precision") or 2)

    if not po.buying_price_list:
        return {"status": "no_price_list"}

    price_list = po.buying_price_list
    price_list_currency = frappe.db.get_value("Price List", price_list, "currency")
    if price_list_currency != po.currency:
        return {
            "status": "currency_mismatch",
            "price_list_currency": price_list_currency,
        }

    add_list, update_list = [], []

    for item in po.items:
        if not item.item_code:
            continue
        if item.item_code == "P020000":  # skip Inbound Freight Item
            continue

        # Fetch all existing prices for this Item & Price List
        item_prices = frappe.get_all(
            "Item Price",
            filters=[["price_list", "=", price_list], ["item_code", "=", item.item_code], ["min_qty", "<=", item.qty]],
            fields=["name", "min_qty", "price_list_rate"],
            order_by="min_qty desc",
        )

        if not item_prices:
            # Suggest to add a new Item Price
            add_list.append({
                "item_code": item.item_code,
                "item_name": item.item_name,
                "min_qty": 1,
                "current_rate": None,
                "rate": flt(item.rate, precision),
            })
            continue

        current_price = item_prices[0]

        diff = abs(flt(current_price.price_list_rate - item.rate, precision))
        if diff > 0.01:
            current_rate = flt(current_price.price_list_rate, precision)
            new_rate = flt(item.rate, precision)
            rate_diff_pct = ((new_rate - current_rate) / current_rate * 100) if current_rate else 0
            update_list.append({
                "item_code": item.item_code,
                "item_name": item.item_name,
                "min_qty": current_price.min_qty,
                "current_rate": current_rate,
                "rate": new_rate,
                "rate_diff_pct": flt(rate_diff_pct, 2)
            })

    return {"status": "ok", "adds": add_list, "updates": update_list}


@frappe.whitelist()
def apply_item_price_changes(price_list, adds, updates):
    """
    Apply user-approved Add and Update operations on Item Prices.
    """
    adds = json.loads(adds)
    updates = json.loads(updates)

    price_list_doc = frappe.get_doc("Price List", price_list)

    if not price_list_doc.enabled:
        frappe.throw(f"The selected Price List {price_list} is disabled. Unable to add or update Item Prices.")

    if not price_list_doc.buying:
        frappe.throw(f"The selected Price List {price_list} is not configured for buying/purchasing. Unable to add or update Item Prices.")

    for entry in adds:
        doc = frappe.new_doc("Item Price")
        doc.item_code = entry["item_code"]
        doc.price_list = price_list
        doc.min_qty = flt(entry["min_qty"])
        doc.price_list_rate = flt(entry["rate"])
        doc.selling = 0
        doc.buying = 1
        doc.save(ignore_permissions=True)

    for entry in updates:
        ip = frappe.get_all(
            "Item Price",
            filters={
                "price_list": price_list,
                "item_code": entry["item_code"],
                "min_qty": entry["min_qty"]
            },
            limit=1,
        )
        if ip:
            doc = frappe.get_doc("Item Price", ip[0].name)
            doc.price_list_rate = flt(entry["rate"])
            doc.save(ignore_permissions=True)

    frappe.db.commit()
    return {"status": "done"}


@frappe.whitelist()
def get_location_path_string(location_name):
    """
    Return the human-readable Location path for a given Location.

    Skips the root "All Locations".
    Maps the second-level node to its code (BAL, GOE, LYO, WIE).
    Other levels are kept as their Location name.

    bench execute microsynth.microsynth.purchasing.get_location_path_string --kwargs "{'location_name': 'Balgach'}"
    """
    # Map second-level location nodes to abbreviations
    SECOND_LEVEL_MAP = {
        "Balgach": "BAL",
        "Göttingen": "GOE",
        "Lyon": "LYO",
        "Wien": "WIE",
    }

    if not location_name:
        return ""

    cache = frappe.cache()

    # Try cache first
    cache_key = f"location_path::{location_name}"
    cached = cache.get_value(cache_key)
    if cached:
        return cached

    # Get the Location doc
    loc = frappe.get_doc("Location", location_name)

    # Get the full tree path (List of ancestor names)
    # This includes the root "All Locations"
    ancestors = frappe.get_all(
        "Location",
        filters={"lft": ["<=", loc.lft], "rgt": [">=", loc.rgt]},
        fields=["name"],
        order_by="lft asc"
    )
    # Extract as list of names
    path = [a["name"] for a in ancestors]

    # Remove the top-level root
    if path and path[0] == "All Locations":
        path = path[1:]

    if not path:
        return ""

    # Map second level if applicable
    if len(path) >= 1:
        first = path[0]
        path[0] = SECOND_LEVEL_MAP.get(first, first)

    path_str = " / ".join(path)

    # Store in cache
    cache.set_value(cache_key, path_str)

    return path_str


@frappe.whitelist()
def add_location_to_item(item, location):
    """
    Adds a row to the Table MultiSelect 'storage_locations' using child DocType 'Location Link'.
    """
    if not item or not location:
        return

    doc = frappe.get_doc("Item", item)

    # Check if location already exists
    existing = {row.location for row in doc.get("storage_locations")}
    if location in existing:
        return

    doc.append("storage_locations", {"location": location})
    doc.save()


@frappe.whitelist()
def check_existing_supplier(supplier_name):
    supplier = frappe.db.get_value("Supplier", {"supplier_name": supplier_name}, "name")
    return {
        "exists": bool(supplier),
        "supplier": supplier
    }


@frappe.whitelist()
def create_supplier(data):
    # ensure JSON string is converted to dict
    if isinstance(data, str):
        data = json.loads(data)
    data = frappe._dict(data)

    # Duplicate check at creation time
    existing = frappe.db.get_value("Supplier", {"supplier_name": data.supplier_name}, "name")
    if existing:
        frappe.throw(f"A Supplier with this name already exists: <b>{existing}</b>")

    default_price_list = None
    if frappe.db.exists("Price List", f"Standard Buying {data.billing_currency}"):
        default_price_list = f"Standard Buying {data.billing_currency}"

    supplier = frappe.get_doc({
        "doctype": "Supplier",
        "supplier_name": data.supplier_name,
        "country": data.country,
        "tax_id": data.get("tax_id"),
        "default_currency": data.billing_currency,
        "default_price_list": default_price_list
    })
    if data.get("webshop_url"):
        supplier.append("supplier_shops", {
            "company": data.get("webshop_company"),
            "webshop_url": data.get("webshop_url")
        })
    supplier.insert()

    address = frappe.get_doc({
        "doctype": "Address",
        "address_title": supplier.supplier_name,
        "address_line1": data.address_line1,
        "address_line2": data.get("address_line2"),
        "city": data.city,
        "pincode": data.get("postal_code"),
        "country": data.country,
        "is_primary_address": 1,
        "links": [{
            "link_doctype": "Supplier",
            "link_name": supplier.name,
            "link_title": supplier.supplier_name
        }]
    })
    address.insert()

    contact = frappe.get_doc({
        "doctype": "Contact",
        "first_name": data.first_name,
        "last_name": data.get("last_name"),
        "salutation": data.get("salutation"),
        "designation": data.get("title"),
        "address": address.name,
        "is_primary_contact": 1,
        "email_ids": [{
            "email_id": data.email,
            "is_primary": 1
        }],
        "phone_nos": [{
            "phone": data.get("phone"),
            "is_primary_phone": 1
        }],
        "links": [{
            "link_doctype": "Supplier",
            "link_name": supplier.name,
            "link_title": supplier.supplier_name
        }]
    })
    contact.insert()

    if frappe.get_meta("Supplier").has_field("order_contact"):
        frappe.db.set_value("Supplier", supplier.name, "order_contact", contact.name)

    frappe.db.commit()

    return {
        "supplier": supplier.name,
        "address": address.name,
        "contact": contact.name
    }


@frappe.whitelist()
def link_items_symmetrically(item_a, item_b):
    """
    Create symmetric links:
       A → B and B → A in child table Item.linked_items avoiding duplicates.
    """
    if item_a == item_b:
        frappe.throw("Cannot link an item with itself.")

    # Fetch both items
    doc_a = frappe.get_doc("Item", item_a)
    doc_b = frappe.get_doc("Item", item_b)

    # Helper to add a link if missing
    def add_link_if_missing(item_doc, other_item):
        exists = any(row.item == other_item for row in item_doc.get("linked_items"))
        if not exists:
            new_row = item_doc.append("linked_items", {})
            new_row.item = other_item
            # item_name, pack_size, pack_uom auto-populate via fetch_from
            item_doc.save()

    # Add A → B and B → A
    add_link_if_missing(doc_a, item_b)
    add_link_if_missing(doc_b, item_a)

    frappe.db.commit()
    return True


@frappe.whitelist()
def get_items_using_supplier(supplier):
    """
    Returns list of enabled Items that have this supplier in the Item Supplier table.

    bench execute microsynth.microsynth.purchasing.get_items_using_supplier --kwargs "{'supplier': 'S-00015'}"
    """
    return frappe.db.sql("""
        SELECT
            `tabItem`.`name`,
            `tabItem`.`item_name`,
            `tabItem`.`stock_uom`,
            `tabItem Supplier`.`supplier_part_no`
        FROM `tabItem Supplier`
        LEFT JOIN `tabItem` ON `tabItem`.`name` = `tabItem Supplier`.`parent`
        WHERE
            `tabItem Supplier`.`supplier` = %(supplier)s
            AND `tabItem`.`disabled` = 0
    """, {"supplier": supplier}, as_dict=True)


@frappe.whitelist()
def get_purchasing_price_context(item_code):
    """
    Returns the purchasing price context for the given Item Code.
    If there is exactly one supplier with a default price list, returns:
    - price_list
    - supplier
    - currency
    - existing_prices (list of dicts with min_qty and price_list_rate)
    Otherwise, returns None for price_list and supplier, and empty list for existing_prices.

    bench execute microsynth.microsynth.purchasing.get_purchasing_price_context --kwargs "{'item_code': 'P007494'}"
    """
    supplier_rows = frappe.db.sql(
        """
        SELECT
            `tabItem Supplier`.`supplier`,
            `tabSupplier`.`default_price_list`
        FROM
            `tabItem Supplier`
        INNER JOIN
            `tabSupplier`
            ON `tabSupplier`.`name` = `tabItem Supplier`.`supplier`
        WHERE
            `tabItem Supplier`.`parent` = %s
            AND `tabSupplier`.`default_price_list` IS NOT NULL
            AND `tabSupplier`.`default_price_list` != ''
        """,
        (item_code,),
        as_dict=True,
    )
    contexts = {
        (row.supplier, row.default_price_list)
        for row in supplier_rows
    }
    if len(contexts) != 1:
        return {
            "price_list": None,
            "supplier": None,
            "existing_prices": [],
            "currency": None,
        }
    supplier, price_list = contexts.pop()

    currency = frappe.db.get_value(
        "Price List",
        price_list,
        "currency"
    )
    existing_prices = frappe.db.sql(
        """
        SELECT
            `tabItem Price`.`min_qty`,
            `tabItem Price`.`price_list_rate`
        FROM
            `tabItem Price`
        WHERE
            `tabItem Price`.`item_code` = %s
            AND `tabItem Price`.`price_list` = %s
        ORDER BY
            `tabItem Price`.`min_qty`
        """,
        (item_code, price_list),
        as_dict=True,
    )
    return {
        "price_list": price_list,
        "supplier": supplier,
        "currency": currency,
        "existing_prices": existing_prices,
    }


@frappe.whitelist()
def add_or_update_item_price(item_code, price_list, min_qty, price_list_rate):
    """
    Add or update an Item Price with:
    - Explicit min_qty
    - Explicit price_list_rate
    - buying = 1 enforced
    """
    min_qty = int(min_qty)
    price_list_rate = float(price_list_rate)

    existing_name = frappe.db.get_value(
        "Item Price",
        {
            "item_code": item_code,
            "price_list": price_list,
            "min_qty": min_qty
        },
        "name",
    )
    if existing_name:
        doc = frappe.get_doc("Item Price", existing_name)
    else:
        doc = frappe.new_doc("Item Price")
        doc.item_code = item_code
        doc.price_list = price_list
        doc.min_qty = min_qty

    doc.price_list_rate = price_list_rate
    doc.buying = 1
    doc.flags.ignore_permissions = True
    doc.save()
    frappe.db.commit()
