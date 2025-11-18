# Copyright (c) 2023, Microsynth, libracore and contributors
# For license information, please see license.txt

import json
import frappe
from frappe import _
from frappe.utils.pdf import get_pdf
from microsynth.microsynth.utils import get_sql_list

def execute(filters=None):
    columns = get_columns()
    data = get_data(filters)
    return columns, data


def get_columns():
    columns = [
        {"label": _("Date"), "fieldname": "date", "fieldtype": "Date", "width": 80},
        {"label": _("Customer"), "fieldname": "customer", "fieldtype": "Link", "options": "Customer", "width": 80},
        {"label": _("Customer name"), "fieldname": "customer_name", "fieldtype": "Data", "width": 200},
        {"label": _("Sales Invoice"), "fieldname": "sales_invoice", "fieldtype": "Link", "options": "Sales Invoice", "width": 120},
        {"label": _("Currency"), "fieldname": "currency", "fieldtype": "Link", "options": "Currency", "width": 70},
        {"label": _("Net Amount"), "fieldname": "net_amount", "fieldtype": "Currency", "width": 105, 'options': 'currency'},
        {"label": _("Outstanding"), "fieldname": "outstanding", "fieldtype": "Currency", "width": 105, 'options': 'currency'},
        {"label": _("Product Type"), "fieldname": "product_type", "fieldtype": "Data", "width": 100},
        {"label": _("Status"), "fieldname": "status", "fieldtype": "Data", "width": 100},
        {"label": _("Reference"), "fieldname": "reference", "fieldtype": "Link", "options": "Sales Invoice", "width": 120},
        {"label": _("Credit Account"), "fieldname": "credit_account", "fieldtype": "Link", "options": "Credit Account", "width": 100},
        {"label": _("Account Type"), "fieldname": "account_type", "fieldtype": "Data", "width": 95},
        {"label": _("Territory"), "fieldname": "territory", "fieldtype": "Link", "options": "Territory", "width": 200},
        {"label": _("InvoiceByDefaultCompany"), "fieldname": "invoice_by_default_company", "fieldtype": "Check", "width": 165, "align": "left"}
    ]
    return columns


def validate_credit_account_customer(credit_account, customer):
    credit_account_customer = frappe.get_value("Credit Account", credit_account, 'customer')
    return customer == credit_account_customer


