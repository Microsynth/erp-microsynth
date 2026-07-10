# -*- coding: utf-8 -*-
# Copyright (c) 2026, Microsynth
# For license information, please see license.txt

from __future__ import unicode_literals
import re
import frappe
from frappe.utils import get_url_to_form
from frappe.model.document import Document
from frappe.model.naming import make_autoname


class QMComputerisedSystem(Document):
	def autoname(self):
		# Keep explicit names (e.g. QMCS-00001-01) provided by version creation.
		if self.name and re.match(r"^QMCS-\d{5}-\d{2}$", self.name):
			return

		# Default naming for freshly created QMCS records.
		self.name = make_autoname(self.naming_series or "QMCS-.#####")


def _get_qmcs_base_name(name):
	# Only strip a version suffix when the name already has a full base id, e.g. QMCS-00001-02.
	match = re.match(r"^(.*-\d{5})-(\d{2})$", name)
	return match.group(1) if match else name


def _extract_qmcs_version_number(name, base_name):
	if name == base_name:
		return 0
	match = re.match(rf"^{re.escape(base_name)}-(\d{{2}})$", name)
	if match:
		return int(match.group(1))
	return None


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


@frappe.whitelist()
def create_new_version(doc, user=None):
	qmcs = frappe.get_doc("QM Computerised System", doc)
	base_name = _get_qmcs_base_name(qmcs.name)

	candidates = frappe.get_all(
		"QM Computerised System",
		filters={"name": ["like", f"{base_name}%"]},
		fields=["name"]
	)

	versions = []
	for candidate in candidates:
		version_number = _extract_qmcs_version_number(candidate["name"], base_name)
		if version_number is not None:
			versions.append((version_number, candidate["name"]))

	if not versions:
		frappe.throw(f"Found no versions for QM Computerised System '{qmcs.name}'.")

	highest_version, highest_name = max(versions, key=lambda x: x[0])
	if qmcs.name != highest_name:
		frappe.throw(
			f"Cannot create a new version of {qmcs.name} because {highest_name} is the highest existing version."
		)

	next_version = highest_version + 1
	if next_version > 99:
		frappe.throw("Cannot create a new version because the version suffix would exceed 99.")

	desired_name = f"{base_name}-{next_version:02d}"
	if frappe.db.exists("QM Computerised System", desired_name):
		frappe.throw(f"Cannot create a new version because {desired_name} already exists.")

	new_doc = frappe.get_doc(qmcs.as_dict())
	new_doc.name = desired_name
	new_doc.docstatus = 0
	new_doc.status = "Unapproved"
	new_doc.version = None
	new_doc.owner = user or frappe.session.user
	new_doc.creation = None
	new_doc.modified = None
	new_doc.modified_by = None
	# Disable automatic naming_series replacement for this explicit versioned name.
	new_doc.flags.name_set = True
	new_doc.insert()

	# Safety net in case naming is still overridden by hooks/meta in this environment (currently not needed)
	# if new_doc.name != desired_name:
	# 	new_doc = frappe.rename_doc("QM Computerised System", new_doc.name, desired_name, force=True)

	frappe.db.commit()

	return {
		'name': new_doc.name,
		'url': get_url_to_form("QM Computerised System", new_doc.name)
	}
