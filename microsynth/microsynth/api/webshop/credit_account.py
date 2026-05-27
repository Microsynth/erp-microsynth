import frappe
import json
import base64
import traceback

from datetime import datetime

from microsynth.microsynth.utils import get_customer, get_alternative_account
from microsynth.microsynth.naming_series import get_naming_series
from microsynth.microsynth.credits import get_credit_account_balance
from microsynth.microsynth.invoicing import transmit_sales_invoice
from microsynth.microsynth.taxes import find_dated_tax_template


def get_product_types(account_id):
    """
    Get the product types linked to the given Credit Account.

    bench execute microsynth.microsynth.api.webshop.credit_account.get_product_types --kwargs "{'account_id': 'CA-000002'}"
    """
    product_types = frappe.get_all(
        "Product Type Link",
        filters={
            "parent": account_id,
            "parentfield": "product_types",
            "parenttype": "Credit Account"
        },
        fields=["product_type"]
    )
    return [pt["product_type"] for pt in product_types]


def get_open_sales_orders(credit_account_id):
    """
    Get all Sales Orders that are associated with the given Credit Account and are not yet fully billed.

    bench execute microsynth.microsynth.api.webshop.credit_account.get_open_sales_orders --kwargs "{'credit_account_id': 'CA-000002'}"
    """
    sql_query = """
        SELECT
            `tabSales Order`.`name`,
            `tabSales Order`.`net_total`,
            `tabSales Order`.`grand_total`,
            `tabSales Order`.`per_billed`,
            `tabSales Order`.`net_total` * (1 - `tabSales Order`.`per_billed` / 100) AS `unbilled_amount`,
            `tabSales Order`.`transaction_date`,
            `tabSales Order`.`contact_display`,
            `tabSales Order`.`status`,
            `tabSales Order`.`web_order_id`,
            `tabSales Order`.`currency`,
            `tabSales Order`.`product_type`,
            `tabSales Order`.`po_no`
        FROM
            `tabSales Order`
        JOIN
            `tabCredit Account Link`
            ON `tabCredit Account Link`.`parent` = `tabSales Order`.`name`
        WHERE
            `tabCredit Account Link`.`credit_account` = %s
            AND `tabSales Order`.`docstatus` = 1
            AND `tabSales Order`.`per_billed` < 100
            AND `tabSales Order`.`status` != 'Closed'
        ORDER BY `tabSales Order`.`transaction_date` ASC, `tabSales Order`.`creation` ASC
        """
    sales_orders = frappe.db.sql(sql_query, (credit_account_id,), as_dict=True)
    return sales_orders


def get_ca_forecast_balance(credit_account_doc, balance):
    """
    Calculate the forecast balance of the given Credit Account by considering unbilled Sales Orders.

    bench execute microsynth.microsynth.api.webshop.credit_account.get_ca_forecast_balance --kwargs "{'credit_account_doc': 'CA-000002', 'balance': 1000.0}"
    """
    if isinstance(credit_account_doc, str):
        credit_account_doc = frappe.get_doc("Credit Account", credit_account_doc)
    unbilled_sales_orders = get_open_sales_orders(credit_account_doc.name)
    if len(unbilled_sales_orders) > 0:
        total_unbilled_amount = sum(so.get('unbilled_amount', 0.0) for so in unbilled_sales_orders)
        forecast_balance = balance - total_unbilled_amount
    else:
        forecast_balance = balance
    return round(forecast_balance, 2)


def get_credit_account_dto(credit_account):
    """
    Takes a Credit Account DocType or dict and returns a data transfer object (DTO) suitable for the webshop.

    bench execute microsynth.microsynth.api.webshop.credit_account.get_credit_account_dto --kwargs "{'credit_account': 'CA-000002'}"
    """
    if isinstance(credit_account, str):
        credit_account = frappe.get_doc("Credit Account", credit_account)
    balance = get_credit_account_balance(credit_account.name)

    return {
        "account_id": credit_account.name,
        "type": credit_account.account_type,
        "name": credit_account.account_name,
        "description": credit_account.description,
        "webshop_account": credit_account.contact_person,
        "status": credit_account.status,
        "company": credit_account.company,
        "customer": credit_account.customer,
        "currency": credit_account.currency,
        "expiry_date": credit_account.expiry_date,
        "balance": round(balance, 2),
        "forecast_balance": get_ca_forecast_balance(credit_account, balance),
        "product_types": get_product_types(credit_account.name),
        "product_types_locked": credit_account.product_types_locked
    }


