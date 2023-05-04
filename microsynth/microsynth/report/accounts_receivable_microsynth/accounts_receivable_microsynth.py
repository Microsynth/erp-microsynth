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
        if c['fieldname'].startswith("range"):
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
        
    return new_columns, data
