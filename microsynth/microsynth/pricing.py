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
    Exception: If the reference rate is 0, no discount can be computed and the general discount is used instead.
    """
    start_ts = datetime.now()
    negative_discount_warnings = ""
    try:
        reference_rate = float(reference_rate)
        new_reference_rate = float(new_reference_rate)
    except ValueError:
        msg = f"Cannot convert '{reference_rate}' or '{new_reference_rate}' to a float ({reference_price_list_name=}, {item_code=}, {min_qty=}). Going to return."
        print(msg)
        frappe.log_error(msg, "pricing.change_reference_rate")
        return negative_discount_warnings

    current_reference_rate = get_rate_or_none(item_code, reference_price_list_name, min_qty)
    if current_reference_rate is None:
        msg = f"No reference rate found for {item_code=}, {reference_price_list_name=}, {min_qty=}. Going to return."
        print(msg)
        frappe.log_error(msg, "pricing.change_reference_rate")
        return negative_discount_warnings

    if abs(reference_rate - new_reference_rate) < 0.0001:
        #print(f"{reference_rate=} == {new_reference_rate=} -> nothing to do. Going to return.")
        return negative_discount_warnings

    if abs(current_reference_rate - reference_rate) > 0.0001:
        msg = f"{current_reference_rate=} in the ERP is unequals given {reference_rate=} ({reference_price_list_name=}, {item_code=}, {min_qty=}). Going to return."
        print(msg)
        frappe.log_error(msg, "pricing.change_reference_rate")
        return negative_discount_warnings
    
    if frappe.get_value('Item', item_code, 'disabled'):
        msg = f"Item {item_code} is disabled. Unable to change Item Prices with {min_qty=} for reference price list '{reference_price_list_name}'. Going to return."
        print(msg)
        frappe.log_error(msg, "pricing.change_reference_rate")
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

        if abs(reference_rate) < 0.0001:  # reference_rate is too close to 0 to calculate the discount (division by 0 issue) -> apply General Discount
            #msg = f"Unable to change customer Price List rate for item {item_code} with {min_qty=} on Price List '{price_list['name']}' since {reference_rate=} is too close to 0 to divide by it for computing the current discount"
            #msg = f"WARNING: {reference_rate=} -> Customer Price List rate is set to 0"
            #frappe.log_error(msg, 'pricing.change_reference_rate')
            try:
                general_discount = frappe.get_value("Price List", price_list['name'], "general_discount")
                new_customer_rate = ((100 - general_discount) / 100) * new_reference_rate
                new_customer_rate = round(new_customer_rate, 4)
                set_rate(item_code, price_list['name'], min_qty, new_customer_rate)
            except Exception as e:
                msg = f"Got the following exception when trying to save the new customer rate {new_customer_rate} for item {item_code} with minimum quantity {min_qty} on Price List '{price_list['name']}':\n{e}"
                print(msg)
                frappe.log_error(msg, 'pricing.change_reference_rate')
            else:
                changes += f"\n{price_list['name']};{customer_rate};{new_customer_rate}"
                counter += 1
            continue

        discount = (reference_rate - customer_rate) / reference_rate * 100

        if discount < 0:
            # "customer_price_list;reference_price_list;item_code;min_qty;customer_rate;reference_rate;discount"
            negative_discount_warnings += f"{price_list['name']};{reference_price_list_name};{item_code};{min_qty};{customer_rate};{reference_rate};{round(discount, 2)}\n"
            #msg = f"WARNING: {discount=} < 0 for item {item_code} with {min_qty=} on Price List '{price_list['name']}' -> new Customer Price List rate will be higher than reference Price List rate"
            #frappe.log_error(msg, 'pricing.change_reference_rate')
            discount = 0

        new_customer_rate = ((100 - discount) / 100) * new_reference_rate
        new_customer_rate = round(new_customer_rate, 4)
        try:
            set_rate(item_code, price_list['name'], min_qty, new_customer_rate)
        except Exception as e:
            msg = f"Got the following exception when trying to save the new customer rate {new_customer_rate} for item {item_code} with minimum quantity {min_qty} on Price List '{price_list['name']}':\n{e}"
            print(msg)
            frappe.log_error(msg, 'pricing.change_reference_rate')
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
        frappe.log_error(msg, 'pricing.change_reference_rate')
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
    bench execute microsynth.microsynth.pricing.change_rates_from_csv --kwargs "{'csv_file': '/mnt/erp_share/JPe/testprices.csv', 'user': 'firstname.lastname@microsynth.ch'}"
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
            csv_reader = csv.reader(file, delimiter=';')
            next(csv_reader)  # skip header
            for line in csv_reader:
                assert len(line) == 9, f"Line '{line}' is expected to have length 9, but has length {len(line)}."  # Sr,Name,Docstatus,Item Code,Minimum Qty,Item Name,Price List,Rate,Currency
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


def find_item_price_duplicates(outfile):
    """
    List Item Prices with multiple occurrences on the same Price List, for the same Item and same Quantity.

    run
    bench execute microsynth.microsynth.pricing.find_item_price_duplicates --kwargs "{'outfile': '/mnt/erp_share/JPe/all_active_item_price_duplicates_2024-07-09.csv'}"
    """
    sql_query = """
        SELECT 
            CONCAT(`item_code`, ":", `price_list`, ":", `min_qty`) AS `key`,
            `item_code`, 
            `price_list`, 
            `min_qty`,
            `modified`,
            `creation`,
            (SELECT `disabled` FROM `tabItem` WHERE `tabItem`.`name` = `tabItem Price`.`item_code`) AS `item_disabled`,
            (SELECT IF(`enabled`=0,1,0) FROM `tabPrice List` WHERE `tabPrice List`.`name` = `tabItem Price`.`price_list`) AS `price_list_disabled`,
            GROUP_CONCAT(`price_list_rate`) AS `rates`,
            GROUP_CONCAT(`modified`) AS `last_modified`,
            GROUP_CONCAT(`creation`) AS `creation`,
            GROUP_CONCAT(`name`) AS `item_price_names`
        FROM `tabItem Price`
        GROUP BY `key`
        HAVING COUNT(`name`) > 1;
    """
    duplicates = frappe.db.sql(sql_query, as_dict=True)
    print("query done")
    active_duplicates = []
    for d in duplicates:
        if not d.item_disabled and not d.price_list_disabled:
            active_duplicates.append(d)

    # duplicates_with_different_non_zero_rates = []
    # for ad in active_duplicates:
    #     rates = ad['rates'].split(',')
    #     # Find first rate != 0
    #     first_non_zero_rate = None
    #     for rate in rates:
    #         rate = round(float(rate), 4)
    #         if rate != 0:
    #             first_non_zero_rate = rate
    #     for rate in rates:
    #         rate = round(float(rate), 4)
    #         if first_non_zero_rate and rate != first_non_zero_rate and rate != 0:
    #             duplicates_with_different_non_zero_rates.append(ad)
    #             break

    grouped_by_price_lists = {}

    # for e in duplicates_with_different_non_zero_rates:
    for e in active_duplicates:
        if e['price_list'] not in grouped_by_price_lists:
            grouped_by_price_lists[e['price_list']] = [e]
        else:
            grouped_by_price_lists[e['price_list']].append(e)

    grouped_by_sales_managers = {}

    for price_list, items in grouped_by_price_lists.items():
        managers = frappe.db.sql(f"""
            SELECT 
                GROUP_CONCAT(`account_manager`) AS `sales_managers`
            FROM `tabCustomer`
            WHERE `tabCustomer`.`default_price_list` = '{price_list}'
                AND `tabCustomer`.`disabled` = 0
            ;""", as_dict=True)
        if managers and len(managers) > 0 and 'sales_managers' in managers[0] and managers[0]['sales_managers'] and len(managers[0]['sales_managers']) > 0:
            users = managers[0]['sales_managers'].split(',')
            distinct_sales_managers = ', '.join(str(u) for u in set(users))
        else:
            distinct_sales_managers = "not the default Price List of any enabled Customer"
            #continue  # ELa decided to disable those Price Lists
        if not distinct_sales_managers in grouped_by_sales_managers:
            grouped_by_sales_managers[distinct_sales_managers] = {}
            grouped_by_sales_managers[distinct_sales_managers][price_list] = {}
        else:
            grouped_by_sales_managers[distinct_sales_managers][price_list] = {}

        for e in items:
            item_price_duplicates = []
            item_price_names = e['item_price_names'].split(',')
            for name in item_price_names:
                item_price = frappe.get_doc("Item Price", name)
                # append a tuple of creation date and a dictionary with details to output
                item_price_duplicates.append((item_price.creation, {
                        'item_name': item_price.item_name,
                        'min_qty': item_price.min_qty,
                        'name': item_price.name,
                        'delete': '',
                        'price_list_rate': item_price.price_list_rate,
                        'currency': item_price.currency,
                        'valid_from': item_price.valid_from,
                        'creation': item_price.creation,
                        'owner': item_price.owner,
                        'modified': item_price.modified,
                        'modified_by': item_price.modified_by
                    }))
            item_price_duplicates.sort()  # sort in-place by the creation date (first element of tuple) ascending (oldest first)
            all_other_by_administrator = True
            if item_price_duplicates[0][1]['price_list_rate'] == 0:  # check if rate of oldest (first) Item Price is 0
                for i in range(1, len(item_price_duplicates)):
                    if item_price_duplicates[i][1]['owner'] != 'Administrator':  # check if all other Item Prices are created by the Administrator
                        all_other_by_administrator = False
                        break
                if all_other_by_administrator:
                    for i in range(1, len(item_price_duplicates)):
                        item_price_duplicates[i][1]['delete'] = 'delete'
            grouped_by_sales_managers[distinct_sales_managers][price_list][e['item_code']] = item_price_duplicates

    with open(outfile, mode='w') as file:
        file.write("Sales Manager;Price List;Item Code;Item Name;Minimum Quantity;Item Price ID;Delete?;Rate;Currency;Valid from date;Creation date;Creator;Last Modified date;Last Modified by\r\n")
        for sales_manager, price_lists in grouped_by_sales_managers.items():
            for price_list, items in price_lists.items():
                for item_code, item_price_duplicates in items.items():
                    for item_price_details in item_price_duplicates:
                        e = item_price_details[-1]
                        file.write(f"{sales_manager};{price_list};{item_code};'{e['item_name']}';{e['min_qty']};{e['name']};{e['delete']};{e['price_list_rate']};{e['currency']};{e['valid_from']};{e['creation']};{e['owner']};{e['modified']};{e['modified_by']}\r\n")
                    file.write(";;;;;;;;;;;;\r\n")
                file.write(";;;;;;;;;;;;\r\n")
            file.write(";;;;;;;;;;;;\r\n")
        file.write(";;;;;;;;;;;;\r\n")

    price_list_duplicates = []
    for price_list, duplicates in grouped_by_price_lists.items():
        price_list_duplicates.append((price_list, len(duplicates)))
    for tuple in sorted(price_list_duplicates, key=lambda x: x[1], reverse=True):
        print(f"Price List '{tuple[0]}' has {tuple[1]} Item Prices with the same Item Code and the same Qty more than once.")

    print(f"\nThere are {len(active_duplicates)} active duplicates (Item enabled and Price List enabled) on {len(grouped_by_price_lists)} different Price Lists.")


def delete_item_price_duplicates(price_list, dry_run=True):
    """
    If there are exact two Item Prices with the same Item Code, same Qty and same rate on the given Price List, delete one of them.

    delete_item_price_duplicates('Fr_Par_ENS', True)

    bench execute microsynth.microsynth.pricing.delete_item_price_duplicates --kwargs "{'price_list': 'Fr_Par_ENS', 'dry_run': True}"
    """
    sql_query = f"""
        SELECT 
            CONCAT(`item_code`, ":", `min_qty`) AS `key`,
            `item_code`, 
            `min_qty`,
            (SELECT `disabled` FROM `tabItem` WHERE `tabItem`.`name` = `tabItem Price`.`item_code`) AS `item_disabled`,
            GROUP_CONCAT(`name`) AS `item_price_names`
        FROM `tabItem Price`
        WHERE `tabItem Price`.`price_list` = '{price_list}'
        GROUP BY `key`
        HAVING COUNT(`name`) > 1;
    """
    duplicates = frappe.db.sql(sql_query, as_dict=True)
    print(f"{len(duplicates)=}")
    if len(duplicates) == 0:
        print(f"Found no duplicates on the given Price List '{price_list}'. Are they already deleted?")
    for dup in duplicates:
        item_price_names = dup['item_price_names'].split(',')
        if len(item_price_names) == 2:
            item_price_0 = frappe.get_doc("Item Price", item_price_names[0])
            item_price_1 = frappe.get_doc("Item Price", item_price_names[1])
            if item_price_0.price_list_rate == item_price_1.price_list_rate:
                details = f"Item Price {item_price_0.name} (Price List {item_price_0.price_list}, Item Code {item_price_0.item_code}, Qty {item_price_0.min_qty}, Rate {item_price_0.price_list_rate} {item_price_0.currency})"
                if not dry_run:
                    item_price_0.delete()
                    print(f"Deleted {details}.")
                else:
                    print(f"Would delete {details}.")
            else:
                print(f"Rates do not match: {len(item_price_names)=} for {dup=}")
        else:
            print(f"{len(item_price_names)=} for {dup=}")


def delete_item_prices(csv_file, dry_run=True):
    """
    Takes a CSV file and deletes the Item Prices that are marked as to be deleted in the CSV file.

    Expected header of csv_file:
    0:Sales Manager; 1:Price List; 2:Item Code; 3:Item Name; 4:Minimum Quantity; 5:Item Price ID; 6:Delete?; 7:Rate; 8:Currency; 9:Valid from date; 10:Creation date; 11:Creator; 12:Last Modified date; 13:Last Modified by
    
    bench execute microsynth.microsynth.pricing.delete_item_prices --kwargs "{'csv_file': '/mnt/erp_share/JPe/2024-07-24_all_active_item_price_duplicates_to_delete.csv', 'dry_run': True}"
    """
    import csv
    with open(csv_file) as file:
        print(f"Parsing '{csv_file}' ...")
        csv_reader = csv.reader(file, delimiter=";")
        next(csv_reader)  # skip header
        for line in csv_reader:
            if len(line) != 14:
                print(f"Line '{line}' has length {len(line)}, but expected length 14. Going to continue.")
                continue
            if line[6] == "delete":
                item_price_name = line[5]
                if not frappe.db.exists("Item Price", item_price_name):
                    print(f"Item Price {item_price_name} does not exist (anymore).")
                    continue
                item_price = frappe.get_doc("Item Price", item_price_name)
                details = f"Item Price {item_price.name} (Price List {item_price.price_list}, Item Code {item_price.item_code}, Qty {item_price.min_qty}, Rate {item_price.price_list_rate} {item_price.currency})"
                # check that there are at least two Item Prices with the same combination of Item Code, Qty and Price List
                sql_query = f"""
                    SELECT
                        `name`,
                        `price_list`,
                        `item_code`, 
                        `min_qty`,
                        `price_list_rate`,
                        `currency`
                    FROM `tabItem Price`
                    WHERE `price_list` = '{item_price.price_list}'
                        AND `item_code` = '{item_price.item_code}'
                        AND `min_qty` = {item_price.min_qty}
                    ;"""
                duplicates = frappe.db.sql(sql_query, as_dict=True)
                if len(duplicates) < 2:
                    print(f"{details} seems to be the only Item Price with the given combination of Item Code and Qty. Going to NOT delete it.")
                    continue
                if not dry_run:
                    item_price.delete()
                    #frappe.db.commit()  # not necessary, the deletion is considered when query again
                    print(f"Deleted {details}.")
                else:
                    print(f"Would delete {details}.")


def delete_item_prices_of_disabled_items(disabled_items, verbose=False, dry_run=True):
    """
    Takes a list of Item Codes, checks if the Item is disabled and if yes, deletes all Item Prices of this Item.

    bench execute microsynth.microsynth.pricing.delete_item_prices_of_disabled_items --kwargs "{'disabled_items': ['30050', '30051'], 'verbose': False, 'dry_run': True}"
    """
    total_counter = 0
    for item_code in disabled_items:
        print(f"process item '{item_code}'...")
        counter = 0
        item = frappe.get_doc("Item", item_code)
        if not item.disabled:
            print(f"The given Item {item_code} is not yet disabled. Going to continue with the next Item.")
            continue
        item_prices = frappe.get_all("Item Price", filters={'item_code': item_code}, fields=['name'])
        for item_price in item_prices:
            if not dry_run:
                item_price_doc = frappe.get_doc("Item Price", item_price['name'])
                item_price_doc.delete()
            if verbose:
                print(f"Deleted Item Price {item_price['name']} of Item {item_code}.")
            counter += 1
        frappe.db.commit()
        print(f"{'Would have deleted' if dry_run else 'Deleted'} {counter} Item Prices for Item {item_code}: {item.item_name}.")
        total_counter += counter
    print(f"{'Would have deleted' if dry_run else 'Deleted'} {total_counter} Item Prices in total.")


def copy_prices_from_projects_to_reference(item_codes, dry_run=True):
    """
    Takes a list of Item Codes and copies the corresponding Item Prices from the Projects to the respective reference Price List.

    bench execute microsynth.microsynth.pricing.copy_prices_from_projects_to_reference --kwargs "{'item_codes': ['20005','20006','20007','20011','20012','20013','20014','20015','20040','20041','20042','20043','20044','30000','30013','30014','30043','30044','30075','30076','30080','30081','30082','30083','30085','30087','30088','30094','30098','30099','30105','30106','30107','30119','30120','30138','30303','30304','30340','30341','30342','30500','30505','30510','30515','30520','30525','30530','30535','30550','30555','30560','30565','30570','30575','30605','30610','30615','30620','30625','30650','30655','30660','30665','30700','30705','30707','30710','30715','30720','30750','30800','30810','30850','31000','31010','31020','31030']}"
    """
    counter = {'CHF': 0, 'EUR': 0, 'USD': 0}
    for item_code in item_codes:
        print(f"Processing Item {item_code} ...")
        # check if Item is enabled
        if frappe.get_value("Item", item_code, "disabled"):
            print(f"Item {item_code} is disabled. Going to skip.")
            continue
        for currency in ['CHF', 'EUR', 'USD']:
            projects_price_list_name = 'Projects ' + currency
            reference_price_list_name = 'Sales Prices ' + currency
            item_prices = frappe.db.get_all("Item Price",
                                            filters=[['price_list', '=', projects_price_list_name], ['item_code', '=', item_code]],
                                            fields=['name', 'price_list_rate', 'min_qty', 'currency'])
            if len(item_prices) == 0:
                print(f"There is no Item Price for Item {item_code} on Price List {projects_price_list_name}.")
                continue
            for item_price in item_prices:
                if currency != item_price['currency']:
                    print(f"Currency mismatch for Item Price {item_price['name']}")
                    continue
                # check if Item Price already exist
                existing_item_prices = frappe.db.get_all("Item Price",
                                            filters=[['price_list', '=', reference_price_list_name], ['item_code', '=', item_code], ['min_qty', '=', item_price['min_qty']]],
                                            fields=['name', 'price_list_rate', 'min_qty', 'currency'])
                if len(existing_item_prices) > 0:
                    part = f"is already one Item Price" if len(existing_item_prices) == 1 else f"are already {len(existing_item_prices)} Item Prices"
                    print(f"There {part} on {reference_price_list_name} for Item {item_code} with Minimum Qty {item_price['min_qty']}. Going to skip Item {item_code}.")
                    continue
                # create new reference price
                new_item_price = frappe.get_doc({
                    'doctype': "Item Price",
                    'item_code': item_code,
                    'min_qty': item_price['min_qty'],
                    'price_list': reference_price_list_name,
                    'buying': 0,
                    'selling': 1,
                    'currency': item_price['currency'],
                    'price_list_rate': item_price['price_list_rate']
                })
                if not dry_run:
                    new_item_price.insert()
                counter[currency] += 1
    print(f"{'Would create' if dry_run else 'Created'} {counter} new Item Prices on the reference Price Lists.")


def max_percentage_diff(a, b):
    if a == b:
        return 0
    try:
        a_to_b = (abs(a - b) / b) * 100.0
        b_to_a = (abs(b - a) / a) * 100.0
        return max(a_to_b, b_to_a)
    except ZeroDivisionError:
        return float('inf')


def group_price_lists(reference_price_list, tolerance_percentage=2.5, verbose_level=3):
    """
    Search for similar Price Lists that refer to the given reference Price List.

    Verbose levels (higher levels include all smaller levels except level 0):
    0: Hide all prints
    1: Print final groups
    2: Print Price List name that is currently checked
    3: Print groups for the recently checked Price List
    4: Print the first reason found why two Price Lists are not similar except missing Items
    5: Print Items for which there is no Item Price with the same minimim qty on both Price Lists compared

    bench execute microsynth.microsynth.pricing.group_price_lists --kwargs "{'reference_price_list': 'Sales Prices USD', 'tolerance_percentage': 3.0, 'verbose_level': 3}"
    """
    price_lists = frappe.db.get_all("Price List", filters={'enabled': 1, 'reference_price_list': reference_price_list}, fields=['name', 'general_discount'])
    groups = []
    my_fields = ['name', 'price_list', 'item_code', 'item_name', 'min_qty', 'price_list_rate', 'currency']
    already_checked = {}
    for i, base_price_list in enumerate(price_lists):
        if verbose_level > 1:
            print(f"Checking Price List '{base_price_list['name']}' ({i+1}/{len(price_lists)}) ...")
        group = [base_price_list['name']]
        already_checked[base_price_list['name']] = [base_price_list['name']]
        base_item_prices = frappe.db.get_all("Item Price", filters={'price_list': base_price_list['name']}, fields=my_fields)
        for price_list in price_lists:
            if price_list['name'] in already_checked[base_price_list['name']] or (price_list['name'] in already_checked and base_price_list['name'] in already_checked[price_list['name']]):
                continue  # avoid to compare a pair of Price Lists more than once
            already_checked[base_price_list['name']].append(price_list['name'])
            if price_list['name'] in already_checked:
                already_checked[price_list['name']].append(base_price_list['name'])
            else:
                already_checked[price_list['name']] = [base_price_list['name']]
            # skip Price List if General Discount differs
            if abs(base_price_list['general_discount'] - price_list['general_discount']) > tolerance_percentage:
                if verbose_level > 3:
                    print(f"General Discount mismatch: {base_price_list['general_discount']} for '{base_price_list['name']}' vs {price_list['general_discount']} for '{price_list['name']}'")
                continue
            item_prices = frappe.db.get_all("Item Price", filters={'price_list': price_list['name']}, fields=my_fields)
            list_mismatch = False
            for bip in base_item_prices:
                rate_mismatch = False
                rate_match = False
                for ip in item_prices:
                    if bip['item_code'] == ip['item_code'] and bip['min_qty'] == ip['min_qty']:
                        # matching item -> compare rates
                        max_percentage_difference = max_percentage_diff(bip['price_list_rate'], ip['price_list_rate'])
                        if max_percentage_difference > tolerance_percentage:
                            # mismatching rates -> Price Lists differ
                            rate_mismatch = True
                            if verbose_level > 3:
                                print(f"Rate mismatch: Item {bip['item_code']}: {bip['item_name']} with Minimum Qty {bip['min_qty']} on Price List '{base_price_list['name']}' = {bip['price_list_rate']} {bip['currency']} differs by {max_percentage_difference:.2f} % from {ip['price_list_rate']} {ip['currency']} of Item {ip['item_code']}: {ip['item_name']} with Minimum Qty {ip['min_qty']} on Price List '{price_list['name']}'")
                        else:
                            rate_match = True
                        break
                if rate_mismatch:
                    list_mismatch = True
                    break
                elif rate_match:
                    continue
                else:
                    list_mismatch = True
                    if verbose_level > 4:
                        print(f"It seems that Item {bip['item_code']}: {bip['item_name']} with minimum quantity {bip['min_qty']} from Price List '{base_price_list['name']}' does not occur on Price List '{price_list['name']}'.")
                    break
            if list_mismatch:
                continue
            group.append(price_list['name'])
        if len(group) > 1:
            if verbose_level > 2:
                print(group)
            groups.append(group)
    if verbose_level > 0:
        print(f"\nThe rates of all Item Prices on the following Price Lists differ by less than {tolerance_percentage} %:")
        for group in groups:
            for pl in group:
                all_sales_managers = frappe.db.get_all("Customer", filters={'disabled': 0, 'default_price_list': pl}, fields=['account_manager'])
                sales_manager_set = set([sm['account_manager'] for sm in all_sales_managers])
                if len(sales_manager_set) > 0:
                    print(f"Price List '{pl}' is used by enabled Customer(s) of {', '.join(sales_manager_set)}")
                else:
                    print(f"Price List '{pl}' is used by no enabled Customer.")
            print("")
    return groups


def group_all_price_lists():
    """
    bench execute microsynth.microsynth.pricing.group_all_price_lists
    """
    reference_price_lists = frappe.db.get_all("Price List", filters={'enabled': 1, 'reference_price_list': ''}, fields=['name'])
    for ref_pl in reference_price_lists:
        print(f"Processing Price Lists referring to the reference Price List '{ref_pl['name']}' ...")
        groups = group_price_lists(ref_pl['name'], verbose_level=0)
        print(f"Groups of identical Price Lists:\n{groups}")


def compare_ref_to_project():
    """
    List Item Prices that are on a reference Price List but not on the corresponding Projects Price List.

    bench execute microsynth.microsynth.pricing.compare_ref_to_project
    """
    my_fields = ['name', 'price_list', 'item_code', 'item_name', 'min_qty']
    for currency in ['CHF', 'EUR', 'USD']:        
        reference_prices = frappe.db.get_all("Item Price", filters={'price_list': f"Sales Prices {currency}"}, fields=my_fields)
        project_prices = frappe.db.get_all("Item Price", filters={'price_list': f"Projects {currency}"}, fields=my_fields)
        for ref_price in reference_prices:
            # ignore Item Prices of disabled Items
            if frappe.get_value("Item", ref_price['item_code'], 'disabled'):
                continue
            found = False
            for project_price in project_prices:
                if project_price['item_code'] == ref_price['item_code'] and project_price['min_qty'] == ref_price['min_qty']:
                    found = True
                    break
            if found:
                continue
            else:
                print(f"Item {ref_price['item_code']}: {ref_price['item_name']} with minimum Qty {ref_price['min_qty']} is on Sales Prices {currency} but not on Projects {currency}.")