@frappe.whitelist()
def get_credit_accounts(webshop_account, workgroup_members):
    """
    Takes a webshop_account (Contact ID) and a list of workgroup_members (Contact IDs)
    and returns all Credit Accounts linked to any of these Contacts.

    Also includes all Credit Accounts with account_type='Legacy' of the Customer
    of the webshop_account (if not already included).

    bench execute microsynth.microsynth.webshop.get_credit_accounts --kwargs "{'webshop_account': '215856', 'workgroup_members': '["215856", "243755"]'}"
    """
    try:
        # Parse workgroup_members
        if isinstance(workgroup_members, str):
            workgroup_members = json.loads(workgroup_members)
        if webshop_account not in workgroup_members:
            workgroup_members.append(webshop_account)
        workgroup_members = [str(member) for member in workgroup_members]

        # Get the Customer linked to the webshop_account
        customer_id = get_customer(webshop_account)

        # Use a single SQL query to fetch both:
        #   1. Credit Accounts linked to any workgroup member contact
        #   2. Legacy Credit Accounts of the same Customer
        #   (avoid duplicates via DISTINCT)
        contacts = ', '.join(['%s'] * len(workgroup_members))
        params = workgroup_members.copy()

        sql = f"""
            SELECT DISTINCT
                name,
                account_name,
                description,
                status,
                company,
                currency,
                expiry_date,
                account_type,
                customer
            FROM `tabCredit Account`
            WHERE
                contact_person IN ({contacts})
                AND status != 'Disabled'
        """

        if customer_id:
            sql += " OR (customer = %s AND account_type = 'Legacy' AND status != 'Disabled')"
            params.append(customer_id)

        credit_accounts = frappe.db.sql(sql, params, as_dict=True)

        if not credit_accounts:
            return {
                "success": True,
                "message": f"No Credit Account found.",
                "internal_message": f"No Credit Account found for Contact '{webshop_account}'",
                "credit_accounts": []
            }
        # Build DTO list
        credit_accounts_to_return = [
            get_credit_account_dto(ca.get('name')) for ca in credit_accounts
        ]
        return {
            "success": True,
            "message": "OK",
            "internal_message": f"Fetched {len(credit_accounts)} Credit Accounts for webshop_account '{webshop_account}'.",
            "credit_accounts": credit_accounts_to_return
        }
    except Exception as err:
        msg = f"Error getting Credit Accounts for webshop_account '{webshop_account}': {err}. Check ERP Error Log for details."
        frappe.log_error(f"{msg}\n\n{traceback.format_exc()}", "webshop.get_credit_accounts")
        return {
            "success": False,
            "message": "Failed to get Credit Accounts.",
            "internal_message": msg,
            "credit_accounts": []
        }


@frappe.whitelist()
def create_credit_account(webshop_account, name, description, company, product_types):
    """
    Create a new Credit Account for the given webshop_account (Contact ID) with the given name, description, company and product types.

    bench execute microsynth.microsynth.api.webshop.credit_account.create_credit_account --kwargs "{'webshop_account': '215856', 'name': 'Test', 'description': 'some description', 'company': 'Microsynth AG', 'product_types': ['Oligos', 'Sequencing']}"
    """
    try:
        if isinstance(product_types, str):
            product_types = json.loads(product_types)

        customer_id = get_customer(webshop_account)

        credit_account = frappe.get_doc({
            'doctype': 'Credit Account',
            'contact_person': webshop_account,
            'customer': customer_id,
            'account_name': name,
            'description': description,
            'company': company,
            'currency': frappe.db.get_value('Customer', customer_id, 'default_currency'),
            'status': 'Active'
        })
        # Add product types
        for pt in product_types:
            credit_account.append("product_types", {
                "product_type": pt
            })
        credit_account.insert()
        return {
            "success": True,
            "message": "OK",
            "internal_message": f"Created Credit Account '{credit_account.name}' for webshop_account '{webshop_account}'.",
            "credit_account": get_credit_account_dto(credit_account)
        }
    except Exception as err:
        msg = f"Error creating Credit Account for webshop_account '{webshop_account}': {err}. Check ERP Error Log for details."
        frappe.log_error(f"{msg}\n\n{traceback.format_exc()}", "webshop.create_credit_account")
        return {
            "success": False,
            "message": "Failed to create Credit Account.",
            "internal_message": msg,
            "credit_accounts": []
        }


