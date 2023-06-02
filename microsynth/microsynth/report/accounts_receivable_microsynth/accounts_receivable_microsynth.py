# Copyright (c) 2023, Microsynth, libracore and contributors and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
from erpnext.accounts.report.accounts_receivable.accounts_receivable import ReceivablePayableReport

def execute(filters=None):
    columns, data = [], []
    
    # raw data
    args = {
        "party_type": "Customer",
        "naming_by": ["Selling Settings", "cust_master_name"],
    }
    columns, data, unused, chart = ReceivablePayableReport(filters).run(args)
    
    currency = data[0]['currency']
    for d in data:
        if d['currency'] != currency:
            frappe.throw("Currency differs for {0}: ".format(d['voucher_no']))

    # extend columns
    new_columns = []
    for c in columns:
        # skip range columns
        if c['fieldname'].startswith("range") \
            or c['fieldname'] == "customer_primary_contact" \
            or c['fieldname'] == "voucher_type" \
            or c['fieldname'] == "age" \
            or c['fieldname'] == "due_date":
            continue
        
        # insert external debtor number
        if c['fieldname'] == "party":
            new_columns.append({
                'fieldtype': 'Data',
                'fieldname': 'ext_customer',
                'label': "Ext. Debtor",
                'width': 80
            })

        # insert contact id
        if c['fieldname'] == "voucher_no":
            new_columns.append({
                'fieldtype': 'Data',
                'fieldname': 'contact_person',
                'label': "Contact Person",
                'width': 80
            })

        new_columns.append(c)
        
    # extend data
    for d in data:
        d['ext_customer'] = frappe.get_cached_value("Customer", d['party'], 'ext_debitor_number')
        if d['voucher_type'] == "Sales Invoice":
            d['contact_person'] = frappe.get_value("Sales Invoice", d['voucher_no'], 'contact_person')

    # group by external debtor number or customer if there is no external debtor number
    external_debtors = []
    individual_customers = []
    output = []
    overall_totals = {
        'invoiced': 0,
        'paid': 0,
        'credit_note': 0,
        'outstanding': 0 
    }

    for d in data:
        if d['ext_customer'] and d['ext_customer'] not in external_debtors:
            external_debtors.append(d['ext_customer'])
        
        if not(d['ext_customer']) and d['party'] not in individual_customers:
            individual_customers.append(d['party'])

    # group by external debtor number
    for c in sorted(external_debtors or []):
        customer_totals = {
            'invoiced': 0,
            'paid': 0,
            'credit_note': 0,
            'outstanding': 0
        }

        for d in data:
            customer = d['ext_customer']
            if customer == c:
                output.append(d)

                customer_totals['invoiced'] += d['invoiced']
                customer_totals['paid'] += d['paid']
                customer_totals['credit_note'] += d['credit_note']
                customer_totals['outstanding'] += d['outstanding']

                overall_totals['invoiced'] += d['invoiced']
                overall_totals['paid'] += d['paid']
                overall_totals['credit_note'] += d['credit_note']
                overall_totals['outstanding'] += d['outstanding']

        output.append({
            'ext_customer': c,
            'invoiced': customer_totals['invoiced'],
            'paid': customer_totals['paid'],
            'credit_note': customer_totals['credit_note'],
            'outstanding': customer_totals['outstanding'],
            'currency': currency
        })

    # group by customer if there is no external debtor number
    for c in sorted(individual_customers or []):
        customer_totals = {
            'invoiced': 0,
            'paid': 0,
            'credit_note': 0,
            'outstanding': 0 
        }
        for d in data:
            customer = d['party'] if 'party' in d else d['customer_name']
            if customer == c:
                output.append(d)
                customer_totals['invoiced'] += d['invoiced']
                customer_totals['paid'] += d['paid']
                customer_totals['credit_note'] += d['credit_note']
                customer_totals['outstanding'] += d['outstanding']

                overall_totals['invoiced'] += d['invoiced']
                overall_totals['paid'] += d['paid']
                overall_totals['credit_note'] += d['credit_note']
                overall_totals['outstanding'] += d['outstanding']

        output.append({
            'party': c,
            'invoiced': customer_totals['invoiced'],
            'paid': customer_totals['paid'],
            'credit_note': customer_totals['credit_note'],
            'outstanding': customer_totals['outstanding'],
            'currency': currency
        })

    # overall total
    output.append({
        'party': _("Total"),
        'invoiced': overall_totals['invoiced'],
        'paid': overall_totals['paid'],
        'credit_note': overall_totals['credit_note'],
        'outstanding': overall_totals['outstanding'],
        'currency': currency
    })

    return new_columns, output #sorted(data, key= lambda x: x['ext_customer'] or "" )