def get_data(filters, short=False, add_print_format=True):
    """
    bench execute microsynth.microsynth.report.customer_credits.customer_credits.get_data --kwargs "{'filters': {'company': 'Microsynth AG', 'exclude_unpaid_deposits': False, 'credit_accounts': ['CA-000003'], 'customer': '8003'}}"
    """
    if not 'company' in filters:
        frappe.throw("Company is a mandatory filter.")
    conditions = f"AND `tabSales Invoice`.`company` = '{filters.get('company')}'"  # company has to be always set
    deposit_conditions = ""
    credit_accounts = []

    if filters and filters.get('exclude_unpaid_deposits'):
        deposit_conditions += f"AND `tabSales Invoice`.`status` IN ('Paid', 'Return', 'Credit Note Issued')"

    if filters and filters.get('credit_type') == 'Standard':
        conditions += f"AND (`tabSales Invoice`.`product_type` is null or `tabSales Invoice`.`product_type` != 'Project')"
    elif filters and filters.get('credit_type') == 'Project':
        conditions += f"AND `tabSales Invoice`.`product_type` = 'Project'"

    if filters and filters.get('to_date'):
        conditions += f"AND `tabSales Invoice`.`posting_date` <= '{filters.get('to_date')}'"
    if filters and filters.get('currency'):
        conditions += f"AND `tabSales Invoice`.`currency` = '{filters.get('currency')}'"

    if filters and filters.get('credit_account'):
        credit_account = filters.get('credit_account')

        if not filters.get('customer'):
            credit_account_customer = frappe.get_value("Credit Account", credit_account, 'customer')
            filters['customer'] = credit_account_customer       # the customer is needed to select the correct report mode (customer)
            credit_accounts.append(credit_account)
        else:
            # check if credit account belongs to customer
            if validate_credit_account_customer(credit_account, customer=filters.get('customer')):
                credit_accounts.append(credit_account)
            else:
                frappe.throw(f"The selected Credit Account {credit_account} does not belong to the selected Customer {filters.get('customer')}.", "Customer Credits Report")

        conditions += f"AND `tabSales Invoice`.`credit_account` = '{credit_account}'"

        if filters.get('account_type'):
            account_type = filters.get('account_type')
            conditions += f"AND `tabCredit Account`.`account_type` = '{account_type}'"

    if filters and filters.get('credit_accounts'):
        if isinstance(filters.get('credit_accounts'), str):
            raw_credit_accounts = json.loads(filters.get('credit_accounts'))
        else:
            raw_credit_accounts = filters.get('credit_accounts')

        if not filters.get('customer'):
            frappe.throw("When selecting multiple Credit Accounts, the Customer must be selected as well to avoid data leakage.", "Customer Credits Report")

        customer_id = filters.get('customer')
        # validate that all credit accounts belong to the customer

        for account in raw_credit_accounts:
            if validate_credit_account_customer(account, customer=customer_id):
                credit_accounts.append(account)
            else:
                frappe.log_error(f"The selected Credit Account {account} does not belong to the selected Customer {customer_id}.", "Customer Credits Report")

        if len(credit_accounts) == 0:
            frappe.throw(f"None of the selected Credit Accounts ({', '.join(credit_accounts)}) belong to the selected Customer {customer_id}. Cannot generate report.", "Customer Credits Report")

        conditions += f"AND `tabSales Invoice`.`credit_account` IN ({get_sql_list(credit_accounts)})"

    if filters.get('customer'):
        # customer based evaluation: ledger
        # TODO: Use territory from Sales Invoice instead of Customer? What if it changed?
        sql_query = """
        SELECT
            `raw`.`type` AS `type`,
            `raw`.`date` AS `date`,
            `raw`.`customer` AS `customer`,
            `raw`.`customer_name` AS `customer_name`,
            `raw`.`sales_invoice` AS `sales_invoice`,
            `raw`.`contact_person` AS `contact_person`,
            `raw`.`contact` AS `contact_name`,
            `raw`.`net_amount` AS `net_amount`,
            `raw`.`product_type` AS `product_type`,
            `raw`.`status` AS `status`,
            `raw`.`reference` AS `reference`,
            `raw`.`credit_account` AS `credit_account`,
            `raw`.`currency` AS `currency`,
            `raw`.`web_order_id` AS `web_order_id`,
            `raw`.`po_no` AS `po_no`,
            `tabCustomer`.`territory` AS `territory`,
            `tabCredit Account`.`account_type` AS `account_type`,
            IF(`webshop_service`.`customer_id` IS NOT NULL, 1, 0) AS `invoice_by_default_company`
        FROM (
            SELECT
                IF(`tabSales Invoice`.`is_return` = 0,
                    "Credit",
                    "Allocation"
                    ) AS `type`,
                `tabSales Invoice`.`posting_date` AS `date`,
                `tabSales Invoice`.`creation` AS `creation`,
                `tabSales Invoice`.`customer` AS `customer`,
                `tabSales Invoice`.`customer_name` AS `customer_name`,
                `tabSales Invoice`.`name` AS `sales_invoice`,
                `tabSales Invoice`.`contact_person` AS `contact_person`,
                `tabSales Invoice`.`contact_display` AS `contact`,
                SUM(`tabSales Invoice Item`.`net_amount`) AS `net_amount`,
                `tabSales Invoice`.`product_type` AS `product_type`,
                `tabSales Invoice`.`status` AS `status`,
                IF(`tabSales Invoice`.`is_return` = 0,
                    `tabSales Invoice Item`.`name`,
                    `tabSales Invoice`.`return_against`
                ) AS `reference`,
                `tabSales Invoice`.`credit_account` AS `credit_account`,
                `tabSales Invoice`.`currency` AS `currency`,
                `tabSales Invoice`.`web_order_id` AS `web_order_id`,
                `tabSales Invoice`.`po_no` AS `po_no`
            FROM `tabSales Invoice Item`
            LEFT JOIN `tabSales Invoice` ON `tabSales Invoice Item`.`parent` = `tabSales Invoice`.`name`
            WHERE
                `tabSales Invoice`.`docstatus` = 1
                AND `tabSales Invoice Item`.`item_code` = "{credit_item}"
                AND `tabSales Invoice`.`customer` = "{customer}"
                {conditions}
                {deposit_conditions}
            GROUP BY `tabSales Invoice`.`name`

            UNION ALL SELECT
                "Allocation" AS `type`,
                `tabSales Invoice`.`posting_date` AS `date`,
                `tabSales Invoice`.`creation` AS `creation`,
                `tabSales Invoice`.`customer` AS `customer`,
                `tabSales Invoice`.`customer_name` AS `customer_name`,
                `tabSales Invoice`.`name` AS `sales_invoice`,
                `tabSales Invoice`.`contact_person` AS `contact_person`,
                `tabSales Invoice`.`contact_display` AS `contact`,
                ( IF (`tabSales Invoice`.`is_return` = 1, 1, -1) * `tabSales Invoice Customer Credit`.`allocated_amount`) AS `net_amount`,
                `tabSales Invoice`.`product_type` AS `product_type`,
                `tabSales Invoice`.`status` AS `status`,
                `tabSales Invoice Customer Credit`.`sales_invoice` AS `reference`,
                (SELECT `deposit_invoice`.`credit_account`
                    FROM `tabSales Invoice` AS `deposit_invoice`
                    WHERE `deposit_invoice`.`name` = `tabSales Invoice Customer Credit`.`sales_invoice`
                ) AS `credit_account`,
                `tabSales Invoice`.`currency` AS `currency`,
                `tabSales Invoice`.`web_order_id` AS `web_order_id`,
                `tabSales Invoice`.`po_no` AS `po_no`
            FROM `tabSales Invoice Customer Credit`
            LEFT JOIN `tabSales Invoice` ON `tabSales Invoice Customer Credit`.`parent` = `tabSales Invoice`.`name`
            WHERE
                `tabSales Invoice`.`docstatus` = 1
                AND `tabSales Invoice`.`customer` = "{customer}"
                {conditions}
        ) AS `raw`
        LEFT JOIN `tabCustomer` ON `raw`.`customer` = `tabCustomer`.`name`
        LEFT JOIN `tabCredit Account` ON `raw`.`credit_account` = `tabCredit Account`.`name`
        LEFT JOIN (
            SELECT DISTINCT `tabWebshop Service Link`.`parent` AS `customer_id`
            FROM `tabWebshop Service Link`
            JOIN `tabWebshop Service` ON `tabWebshop Service Link`.`webshop_service` = `tabWebshop Service`.`name`
            WHERE `tabWebshop Service`.`service_name` = 'InvoiceByDefaultCompany'
        ) AS `webshop_service` ON `raw`.`customer` = `webshop_service`.`customer_id`
        ORDER BY `raw`.`date` DESC, `raw`.`sales_invoice` DESC;
        """.format(credit_item=frappe.get_value("Microsynth Settings", "Microsynth Settings", "credit_item"),
            customer=filters.get('customer'),
            conditions=conditions,
            deposit_conditions=deposit_conditions)

        raw_data = frappe.db.sql(sql_query, as_dict=True)

        data = []
        if credit_accounts:
            for r in raw_data:
                if r['credit_account'] in credit_accounts:
                    data.append(r)
        else:
            data = raw_data

        credit_positions = {}       # Key is per invoice
        # find open balances that have credit left
        for d in data:
            if d['type'] == "Credit":
                # open credit
                if not d['sales_invoice'] in credit_positions:
                    credit_positions[d['sales_invoice']] = 0
                credit_positions[d['sales_invoice']] += d['net_amount']
            else:
                # deduct allocation:
                if not d['reference'] in credit_positions:
                    credit_positions[d['reference']] = 0
                credit_positions[d['reference']] += d['net_amount']

        # apply to credits
        for d in data:
            if d['type'] == "Credit":
                d['outstanding'] = credit_positions[d['sales_invoice']]

        # shorten output
        if short:
            output = []
            for d in data:
                if d['type'] == "Credit" and d['outstanding'] > 0:
                    output.append(d)
            data = output

        if len(data) > 0 and add_print_format:  # prevent crash if there are no entries
            # add data required in the print format
            print_format = {}
            letter_head = frappe.get_doc("Letter Head", filters.get('company'))
            customer = frappe.get_doc("Customer", filters.get('customer'))
            address = frappe.get_value("Contact", customer.invoice_to, 'address')
            if not address:
                frappe.throw(f"The Invoice To Contact '{customer.invoice_to}' of Customer '{customer.name}' has no Address.")
            print_format['header'] = letter_head.content
            print_format['customer_address'] = frappe.render_template("microsynth/templates/includes/address.html", {'contact': customer.invoice_to, 'address': address, 'customer_name': customer.customer_name })
            print_format['footer'] = letter_head.footer
            #frappe.log_error(print_format['footer'], "print_format['footer']")
            print_format['currency'] = filters.get('currency') or customer.default_currency or data[0]['currency']
            remaining_credit = 0
            for row in data:
                if 'outstanding' in row:
                    remaining_credit += row['outstanding']
            print_format['remaining_credit'] = remaining_credit
            # attach to first record instead of a separate line
            data[0]['print_format'] = print_format
    else:
        # overview, group by customer
        sql_query = """
        SELECT
            `raw`.`customer` AS `customer`,
            `raw`.`customer_name` AS `customer_name`,
            SUM(`raw`.`net_amount`) AS `outstanding`,
            `raw`.`product_type` AS `product_type`,
            `raw`.`currency` AS `currency`,
            `tabCustomer`.`territory` AS `territory`,
            IF(`webshop_service`.`customer_id` IS NOT NULL, 1, 0) AS `invoice_by_default_company`
        FROM (
            SELECT
                "Credit" AS `type`,
                `tabSales Invoice`.`posting_date` AS `date`,
                `tabSales Invoice`.`customer` AS `customer`,
                `tabSales Invoice`.`customer_name` AS `customer_name`,
                `tabSales Invoice`.`name` AS `sales_invoice`,
                `tabSales Invoice Item`.`net_amount` AS `net_amount`,
                `tabSales Invoice`.`product_type` AS `product_type`,
                `tabSales Invoice`.`status` AS `status`,
                `tabSales Invoice Item`.`name` AS `reference`,
                `tabSales Invoice`.`currency` AS `currency`
            FROM `tabSales Invoice Item`
            LEFT JOIN `tabSales Invoice` ON `tabSales Invoice Item`.`parent` = `tabSales Invoice`.`name`
            WHERE
                `tabSales Invoice`.`docstatus` = 1
                AND `tabSales Invoice Item`.`item_code` = "{credit_item}"
                {conditions}

            UNION ALL SELECT
                "Allocation" AS `type`,
                `tabSales Invoice`.`posting_date` AS `date`,
                `tabSales Invoice`.`customer` AS `customer`,
                `tabSales Invoice`.`customer_name` AS `customer_name`,
                `tabSales Invoice`.`name` AS `sales_invoice`,
                ( IF (`tabSales Invoice`.`is_return` = 1, 1, -1) * `tabSales Invoice Customer Credit`.`allocated_amount`) AS `net_amount`,
                `tabSales Invoice`.`product_type` AS `product_type`,
                `tabSales Invoice`.`status` AS `status`,
                `tabSales Invoice Customer Credit`.`sales_invoice` AS `reference`,
                `tabSales Invoice`.`currency` AS `currency`
            FROM `tabSales Invoice Customer Credit`
            LEFT JOIN `tabSales Invoice` ON `tabSales Invoice Customer Credit`.`parent` = `tabSales Invoice`.`name`
            WHERE
                `tabSales Invoice`.`docstatus` = 1
                {conditions}
        ) AS `raw`
        LEFT JOIN `tabCustomer` ON `raw`.`customer` = `tabCustomer`.`name`
        LEFT JOIN (
            SELECT DISTINCT `tabWebshop Service Link`.`parent` AS `customer_id`
            FROM `tabWebshop Service Link`
            JOIN `tabWebshop Service` ON `tabWebshop Service Link`.`webshop_service` = `tabWebshop Service`.`name`
            WHERE `tabWebshop Service`.`service_name` = 'InvoiceByDefaultCompany'
        ) AS `webshop_service` ON `raw`.`customer` = `webshop_service`.`customer_id`
        GROUP BY `raw`.`customer`
        ORDER BY `raw`.`customer` ASC;
        """.format(credit_item=frappe.get_value("Microsynth Settings", "Microsynth Settings", "credit_item"),
            conditions=conditions)

        data = frappe.db.sql(sql_query, as_dict=True)

    return data


