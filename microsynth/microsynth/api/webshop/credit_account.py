import frappe
import traceback

from microsynth.microsynth.utils import get_customer
from microsynth.microsynth.credits import get_credit_account_balance


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
