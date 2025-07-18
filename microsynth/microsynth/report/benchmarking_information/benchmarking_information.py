# Copyright (c) 2024, Microsynth, libracore and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _


def get_columns(filters):
    return [
        {"label": _("Name"), "fieldname": "name", "fieldtype": "Link", "options": "Benchmark", "width": 85 },
        {"label": _("Last Modified"), "fieldname": "modified", "fieldtype": "Date", "width": 125 },
        {"label": _("Item Group"), "fieldname": "item_group", "fieldtype": "Link", "options": "Item Group", "width": 140 },
        {"label": _("Territory"), "fieldname": "territory", "fieldtype": "Link", "options": "Territory", "width": 185 },
        {"label": _("Product"), "fieldname": "product", "fieldtype": "Data", "width": 240 },
        {"label": _("Rate"), "fieldname": "rate", "fieldtype": "Currency", "width": 95, 'options': 'currency'},
        {"label": _("Currency"), "fieldname": "currency", "fieldtype": "Link", "options": "Currency", "width": 40 },
        {"label": _("Item"), "fieldname": "item", "fieldtype": "Link", "options": "Item", "width": 50 },
        {"label": _("Competitor"), "fieldname": "competitor", "fieldtype": "Data", "width": 180 },
        {"label": _("Notes"), "fieldname": "notes", "fieldtype": "Data", "width": 300 },
        {"label": _("Has Attachment"), "fieldname": "has_attachment", "fieldtype": "Data", "width": 110 },
        {"label": _("Created By"), "fieldname": "owner", "fieldtype": "Link", "options": "User", "width": 100 }
    ]


def get_data(filters):
    """
    Get raw Benchmark records for Benchmarking Information report.
    """
    filter_conditions = ''

    if filters:
        if filters.get('item_group'):
            filter_conditions += f"AND `tabBenchmark`.`item_group` = '{filters.get('item_group')}'"
        if filters.get('territory'):
            filter_conditions += f"AND `tabCustomer`.`territory` = '{filters.get('territory')}'"
        if filters.get('product'):
            filter_conditions += f"AND `tabBenchmark`.`product` LIKE '%{filters.get('product')}%'"
        if filters.get('item'):
            filter_conditions += f"AND `tabBenchmark`.`item` = '{filters.get('item')}'"
        if filters.get('competitor'):
            filter_conditions += f"AND `tabBenchmark`.`competitor` LIKE '%{filters.get('competitor')}%'"
        if filters.get('from_date'):
            filter_conditions += f"AND `tabBenchmark`.`modified` >= '{filters.get('from_date')}'"
        if filters.get('to_date'):
            filter_conditions += f"AND `tabBenchmark`.`modified` <= '{filters.get('to_date')}'"

    query = """
            SELECT
                `tabBenchmark`.`name`,
                `tabBenchmark`.`modified`,
                `tabBenchmark`.`item_group`,
                `tabCustomer`.`territory`,
                `tabBenchmark`.`product`,
                `tabBenchmark`.`rate`,
                `tabBenchmark`.`currency`,
                `tabBenchmark`.`item`,
                `tabBenchmark`.`competitor`,
                `tabBenchmark`.`notes`,
                CASE
                    WHEN EXISTS (
                        SELECT 1 FROM `tabFile`
                        WHERE `tabFile`.`attached_to_doctype` = 'Benchmark'
                        AND `tabFile`.`attached_to_name` = `tabBenchmark`.`name`
                    )
                    THEN 'Yes'
                    ELSE 'No'
                END AS has_attachment,
                `tabBenchmark`.`owner`
            FROM `tabBenchmark`
            LEFT JOIN `tabContact` ON `tabContact`.`name` = `tabBenchmark`.`contact_person`
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
