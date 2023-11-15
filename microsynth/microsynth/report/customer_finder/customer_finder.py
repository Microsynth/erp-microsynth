# Copyright (c) 2022, Microsynth, libracore and contributors and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
import json


def execute(filters=None):
    columns, data = get_columns(filters), get_data(filters)
    return columns, data


def get_columns(filters):
    return [
        {"label": _("Customer ID"), "fieldname": "customer_id", "fieldtype": "Link", "options": "Customer", "width": 75},
        {"label": _("Customer"), "fieldname": "customer", "fieldtype": "Data", "width": 125},
        {"label": _("Type"), "fieldname": "address_type", "fieldtype": "Data", "width": 35},
        {"label": _("Contact ID"), "fieldname": "contact_id", "fieldtype": "Link", "options":"Contact", "width": 75},
        {"label": _("First Name"), "fieldname": "first_name", "fieldtype": "Data", "width": 75},
        {"label": _("Last Name"), "fieldname": "last_name", "fieldtype": "Data", "width": 75},
        {"label": _("Institute"), "fieldname": "institute", "fieldtype": "Data", "width": 100},
        {"label": _("Institute key"), "fieldname": "institute_key", "fieldtype": "Data", "width": 100},
        {"label": _("Department"), "fieldname": "department", "fieldtype": "Data", "width": 100},
        {"label": _("Group Leader"), "fieldname": "group_leader", "fieldtype": "Data", "width": 75},
        {"label": _("Country"), "fieldname": "country", "fieldtype": "Data", "width": 75},
        {"label": _("City"), "fieldname": "city", "fieldtype": "Data", "width": 75},
        {"label": _("Street"), "fieldname": "street", "fieldtype": "Data", "width": 100},
        {"label": _("Email"), "fieldname": "email_id", "fieldtype": "Data", "width": 120},
        {"label": _("Sales Manager"), "fieldname": "account_manager", "fieldtype": "Data", "width": 70},
        {"label": _("Price List"), "fieldname": "price_list", "fieldtype": "Link", "options":"Price List", "width": 120},
        {"label": _("Tax ID"), "fieldname": "tax_id", "fieldtype": "Data", "width": 110},
        {"label": _("Contact created"), "fieldname": "contact_created", "fieldtype": "Date", "width": 125},
    ]


