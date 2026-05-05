# Copyright (c) 2026, Microsynth
# For license information, please see license.txt

import frappe

# Time interval constants (single source of truth)
REQUALIFICATION_INTERVAL_MONTHS = 24
VERIFICATION_INTERVAL_MONTHS = 12
CALIBRATION_INTERVAL_YEARS = 5

REQUALIFICATION_LOOKAHEAD_WEEKS = 6
VERIFICATION_LOOKAHEAD_WEEKS = 24
CALIBRATION_LOOKAHEAD_WEEKS = 24


def get_columns():
    return [
        {"label": "Instrument", "fieldname": "name", "fieldtype": "Link", "options": "QM Instrument", "width": 80},
        {"label": "Instrument Name", "fieldname": "instrument_name", "fieldtype": "Data", "width": 210},
        {"label": "Instrument Status", "fieldname": "status", "fieldtype": "Data", "width": 120},
        {"label": "Instrument Class", "fieldname": "instrument_class", "fieldtype": "Data", "width": 140},
        {"label": "Requirement Type", "fieldname": "requirement_type", "fieldtype": "Data", "width": 120},
        {"label": "Last Date", "fieldname": "last_activity_date", "fieldtype": "Date", "width": 80},
        {"label": "Last Type", "fieldname": "last_activity_type", "fieldtype": "Data", "width": 120},
        {"label": "Due Date", "fieldname": "due_date", "fieldtype": "Date", "width": 80},
        {"label": "Process", "fieldname": "qm_process", "fieldtype": "Link", "options": "QM Process", "width": 120},
        {"label": "Site", "fieldname": "site", "fieldtype": "Data", "width": 90},
        {"label": "Manufacturer", "fieldname": "manufacturer", "fieldtype": "Data", "width": 120},
        {"label": "Serial No", "fieldname": "serial_no", "fieldtype": "Data", "width": 100},
        {"label": "Supplier", "fieldname": "supplier", "fieldtype": "Link", "options": "Supplier", "width": 85},
        {"label": "Supplier Name", "fieldname": "supplier_name", "fieldtype": "Data", "width": 180},
    ]


def get_conditions(filters):
    requirement = filters.get("requirement_type")

    if requirement == "Requalification in next 6 weeks":
        return f"""AND `requirement_type` = 'Requalification' AND `due_date` <= DATE_ADD(CURDATE(), INTERVAL {REQUALIFICATION_LOOKAHEAD_WEEKS} WEEK)"""

    if requirement == "Verification in next 24 weeks":
        return f"""AND `requirement_type` = 'Verification' AND `due_date` <= DATE_ADD(CURDATE(), INTERVAL {VERIFICATION_LOOKAHEAD_WEEKS} WEEK)"""

    if requirement == "Calibration in next 24 weeks":
        return f"""AND `requirement_type` = 'Calibration' AND `due_date` <= DATE_ADD(CURDATE(), INTERVAL {CALIBRATION_LOOKAHEAD_WEEKS} WEEK)"""

    if requirement == "Overdue":
        return "AND `due_date` < CURDATE()"
    # default
    return f""" AND (
        (`requirement_type` = 'Requalification'
            AND `due_date` <= DATE_ADD(CURDATE(), INTERVAL {REQUALIFICATION_LOOKAHEAD_WEEKS} WEEK))
        OR
        (`requirement_type` IN ('Verification','Calibration')
            AND `due_date` <= DATE_ADD(CURDATE(), INTERVAL {VERIFICATION_LOOKAHEAD_WEEKS} WEEK))
    )"""