@frappe.whitelist()
def download_pdf(company, customer, credit_account=None):
    from erpnextswiss.erpnextswiss.attach_pdf import get_pdf_data
    filters={'customer': customer, 'company': company}

    # --- CASE 1: Specific Credit Account ---
    if credit_account:
        filters['credit_account'] = credit_account
        credit_account_doc = frappe.get_doc("Credit Account", credit_account)

        if credit_account_doc.customer != customer:
            frappe.throw(
                _(f"The selected Credit Account {credit_account} does not belong to the selected Customer {customer}."),
                _("Customer Credits Report")
            )
        if credit_account_doc.company != company:
            frappe.throw(
                _(f"The selected Credit Account {credit_account} does not belong to the selected Company {company}."),
                _("Customer Credits Report")
            )
        pdf = get_pdf_data(doctype='Credit Account', name=credit_account, print_format='Credit Account')
        filename = f"Credit_Account_{credit_account_doc.name}.pdf"
    # TODO: Unify print formats regarding style
    # --- CASE 2: Overview for entire Customer ---
    else:
        data = get_data(filters)
        content = frappe.render_template(
            "microsynth/microsynth/report/customer_credits/customer_credits_server.html",
            {'data': data, 'filters': filters}
        )
        filename = f"Customer_Credits_{customer}.pdf"
        options = {
            'disable-smart-shrinking': ''
        }
        pdf = get_pdf(content, options)

    # Generate and send PDF response
    frappe.local.response.filename = filename
    frappe.local.response.filecontent = pdf
    frappe.local.response.type = "download"