def get_data(filters):
    
    if type(filters) == str:
        filters = json.loads(filters)
    elif type(filters) == dict:
        pass
    else:
        filters = dict(filters)

    criteria = ""

    hasFilters = False

    if not 'include_disabled' in filters:
        criteria += """ AND `tabCustomer`.`disabled` <> 1 """
    else:
        hasFilters = True

    if 'contact_name' in filters:
        criteria += """ AND `tabContact`.`name` LIKE '%{0}%' """.format(filters['contact_name'])
        hasFilters = True

    if 'contact_full_name' in filters:
        criteria += """ AND `tabContact`.`full_name` LIKE '%{0}%' """.format(filters['contact_full_name'])
        hasFilters = True

    if 'contact_email' in filters:
        criteria += """ AND `tabContact`.`email_id` LIKE '%{0}%' """.format(filters['contact_email'])
        hasFilters = True

    if 'customer' in filters:
        criteria += """ AND `tabCustomer`.`customer_name` LIKE '%{0}%' """.format(filters['customer'])
        hasFilters = True
    
    if 'customer_id' in filters:
        criteria += """ AND `tabCustomer`.`name` = '{0}' """.format(filters['customer_id'])
        hasFilters = True

    if 'contact_institute' in filters:
        criteria += """ AND `tabContact`.`institute` LIKE '%{0}%' """.format(filters['contact_institute'])
        hasFilters = True

    if 'contact_institute_key' in filters:
        criteria += """ AND `tabContact`.`institute_key` LIKE '%{0}%' """.format(filters['contact_institute_key'])
        hasFilters = True

    if 'contact_department' in filters:
        criteria += """ AND `tabContact`.`department` LIKE '%{0}%' """.format(filters['contact_department'])
        hasFilters = True

    if 'contact_group_leader' in filters:
        criteria += """ AND `tabContact`.`group_leader` LIKE '%{0}%' """.format(filters['contact_group_leader'])
        hasFilters = True

    if 'address_country' in filters:
        criteria += """ AND `tabAddress`.`country` LIKE '%{0}%' """.format(filters['address_country'])
        hasFilters = True

    if 'address_city' in filters:
        criteria += """ AND `tabAddress`.`city` LIKE '%{0}%' """.format(filters['address_city'])
        hasFilters = True

    if 'address_street' in filters:
        criteria += """ AND `tabAddress`.`address_line1` LIKE '%{0}%' """.format(filters['address_street'])
        hasFilters = True

    if 'price_list' in filters:
        criteria += """ AND `tabCustomer`.`default_price_list` LIKE '%{0}%' """.format(filters['price_list'])
        hasFilters = True

    if 'tax_id' in filters:
        criteria += """ AND `tabCustomer`.`tax_id` LIKE '%{0}%' """.format(filters['tax_id'])
        hasFilters = True

    if 'account_manager' in filters:
        criteria += """ AND `tabCustomer`.`account_manager` LIKE '%{0}%' """.format(filters['account_manager'])
        hasFilters = True

    if 'contact_status' in filters and filters['contact_status']:
        criteria += """ AND `tabContact`.`status` = '{0}' """.format(filters['contact_status'])
        hasFilters = True

    data = []

    if hasFilters:
        sql_query = """SELECT
            `tabCustomer`.`name` AS `customer_id`,
            `tabCustomer`.`customer_name` AS `customer`,
            `tabAddress`.`address_type` AS `address_type`,
            `tabContact`.`name` AS `contact_id`,
            `tabContact`.`first_name` AS `first_name`,
            `tabContact`.`last_name` AS `last_name`,
            `tabContact`.`email_id` AS `email_id`,
            `tabContact`.`institute` AS `institute`,
            `tabContact`.`department` AS `department`,
            `tabContact`.`group_leader` AS `group_leader`,
            `tabContact`.`institute_key` AS `institute_key`,
            `tabAddress`.`address_line1` AS `address_line1`,
            `tabAddress`.`city` AS `city`,
            `tabAddress`.`country` AS `country`,
            `tabCustomer`.`account_manager` AS `account_manager`,
            `tabCustomer`.`default_price_list` as `price_list`,
            `tabCustomer`.`tax_id` as `tax_id`,
            `tabContact`.`creation` AS `contact_created`

            FROM `tabContact`
            LEFT JOIN `tabDynamic Link` AS `tDLA` ON `tDLA`.`parent` = `tabContact`.`name` 
                                                AND `tDLA`.`parenttype`  = "Contact" 
                                                AND `tDLA`.`link_doctype` = "Customer"
            LEFT JOIN `tabCustomer` ON `tabCustomer`.`name` = `tDLA`.`link_name` 
            LEFT JOIN `tabAddress` ON `tabContact`.`address` = `tabAddress`.`name`
            
            WHERE TRUE
                {criteria}
        """.format(criteria=criteria)

        fetched_data = frappe.db.sql(sql_query, as_dict = True)

        for d in fetched_data:
            entry = {
                "customer_id": d.customer_id,
                "customer": d.customer,
                "address_type": d.address_type,
                "contact_id": d.contact_id,
                "first_name": d.first_name,
                "last_name": d.last_name,
                "email_id": d.email_id,
                "institute": d.institute,
                "institute_key": d.institute_key,
                "department": d.department,
                "group_leader": d.group_leader,
                "country": d.country,
                "city": d.city,
                "street": d.address_line1,
                "account_manager": d.account_manager,
                "price_list": d.price_list,
                "tax_id": d.tax_id,
                "contact_created": d.contact_created
            }
            data.append(entry)

    return data
