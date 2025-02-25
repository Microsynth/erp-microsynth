# -*- coding: utf-8 -*-
# Copyright (c) 2025, libracore (https://www.libracore.com), Microsynth and contributors
# For license information, please see license.txt

import datetime
import frappe
from frappe.utils import rounded

def find_op_deviation_date(start_date, account, company):
    """
    bench execute microsynth.microsynth.troubleshooting.find_op_deviation_date --kwargs "{'company': '', 'account': '', 'start_date': '2025-01-01'}"
    """
    from microsynth.microsynth.report.accounts_receivable_microsynth.accounts_receivable_microsynth import execute
    
    filters = frappe._dict({
        'company': company,
        'account': account,
        'ageing_based_on': "Posting Date",
        'report_date': start_date,
        'range1': 30,
        'range2': 60,
        'range3': 90,
        'range4': 120
    })
    
    if type(start_date) == str:
        start_date = datetime.datetime.strptime(start_date, "%Y-%m-%d")
    
    print(f"Date\tOP\tGL")
    while start_date.date() <= datetime.datetime.today().date():
        filters.report_date = start_date.strftime("%Y-%m-%d")
        columns, op_data = execute(filters)
        gl_balance = get_foreign_currency_balance(account, filters.report_date)
        
        op_foreign_currency = op_data[-1]['doc_outstanding']
        print(f"{filters.report_date}\t{op_foreign_currency}\t{gl_balance}")
        if rounded(op_foreign_currency, 2) != rounded(gl_balance, 2):
            break
        start_date += datetime.timedelta(days=1)
        
    return
    
def get_foreign_currency_balance(account, date):
    sql_query = """
        SELECT IFNULL((SUM(`debit_in_account_currency`) - SUM(`credit_in_account_currency`)), 0) AS `balance` 
        FROM `tabGL Entry` 
        WHERE
            `account` = "{account}" 
            AND `posting_date` <= "{date}";
        """.format(account=account, date=date)
    
    return frappe.db.sql(sql_query, as_dict=True)[0]['balance']
