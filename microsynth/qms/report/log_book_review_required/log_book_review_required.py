# Copyright (c) 2026, Microsynth
# For license information, please see license.txt

# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import frappe


def get_columns():
    return [
        # QM Log Book fields
        {"label": "Log Book Entry", "fieldname": "name", "fieldtype": "Link", "options": "QM Log Book", "width": 105},
        #{"label": "Status", "fieldname": "status", "fieldtype": "Data", "width": 100},
        {"label": "Entry Type", "fieldname": "entry_type", "fieldtype": "Data", "width": 135},
        {"label": "Date", "fieldname": "date", "fieldtype": "Date", "width": 80},
		{"label": "Created by", "fieldname": "log_book_creator", "fieldtype": "Link", "options": "User", "width": 150},
        {"label": "Description", "fieldname": "description", "fieldtype": "Text", "width": 250},
        #{"label": "Costs", "fieldname": "costs", "fieldtype": "Link", "options": "Purchase Invoice", "width": 150},
        {"label": "Instrument ID", "fieldname": "document_name", "fieldtype": "Link", "options": "QM Instrument", "width": 95},

        # QM Instrument fields
        {"label": "Instrument Name", "fieldname": "instrument_name", "fieldtype": "Data", "width": 200},
        {"label": "Instrument Status", "fieldname": "instrument_status", "fieldtype": "Data", "width": 120},
        {"label": "Instrument Class", "fieldname": "instrument_class", "fieldtype": "Data", "width": 180},
        {"label": "Regulatory Classification", "fieldname": "regulatory_classification", "fieldtype": "Data", "width": 150},
        {"label": "Site", "fieldname": "site", "fieldtype": "Data", "width": 85},
        #{"label": "Manufacturer", "fieldname": "manufacturer", "fieldtype": "Data", "width": 140},
        {"label": "Serial No", "fieldname": "serial_no", "fieldtype": "Data", "width": 100},
        #{"label": "Supplier", "fieldname": "supplier", "fieldtype": "Link", "options": "Supplier", "width": 75},
        #{"label": "Supplier Name", "fieldname": "supplier_name", "fieldtype": "Data", "width": 200},
    ]


def get_conditions(filters):
    conditions = ""

    if filters.get("qm_instrument"):
        conditions += " AND `tabQM Log Book`.`document_name` = %(qm_instrument)s"

    if filters.get("entry_type"):
        conditions += " AND `tabQM Log Book`.`entry_type` = %(entry_type)s"

    if filters.get("instrument_class"):
        conditions += " AND `tabQM Instrument`.`instrument_class` = %(instrument_class)s"

    if filters.get("regulatory_classification"):
        conditions += " AND `tabQM Instrument`.`regulatory_classification` = %(regulatory_classification)s"

    return conditions


def get_data(filters):
    conditions = get_conditions(filters)

    return frappe.db.sql(f"""
        SELECT
            `tabQM Log Book`.`name`,
            `tabQM Log Book`.`status`,
            `tabQM Log Book`.`entry_type`,
            `tabQM Log Book`.`date`,
            `tabQM Log Book`.`owner` AS `log_book_creator`,
            `tabQM Log Book`.`document_name`,
            `tabQM Log Book`.`description`,
            `tabQM Log Book`.`costs`,

            `tabQM Instrument`.`instrument_name`,
            `tabQM Instrument`.`instrument_class`,
            `tabQM Instrument`.`regulatory_classification`,
            `tabQM Instrument`.`manufacturer`,
            `tabQM Instrument`.`serial_no`,
            `tabQM Instrument`.`supplier`,
            `tabQM Instrument`.`supplier_name`,
            `tabQM Instrument`.`site`,
            `tabQM Instrument`.`status` AS `instrument_status`

        FROM
            `tabQM Log Book`

        LEFT JOIN
                `tabQM Instrument`
            ON
                `tabQM Instrument`.`name` = `tabQM Log Book`.`document_name`

        WHERE
            `tabQM Log Book`.`docstatus` = 1
            AND `tabQM Log Book`.`status` = 'To Review'
            AND `tabQM Log Book`.`date` <= %(to_date)s
            {conditions}

        ORDER BY
            `tabQM Log Book`.`date` ASC,
            `tabQM Instrument`.`name` ASC,
            `tabQM Log Book`.`entry_type` ASC
    """, filters, as_dict=1)


def execute(filters=None):
    if not filters:
        filters = {}
    columns = get_columns()
    data = get_data(filters)
    return columns, data
