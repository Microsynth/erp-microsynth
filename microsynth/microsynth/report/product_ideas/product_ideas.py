# Copyright (c) 2024, Microsynth, libracore and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _


def get_columns(filters):
    return [
        {"label": _("Name"), "fieldname": "name", "fieldtype": "Link", "options": "Product Idea", "width": 80 },
        {"label": _("Last Modified"), "fieldname": "modified", "fieldtype": "Date", "width": 125 },
        {"label": _("Item Group"), "fieldname": "item_group", "fieldtype": "Link", "options": "Item Group", "width": 150 },
        {"label": _("Territory"), "fieldname": "territory", "fieldtype": "Link", "options": "Territory", "width": 200 },
        {"label": _("Product"), "fieldname": "product", "fieldtype": "Data", "width": 300 },
        {"label": _("Item"), "fieldname": "item", "fieldtype": "Link", "options": "Item", "width": 50 },
        {"label": _("Rating"), "fieldname": "rating", "fieldtype": "Int", "width": 60 },
        {"label": _("Notes"), "fieldname": "notes", "fieldtype": "Data", "width": 350 },
        {"label": _("Has Attachment"), "fieldname": "has_attachment", "fieldtype": "Data", "width": 110},
    ]


def get_data(filters):
    """
    Get raw Product Idea records for Product Ideas report.
    """
    filter_conditions = ''

    if filters:
        if filters.get('from_date'):
            filter_conditions += f"AND `tabProduct Idea`.`modified` >= '{filters.get('from_date')}'"
        if filters.get('to_date'):
            filter_conditions += f"AND `tabProduct Idea`.`modified` <= '{filters.get('to_date')}'"
        if filters.get('item_group'):
            filter_conditions += f"AND `tabProduct Idea`.`item_group` = '{filters.get('item_group')}'"
        if filters.get('territory'):
            filter_conditions += f"AND `tabCustomer`.`territory` = '{filters.get('territory')}'"
        if filters.get('product'):
            filter_conditions += f"AND `tabProduct Idea`.`product` LIKE '%{filters.get('product')}%'"
        if filters.get('item'):
            filter_conditions += f"AND `tabProduct Idea`.`item` = '{filters.get('item')}'"
        if filters.get('rating'):
            filter_conditions += f"AND `tabProduct Idea`.`rating` = '{filters.get('rating')}'"

    query = """
            SELECT
                `tabProduct Idea`.`name`,
                `tabProduct Idea`.`modified`,
                `tabProduct Idea`.`item_group`,
                `tabCustomer`.`territory`,
                `tabProduct Idea`.`product`,
                `tabProduct Idea`.`item`,
                `tabProduct Idea`.`rating`,
                `tabProduct Idea`.`notes`,
                CASE
                    WHEN EXISTS (
                        SELECT 1 FROM `tabFile`
                        WHERE `tabFile`.`attached_to_doctype` = 'Product Idea'
                        AND `tabFile`.`attached_to_name` = `tabProduct Idea`.`name`
                    )
                    THEN 'Yes'
                    ELSE 'No'
                END AS has_attachment
            FROM `tabProduct Idea`
            LEFT JOIN `tabContact` ON `tabContact`.`name` = `tabProduct Idea`.`contact_person`
            LEFT JOIN `tabDynamic Link` AS `tDLA` ON `tDLA`.`parent` = `tabContact`.`name`
                                              AND `tDLA`.`parenttype`  = "Contact"
                                              AND `tDLA`.`link_doctype` = "Customer"
            LEFT JOIN `tabCustomer` ON `tabCustomer`.`name` = `tDLA`.`link_name`
            WHERE TRUE
                {filter_conditions}
            """.format(filter_conditions=filter_conditions)

    return frappe.db.sql(query, as_dict=True)


def execute(filters=None):
    columns, data = get_columns(filters), get_data(filters)
    return columns, data
