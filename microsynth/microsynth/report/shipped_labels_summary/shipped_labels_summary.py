# Copyright (c) 2024, Microsynth, libracore and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import csv
import os
import re
from datetime import date, timedelta

import frappe
from frappe import _


def get_columns(filters):
    return [
        {"label": _("Company"), "fieldname": "company", "fieldtype": "Data", "width": 160 },
        {"label": _("Item Code"), "fieldname": "item_code", "fieldtype": "Link", "options": "Item", "width": 75 },
        {"label": _("Quantity"), "fieldname": "count", "fieldtype": "Int", "width": 65 }
    ]


def get_data(filters):
    filters = filters or {}
    where_company = ""
    query_params = {
        "from_date": filters.get("from_date"),
        "to_date": filters.get("to_date"),
    }
    if filters.get("company"):
        where_company = "AND `raw`.`company` = %(company)s"
        query_params["company"] = filters.get("company")

    sql_query = """
        SELECT `company`,
            `item_code`,
            COUNT(`name`) AS `count`
        FROM (
            SELECT
                `name`,
                `item_code`,
                IFNULL (`company`,
                    (SELECT `default_company` FROM `tabCustomer` WHERE `tabCustomer`.`name` = `base`.`customer`)) AS `company`,
                `sales_order`,
                `dn_posting_date`
            FROM (
                SELECT
                    `tabSequencing Label`.`name`,

                    `tabSequencing Label`.`item` AS `item_code`,

                    `tabSequencing Label`.`sales_order`,

                    (SELECT `company`
                    FROM `tabSales Order`
                    WHERE `tabSales Order`.`name` = `tabSequencing Label`.`sales_order`) AS `company`,

                    (SELECT `link_name`
                    FROM `tabDynamic Link`
                    WHERE `tabDynamic Link`.`link_doctype` = "Customer"
                    AND `tabDynamic Link`.`parenttype`= "Contact"
                    AND `tabDynamic Link`.`parent` = `tabSequencing Label`.`contact`) AS `customer`,

                    (SELECT DISTINCT `tabDelivery Note`.`posting_date`
                    FROM `tabDelivery Note Item`
                    LEFT JOIN `tabDelivery Note` ON `tabDelivery Note`.`name` = `tabDelivery Note Item`.`parent`
                    WHERE `tabDelivery Note Item`.`against_sales_order` = `tabSequencing Label`.`sales_order`
                        AND `tabDelivery Note`.`docstatus` = 1
                    ORDER BY `tabDelivery Note`.`posting_date` DESC
                        LIMIT 1) AS `dn_posting_date`

                FROM `tabSequencing Label`
            ) AS `base`
            WHERE `base`.`dn_posting_date` IS NOT NULL
                AND `base`.`dn_posting_date` BETWEEN DATE(%(from_date)s) AND DATE(%(to_date)s)
        )  AS `raw`
        WHERE `raw`.`company` IS NOT NULL
        {where_company}
        GROUP BY CONCAT(`raw`.`company`, ":", `raw`.`item_code`);
    """.format(where_company=where_company)
    data = frappe.db.sql(sql_query, query_params, as_dict=True)
    return data


def get_company_summary_rows(from_date, to_date):
    companies = [c.get("name") for c in frappe.get_all("Company", fields=["name"]) if c.get("name")]
    rows = []
    for company in companies:
        company_rows = get_data({
            "from_date": from_date,
            "to_date": to_date,
            "company": company,
        })
        if company_rows:
            rows.extend(company_rows)

    rows.sort(key=lambda row: (row.get("company") or "", row.get("item_code") or ""))
    return rows


def _sanitize_filename_part(value):
    return re.sub(r"[^A-Za-z0-9._-]+", "_", value or "unknown").strip("_") or "unknown"


def _write_company_csv(export_dir, company, rows, month_label):
    safe_company = _sanitize_filename_part(company)
    filename = f"shipped_labels_summary_{month_label}_{safe_company}.csv"
    filepath = os.path.join(export_dir, filename)

    with open(filepath, mode="w", encoding="utf-8", newline="") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=["company", "item_code", "count"])
        writer.writeheader()
        for row in rows:
            writer.writerow({
                "company": row.get("company"),
                "item_code": row.get("item_code"),
                "count": row.get("count"),
            })

    return filepath


def export_previous_month_shipped_labels_summary_to_csv():
    """
    Intended for cron execution on the first day of a month.
    Exports one CSV per company for the previous month to a path configured in Sequencing Settings.
    30 0 1 * * cd /home/frappe/frappe-bench && /usr/local/bin/bench execute microsynth.microsynth.report.shipped_labels_summary.shipped_labels_summary.export_previous_month_shipped_labels_summary_to_csv

    bench execute microsynth.microsynth.report.shipped_labels_summary.shipped_labels_summary.export_previous_month_shipped_labels_summary_to_csv
    """
    export_dir = frappe.get_value("Sequencing Settings", "Sequencing Settings", "shipped_labels_export_path")
    if not export_dir:
        frappe.throw(_("Please configure Shipped Labels Export Path in Sequencing Settings."))

    today = date.today()
    first_day_current_month = today.replace(day=1)
    last_day_previous_month = first_day_current_month - timedelta(days=1)
    first_day_previous_month = last_day_previous_month.replace(day=1)
    month_label = first_day_previous_month.strftime("%Y-%m")

    os.makedirs(export_dir, exist_ok=True)

    rows = get_company_summary_rows(first_day_previous_month, last_day_previous_month)
    rows_by_company = {}
    for row in rows:
        rows_by_company.setdefault(row.get("company"), []).append(row)

    exported_files = []
    for company, company_rows in rows_by_company.items():
        exported_files.append(_write_company_csv(export_dir, company, company_rows, month_label))

    return {
        "from_date": str(first_day_previous_month),
        "to_date": str(last_day_previous_month),
        "export_dir": export_dir,
        "files": exported_files,
        "companies": len(rows_by_company),
        "rows": len(rows),
    }


def execute(filters):
    filters = filters or {}
    columns, data = get_columns(filters), get_data(filters)
    return columns, data
