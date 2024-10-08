# -*- coding: utf-8 -*-
# Copyright (c) 2024, Microsynth, libracore and contributors and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.utils import get_url_to_form
from frappe.model.document import Document


class AccountingNote(Document):
    pass


@frappe.whitelist()
def get_accounting_notes_html(reference_name):
    """
    """
    comment_string = ""
    query = f"""
        SELECT
            `tabAccounting Note`.`note`,
            `tabAccounting Note`.`name`
        FROM `tabAccounting Note`
        LEFT JOIN `tabAccounting Note Reference` ON `tabAccounting Note Reference`.`parent` = `tabAccounting Note`.`name`
        WHERE 
            `tabAccounting Note`.`reference_name` = '{reference_name}'
            OR `tabAccounting Note Reference`.`reference_name` = '{reference_name}'
        GROUP BY `tabAccounting Note`.`name`
        ORDER BY `tabAccounting Note`.`date` ASC;
        """
    notes = frappe.db.sql(query, as_dict=True)

    for i, note in enumerate(notes):
        url = get_url_to_form("Accounting Note", note['name'])
        url_str = f"<a href={url}><b>{note['name']}</b></a>"
        comment_string += f"{url_str}: {note['note']}"
        if i+1 < len(notes):
            comment_string += "<br>"

    return comment_string