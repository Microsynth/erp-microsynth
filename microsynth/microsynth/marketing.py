# Copyright (c) 2023, Microsynth
# For license information, please see license.txt

import frappe
from datetime import date, datetime, timedelta
from dateutil.relativedelta import relativedelta
from microsynth.microsynth.utils import get_customer


def update_marketing_classification(contact_id):
    """
    Updates the marketing classification of the given Contact ID.

    run
    bench execute microsynth.microsynth.marketing.update_marketing_classification --kwargs "{'contact_id': 236203}"
    """
    sales_orders = get_sales_orders(contact_person=contact_id)
    update_contact_classification(sales_orders, contact_id)
    customer = get_customer(contact_id)
    update_customer_status([customer])


def get_sales_orders(start_date=None, end_date=None, contact_person=None):
    """
    Returns a dictionary of all submitted Sales Orders in the given date range with the given Contact Person that are not Closed or Cancelled.
    """
    if not start_date and not end_date:
        date_filter = ""
    else:
        assert start_date and end_date  # it is not supported to provide only start_date or end_date
        date_filter = f'AND `transaction_date` BETWEEN "{start_date}" AND "{end_date}"'
    if contact_person:
        person_filter = f'AND `contact_person` = "{contact_person}"'
    else:
        person_filter = ""

    sql_query = f"""
        SELECT `name`,
            `contact_person`,
            `customer`,
            `transaction_date`
        FROM `tabSales Order`
        WHERE
          `docstatus` = 1
          AND `status` NOT IN ("Closed", "Cancelled")
          {date_filter}
          {person_filter}
        ORDER BY `transaction_date` DESC
        """
    return frappe.db.sql(sql_query, as_dict=True)


def get_contacts(customer_id):
    """
    Returns a dictionary of the Contact IDs of all non-Disabled Contacts of the given Customer ID.
    """
    sql_query = f"""
        SELECT `tabContact`.`name` AS `name`
        FROM `tabContact`
        LEFT JOIN `tabDynamic Link` AS `tDLA` ON `tDLA`.`parent` = `tabContact`.`name` 
                                              AND `tDLA`.`parenttype`  = "Contact" 
                                              AND `tDLA`.`link_doctype` = "Customer"
        LEFT JOIN `tabCustomer` ON `tabCustomer`.`name` = `tDLA`.`link_name`
        WHERE `tabCustomer`.`name` = "{customer_id}"
            AND `tabContact`.`status` != "Disabled"
        """
    return frappe.db.sql(sql_query, as_dict=True)


def update_newly_created_contacts(already_updated_contacts, previous_days):
    """
    Called by the function update_new_and_active_contacts.
    Sets the Contact Classification and Customer Status of all new Contacts that are not already processed by the function update_contacts_from_new_orders.
    """
    customers = set()
    sql_query = f"""
        SELECT `tabContact`.`name` AS `name`
        FROM `tabContact`
        WHERE `tabContact`.`creation` BETWEEN "{date.today() - timedelta(days=previous_days)}" AND "{date.today()}"
            AND `tabContact`.`status` != "Disabled"
        """
    new_contacts = frappe.db.sql(sql_query, as_dict=True)

    for contact in new_contacts:
        if contact['name'] in already_updated_contacts:
            continue
        sales_orders = get_sales_orders(contact_person=contact['name'])
        update_contact_classification(sales_orders, contact['name'])
        customer = get_customer(contact['name'])
        customers.add(customer)
    update_customer_status(customers)


def update_contacts_from_new_orders(previous_days):
    """
    Called by the function update_new_and_active_contacts.
    Sets a Contact to active and Buyer if this Contact is Contact Person of a new Sales Order.
    """
    start_date = date.today() - timedelta(days=previous_days)
    updated_contact_persons = set()
    new_orders = get_sales_orders(start_date=start_date, end_date=date.today())
    print(f"{datetime.now()}: Going to update Contacts of {len(new_orders)} new Sales Orders...")

    for idx, order in enumerate(new_orders):
        if order['contact_person'] in updated_contact_persons:
            continue  # avoid processing Contacts twice

        contact_person = frappe.get_doc('Contact', order['contact_person'])

        if contact_person.contact_classification != 'Buyer':
            # update Contact Classification
            contact_person.contact_classification = 'Buyer'
            contact_person.save()

        # update Customer Status of all Contacts of the corresponding Customer
        customer_contacts = get_contacts(order['customer'])
        for contact_id in customer_contacts:
            contact = frappe.get_doc('Contact', contact_id)
            if contact.customer_status != 'active':
                contact.customer_status = 'active'
                try:
                    contact.save()
                except Exception as e:
                    msg = f"Unable to save Contact {contact.name} due to the following error:\n{e}"
                    print(msg)
                    frappe.log_error(msg, 'marketing.update_contacts_from_new_orders')

        updated_contact_persons.add(order['contact_person'])
        frappe.db.commit()

        if idx % 50 == 0 and idx > 0:
            perc = round(100 * idx / len(new_orders), 2)
            print(f"{datetime.now()}: Already updated Contacts of {perc} % ({idx}) of {len(new_orders)} new Sales Orders.")

    return updated_contact_persons


