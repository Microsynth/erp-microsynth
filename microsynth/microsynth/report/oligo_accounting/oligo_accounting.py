# Copyright (c) 2024, Microsynth, libracore and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
from microsynth.microsynth.utils import get_child_territories


MONTHS = {
    1: _("January"),
    2: _("February"),
    3: _("March"),
    4: _("April"),
    5: _("May"),
    6: _("June"),
    7: _("July"),
    8: _("August"),
    9: _("September"),
    10: _("October"),
    11: _("November"),
    12: _("December"),
}


def get_columns(filters):
    columns = [
        {"label": _("Scale"), "fieldname": "scale", "fieldtype": "Data", "width": 130}
    ]
    for m in range(1, 13):
        columns.append(
            {"label": MONTHS[m], "fieldname": f"month{m}", "fieldtype": "Integer", "width": 80, "precision": "0" }
        )
    return columns


def get_data(filters):
    conditions = ''

    if 'territory' in filters and filters.get("territory"):
        conditions += "AND `tabCustomer`.`territory` IN ('{0}')".format("', '".join(get_child_territories(filters.get("territory"))))

    if filters.get("fiscal_year"):  # mandatory
        conditions += f"AND YEAR(`tabDelivery Note`.`posting_date`) = {filters.get('fiscal_year')}"

    sql_query = f"""
        SELECT
            YEAR(`oligos`.`date`) AS `year`,
            MONTH(`oligos`.`date`) AS `month`,
            `oligos`.`scale` AS `scale`,
            COUNT(`oligos`.`oligo_name`) AS `oligo_count`

        FROM (
            SELECT `tabOligo`.`name` AS `oligo_name`,
            `tabDelivery Note`.`posting_date` AS `date`,
            `tabOligo`.`scale` AS `scale`

            FROM `tabDelivery Note`

            LEFT JOIN `tabOligo Link` AS `tOL` ON `tabDelivery Note`.`name` = `tOL`.`parent`
                                                AND `tOL`.`parenttype` = "Delivery Note"
            LEFT JOIN `tabOligo` ON `tabOligo`.`name` = `tOL`.`oligo`
            LEFT JOIN `tabCustomer` ON `tabCustomer`.`name` = `tabDelivery Note`.`customer`

            WHERE `tabDelivery Note`.`customer` NOT IN ('8003')
                AND `tabDelivery Note`.`docstatus` = 1
                AND `tabDelivery Note`.`status` != 'Closed'
                {conditions}
        ) AS `oligos`

        GROUP BY CONCAT(`year`, ":", `month`, ":", `scale`)
        ORDER BY `year`, `month`, `scale`;
        """

    raw_data = frappe.db.sql(sql_query, as_dict=True)
    rows = {}
    total_row = {"scale": "Total"}
    data = []

    for entry in raw_data:
        month_key = f"month{entry['month']}"
        scale = entry['scale'] if entry['scale'] else 'unknown'
        if not scale in rows:
            rows[scale] = {}
        rows[scale][month_key] = entry['oligo_count']
        if not month_key in total_row:
            total_row[month_key] = entry['oligo_count']
        else:
            total_row[month_key] += entry['oligo_count']

    for scale, months in rows.items():
        if scale:
            row = {"scale": scale}
            positive_count = False
            for m in range (1, 13):
                month_key = f"month{m}"
                if month_key in months:
                    count = months[month_key]
                    row[month_key] = count
                    positive_count = count > 0 or positive_count
            if positive_count:
                data.append(row)

    data.sort(key=lambda row: row['scale'])
    data.append(total_row)
    return data


def execute(filters=None):
    columns, data = get_columns(filters), get_data(filters)
    return columns, data


def test_get_data():
    """
    bench execute microsynth.microsynth.report.oligo_accounting.oligo_accounting.test_get_data
    """
    filters = {
        'territory': 'Switzerland',
        'fiscal_year': '2023',
    }
    data = get_data(filters)
    print(f"{data=}")