@frappe.whitelist()
def update_credit_account(credit_account):
    """
    Update the Credit Account with the given account_id (Credit Account name) with the given fields.
    Only the fields name, description, status, webshop_account (Contact ID) and product_types can be changed.

    "credit_account": {
        "account_id": "Account-000003",
        "name": "MyChangedName",
        "description": "some changed description",
        "status": "Disabled",
        "webshop_account": "215856" # to change the owner (ERP validates if it is the same customer),
        "product_types": ["Oligos", "Sequencing"] # not implemented yet
    }

    bench execute microsynth.microsynth.api.webshop.credit_account.update_credit_account --kwargs "{'credit_account': {'account_id': 'CA-000003', 'name': 'Changed Name', 'description': 'Changed Description', 'product_types': ['Oligos', 'Sequencing', 'NGS']}}"
    """
    try:
        credit_account_doc = frappe.get_doc('Credit Account', credit_account.get('account_id'))
        if 'name' in credit_account and credit_account.get('name') != credit_account_doc.account_name:
            credit_account_doc.account_name = credit_account.get('name')
        if 'description' in credit_account and credit_account.get('description') != credit_account_doc.description:
            credit_account_doc.description = credit_account.get('description')
        if 'status' in credit_account and credit_account.get('status') != credit_account_doc.status:
            if credit_account_doc.status == 'Disabled':
                frappe.throw(f"Not allowed to change status of Credit Account '{credit_account.get('account_id')}' because it is Disabled.")
            if credit_account.get('status') not in ['Active', 'Frozen', 'Disabled']:
                frappe.throw(f"Not allowed to change status of Credit Account '{credit_account.get('account_id')}' to '{credit_account.get('status')}'. Allowed values are 'Active', 'Frozen' and 'Disabled'.")
            if credit_account.get('status') == 'Disabled':
                # Only allow to disable a Credit Account if its balance is zero
                balance = get_credit_account_balance(credit_account.get('account_id'))
                if balance >= 0.01 or balance <= -0.01:
                    frappe.throw(f"Not allowed to change status of Credit Account '{credit_account.get('account_id')}' to 'Disabled' because its balance is not zero (balance: {balance}).")
            credit_account_doc.status = credit_account.get('status')
        if 'webshop_account' in credit_account and credit_account.get('webshop_account') != credit_account_doc.contact_person:
            # Change the owner of the credit account
            new_contact = credit_account.get('webshop_account')
            if not new_contact:
                frappe.throw(f"Not allowed to change owner of Credit Account '{credit_account.get('account_id')}' to empty value.")
            if not frappe.db.exists('Contact', new_contact):
                frappe.throw(f"Not allowed to change owner of Credit Account '{credit_account.get('account_id')}' to Contact '{new_contact}' that does not exist.")
            old_customer = get_customer(credit_account_doc.contact_person)
            new_customer = get_customer(new_contact)
            if old_customer != new_customer:
                frappe.throw(f"Not allowed to change owner of Credit Account '{credit_account.get('account_id')}' from Contact '{credit_account_doc.contact_person}' (Customer '{old_customer}') to Contact '{new_contact}' (Customer '{new_customer}') because they belong to different Customers.")
            credit_account_doc.contact_person = new_contact
        if 'product_types' in credit_account:
            if not isinstance(credit_account.get('product_types'), list):
                new_product_types = json.loads(credit_account.get('product_types'))
            else:
                new_product_types = credit_account.get('product_types')
            if set(new_product_types) != set(get_product_types(credit_account.get('account_id'))):
                if credit_account_doc.product_types_locked:
                    frappe.throw(f"Not allowed to change product types of Credit Account '{credit_account.get('account_id')}' because it is locked for editing by the webshop.")
                # Remove all existing product types
                credit_account_doc.product_types = []
                # Add new product types
                for pt in new_product_types:
                    credit_account_doc.append("product_types", {
                        "product_type": pt
                    })
        if 'company' in credit_account and (credit_account.get('company') != credit_account_doc.company or credit_account_doc.has_transactions):
            frappe.throw(f"Not allowed to change company of Credit Account '{credit_account.get('account_id')}'.")
        if 'customer' in credit_account and (credit_account.get('customer') != get_customer(credit_account_doc.contact_person) or credit_account_doc.has_transactions):
            frappe.throw(f"Not allowed to change customer of Credit Account '{credit_account.get('account_id')}'.")
        if 'currency' in credit_account and (credit_account.get('currency') != credit_account_doc.currency or credit_account_doc.has_transactions):
            frappe.throw(f"Not allowed to change currency of Credit Account '{credit_account.get('account_id')}'.")
        credit_account_doc.save()
        return {
            "success": True,
            "message": "OK",
            "internal_message": f"Updated Credit Account '{credit_account.get('account_id')}'.",
            "credit_account": get_credit_account_dto(credit_account_doc)
        }
    except Exception as err:
        msg = f"Error updating Credit Account '{credit_account.get('account_id')}': {err}. Check ERP Error Log for details."
        frappe.log_error(f"{msg}\n\n{traceback.format_exc()}", "webshop.update_credit_account")
        return {
            "success": False,
            "message": "Error updating Credit Account",
            "internal_message": msg,
            "credit_accounts": []
        }


