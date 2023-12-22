# Copyright (c) 2023, Microsynth
# For license information, please see license.txt

import frappe
from frappe import _
from microsynth.microsynth.report.pricing_configurator.pricing_configurator import set_rate, get_rate_or_none
from datetime import datetime, timedelta
import csv


def change_reference_rate(reference_price_list_name, item_code, min_qty, reference_rate, new_reference_rate, user):
    """
    Change the rate (price) of the given combination of Item Code and minimum quantity
    on each customer price list referring to the given reference price list.
    Thereby, the existing discounts are kept and the new rate is calculated
    by applying this calculated discount to the new reference rate.
    """
    start_ts = datetime.now()
    negative_discount_warnings = ""
    try:
        reference_rate = float(reference_rate)
        new_reference_rate = float(new_reference_rate)
    except ValueError:
        msg = f"Cannot convert '{reference_rate}' or '{new_reference_rate}' to a float ({reference_price_list_name=}, {item_code=}, {min_qty=}). Going to return."
        print(msg)
        frappe.log_error(msg, "pricing_configurator.change_reference_rate")
        return negative_discount_warnings

    current_reference_rate = get_rate_or_none(item_code, reference_price_list_name, min_qty)
    if current_reference_rate is None:
        msg = f"No reference rate found for {item_code=}, {reference_price_list_name=}, {min_qty=}. Going to return."
        print(msg)
        frappe.log_error(msg, "pricing_configurator.change_reference_rate")
        return negative_discount_warnings

    if abs(reference_rate - new_reference_rate) < 0.0001:
        #print(f"{reference_rate=} == {new_reference_rate=} -> nothing to do. Going to return.")
        return negative_discount_warnings

    if abs(current_reference_rate - reference_rate) > 0.0001:
        msg = f"{current_reference_rate=} in the ERP is unequals given {reference_rate=} ({reference_price_list_name=}, {item_code=}, {min_qty=}). Going to return."
        print(msg)
        frappe.log_error(msg, "pricing_configurator.change_reference_rate")
        return negative_discount_warnings
    
    if frappe.get_value('Item', item_code, 'disabled'):
        msg = f"Item {item_code} is disabled. Unable to change Item Prices with {min_qty=} for reference price list '{reference_price_list_name}'. Going to return."
        print(msg)
        frappe.log_error(msg, "pricing_configurator.change_reference_rate")
        return negative_discount_warnings
     
    changes = "pricelist;old_rate;new_rate"
    counter = 0
    
    sql_query = """
        SELECT `name`
        FROM `tabPrice List`
        WHERE `reference_price_list` = '{reference_price_list_name}'
        AND `enabled` = 1
        ;""".format(reference_price_list_name=reference_price_list_name)
    
    price_lists = frappe.db.sql(sql_query, as_dict=True)

    for price_list in price_lists:
        customer_rate = get_rate_or_none(item_code, price_list['name'], min_qty)
        if customer_rate is None:
            # The combination of item_code and min_qty is not on the customer Price List. Happens.
            # Do not add the combination of item_code and min_qty to the customer Price List.
            continue

        if abs(reference_rate) < 0.0001:  # reference_rate is too close to 0 to calculate the discount (division by 0 issue) -> set Customer Price List rate to 0
            #msg = f"Unable to change customer Price List rate for item {item_code} with {min_qty=} on Price List '{price_list['name']}' since {reference_rate=} is too close to 0 to divide by it for computing the current discount"
            #msg = f"WARNING: {reference_rate=} -> Customer Price List rate is set to 0"
            #frappe.log_error(msg, 'pricing_configurator.change_reference_rate')
            set_rate(item_code, price_list['name'], min_qty, 0)
            counter += 1
            continue

        discount = (reference_rate - customer_rate) / reference_rate * 100

        if discount < 0:
            # "customer_price_list;reference_price_list;item_code;min_qty;customer_rate;reference_rate;discount"
            negative_discount_warnings += f"{price_list['name']};{reference_price_list_name};{item_code};{min_qty};{customer_rate};{reference_rate};{round(discount, 2)}\n"
            #msg = f"WARNING: {discount=} < 0 for item {item_code} with {min_qty=} on Price List '{price_list['name']}' -> new Customer Price List rate will be higher than reference Price List rate"
            #frappe.log_error(msg, 'pricing_configurator.change_reference_rate')
            discount = 0

        new_customer_rate = ((100 - discount) / 100) * new_reference_rate
        new_customer_rate = round(new_customer_rate, 4)
        try:
            set_rate(item_code, price_list['name'], min_qty, new_customer_rate)
        except Exception as e:
            msg = f"Got the following exception when trying to save the new customer rate {new_customer_rate} for item {item_code} with minimum quantity {min_qty} on Price List '{price_list['name']}':\n{e}"
            print(msg)
            frappe.log_error(msg, 'pricing_configurator.change_reference_rate')
        else:
            changes += f"\n{price_list['name']};{customer_rate};{new_customer_rate}"
            counter += 1

    # set the new reference rate on the reference price list
    set_rate(item_code, reference_price_list_name, min_qty, new_reference_rate)
    # log changes by creating a new Item Price Log
    end_ts = datetime.now()
    changes += f"\n\nChanged {counter}/{len(price_lists)} Price Lists referring to '{reference_price_list_name}' in {round((end_ts - start_ts).total_seconds(), 2)} seconds. If not all Price Lists are changed, the combination of item_code and min_qty was not on the customer Price List or see the Error Log in the ERP for all others."
    max_length = 65_000  # 65_500 is too large
    if len(changes) > max_length:
        msg = f"{len(changes)=} -> string is going to be truncated to {max_length} characters. Please revise architecture. ({user=}; {price_list['name']=}; {reference_price_list_name=}; {item_code=}; {min_qty=}; {customer_rate=}; {reference_rate=};)"
        print(msg)
        frappe.log_error(msg, 'pricing_configurator.change_reference_rate')
    item_price_log = frappe.get_doc({
        'doctype': 'Item Price Log',
        'price_list': reference_price_list_name,
        'item_code': item_code,
        'min_qty': min_qty,
        'original_rate': reference_rate,
        'new_rate': new_reference_rate,
        'user': user,
        'changes': changes[:max_length]
    })
    item_price_log.insert()
    return negative_discount_warnings


