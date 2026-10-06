# -*- coding: utf-8 -*-
# Copyright (c) 2026, Microsynth
# For license information, please see license.txt

from __future__ import unicode_literals

import frappe
from frappe import _
from frappe.model.document import Document

from microsynth.qms.doctype.qm_document.qm_document import get_valid_version
from microsynth.qms.versioning import get_newer_active_versions, get_next_suffix, get_versioned_documents


def invalidate_previous_versions(docname):
	base_name, current_suffix, available_versions = get_versioned_documents("Competency", docname)

	for suffix, version_name, status, docstatus in available_versions:
		if suffix >= current_suffix or version_name == docname or docstatus != 1:
			continue
		frappe.db.set_value("Competency", version_name, "status", "Invalid", update_modified=False)


def validate_linked_qm_documents(doc):
	replacements = []
	invalid_rows = []

	for row in doc.qm_documents or []:
		qm_document_name = row.qm_document
		if not qm_document_name:
			continue

		qm_document_status = frappe.db.get_value("QM Document", qm_document_name, "status")
		if qm_document_status == "Valid":
			continue

		base_name = qm_document_name.split("-")[0]
		valid_doc = get_valid_version(base_name)
		if valid_doc:
			row.qm_document = valid_doc.get("name")
			row.title = valid_doc.get("title")
			replacements.append({
				"row": row.idx,
				"original": qm_document_name,
				"replacement": valid_doc.get("name"),
			})
			continue

		invalid_rows.append({
			"row": row.idx,
			"qm_document": qm_document_name,
			"status": qm_document_status or _("not found"),
		})

	if invalid_rows:
		details = "<br>".join(
			_("Row {0}: QM Document {1} is not valid (current status: {2}) and no valid version could be found.").format(
				frappe.bold(row.get("row")),
				frappe.bold(row.get("qm_document")),
				frappe.bold(row.get("status")),
			)
			for row in invalid_rows
		)
		frappe.throw(
			_(
				"This Competency cannot be saved because at least one linked QM Document is not valid and no valid replacement version could be proposed.<br><br>{0}<br><br>"
				"Please replace the affected QM Documents with a valid version and try again."
			).format(details),
			title=_("Invalid QM Document Version"),
		)

	if replacements:
		details = "<br>".join(
			_("Row {0}: replaced QM Document {1} with valid version {2}.").format(
				frappe.bold(row.get("row")),
				frappe.bold(row.get("original")),
				frappe.bold(row.get("replacement")),
			)
			for row in replacements
		)
		frappe.msgprint(
			_(
				"One or more linked QM Documents were not valid. The corresponding valid version was proposed automatically before saving:<br><br>{0}"
			).format(details),
			title=_("Linked QM Documents Updated"),
			indicator="orange",
		)


@frappe.whitelist()
def create_new_version(docname):
	if not docname:
		frappe.throw(_("Missing Competency name."))

	current_doc = frappe.get_doc("Competency", docname)
	if current_doc.docstatus != 1 or current_doc.status != "Valid":
		frappe.throw(
			_("A new Competency version can only be created from a submitted competency in status Valid.")
		)

	base_name, current_suffix, available_versions = get_versioned_documents("Competency", docname)
	newer_versions = get_newer_active_versions(available_versions, current_suffix)

	if newer_versions:
		frappe.throw(
			_(
				"Cannot create a new version for Competency {0}. A newer non-cancelled version already exists: {1}. "
				"Only the latest Competency version may be used as the source for the next draft. "
				"Cancelled newer versions are ignored, but active newer versions still block creating another draft. "
				"Please continue from the newest active version instead."
			).format(frappe.bold(docname), ", ".join(frappe.bold(name) for name in newer_versions)),
			title=_("Newer Version Exists"),
		)

	next_suffix = get_next_suffix(available_versions, current_suffix)
	if next_suffix > 99:
		frappe.throw(
			_("Cannot create a new version for Competency {0} because the version suffix would exceed 99.").format(
				frappe.bold(docname)
			),
			title=_("Version Limit Reached"),
		)

	new_name = "{0}-{1}".format(base_name, next_suffix)
	if frappe.db.exists("Competency", new_name):
		frappe.throw(
			_("Cannot create a new version because the target Competency name {0} already exists.").format(
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


class Competency(Document):
	def validate(self):
		validate_linked_qm_documents(self)

	def on_submit(self):
		self.status = "Valid"
		invalidate_previous_versions(self.name)
		self.save()
		frappe.db.commit()

	def on_cancel(self):
		self.status = "Invalid"
		self.save()
		frappe.db.commit()