# TODO: move this function to a more suitable place
def get_default_shipping_address(webshop_address_id):
    """
    Get the default shipping address of the given Webshop Address.

    bench execute microsynth.microsynth.api.webshop.credit_account.get_default_shipping_address --kwargs "{'webshop_address_id': '215856'}"
    """
    webshop_address_doc = frappe.get_doc("Webshop Address", webshop_address_id)
    for a in webshop_address_doc.addresses:
        if a.is_default_shipping and not a.disabled:
            return frappe.get_value("Contact", a.contact, "address")
    return None


# TODO: move the core of this function to a more suitable place and split it into smaller functions if necessary
@frappe.whitelist()
def create_deposit_invoice(webshop_account, account_id, amount, currency, description, company, customer, customer_order_number, ignore_permissions=False, transmit_invoice=True, allow_recharge=False):
    """
    Create a Sales Invoice to deposit customer credits.

    Request:
    {
        "webshop_account": "215856",
        "account_id": "CA-000003",
        "amount": "1000.00",
        "currency": "CHF",
        "description": "Cloning Primers",
        "company": "Microsynth AG",
        "customer": "801234",
        "customer_order_number": "PO-12345"
    }
    * Company, Currency and Customer are pulled from the Credit Account and transmitted over the API for validation
    * Credits will be available as soon as the payment of the Sales Invoice is received
    * ERP validates that the company, customer and currency matches the account currency
    * The description will be used to name the item. if not set (null) the standard text "Primers and Sequencing" will be shown on the Sales Invoice
    * If allow_recharge is set to True, the deposit invoice can be created even if the Enforced or Legacy Credit Account already has transactions.

    bench execute microsynth.microsynth.api.webshop.credit_account.create_deposit_invoice --kwargs "{'webshop_account': '215856', 'account_id': 'CA-000003', 'amount': 1000.00, 'currency': 'CHF', 'description': 'Primers', 'company': 'Microsynth AG', 'customer': '8003', 'customer_order_number': 'PO-12345'}"
    """
    try:
        if ignore_permissions and frappe.get_user().name == 'webshop@microsynth.ch':
            frappe.throw("Not allowed to use ignore_permissions.")
        credit_account_doc = frappe.get_doc('Credit Account', account_id)
        # Validate that the company, customer and currency matches the account currency
        if credit_account_doc.company != company:
            frappe.throw(f"The given Company '{company}' does not match the company '{credit_account_doc.company}' of Credit Account '{account_id}'.")
        if credit_account_doc.customer != customer:
            frappe.throw(f"The given Customer '{customer}' does not match the customer '{credit_account_doc.customer}' of Credit Account '{account_id}'.")
        if credit_account_doc.currency != currency:
            frappe.throw(f"The given Currency '{currency}' does not match the currency '{credit_account_doc.currency}' of Credit Account '{account_id}'.")
        if credit_account_doc.has_transactions and credit_account_doc.account_type in ['Enforced Credit', 'Legacy'] and not allow_recharge:
            frappe.throw(f"Not allowed to create a deposit invoice for a Credit Account of type 'Legacy' or 'Enforced Credit' that already has transactions.")

        # Fetch credit item from Microsynth Settings
        credit_item_code = frappe.get_value("Microsynth Settings", "Microsynth Settings", "credit_item")
        credit_item = frappe.get_doc("Item", credit_item_code)

        # Fetch shipping address of the webshop account
        shipping_address = get_default_shipping_address(webshop_account)
        if not shipping_address:
            frappe.throw(f"Webshop Address '{webshop_account}' has no default shipping address. Unable to create deposit invoice.")
        tax_template = find_dated_tax_template(company, customer, shipping_address, "Service", datetime.now().date())
        customer_doc = frappe.get_doc("Customer", customer)

        # define the income account for the credits
        income_account = None
        for d in credit_item.item_defaults:
            if d.company == company:
                income_account = get_alternative_account(d.income_account, currency)
        if not income_account:
            frappe.throw("Please define an income account for the credit item {0}".format(credit_item.name))

        # Create the Sales Invoice
        invoice = frappe.get_doc({
            "doctype": "Sales Invoice",
            "company": company,
            "customer": customer,
            "contact_person": webshop_account,
            "contact_display": frappe.get_value("Contact", webshop_account, "full_name"),
            "po_no": customer_order_number,
            "product_type": "Service",
            "territory": customer_doc.territory or "All Territories",
            "currency": currency,
            "selling_price_list": customer_doc.default_price_list or f"Sales Prices {currency}",
            "items": [{
                "item_code": credit_item.item_code,
                "qty": 1,
                "rate": amount,
                "item_name": description if description else credit_item.item_name,
                "cost_center": credit_item.get("selling_cost_center") or frappe.get_value("Company", company, "cost_center"),
                "income_account": income_account
            }],
            "taxes_and_charges": tax_template,
            "credit_account": account_id,
            "remarks": f"Webshop deposit for Credit Account {account_id}"
        })
        invoice.naming_series = get_naming_series("Sales Invoice", company)
        invoice.insert(ignore_permissions=ignore_permissions)
        invoice.submit()
        # Transmit the Sales Invoice
        if isinstance(transmit_invoice, str):
            transmit_invoice = transmit_invoice.strip().lower() in ("true", "1", "yes")
        if transmit_invoice:
            transmit_sales_invoice(invoice.name)
        # Set has_transaction on the Credit Account
        account_doc = frappe.get_doc("Credit Account", account_id)
        if not account_doc.has_transactions:
            account_doc.has_transactions = True
            account_doc.save(ignore_permissions=ignore_permissions)
        return {
            "success": True,
            "message": "OK",
            "internal_message": f"Deposit invoice '{invoice.name}' created successfully for Credit Account '{account_id}'.",
            "reference": invoice.name
        }
    except Exception as err:
        msg = f"Error creating deposit invoice for Credit Account '{account_id}':\r\n{err}"
        frappe.log_error(f"{msg}\n\n{traceback.format_exc()}", "webshop.create_deposit_invoice")
        return {
            "success": False,
            "message": "Failed to create deposit invoice.",
            "internal_message": msg,
            "reference": None
        }


