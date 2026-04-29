# Copyright (c) 2026, Microsynth
# For license information, please see license.txt

# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import json
import frappe
from frappe import _
from microsynth.qms.signing import check_approval_password, sign


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

    if filters.get("qm_process"):
        conditions += " AND `tabQM Instrument`.`qm_process` = %(qm_process)s"

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


site_company_mapping = {
        'Lyon': 'Microsynth France SAS',
        'Göttingen': 'Microsynth Seqlab GmbH',
        'Wien': 'Microsynth Austria GmbH',
        'Balgach': 'Microsynth AG'
    }


@frappe.whitelist()
def review_all_log_book_entries(filters_json, approval_password=None):
    """
    Bulk review all QM Log Book entries matching the filters.

    Permissions:
    - QAU
    - Process owner (if qm_process filter is set)
    - Instrument manager or deputy for ALL involved instruments
    """
    user = frappe.session.user
    filters = json.loads(filters_json) if isinstance(filters_json, str) else filters_json
    entries = get_data(filters)
    if not entries:
        frappe.throw(_("No log book entries found for review."))

    # 1. Preload instruments to minimize db hits
    instrument_names = list({e["document_name"] for e in entries if e.get("document_name")})
    instruments = {}
    if instrument_names:
        instrument_list = frappe.get_all(
            "QM Instrument",
            filters={"name": ["in", instrument_names]},
            fields=[
                "name",
                "site",
                "instrument_manager",
                "deputy_instrument_manager",
                "regulatory_classification"
            ]
        )
        instruments = {inst.name: inst for inst in instrument_list}

    # 2. Permission check: user must be QAU, process owner, or (deputy) instrument manager for all involved instruments
    roles = frappe.get_roles(user)
    is_qau = "QAU" in roles
    is_process_owner = False
    is_instrument_manager = False

    if not is_qau:
        # Process owner check
        if filters.get("qm_process") and instruments:
            site = next(iter(instruments.values())).site
            company = site_company_mapping.get(site)
            if not company:
                frappe.throw(f"Found no company for site {site} to check process owner permissions.")
            owners = frappe.get_all(
                "QM Process Owner",
                filters={
                    "qm_process": filters["qm_process"],
                    "company": company
                },
                fields=["process_owner"]
            )
            is_process_owner = any(o.process_owner == user for o in owners)

        if not is_process_owner:
            # Instrument manager check
            is_instrument_manager = all(
                user in [
                    inst.instrument_manager,
                    inst.deputy_instrument_manager
                ]
                for inst in instruments.values()
            )
    if not (is_qau or is_process_owner or is_instrument_manager):
        frappe.throw(_(
            "You do not have permission to review all entries. "
            "You must be QAU, process owner, or (deputy) instrument manager for all instruments."
        ))

    # 3. Check if any entries are related to GMP instruments
    gmp_instruments = {
        name for name, inst in instruments.items()
        if inst.regulatory_classification == "GMP"
    }
    gmp_entries_exist = any(
        e["document_name"] in gmp_instruments for e in entries
    )
    if gmp_entries_exist:
        frappe.throw("Bulk review of log book entries related to GMP instruments is not allowed. Please review these entries individually to provide the required approval password.")

    # 4. Load Log Book entries and check if they are still "To Review" (might have changed since report was loaded)
    logbook_names = [e["name"] for e in entries]
    logbooks = frappe.get_all(
        "QM Log Book",
        filters={"name": ["in", logbook_names]},
        fields=["name", "status", "document_name"]
    )
    logbooks_map = {lb.name: lb for lb in logbooks}

    # 5. Close entries: set status to "Closed", set closed_on and closed_by, and save
    closed = []
    now = frappe.utils.now_datetime()

    for entry in entries:
        lb = logbooks_map.get(entry["name"])
        if not lb or lb.status != "To Review":
            continue
        is_gmp = lb.document_name in gmp_instruments
        if is_gmp:
            frappe.throw("Bulk review of log book entries related to GMP instruments is not allowed. Please review these entries individually to provide the required approval password.")
        # Load full doc only when needed
        doc = frappe.get_doc("QM Log Book", lb.name)
        doc.status = "Closed"
        doc.closed_on = now
        doc.closed_by = user
        doc.save()
        closed.append(doc.name)

    frappe.db.commit()  # TODO: necessary?
    return {"closed": closed, "count": len(closed)}
