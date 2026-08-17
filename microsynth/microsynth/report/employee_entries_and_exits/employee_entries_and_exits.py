# Copyright (c) 2026, Microsynth
# For license information, please see license.txt

from __future__ import unicode_literals

import base64
import mimetypes
import os
import re

import frappe
from frappe import _
from frappe.utils import formatdate, getdate, now_datetime
from frappe.utils.pdf import get_pdf


def get_columns():
	return [
		{"label": _("Employee ID"), "fieldname": "employee", "fieldtype": "Link", "options": "Employee", "width": 220},
		{"label": _("Full Name"), "fieldname": "employee_name", "fieldtype": "Data", "width": 180},
		{"label": _("Visa"), "fieldname": "visa", "fieldtype": "Data", "width": 50},
		{"label": _("Department"), "fieldname": "department", "fieldtype": "Link", "options": "Department", "width": 200},
		{"label": _("QM Process"), "fieldname": "qm_process", "fieldtype": "Data", "width": 250, "align": "left"},
		{"label": _("Date of Joining"), "fieldname": "date_of_joining", "fieldtype": "Date", "width": 105, "align": "left"},
		{"label": _("Relieving Date"), "fieldname": "relieving_date", "fieldtype": "Date", "width": 100, "align": "left"},
		{"label": _("Picture Path"), "fieldname": "image", "fieldtype": "Data", "width": 300},
	]


def get_data(filters):
	if not filters.get("company"):
		frappe.throw(_("Filter Company is required."))
	if not filters.get("from_date"):
		frappe.throw(_("Filter From Date is required."))

	conditions = [
		"`tabEmployee`.`company` = %(company)s",
	]

	if filters.get("to_date"):
		conditions.append(
			"""
			(
				(`tabEmployee`.`date_of_joining` IS NOT NULL AND `tabEmployee`.`date_of_joining` >= %(from_date)s AND `tabEmployee`.`date_of_joining` <= %(to_date)s)
				OR
				(`tabEmployee`.`relieving_date` IS NOT NULL AND `tabEmployee`.`relieving_date` >= %(from_date)s AND `tabEmployee`.`relieving_date` <= %(to_date)s)
			)
			"""
		)
	else:
		conditions.append(
			"""
			(
				(`tabEmployee`.`date_of_joining` IS NOT NULL AND `tabEmployee`.`date_of_joining` >= %(from_date)s)
				OR
				(`tabEmployee`.`relieving_date` IS NOT NULL AND `tabEmployee`.`relieving_date` >= %(from_date)s)
			)
			"""
		)

	return frappe.db.sql(
		"""
			SELECT
				`tabEmployee`.`name` AS employee,
				`tabEmployee`.`employee_name`,
				`tabEmployee`.`visa`,
				`tabEmployee`.`department`,
				GROUP_CONCAT(DISTINCT `tabQM User Process Assignment`.`qm_process` ORDER BY `tabQM User Process Assignment`.`qm_process` SEPARATOR ', ') AS qm_process,
				`tabEmployee`.`date_of_joining`,
				`tabEmployee`.`relieving_date`,
				`tabEmployee`.`image`
			FROM `tabEmployee`
			LEFT JOIN `tabUser Settings`
				ON `tabUser Settings`.`user` = `tabEmployee`.`user_id`
				AND `tabUser Settings`.`disabled` = 0
			LEFT JOIN `tabQM User Process Assignment`
				ON `tabQM User Process Assignment`.`parent` = `tabUser Settings`.`name`
				AND `tabQM User Process Assignment`.`company` = `tabEmployee`.`company`
			WHERE {conditions}
			GROUP BY
				`tabEmployee`.`name`,
				`tabEmployee`.`employee_name`,
				`tabEmployee`.`visa`,
				`tabEmployee`.`department`,
				`tabEmployee`.`date_of_joining`,
				`tabEmployee`.`relieving_date`,
				`tabEmployee`.`image`
			ORDER BY `tabEmployee`.`company` ASC, COALESCE(`tabEmployee`.`date_of_joining`, `tabEmployee`.`relieving_date`) ASC, `tabEmployee`.`employee_name` ASC
		""".format(conditions=" AND ".join(["({0})".format(c) for c in conditions])),
		filters,
		as_dict=True,
	)

def execute(filters=None):
	filters = filters or {}
	columns = get_columns()
	data = get_data(filters)
	return columns, data


def _is_in_range(value, from_date, to_date=None):
	if not value:
		return False
	date_value = getdate(value)
	start = getdate(from_date)
	if to_date:
		return start <= date_value <= getdate(to_date)
	return date_value >= start


def _get_letter_head_content(company):
	letter_head_name = frappe.db.get_value("Company", company, "default_letter_head")
	if letter_head_name and frappe.db.exists("Letter Head", letter_head_name):
		return frappe.get_doc("Letter Head", letter_head_name)
	if frappe.db.exists("Letter Head", company):
		return frappe.get_doc("Letter Head", company)
	return None


def _image_url(image_path):
	if not image_path:
		return _placeholder_image_data_uri()
	if image_path.startswith("http://") or image_path.startswith("https://"):
		# Avoid external dependencies in PDF rendering; use placeholder for remote links.
		return _placeholder_image_data_uri()

	# Prefer embedded data URI for local files to avoid wkhtmltopdf URL loading issues.
	data_uri = _file_url_to_data_uri(image_path)
	if data_uri:
		return data_uri

	return _placeholder_image_data_uri()


