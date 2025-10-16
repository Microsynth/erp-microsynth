# Copyright (c) 2023, Microsynth, libracore and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.utils.pdf import get_pdf

def execute(filters=None):
    columns = get_columns()
    data = get_data(filters)
    return columns, data


def get_columns():
    columns = [
        {"label": _("Date"), "fieldname": "date", "fieldtype": "Date", "width": 80},
        {"label": _("Customer"), "fieldname": "customer", "fieldtype": "Link", "options": "Customer", "width": 80},
        {"label": _("Customer name"), "fieldname": "customer_name", "fieldtype": "Data", "width": 200},
        {"label": _("Sales Invoice"), "fieldname": "sales_invoice", "fieldtype": "Link", "options": "Sales Invoice", "width": 125},
        {"label": _("Currency"), "fieldname": "currency", "fieldtype": "Link", "options": "Currency", "width": 75},
        {"label": _("Net Amount"), "fieldname": "net_amount", "fieldtype": "Currency", "width": 125, 'options': 'currency'},
        {"label": _("Outstanding"), "fieldname": "outstanding", "fieldtype": "Currency", "width": 125, 'options': 'currency'},
        {"label": _("Product Type"), "fieldname": "product_type", "fieldtype": "Data", "width": 100},
        {"label": _("Status"), "fieldname": "status", "fieldtype": "Data", "width": 100},
        {"label": _("Reference"), "fieldname": "reference", "fieldtype": "Link", "options": "Sales Invoice", "width": 125},
        {"label": _("Credit Account"), "fieldname": "credit_account", "fieldtype": "Link", "options": "Credit Account", "width": 100},
        {"label": _("Territory"), "fieldname": "territory", "fieldtype": "Link", "options": "Territory", "width": 200},
        {"label": _("InvoiceByDefaultCompany"), "fieldname": "invoice_by_default_company", "fieldtype": "Check", "width": 165}
    ]
    return columns


def get_data(filters, short=False):
    conditions = f"AND `tabSales Invoice`.`company` = '{filters.get('company')}'"  # company has to be always set
    deposit_conditions = ""

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
        credit_account_customer = frappe.get_value("Credit Account", credit_account, 'customer')
        if not filters.get('customer'):
            filters['customer'] = credit_account_customer
        else:
            # check if credit account belongs to customer
            if filters['customer'] != credit_account_customer:
                frappe.throw(f"The selected Credit Account {credit_account} does not belong to the selected Customer {filters.get('customer')}, but Customer {credit_account_customer}.")
        conditions += f"AND `tabSales Invoice`.`credit_account` = '{credit_account}'"
    else:
        credit_account = None

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
        if credit_account:
            for r in raw_data:
                if r['credit_account'] == credit_account:
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

        if len(data) > 0:  # prevent crash if there are no entries
            # add data required in the print format
            print_format = {}
            letter_head = frappe.get_doc("Letter Head", filters.get('company'))
            customer = frappe.get_doc("Customer", filters.get('customer'))
            address = frappe.get_value("Contact", customer.invoice_to, 'address')
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

    # Debugging:
    #pf = data[(len(data) - 1)]
    #frappe.log_error(f"{pf=}\n\n{pf['header']=}\n\n{pf['customer_address']=}")

    return data

@frappe.whitelist()
def download_pdf(company, customer):
    filters={'customer': customer, 'company': company}
    content = frappe.render_template(
        "microsynth/microsynth/report/customer_credits/customer_credits_server.html",
        {
            'data': get_data(filters),
            'filters': filters
        }
    )

    pdf = get_pdf(content)

    frappe.local.response.filename = "Customer_Credits_{0}.pdf".format(customer)
    frappe.local.response.filecontent = pdf
    frappe.local.response.type = "download"

    return
