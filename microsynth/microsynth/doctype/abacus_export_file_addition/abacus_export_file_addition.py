# -*- coding: utf-8 -*-
# Copyright (c) 2023, Microsynth, libracore and contributors and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document
from erpnextswiss.erpnextswiss.doctype.abacus_export_file.abacus_export_file import set_export_flag
import html

class AbacusExportFileAddition(Document):
    def submit(self):
        self.get_transactions()
        return

    def on_cancel(self):
        set_export_flag("Payment Entry", get_sql_list(self.get_docs("Payment Entry")), 0)
        set_export_flag("Journal Entry", get_sql_list(self.get_docs("Journal Entry")), 0)
        return
        
    # find all transactions, add the to references and mark as collected
    def get_transactions(self):
        account_list_str = get_sql_list(self.get_account_list())
        # get all documents
        document_query = """
            SELECT 
                `tabGL Entry`.`voucher_type` AS `dt`,
                `tabGL Entry`.`voucher_no` AS `dn`
            FROM `tabGL Entry`
            LEFT JOIN `tabPayment Entry` ON `tabPayment Entry`.`name` = `tabGL Entry`.`voucher_no`
            LEFT JOIN `tabJournal Entry` ON `tabJournal Entry`.`name` = `tabGL Entry`.`voucher_no`
            WHERE
                `tabGL Entry`.`posting_date` BETWEEN '{start_date}' AND '{end_date}'
                AND `tabGL Entry`.`docstatus` = 1
                AND `tabGL Entry`.`company` = '{company}'
                AND `tabGL Entry`.`account` IN ({accounts})
                AND `tabGL Entry`.`voucher_type` IN ("Payment Entry", "Journal Entry")
                AND IFNULL(`tabPayment Entry`.`exported_to_abacus`, `tabJournal Entry`.`exported_to_abacus`) = 0
            ;""".format(
                start_date=self.from_date, end_date=self.to_date, 
                company=self.company, accounts=account_list_str)
        
        docs = frappe.db.sql(document_query, as_dict=True)
        
        # clear all children
        self.references = []
        
        # add to child table
        for doc in docs:
            row = self.append('references', {'dt': doc['dt'], 'dn': doc['dn']})
        self.save()
        
        # mark as exported
        set_export_flag("Payment Entry", get_sql_list(self.get_docs("Payment Entry")), 1)
        set_export_flag("Journal Entry", get_sql_list(self.get_docs("Journal Entry")), 1)
        return
    
    def prepare_transactions(self):
        base_currency = frappe.get_value("Company", self.company, "default_currency")
        transactions = []
            
        # add payment entry transactions
        pes = self.get_docs("Payment Entry")
        sql_query = """SELECT `tabPayment Entry`.`name`
                    FROM `tabPayment Entry`
                    WHERE`tabPayment Entry`.`name` IN ({pes})
            """.format(pes=get_sql_list(pes))

        pe_items = frappe.db.sql(sql_query, as_dict=True)
        
        # create item entries
        for item in pe_items:
            pe_record = frappe.get_doc("Payment Entry", item.name)
            if pe_record.payment_type == "Pay":
                debit_credit = "C"
            else:
                debit_credit = "D"
            # create content
            transaction = {
                'account': get_account_number(pe_record.paid_to),  # bank
                'amount': pe_record.paid_amount, 
                'against_singles': [{
                    'account': get_account_number(pe_record.paid_from),    # debtor
                    'amount': pe_record.total_allocated_amount,
                    'currency': pe_record.paid_from_account_currency,
                    'key_currency': base_currency,
                    'key_amount': pe_record.base_total_allocated_amount
                }],
                'debit_credit': debit_credit, 
                'date': pe_record.posting_date, 
                'currency': pe_record.paid_from_account_currency, 
                'key_currency': base_currency,
                'key_amount': pe_record.base_paid_amount,
                'exchange_rate': pe_record.source_exchange_rate,
                'tax_account': None, 
                'tax_amount': None, 
                'tax_rate': None, 
                'tax_code': None, 
                'text1': html.escape(pe_record.name)
            }
            # append deductions
            for deduction in pe_record.deductions:
                sign = 1
                if frappe.get_cached_value("Account", deduction.account, 'root_type') in ['Asset', 'Expense']:
                    sign = (-1)
                transaction['against_singles'].append({
                    'account': get_account_number(deduction.account),
                    'amount': sign * (deduction.amount / pe_record.source_exchange_rate),    # virtual valuation to other currency
                    'currency': pe_record.paid_to_account_currency,
                    'key_amount': sign * deduction.amount,
                    'key_currency': base_currency
                })
                
            # verify integrity
            sums = {'base': transaction['key_amount'], 'other': transaction['amount']}
            for s in transaction['against_singles']:
                sums['base'] -= s['key_amount']
                sums['other'] -= s['amount']
            
            if sums['base'] != 0:           # correct difference on last entry
                transaction['against_singles'][-1]['key_amount'] += sums['base']
            if sums['other'] != 0:           # correct difference on last entry
                transaction['against_singles'][-1]['amount'] += sums['other']
                
            # insert transaction
            transactions.append(transaction)  

        # add journal entry transactions
        jvs = self.get_docs("Journal Entry")
        sql_query = """SELECT `tabJournal Entry`.`name`
                    FROM `tabJournal Entry`
                    WHERE`tabJournal Entry`.`name` IN ({jvs})
            """.format(jvs=get_sql_list(jvs))

        jv_items = frappe.db.sql(sql_query, as_dict=True)
        
        # create item entries
        for item in jv_items:
            jv_record = frappe.get_doc("Journal Entry", item.name)
            key_currency = frappe.get_cached_value("Company", jv_record.company, "default_currency")
            if jv_record.accounts[0].debit_in_account_currency != 0:
                debit_credit = "D"
                amount = jv_record.accounts[0].debit_in_account_currency
                key_amount = jv_record.accounts[0].debit
            else:
                debit_credit = "C"
                amount = jv_record.accounts[0].credit_in_account_currency
                key_amount = jv_record.accounts[0].credit
            # create content
            transaction = {
                'account': get_account_number(jv_record.accounts[0].account), 
                'amount': amount, 
                'against_singles': [],
                'debit_credit': debit_credit, 
                'date': jv_record.posting_date, 
                'currency': jv_record.accounts[0].account_currency, 
                'tax_account': None, 
                'tax_amount': None, 
                'tax_rate': None, 
                'tax_code': None, 
                'text1': html.escape(jv_record.name),
                'key_currency': key_currency,
                'key_amount': key_amount
            }
            if jv_record.multi_currency == 1:
                transaction['exchange_rate'] = jv_record.accounts[0].exchange_rate
                
            # append single accounts
            for i in range(1, len(jv_record.accounts), 1):
                if debit_credit == "D":
                    amount = jv_record.accounts[i].credit_in_account_currency - jv_record.accounts[i].debit_in_account_currency
                    key_amount = jv_record.accounts[i].credit - jv_record.accounts[i].debit
                else:
                    amount = jv_record.accounts[i].debit_in_account_currency - jv_record.accounts[i].credit_in_account_currency
                    key_amount = jv_record.accounts[i].debit - jv_record.accounts[i].credit
                transaction_single = {
                    'account': get_account_number(jv_record.accounts[i].account),
                    'amount': amount,
                    'currency': jv_record.accounts[i].account_currency,
                    'key_currency': key_currency,
                    'key_amount': key_amount
                }
                if jv_record.multi_currency == 1:
                    transaction_single['exchange_rate'] = jv_record.accounts[i].exchange_rate

                transaction['against_singles'].append(transaction_single)
            # insert transaction
            transactions.append(transaction)  
                    
        return transactions      
          
    # prepare transfer file
    def render_transfer_file(self, restrict_currencies=None):
        data = {
            'transactions': self.prepare_transactions()
        }            
        
        
        content = frappe.render_template('erpnextswiss/erpnextswiss/doctype/abacus_export_file/transfer_file.html', data)
        return {'content': content}

    def get_account_list(self):
        account_list = []
        for a in self.accounts:
            account_list.append(a.account)
        return account_list
        
    # extract document names of one doctype as list
    def get_docs(self, dt):
        docs = []
        for d in self.references:
            if d.get('dt') == dt:
                docs.append(d.get('dn'))
        return docs
        
# safe call to get SQL IN statement    
def get_sql_list(docs):
    if docs:
        return (','.join('"{0}"'.format(w) for w in docs))
    else:
        return '""'

# get account number
def get_account_number(account_name):
    if account_name:
        return frappe.get_value("Account", account_name, "account_number")
    else:
        return None