def get_data(filters):
    conditions = get_conditions(filters)
    return frappe.db.sql(f"""
        WITH
        `logbook_agg` AS (
            SELECT
                `tabQM Log Book`.`document_name`,
                MAX(CASE WHEN `tabQM Log Book`.`entry_type` = '(Re-)Qualification' THEN `tabQM Log Book`.`date` END) AS `last_requalification`,
                MAX(CASE WHEN `tabQM Log Book`.`entry_type` = 'Verification' THEN `tabQM Log Book`.`date` END) AS `last_verification`,
                MAX(CASE WHEN `tabQM Log Book`.`entry_type` = 'Calibration' THEN `tabQM Log Book`.`date` END) AS `last_calibration`,
                MAX(CASE WHEN `tabQM Log Book`.`entry_type` IN ('Verification','Calibration') THEN `tabQM Log Book`.`date` END) AS `last_verification_or_calibration`
            FROM `tabQM Log Book`
            WHERE `tabQM Log Book`.`docstatus` = 1
                AND `tabQM Log Book`.`status` IN ('To Review','Closed')
            GROUP BY `tabQM Log Book`.`document_name`
        ),
        `instrument_base` AS (
            SELECT
                `tabQM Instrument`.`name`,
                `tabQM Instrument`.`instrument_name`,
                `tabQM Instrument`.`instrument_class`,
                LEFT(`tabQM Instrument`.`instrument_class`, 1) AS `class_letter`,
                `tabQM Instrument`.`qm_process`,
                `tabQM Instrument`.`site`,
                `tabQM Instrument`.`manufacturer`,
                `tabQM Instrument`.`serial_no`,
                `tabQM Instrument`.`supplier`,
                `tabQM Instrument`.`supplier_name`,
                `tabQM Instrument`.`status`,
                `tabQM Instrument`.`acquisition_date`,
                COALESCE(`logbook_agg`.`last_requalification`, `tabQM Instrument`.`acquisition_date`) AS `last_requalification_date`,
                COALESCE(`logbook_agg`.`last_verification`, `tabQM Instrument`.`acquisition_date`) AS `last_verification_date`,
                COALESCE(`logbook_agg`.`last_calibration`, `tabQM Instrument`.`acquisition_date`) AS `last_calibration_date`,
                COALESCE(`logbook_agg`.`last_verification_or_calibration`, `tabQM Instrument`.`acquisition_date`) AS `last_verification_or_calibration_date`
            FROM `tabQM Instrument`
            LEFT JOIN `logbook_agg` ON `logbook_agg`.`document_name` = `tabQM Instrument`.`name`
            WHERE `tabQM Instrument`.`status` != 'Disposed'
                AND LEFT(`tabQM Instrument`.`instrument_class`, 1) IN ('A','P','T','W')
        ),
        `instrument_eval` AS (
            SELECT
                *,
                -- requirement_type
                CASE
                    WHEN `class_letter` = 'A' THEN 'Requalification'
                    WHEN `class_letter` IN ('T','W') THEN 'Verification'
                    WHEN `class_letter` = 'P'
                        AND DATE_ADD(`last_calibration_date`, INTERVAL {CALIBRATION_INTERVAL_YEARS} YEAR) <= DATE_ADD(CURDATE(), INTERVAL {CALIBRATION_LOOKAHEAD_WEEKS} WEEK)
                    THEN 'Calibration'
                    ELSE 'Verification'
                END AS `requirement_type`,

                -- last_activity_date
                CASE
                    WHEN `class_letter` = 'A' THEN `last_requalification_date`
                    WHEN `class_letter` IN ('T','W') THEN `last_verification_date`
                    WHEN `class_letter` = 'P'
                        AND DATE_ADD(`last_calibration_date`, INTERVAL {CALIBRATION_INTERVAL_YEARS} YEAR) <= DATE_ADD(CURDATE(), INTERVAL {CALIBRATION_LOOKAHEAD_WEEKS} WEEK)
                    THEN `last_calibration_date`
                    ELSE `last_verification_or_calibration_date`
                END AS `last_activity_date`,

                -- due_date
                CASE
                    WHEN `class_letter` = 'A' THEN DATE_ADD(`last_requalification_date`, INTERVAL {REQUALIFICATION_INTERVAL_MONTHS} MONTH)
                    WHEN `class_letter` IN ('T','W') THEN DATE_ADD(`last_verification_date`, INTERVAL {VERIFICATION_INTERVAL_MONTHS} MONTH)
                    WHEN `class_letter` = 'P' AND DATE_ADD(`last_calibration_date`, INTERVAL {CALIBRATION_INTERVAL_YEARS} YEAR) <= DATE_ADD(CURDATE(), INTERVAL {CALIBRATION_LOOKAHEAD_WEEKS} WEEK) THEN DATE_ADD(`last_calibration_date`, INTERVAL {CALIBRATION_INTERVAL_YEARS} YEAR)
                    ELSE DATE_ADD(`last_verification_or_calibration_date`, INTERVAL {VERIFICATION_INTERVAL_MONTHS} MONTH)
                END AS `due_date`
            FROM `instrument_base`
        )
        SELECT *
        FROM `instrument_eval`
        WHERE TRUE
        {conditions}
        ORDER BY
            `due_date` ASC,
            `name` ASC
    """, filters, as_dict=True)


def execute(filters=None):
    if not filters:
        filters = {}
    columns = get_columns()
    data = get_data(filters)
    return columns, data
