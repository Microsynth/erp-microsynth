# -*- coding: utf-8 -*-
# Copyright (c) 2026, Microsynth
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.utils import get_url_to_form
from frappe.model.document import Document


class QMComputerisedSystem(Document):
	pass


@frappe.whitelist()
def get_qm_process_owner(qm_process, company):
	owners = frappe.db.get_all(
		"QM Process Owner",
		filters={"qm_process": qm_process, "company": company},
		fields=["process_owner"]
	)
	return [owner["process_owner"] for owner in owners]


@frappe.whitelist()
def create_logbook_entry(qm_computerised_system, entry_type, description, date):
	logbook_entry = frappe.get_doc({
		'doctype': "QM Log Book",
		'document_type': "QM Computerised System",
		'document_name': qm_computerised_system,
		'entry_type': entry_type,
		'description': description,
		'date': date,
		'status': "Closed"
	})
	logbook_entry.insert()
	logbook_entry.submit()
	logbook_entry.status = "Closed"
	logbook_entry.save()
	return get_url_to_form(logbook_entry.doctype, logbook_entry.name)