def update_new_and_active_contacts(previous_days):
    """
    Update Contact Classification and Customer Status of Contact Persons from new Sales Orders and newly created Contacts from the last previous_days.
    Should be run by a cron job every day at midnight or a few minutes after midnight.

    run
    bench execute microsynth.microsynth.marketing.update_new_and_active_contacts --kwargs "{'previous_days': 1}"
    """
    start_ts = datetime.now()
    updated_contact_persons = update_contacts_from_new_orders(previous_days)
    update_newly_created_contacts(updated_contact_persons, previous_days)
    elapsed_time = timedelta(seconds=(datetime.now() - start_ts).total_seconds())
    print(f"{datetime.now()}: Finished update_new_and_active_contacts after {elapsed_time} hh:mm:ss.")


def update_contacts_from_old_orders(days):
    """
    Updates the two fields Contact.contact_classification and Contact.customer_status
    of Contact Persons from Sales Orders that turned one year old in the last :param days.
    Should be run by a cron job once per week (always on the same day of the week).

    run
    bench execute microsynth.microsynth.marketing.update_contacts_from_old_orders --kwargs "{'days': 7}"
    """
    start_ts = datetime.now()
    one_year_ago = date.today() - relativedelta(months = 12)
    start_date = one_year_ago - timedelta(days=days)

    orders = get_sales_orders(start_date=start_date, end_date=one_year_ago)
    print(f"{datetime.now()}: Going to update Contacts of {len(orders)} old Sales Orders...")

    # create empty sets (no duplicates)
    updated_contact_persons = set()
    customers_to_check = set()

    for idx, order in enumerate(orders):
        if order['contact_person'] in updated_contact_persons:
            continue  # avoid processing Contacts twice

        new_orders = get_sales_orders(start_date=one_year_ago, end_date=date.today(), contact_person=order['contact_person'])
        if len(new_orders) < 1:
            contact_person = frappe.get_doc('Contact', order['contact_person'])
            contact_person.contact_classification = 'Former Buyer'
            contact_person.save()
        # else: contact_classification should remain 'Buyer'

        customers_to_check.add(order['customer'])
        updated_contact_persons.add(order['contact_person'])

        if idx % 50 == 0 and idx > 0:
            perc = round(100 * idx / len(orders), 2)
            print(f"{datetime.now()}: Already updated Contact Classification of Contact Persons of {perc} % ({idx}) of {len(orders)} old Sales Orders.")

        frappe.db.commit()

    update_customer_status(customers_to_check)
    elapsed_time = timedelta(seconds=(datetime.now() - start_ts).total_seconds())
    print(f"{datetime.now()}: Finished update_contacts_from_old_orders after {elapsed_time} hh:mm:ss.")


def update_customer_status(customers):
    """
    Sets the Customer Status of all Contacts of the given Customers.
    Assumes that the Contact Classification of the Contacts is correctly set.
    """
    print(f"\n{datetime.now()}: Going to update customer_status of Contacts of {len(customers)} Customers...")

    for idx, customer in enumerate(customers):
        try:
            contacts = get_contacts(customer)
        except Exception as e:
            msg = f"Got the following error when querying Contacts of the Customer '{customer['name']}':\n{e}"
            print(msg)
            frappe.log_error(msg, 'marketing.update_customer_status')
            continue

        status = {'active': False, 'former': False}

        for contact in contacts:
            contact_classification = frappe.get_value('Contact', contact['name'], 'contact_classification')
            if contact_classification == 'Buyer':
                status['active'] = True
            elif contact_classification == 'Former Buyer':
                status['former'] = True
            # else: Lead or ''

        if status['active']:
            # If at least one Contact of this Customer has Contact Classification 'Buyer',
            # all Contacts of this Customer get assigned Customer Status 'active'.
            customer_status = 'active'
        elif status['former']:
            # If no Contact of this Customer has Contact Classification 'Buyer' but at least one Contact of this Customer
            # has Contact Classification 'Former Buyer', all Contacts of this Customer get assigned Customer Status 'former'.
            customer_status = 'former'
        else:
            # If no Contact of this Customer has Contact Classification 'Buyer' or 'Former Buyer',
            # all Contacts of this Customer get assigned Customer Status 'potential'.
            customer_status = 'potential'

        for contact in contacts:
            contact_doc = frappe.get_doc('Contact', contact['name'])
            if contact_doc.customer_status != customer_status:
                contact_doc.customer_status = customer_status
                #frappe.db.set_value("Contact", contact['name'], "customer_status", customer_status, update_modified = False)
                try:
                    contact_doc.save()
                except Exception as e:
                    msg = f"Unable to save Contact {contact.name} due to the following error:\n{e}"
                    print(msg)
                    frappe.log_error(msg, 'marketing.update_customer_status')

        if idx % 200 == 0 and idx > 0:
            frappe.db.commit()
            print(f"{datetime.now()}: Already updated Customer Status of Contacts of {round(100 * idx / len(customers), 2)} % ({idx}) of {len(customers)} Customers.")

    frappe.db.commit()