def change_rates_from_csv(csv_file, user):
    """
    Change the reference rate and all dependent customer rates for all entries in the given CSV file
    using the function change_reference_rate.
    IMPORTANT: It is expected that the CSV file has a header and exactly the following columns in this order:
    Reference Price List Name, Item Code, Item Name, Minimum Qty, Current Rate, New Rate
    Outputs a CSV file with warnings about negative discounts to the given csv_file path appended by _warnings.csv

    run from bench
    bench execute microsynth.microsynth.report.pricing_configurator.pricing_configurator.change_rates_from_csv --kwargs "{'csv_file': '/mnt/erp_share/JPe/testprices.csv', 'user': 'firstname.lastname@microsynth.ch'}"
    """
    start_ts = datetime.now()
    # Dry run only to check the CSV file (no changes)
    with open(csv_file, 'r') as file:
        print(f"Checking {csv_file} ...")
        csv_reader = csv.reader(file, delimiter=';')
        next(csv_reader)  # skip header
        no_lines = 0
        for line in csv_reader:
            if len(line) != 6:
                print(f"Expected line length 6 but was {len(line)} for the following line:\n{line}\n"
                      f"No Prices are changed. Please correct CSV file and restart. Going to return.")
                return
            if line[0] not in ('Sales Prices CHF', 'Sales Prices EUR', 'Sales Prices SEK', 'Sales Prices USD'):
                print(f"Got unknown reference price list '{line[0]}'. No Prices are changed. "
                      f"Please correct CSV file or add '{line[0]}' here in the code and restart. Going to return.")
                return
            try:
                min_qty = int(line[3])
                reference_rate = float(line[4])
                new_reference_rate = float(line[5])
            except Exception as error:
                print(f"The following exception occurred during type conversion of min_qty, reference_rate or new_reference_rate:\n{error}\n"
                      f"No Prices are changed. Please correct CSV file and restart. Going to return.")
                return
            no_lines += 1

    negative_discount_warnings = ""

    with open(csv_file, 'r') as file:
        print(f"Changing prices according to {csv_file} ...")
        csv_reader = csv.reader(file, delimiter=';')
        next(csv_reader)  # skip header
        line_counter = 0
        for line in csv_reader:
            reference_price_list_name = line[0]
            item_code = line[1]  # keep as string since leading zeros are removed when converting it to an integer
            # line[2] is Item name and only for human readability
            min_qty = int(line[3])
            reference_rate = float(line[4])
            new_reference_rate = float(line[5])
            warnings = change_reference_rate(reference_price_list_name, item_code, min_qty, reference_rate, new_reference_rate, user)
            negative_discount_warnings += warnings
            line_counter += 1
            print(f"Finished line {line_counter}/{no_lines}: {line}")
    
    if len(negative_discount_warnings) > 0:
        with open(csv_file + '_warnings.csv', 'w') as warnings_file:
            # header for a CSV file collecting warnings about negative discounts
            warnings_file.write("customer_price_list;reference_price_list;item_code;min_qty;customer_rate;reference_rate;discount\n")
            warnings_file.write(negative_discount_warnings)
    
    elapsed_time = timedelta(seconds=(datetime.now() - start_ts).total_seconds())
    print(f"Finished after {elapsed_time} hh:mm:ss.")