def _placeholder_image_data_uri():
	svg = """<svg xmlns='http://www.w3.org/2000/svg' width='90' height='90'>
	<rect width='100%' height='100%' fill='#f3f4f6'/>
	<rect x='1' y='1' width='88' height='88' fill='none' stroke='#d1d5db'/>
	<text x='45' y='48' text-anchor='middle' font-family='Arial' font-size='10' fill='#6b7280'>No Image</text>
</svg>"""
	encoded = base64.b64encode(svg.encode("utf-8")).decode("ascii")
	return "data:image/svg+xml;base64,{0}".format(encoded)


def _file_url_to_data_uri(file_url):
	if not file_url:
		return ""

	clean_url = file_url.split("?", 1)[0].strip()
	if not clean_url:
		return ""

	if clean_url.startswith("files/"):
		clean_url = "/{0}".format(clean_url)
	if clean_url.startswith("private/files/"):
		clean_url = "/{0}".format(clean_url)

	abs_path = ""
	if clean_url.startswith("/files/"):
		rel_parts = clean_url.lstrip("/").split("/")
		abs_path = frappe.get_site_path("public", *rel_parts)
	elif clean_url.startswith("/private/files/"):
		rel_parts = clean_url.lstrip("/").split("/")
		abs_path = frappe.get_site_path(*rel_parts)
	elif clean_url.startswith("/assets/"):
		rel_parts = clean_url.lstrip("/").split("/")
		abs_path = frappe.get_site_path(*rel_parts)
	else:
		return ""

	if not abs_path or not os.path.exists(abs_path):
		return ""

	with open(abs_path, "rb") as image_file:
		content = image_file.read()

	mime_type = mimetypes.guess_type(abs_path)[0] or "application/octet-stream"
	return "data:{0};base64,{1}".format(mime_type, base64.b64encode(content).decode("ascii"))


def _rewrite_html_image_sources(html):
	if not html:
		return ""

	def repl(match):
		prefix, src, suffix = match.groups()
		src = (src or "").strip()
		if not src or src.startswith("data:"):
			return "{0}{1}{2}".format(prefix, src, suffix)

		if src.startswith("files/") or src.startswith("private/files/"):
			src = "/{0}".format(src)

		if src.startswith("/files/") or src.startswith("/private/files/"):
			data_uri = _file_url_to_data_uri(src)
			if data_uri:
				return "{0}{1}{2}".format(prefix, data_uri, suffix)
			return "{0}{1}{2}".format(prefix, _placeholder_image_data_uri(), suffix)

		if src.startswith("/assets/"):
			data_uri = _file_url_to_data_uri(src)
			if data_uri:
				return "{0}{1}{2}".format(prefix, data_uri, suffix)
			return "{0}{1}{2}".format(prefix, _placeholder_image_data_uri(), suffix)

		if src.startswith("/"):
			return "{0}{1}{2}".format(prefix, _placeholder_image_data_uri(), suffix)

		if src.startswith("http://") or src.startswith("https://"):
			return "{0}{1}{2}".format(prefix, _placeholder_image_data_uri(), suffix)

		# Relative src paths are not reliable for wkhtmltopdf in dev systems.
		return "{0}{1}{2}".format(prefix, _placeholder_image_data_uri(), suffix)

	return re.sub(r'(<img[^>]+src=["\'])([^"\']+)(["\'])', repl, html, flags=re.IGNORECASE)


def _prepare_employee_for_print(employee):
	return {
		"employee": employee.get("employee"),
		"employee_name": employee.get("employee_name") or employee.get("employee") or "",
		"qm_or_department": employee.get("qm_process") or employee.get("department") or "",
		"date_of_joining": formatdate(employee.get("date_of_joining")) if employee.get("date_of_joining") else "",
		"relieving_date": formatdate(employee.get("relieving_date")) if employee.get("relieving_date") else "",
		"image_url": _image_url(employee.get("image")),
	}


@frappe.whitelist()
def create_print_overview_pdf(company, from_date, to_date=None):
	filters = {
		"company": company,
		"from_date": from_date,
	}
	if to_date:
		filters["to_date"] = to_date

	rows = get_data(filters)
	joiners = [row for row in rows if _is_in_range(row.get("date_of_joining"), from_date, to_date)]
	joiner_ids = {row.get("employee") for row in joiners if row.get("employee")}
	leavers = [
		row for row in rows
		if _is_in_range(row.get("relieving_date"), from_date, to_date)
		and row.get("employee") not in joiner_ids
	]

	letter_head = _get_letter_head_content(company)
	header_html = letter_head.content if letter_head and letter_head.content else ""
	footer_html = letter_head.footer if letter_head and letter_head.footer else ""
	header_html = _rewrite_html_image_sources(header_html)
	footer_html = _rewrite_html_image_sources(footer_html)

	content = frappe.render_template(
		"microsynth/microsynth/report/employee_entries_and_exits/employee_entries_and_exits_print_overview.html",
		{
			"header_html": header_html,
			"footer_html": footer_html,
			"joiners": [_prepare_employee_for_print(employee) for employee in joiners],
			"leavers": [_prepare_employee_for_print(employee) for employee in leavers],
		}
	)

	pdf = get_pdf(content, {
		"disable-smart-shrinking": "",
		"load-error-handling": "ignore",
		"load-media-error-handling": "ignore",
	})
	filename = "employee_entries_and_exits_{0}.pdf".format(now_datetime().strftime("%Y%m%d_%H%M%S"))

	file_doc = frappe.get_doc({
		"doctype": "File",
		"file_name": filename,
		"is_private": 1,
		"content": pdf,
	})
	file_doc.save(ignore_permissions=True)

	return file_doc.file_url
