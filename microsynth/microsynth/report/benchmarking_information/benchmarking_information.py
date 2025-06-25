# Copyright (c) 2024, Microsynth, libracore and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _


def get_columns(filters):
    return [
        {"label": _("Name"), "fieldname": "name", "fieldtype": "Link", "options": "Benchmark", "width": 85 },
        {"label": _("Item Group"), "fieldname": "item_group", "fieldtype": "Link", "options": "Item Group", "width": 150 },
        {"label": _("Territory"), "fieldname": "territory", "fieldtype": "Link", "options": "Territory", "width": 180 },
        {"label": _("Product"), "fieldname": "product", "fieldtype": "Data", "width": 200 },
        {"label": _("Rate"), "fieldname": "rate", "fieldtype": "Currency", "width": 100, 'options': 'currency'},
        {"label": _("Item"), "fieldname": "item", "fieldtype": "Link", "options": "Item", "width": 65 },
        {"label": _("Competitor"), "fieldname": "competitor", "fieldtype": "Data", "width": 150 },
        {"label": _("Notes"), "fieldname": "notes", "fieldtype": "Data", "width": 250 },
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

    query = """
            SELECT
                `tabBenchmark`.`name`,
                `tabBenchmark`.`item_group`,
                `tabCustomer`.`territory`,
                `tabBenchmark`.`product`,
                `tabBenchmark`.`rate`,
                `tabBenchmark`.`currency`,
                `tabBenchmark`.`item`,
                `tabBenchmark`.`competitor`,
                `tabBenchmark`.`notes`
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