def change_rates_from_csv_files(user, file_path):
    """
    Wrapper to call function change_rates_from_csv with multiple csv files.
    Don't forget to change the hard coded file path if necessary.

    run from bench
    bench execute microsynth.microsynth.pricing.change_rates_from_csv_files --kwargs "{'user': 'firstname.lastname@microsynth.ch', 'file_path': '/mnt/erp_share/price_adjustments'}"
    """
    if not frappe.db.exists("User", user):
        print(f"User '{user}' does not exist. Please check User and restart. Going to return.")
        return
    for currency in ['sek', 'usd', 'eur']:  # 'chf',
        print(f"\n########## Start with {currency} ...")
        change_rates_from_csv(f"{file_path}/{currency}.csv", user)


@frappe.whitelist()
def async_change_reference_rate(reference_price_list_name, item_code, min_qty, reference_rate, new_reference_rate, user):
    """
    Wrapper to call function change_reference_rate with a timeout > 120 seconds (here 360 seconds = 6 minutes).
    """        
    frappe.enqueue(method=change_reference_rate, queue='long', timeout=360, is_async=True, job_name='change_reference_rate',
                   reference_price_list_name=reference_price_list_name,
                   item_code=item_code,
                   min_qty=min_qty,
                   reference_rate=reference_rate,
                   new_reference_rate=new_reference_rate,
                   user=user)


def merge_price_lists(filepath):
    """
    Merge four reference price list CSV files to create an overview CSV where the input CSV files originate from Report: Item Price -> Menu -> Export.

    bench execute microsynth.microsynth.pricing.merge_price_lists --kwargs "{'filepath': '/mnt/erp_share/JPe/prices'}"
    """
    merge = dict()
    for currency in ['SEK', 'USD', 'EUR', 'CHF']:
        with open(f"{filepath}/{currency}.csv", 'r') as file:
            csv_reader = csv.reader(file, delimiter=',')
            next(csv_reader)  # skip header
            for line in csv_reader:
                assert len(line) == 9  # Sr,Name,Docstatus,Item Code,Minimum Qty,Item Name,Price List,Rate,Currency
                item_code_qty = (line[3], line[4])  # tuple of Item Code and Minimum Qty
                if item_code_qty not in merge:
                    merge[item_code_qty] = {'CHF': None, 'EUR': None, 'USD': None, 'SEK': None, 'item_name': line[5]}  # create new dict as value of the dict merge
                merge[item_code_qty][currency] = line[7]  # Rate

    with open(f"{filepath}/merge.csv", 'w') as outfile:  # write dict merge to an output CSV file
        outfile.write('Item Code;Minimum Qty;Item Name;Rate [CHF];Rate [EUR];Rate [USD];Rate [SEK]\n')  # header
        for key, value in merge.items():
            outfile.write(f'{key[0]};{key[1]};"{value["item_name"]}";{value["CHF"]};{value["EUR"]};{value["USD"]};{value["SEK"]}\n')


def find_credits_without_jv():
    """
    bench execute microsynth.microsynth.pricing.find_credits_without_jv
    """
    invoices = frappe.get_all('Sales Invoice', filters=[['total_customer_credit', '!=', 0], ['docstatus', '=', 1]], fields=['name'])
    counter = 0
    names = []
    sum = {'EUR': 0, 'USD': 0, 'CHF': 0}
    for invoice in invoices:
        #journal_entries_cancelled = frappe.get_all('Journal Entry', filters=[['user_remark', '=', f"Credit from {invoice['name']}"], ['docstatus', '=', 2]], fields=['name'])
        journal_entries_submitted = frappe.get_all('Journal Entry', filters=[['user_remark', '=', f"Credit from {invoice['name']}"], ['docstatus', '=', 1]], fields=['name'])
        if not journal_entries_submitted:  # journal_entries_cancelled and
            if counter == 0:
                print('Sales Invoice name\tposting_date\ttotal\tcurrency\tdocstatus')
            invoice_obj = frappe.get_doc('Sales Invoice', invoice['name'])
            print(f'{invoice_obj.name}{"  " if len(invoice_obj.name) < 17 else ""}\t{invoice_obj.posting_date}\t{invoice_obj.total}\t{invoice_obj.currency}\t\t{invoice_obj.docstatus}')
            counter += 1
            sum[invoice_obj.currency] += abs(invoice_obj.total)
            names.append(invoice_obj.name)
        else:
            # TODO: Check whether the Journal Entries sum up to the correct amount?
            continue

    print(f'Found {counter} submitted Sales Invoices with total_customer_credit != 0 and no submitted Journal Entry. {sum=}')
