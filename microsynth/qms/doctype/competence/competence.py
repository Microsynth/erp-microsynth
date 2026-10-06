# -*- coding: utf-8 -*-
# Copyright (c) 2026, Microsynth
# For license information, please see license.txt

from __future__ import unicode_literals

import frappe
from frappe import _
from frappe.model.document import Document

from microsynth.qms.versioning import get_newer_active_versions, get_next_suffix, get_versioned_documents


def invalidate_previous_versions(docname):
	base_name, current_suffix, available_versions = get_versioned_documents("Competence", docname)

	for suffix, version_name, status, docstatus in available_versions:
		if suffix >= current_suffix or version_name == docname or docstatus != 1:
			continue
		frappe.db.set_value("Competence", version_name, "status", "Invalid", update_modified=False)


@frappe.whitelist()
def create_new_version(docname):
	if not docname:
		frappe.throw(_("Missing Competence name."))

	current_doc = frappe.get_doc("Competence", docname)
	if current_doc.docstatus != 1 or current_doc.status != "Valid":
		frappe.throw(
			_("A new Competence version can only be created from a submitted competence in status Valid.")
		)

	base_name, current_suffix, available_versions = get_versioned_documents("Competence", docname)
	newer_versions = get_newer_active_versions(available_versions, current_suffix)

	if newer_versions:
		frappe.throw(
			_(
				"Cannot create a new version for Competence {0}. A newer non-cancelled version already exists: {1}. "
				"Only the latest Competence version may be used as the source for the next draft. "
				"Cancelled newer versions are ignored, but active newer versions still block creating another draft. "
				"Please continue from the newest active version instead."
			).format(frappe.bold(docname), ", ".join(frappe.bold(name) for name in newer_versions)),
			title=_("Newer Version Exists"),
		)

	next_suffix = get_next_suffix(available_versions, current_suffix)
	if next_suffix > 99:
		frappe.throw(
			_("Cannot create a new version for Competence {0} because the version suffix would exceed 99.").format(
				frappe.bold(docname)
			),
			title=_("Version Limit Reached"),
		)

	new_name = "{0}-{1}".format(base_name, next_suffix)
	if frappe.db.exists("Competence", new_name):
		frappe.throw(
			_("Cannot create a new version because the target Competence name {0} already exists.").format(
				frappe.bold(new_name)
			),
			title=_("Duplicate Version Name"),
		)

	new_doc = frappe.copy_doc(current_doc)
	new_doc.name = new_name
	new_doc.docstatus = 0
	new_doc.status = "Draft"
	new_doc.amended_from = current_doc.name
	new_doc.owner = frappe.session.user
	new_doc.creation = None
	new_doc.modified = None
	new_doc.modified_by = None
	new_doc.flags.name_set = True
	new_doc.insert()

	frappe.db.commit()
	return {"name": new_doc.name}


class Competence(Document):

	def on_submit(self):
		self.status = "Valid"
		invalidate_previous_versions(self.name)
		self.save()
		frappe.db.commit()

	def on_cancel(self):
		self.status = "Invalid"
		self.save()
		frappe.db.commit()
