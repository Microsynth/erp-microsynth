# Copyright (c) 2023, Microsynth, libracore and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _


def get_columns(filters):
    return [
        {"label": _("Note ID"), "fieldname": "note_id", "fieldtype": "Link", "options": "Contact Note", "width": 85 },
        {"label": _("Date"), "fieldname": "date", "fieldtype": "Date", "width": 75 },
        {"label": _("Contact"), "fieldname": "contact", "fieldtype": "Link", "options": "Contact", "width": 65 },
        {"label": _("First Name"), "fieldname": "first_name", "fieldtype": "Data", "width": 75 },
        {"label": _("Last Name"), "fieldname": "last_name", "fieldtype": "Data", "width": 100 },
        {"label": _("Sales Manager"), "fieldname": "sales_manager", "fieldtype": "Data", "options": "User", "width": 125 },
        {"label": _("Territory"), "fieldname": "territory", "fieldtype": "Link", "options": "Territory", "width": 150 },
        {"label": _("City"), "fieldname": "city", "fieldtype": "Data", "width": 100 },
        {"label": _("Institute"), "fieldname": "institute", "fieldtype": "Data", "width": 175 },
        {"label": _("Institute Key"), "fieldname": "institute_key", "fieldtype": "Data", "width": 100 },
        {"label": _("Department"), "fieldname": "department", "fieldtype": "Data", "width": 125 },
        {"label": _("Group Leader"), "fieldname": "group_leader", "fieldtype": "Data", "width": 100 },
        {"label": _("Note Type"), "fieldname": "note_type", "fieldtype": "Data", "width": 80 },
        {"label": _("Notes"), "fieldname": "notes", "fieldtype": "Data", "options": "Notes", "width": 250 },
    ]


def get_data(filters):
    """
    Get raw Contact Notes records for find notes report.
    """
    contact_condition = first_name_cond = last_name_cond = sales_manager_cond = ''
    territory_cond = city_cond = institute_cond = institute_key_cond = ''
    group_leader_cond = department_cond = from_date_cond = to_date_cond = ''

    if filters and filters.get('contact'):
        contact_condition = f"AND `tabContact Note`.`contact_person` = '{filters.get('contact')}' "
    if filters and filters.get('first_name'):
        first_name_cond = f"AND `tabContact Note`.`first_name` = '{filters.get('first_name')}' "
    if filters and filters.get('last_name'):
        last_name_cond = f"AND `tabContact Note`.`last_name` = '{filters.get('last_name')}' "
    if filters and filters.get('sales_manager'):
        sales_manager_cond = f"AND `tabCustomer`.`account_manager` LIKE '%{filters.get('sales_manager')}%' "
    if filters and filters.get('territory'):
        territory_cond = f"AND `tabCustomer`.`territory` = '{filters.get('territory')}' "
    if filters and filters.get('city'):
        city_cond = f"AND `tabAddress`.`city` LIKE '%{filters.get('city')}%'"
    if filters and filters.get('institute'):
        institute_cond = f"AND `tabContact`.`institute` LIKE '%{filters.get('institute')}%'"
    if filters and filters.get('institute_key'):
        institute_key_cond = f"AND `tabContact`.`institute_key` LIKE '%{filters.get('institute_key')}%'"
    if filters and filters.get('department'):
        department_cond = f"AND `tabContact`.`department` LIKE '%{filters.get('department')}%'"
    if filters and filters.get('group_leader'):
        group_leader_cond = f"AND `tabContact`.`group_leader` LIKE '%{filters.get('group_leader')}%'"
    if filters and filters.get('from_date'):
        from_date_cond = f"AND `tabContact Note`.`date` >= DATE('{filters.get('from_date')}')"
    if filters and filters.get('to_date'):
        to_date_cond = f"AND `tabContact Note`.`date` <= DATE('{filters.get('to_date')}')"

    query = """
            SELECT
                `tabContact Note`.`name` AS `note_id`,
                `tabContact Note`.`date`,
                `tabContact Note`.`contact_person` AS `contact`,
                `tabContact Note`.`first_name`,
                `tabContact Note`.`last_name`,
                `tabCustomer`.`account_manager` AS `sales_manager`,
                `tabCustomer`.`territory`,
                `tabAddress`.`city`,
                `tabContact`.`institute`,
                `tabContact`.`institute_key`,
                `tabContact`.`department`,
                `tabContact`.`group_leader`,
                `tabContact Note`.`contact_note_type` AS `note_type`,
                `tabContact Note`.`notes`
            FROM `tabContact Note`
            LEFT JOIN `tabContact` ON `tabContact`.`name` = `tabContact Note`.`contact_person`
            LEFT JOIN `tabDynamic Link` AS `tDLA` ON `tDLA`.`parent` = `tabContact`.`name` 
                                              AND `tDLA`.`parenttype`  = "Contact" 
                                              AND `tDLA`.`link_doctype` = "Customer"
            LEFT JOIN `tabCustomer` ON `tabCustomer`.`name` = `tDLA`.`link_name`
            LEFT JOIN `tabAddress` ON `tabAddress`.`name` = `tabContact`.`address`
            WHERE TRUE
                {contact_condition}
                {first_name_cond}
                {last_name_cond}
                {sales_manager_cond}
                {territory_cond}
                {city_cond}
                {institute_cond}
                {institute_key_cond}
                {department_cond}
                {group_leader_cond}
                {from_date_cond}
                {to_date_cond}
            ORDER BY `tabContact Note`.`date` DESC
        """.format(contact_condition=contact_condition, first_name_cond=first_name_cond,
                   last_name_cond=last_name_cond, sales_manager_cond=sales_manager_cond,
                   territory_cond=territory_cond, city_cond=city_cond,
                   from_date_cond=from_date_cond, to_date_cond=to_date_cond,
                   institute_cond=institute_cond, institute_key_cond=institute_key_cond,
                   department_cond=department_cond, group_leader_cond=group_leader_cond)

    return frappe.db.sql(query, as_dict=True)


def execute(filters=None):
    columns, data = get_columns(filters), get_data(filters)
    return columns, data
