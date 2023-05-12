# Copyright (c) 2023, Microsynth, libracore and contributors and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from erpnext.accounts.report.accounts_receivable.accounts_receivable import ReceivablePayableReport

def execute(filters=None):
    columns, data = [], []
    
    # raw data
    args = {
        "party_type": "Customer",
        "naming_by": ["Selling Settings", "cust_master_name"],
    }
    columns, data, unused, chart = ReceivablePayableReport(filters).run(args)
    
    # extend columns
    new_columns = []
    for c in columns:
        # skip range columns
        if c['fieldname'].startswith("range") \
            or c['fieldname'] == "voucher_type" \
            or c['fieldname'] == "voucher_no" \
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
            
        new_columns.append(c)
        
    # extend data
    for d in data:
        d['ext_customer'] = frappe.get_cached_value("Customer", d['party'], 'ext_debitor_number')
    
    # now, aggregate by external debitor
    output = []
    customer_keys = {}
    for d in data:
        customer = (d['party'] or "-")
        if customer not in customer_keys:
            # this customer was not seen, add to output
            customer_keys[customer] = len(output)       # store index to row
            output.append(d)                                # append this row
        else:
            # this customer is already in the list, update
            output[customer_keys[customer]]['invoiced'] += d['invoiced']
            output[customer_keys[customer]]['paid'] += d['paid']
            output[customer_keys[customer]]['credit_note'] += d['credit_note']
            output[customer_keys[customer]]['outstanding'] += d['outstanding']
            
    return new_columns, output