def get_unpaid_deposit_invoices(account_id):
    """
    Get all unpaid deposit Sales Invoices for the given Credit Account.

    bench execute microsynth.microsynth.webshop.get_unpaid_deposit_invoices --kwargs "{'account_id': 'CA-000002'}"
    """
    credit_item_code = frappe.get_value("Microsynth Settings", "Microsynth Settings", "credit_item")
    sql_query = """
        SELECT
            `tabSales Invoice`.`name`,
            `tabSales Invoice`.`web_order_id`,
            `tabSales Invoice`.`posting_date` AS `transaction_date`,
            `tabSales Invoice`.`product_type`,
            `tabSales Invoice`.`currency`,
            (
                `tabSales Invoice`.`outstanding_amount`
                *
                (CASE
                    WHEN `tabSales Invoice`.`grand_total` = 0
                        THEN 0
                    ELSE `tabSales Invoice`.`net_total` / `tabSales Invoice`.`grand_total`
                END)
            ) AS `unbilled_amount`,
            `tabSales Invoice`.`contact_display`,
            `tabSales Invoice`.`status`,
            `tabSales Invoice`.`currency`,
            `tabSales Invoice`.`po_no`,
            `tabSales Invoice`.`creation`,
            'unpaid_deposit' AS `invoice_type`
        FROM
            `tabSales Invoice`
        JOIN
            `tabSales Invoice Item` ON `tabSales Invoice Item`.`parent` = `tabSales Invoice`.`name`
        WHERE
            `tabSales Invoice`.`credit_account` = %s
            AND `tabSales Invoice`.`docstatus` = 1
            AND `tabSales Invoice`.`outstanding_amount` > 0
            AND `tabSales Invoice Item`.`item_code` = %s
        ORDER BY `tabSales Invoice`.`posting_date` ASC, `tabSales Invoice`.`creation` ASC
        """
    sales_invoices = frappe.db.sql(sql_query, (account_id, credit_item_code), as_dict=True)
    return sales_invoices