def update_contact_classification(sales_orders, contact_name):
    """
    Sets the Contact Classification of the given Contact according to the given Sales Orders.
    Assumes that the given Sales Orders are sorted by transaction_date descending (newest first).
    """
    contact = frappe.get_doc("Contact", contact_name)
    one_year_ago = date.today() - relativedelta(months = 12)
    if len(sales_orders) > 0:
        newest_order = sales_orders[0]
        if newest_order['transaction_date'] >= one_year_ago:
            contact_classification = 'Buyer'
        else:
            contact_classification = 'Former Buyer'
    else:
        # Do not change contact.status since webshop is using it
        contact_classification = 'Lead'
        
    #frappe.db.set_value("Contact", contact_name, "contact_classification", contact_classification, update_modified = False)
    if contact.contact_classification != contact_classification:
        contact.contact_classification = contact_classification
        try:
            contact.save()
        except Exception as e:
            msg = f"Unable to save Contact {contact_name} due to the following error:\n{e}"
            print(msg)
            frappe.log_error(msg, 'marketing.initialize_contact_classification')
        frappe.db.commit()


def initialize_contact_classification():
    """
    Initializes the field Contact.contact_classification for all Contacts that have not Status Disabled.
    """
    start_ts = datetime.now()
    contacts = frappe.get_all("Contact", filters={'status': ('!=', 'Disabled')}, fields=['name'])
    print(f"{datetime.now()}: Going to initialize contact_classification of {len(contacts)} Contacts...")

    for idx, contact in enumerate(contacts):
        sales_orders = get_sales_orders(contact_person=contact['name'])
        update_contact_classification(sales_orders, contact['name'])
        
        if idx % 100 == 0 and idx > 0:
            frappe.db.commit()
            perc = round(100 * idx / len(contacts), 2)
            print(f"{datetime.now()}: Already initialized Contact Classification of {perc} % ({idx}) of all {len(contacts)} Contacts.")

    frappe.db.commit()
    elapsed_time = timedelta(seconds=(datetime.now() - start_ts).total_seconds())
    print(f"{datetime.now()}: Finished initialize_contact_classification after {elapsed_time} hh:mm:ss.")


def initialize_customer_status():
    """
    Initializes the field Contact.customer_status for all Contacts of all Customers.
    Assumes the function initialize_contact_classification to be run beforehand.
    """
    start_ts = datetime.now()
    customers_dict = frappe.get_all("Customer", fields=['name'])
    customers_set = set([c['name'] for c in customers_dict])  # convert dict to a set
    update_customer_status(customers_set)
    elapsed_time = timedelta(seconds=(datetime.now() - start_ts).total_seconds())
    print(f"{datetime.now()}: Finished initialize_customer_status after {elapsed_time} hh:mm:ss.")


def initialize_marketing_classification():
    """
    Initializes the two fields Contact.contact_classification and Contact.customer_status.

    run
    bench execute microsynth.microsynth.marketing.initialize_marketing_classification
    """
    initialize_contact_classification()
    initialize_customer_status()


def lock_contact_by_name(contact):
    """
    Create Contact Lock for the contact specified by its name.

    run
    bench execute microsynth.microsynth.marketing.lock_contact_by_name --kwargs "{'contact': '220000'}"
    """
    existing_locks = frappe.get_all("Contact Lock", filters={'contact': contact})

    if len(existing_locks) == 0:
        frappe.get_doc({
            'doctype': 'Contact Lock',
            'contact': contact
        }).insert(ignore_permissions=True)
    return


def lock_contact(self, event=None):
    lock_contact_by_name(self.name)
    frappe.db.commit()
    return
