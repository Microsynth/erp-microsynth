# Copyright (c) 2025, Microsynth
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
import json


def get_columns(filters):
    return [
        {"label": _("Job Opening"), "fieldname": "job_opening", "fieldtype": "Link", "options": "Job Opening", "width": 140},
        {"label": _("Job Title"), "fieldname": "job_title", "fieldtype": "Data", "width": 170},
        # {"label": _("Job Subtitle"), "fieldname": "job_subtitle", "fieldtype": "Data", "width": 180},
        {"label": _("Company"), "fieldname": "company", "fieldtype": "Link", "options": "Company", "width": 160},
        {"label": _("Job Applicant"), "fieldname": "job_applicant", "fieldtype": "Link", "options": "Job Applicant", "width": 210},
        {"label": _("Creation"), "fieldname": "creation", "fieldtype": "Date", "width": 125},
        {"label": _("Salutation"), "fieldname": "salutation", "fieldtype": "Link", "options": "Salutation", "width": 1},
        {"label": _("Applicant Name"), "fieldname": "applicant_name", "fieldtype": "Data", "width": 160},
        {"label": _("Applicant Status"), "fieldname": "status", "fieldtype": "Data", "width": 110},
        {"label": _("Requirements Fit Assessments"), "fieldname": "assessments", "fieldtype": "Data", "width": 600},
    ]


def get_data(filters):
    conditions = []
    params = {}

    if filters.get("job_title"):
        conditions.append("`tabJob Opening`.`job_title` = %(job_title)s")
        params["job_title"] = filters["job_title"]

    if filters.get("job_subtitle"):
        conditions.append("`tabJob Opening`.`job_subtitle` = %(job_subtitle)s")
        params["job_subtitle"] = filters["job_subtitle"]

    if filters.get("company"):
        conditions.append("`tabJob Applicant`.`company` = %(company)s AND `tabJob Opening`.`company` = %(company)s")
        params["company"] = filters["company"]

    if filters.get("applicant_name"):
        conditions.append("`tabJob Applicant`.`applicant_name` LIKE %(applicant_name)s")
        params["applicant_name"] = f"%{filters['applicant_name']}%"

    if filters.get("status"):
        conditions.append("`tabJob Applicant`.`status` = %(status)s")
        params["status"] = filters["status"]

    assessment_filter = filters.get("assessment")
    having_clause = ""
    if assessment_filter == "Meet Requirements":
        having_clause = "HAVING SUM(CASE WHEN `tabJob Applicant Assessment`.`requirements_fit` = '1: Met' THEN 1 ELSE 0 END) > 0"
    elif assessment_filter == "Not Meet Requirements":
        having_clause = "HAVING SUM(CASE WHEN `tabJob Applicant Assessment`.`requirements_fit` != '3: Not met' THEN 1 ELSE 0 END) > 0"

    where_clause = " AND ".join(conditions)
    if where_clause:
        where_clause = "WHERE " + where_clause

    query = f"""
        SELECT
        	`tabJob Opening`.`name` AS `job_opening`,
            `tabJob Opening`.`job_title`,
            `tabJob Opening`.`job_subtitle`,
            `tabJob Applicant`.`name` AS `job_applicant`,
            `tabJob Applicant`.`creation`,
            `tabJob Applicant`.`company`,
            `tabJob Applicant`.`salutation`,
            `tabJob Applicant`.`applicant_name`,
            `tabJob Applicant`.`status`,
            GROUP_CONCAT(CONCAT_WS(': ', `tabJob Applicant Assessment`.`assessor`, `tabJob Applicant Assessment`.`requirements_fit`) SEPARATOR ', ') AS `assessments`,
            `tabJob Applicant`.`email_id`,
            `tabJob Applicant`.`name` AS `job_applicant_name`
        FROM `tabJob Applicant`
        JOIN `tabJob Opening` ON `tabJob Applicant`.`job_title` = `tabJob Opening`.`name`
        LEFT JOIN `tabJob Applicant Assessment` ON `tabJob Applicant Assessment`.`parent` = `tabJob Applicant`.`name`
        {where_clause}
        GROUP BY `tabJob Applicant`.`name`
        {having_clause}
    """
    return frappe.db.sql(query, params, as_dict=True)


def execute(filters=None):
    if not filters:
        filters = {}
    columns = get_columns(filters)
    data = get_data(filters)
    return columns, data


@frappe.whitelist()
def send_rejection_emails(template, subject, bcc, applicants):
    applicants = json.loads(applicants)  # received as JSON string

    for row in applicants:
        try:
            context = {
                "salutation": row.get("salutation", ""),
                "applicant_name": row.get("applicant_name", "")
            }
            rendered_message = frappe.render_template(template, context)

            frappe.sendmail(
                recipients=row.get("email_id"),
                subject=subject,
                content=rendered_message,
                bcc=bcc or ""
            )
            # Load doc, update status, and save to trigger validation and hooks
            doc = frappe.get_doc("Job Applicant", row.get("job_applicant"))
            doc.status = "Rejected"
            doc.save()

        except Exception:
            frappe.log_error(frappe.get_traceback(), "Error sending rejection email")

    return "Emails sent and statuses updated"