def get_reservations(account_id, current_balance):
    raw_reservations = get_open_sales_orders(account_id) + get_unpaid_deposit_invoices(account_id)
    running_balance = current_balance
    raw_reservations.sort(
        key=lambda x: (
            x.get('transaction_date') or datetime.min,
            x.get('creation') or datetime.min
        )
    )
    reservations = []
    i = len(raw_reservations) - 1
    for entry in raw_reservations:
        unbilled_amount = entry.get('unbilled_amount') or 0.0
        if entry.get('invoice_type') != 'unpaid_deposit':
            running_balance -= unbilled_amount
        reservations.append({
            "date": entry.get('transaction_date'),
            "type": "Charge" if entry.get('invoice_type') != 'unpaid_deposit' else "Deposit",
            "reference": entry.get('name'),
            "contact_name": entry.get('contact_display'),
            "status": entry.get('status'),
            "web_order_id": entry.get('web_order_id'),
            "currency": entry.get('currency'),
            "amount": round((-1) * unbilled_amount, 2) if entry.get('invoice_type') != 'unpaid_deposit' else round(unbilled_amount, 2),
            "balance": round(running_balance, 2),
            "product_type": entry.get('product_type'),
            "po_no": entry.get('po_no'),
            "idx": i    # index for webshop api to maintain the order of transactions
        })
        i -= 1
    reservations.reverse()  # to have the oldest reservation first, using directly "return reservations.reverse()" does not work as reverse() returns None
    return reservations


@frappe.whitelist()
def get_transactions(account_id):
    """
    Get all transactions for the given Credit Account.

    bench execute microsynth.microsynth.api.webshop.credit_account.get_transactions --kwargs "{'account_id': 'CA-000020'}"
    """
    from microsynth.microsynth.report.customer_credits.customer_credits import build_transactions_with_running_balance
    type_mapping = {
        'Allocation': 'Charge',
        'Credit': 'Deposit'
    }
    try:
        credit_account = frappe.get_doc('Credit Account', account_id)
        filters = {
            'credit_account': account_id,
            'company': credit_account.company,
            'customer': credit_account.customer
        }
        transactions = build_transactions_with_running_balance(filters, type_mapping=type_mapping)

        # reverse to display the most recent transaction first
        transactions.reverse()
        current_balance = transactions[0].get('balance') if len(transactions) > 0 else 0.0

        return {
            "success": True,
            "message": "OK",
            "internal_message": f"Fetched {len(transactions)} transactions for Credit Account '{account_id}'.",
            "credit_account": get_credit_account_dto(credit_account),
            "transactions": transactions,
            "reservations": get_reservations(account_id, current_balance)
        }
    except Exception as err:
        msg = f"Error fetching Credit Account '{account_id}': {err}"
        frappe.log_error(f"{msg}\n\n\n{traceback.format_exc()}", "webshop.get_transactions")
        return {
            "success": False,
            "message": "Failed to fetch Credit Account data.",
            "internal_message": msg,
            "credit_account": None,
            "transactions": [],
            "reservations": None
        }


@frappe.whitelist()
def get_balance_sheet_pdf(account_id):
    """
    Return a base64-encoded PDF and file name of the balance sheet for the given credit account

    bench execute microsynth.microsynth.api.webshop.credit_account.get_balance_sheet_pdf --kwargs "{'account_id': 'CA-000002'}"
    """
    from erpnextswiss.erpnextswiss.attach_pdf import get_pdf_data
    try:
        pdf = get_pdf_data(doctype='Credit Account', name=account_id, print_format='Credit Account')
        encoded_pdf = base64.b64encode(pdf).decode("utf-8")
        file_name = f"Balance_Sheet_{account_id.replace(' ', '_')}.pdf"
        return {
            "success": True,
            "file": {
                "file_name": file_name,
                "content_base64": encoded_pdf,
                "mime_type": "application/pdf"
            },
            "internal_message": f"Generated balance sheet PDF for Credit Account '{account_id}'.",
            "message": "OK"
        }
    except Exception as err:
        frappe.log_error(frappe.get_traceback(), "webshop.get_balance_sheet_pdf")
        return {
            "success": False,
            "file": None,
            "internal_message": f"Failed to generate PDF: {str(err)}",
            "message": "Failed to generate PDF"
        }
