# Copyright (c) 2024, Microsynth, libracore and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _


def get_columns(filters):
    return [
        #{"label": _("User"), "fieldname": "user", "fieldtype": "Data", "width": 200},
        {"label": _("User"), "fieldname": "name", "fieldtype": "Link", "options": "User Settings", "width": 250}
    ]


def get_data(filters):
    chapter_condition = ""
    if filters:
        if filters.get('chapter'):
            chapter_condition = f"AND (`tabQM User Process Assignment`.`chapter` = '{filters.get('chapter')}' OR `tabQM User Process Assignment`.`all_chapters` = 1)"

        query = f"""
            SELECT `tabUser Settings`.`user`,
                `tabUser Settings`.`name`
            FROM `tabUser Settings`
            LEFT JOIN `tabQM User Process Assignment` ON `tabQM User Process Assignment`.`parent` = `tabUser Settings`.`name`
            WHERE `tabQM User Process Assignment`.`process_number` = '{filters.get('process_number')}'
                AND `tabQM User Process Assignment`.`subprocess_number` = '{filters.get('subprocess_number')}'
                {chapter_condition}
            """
        return frappe.db.sql(query, as_dict=True)
    else:
        return None


def execute(filters=None):
    columns, data = get_columns(filters), get_data(filters)
    return columns, data


def get_users(process, subprocess, chapter=None):
    filters = {
        'process_number': process,
        'subprocess_number': subprocess
    }
    if chapter:
        filters['chapter'] = chapter
    return get_data(filters)
