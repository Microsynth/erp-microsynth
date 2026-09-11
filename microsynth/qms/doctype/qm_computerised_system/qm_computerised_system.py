# -*- coding: utf-8 -*-
# Copyright (c) 2026, Microsynth
# For license information, please see license.txt

from __future__ import unicode_literals
import re
import csv
import frappe
from frappe.utils import get_url_to_form
from frappe.model.document import Document
from frappe.model.naming import make_autoname
from microsynth.qms.doctype.qm_document.qm_document import get_valid_version


class QMComputerisedSystem(Document):
    def autoname(self):
        # Keep explicit names (e.g. QMCS-00001-01) provided by version creation.
        if self.name and re.match(r"^QMCS-\d{5}-\d{2}$", self.name):
            return

        # Default naming for freshly created QMCS records.
        self.name = make_autoname(self.naming_series or "QMCS-.#####")

    def get_advanced_dashboard(self):
        html = frappe.render_template(
            "microsynth/qms/doctype/qm_computerised_system/advanced_dashboard.html",
            {
                "doc": self,
                "changes": self.get_qm_changes(),
                "qm_documents": self.get_qm_documents()
            }
        )
        return html

    def get_qm_documents(self):
        """
        Fetch a list of all QM Documents linked on this QM Computerised System.
        If a linked document is not Valid, try to find the latest Valid version.
        """
        relating_docs = []
        for doc in self.qm_documents:
            if frappe.get_value("QM Document", doc.qm_document, "status") == "Valid":
                relating_docs.append(doc.qm_document)
                continue

            without_version = doc.qm_document.split("-")[0]
            valid_doc = get_valid_version(without_version)
            if valid_doc:
                relating_docs.append(valid_doc.get("name"))

        return relating_docs

    def get_qm_changes(self):
        """
        Fetch all QM Changes that are not cancelled and link to this system.
        """
        return frappe.db.sql(
            """
            SELECT `tabQM Change`.`name`, `tabQM Change`.`cc_type`, `tabQM Change`.`title`, `tabQM Change`.`status`, `tabQM Change`.`creation`
            FROM `tabQM Change`
            JOIN `tabQM Computerised System Link`
                ON `tabQM Computerised System Link`.`parent` = `tabQM Change`.`name`
                AND `tabQM Computerised System Link`.`parenttype` = 'QM Change'
            WHERE `tabQM Computerised System Link`.`qm_computerised_system` = %s
                AND `tabQM Change`.`status` != 'Cancelled'
            ORDER BY `tabQM Change`.`creation` DESC
            """,
            (self.name,),
            as_dict=True
        )


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
        'date': date
    })
    logbook_entry.insert()
    logbook_entry.submit()
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


@frappe.whitelist()
def get_linked_qm_documents(qm_computerised_system):
    change_parent_rows = frappe.get_all(
        "QM Computerised System Link",
        filters={
            "parenttype": "QM Change",
            "qm_computerised_system": qm_computerised_system
        },
        fields=["parent"]
    )
    nonconformity_parent_rows = frappe.get_all(
        "QM Computerised System Link",
        filters={
            "parenttype": "QM Nonconformity",
            "qm_computerised_system": qm_computerised_system
        },
        fields=["parent"]
    )

    change_parents = [row.get("parent") for row in change_parent_rows if row.get("parent")]
    nonconformity_parents = [row.get("parent") for row in nonconformity_parent_rows if row.get("parent")]

    change_names = []
    if change_parents:
        change_rows = frappe.get_all(
            "QM Change",
            filters={
                "name": ["in", sorted(set(change_parents))],
                "docstatus": ["<", 2]
            },
            fields=["name"]
        )
        change_names = [row.get("name") for row in change_rows if row.get("name")]

    nonconformity_names = []
    if nonconformity_parents:
        nonconformity_rows = frappe.get_all(
            "QM Nonconformity",
            filters={
                "name": ["in", sorted(set(nonconformity_parents))],
                "docstatus": ["<", 2]
            },
            fields=["name"]
        )
        nonconformity_names = [row.get("name") for row in nonconformity_rows if row.get("name")]

    return {
        "qm_change_names": change_names,
        "qm_change_count": len(change_names),
        "qm_nonconformity_names": nonconformity_names,
        "qm_nonconformity_count": len(nonconformity_names)
    }


def import_qm_computerised_systems(file_path, expected_line_length=14, verbose=False, dry_run=True):
    """
    Import QM Computerised Systems from a CSV/TSV export.

    Expected columns (first column "ID" is ignored):
    ID, Name, Type, GAMP5 Class, Regulatory Classification, Version Control,
    QM Process, Status, Description, ATR frequency, Source, Company,
    Responsible Person, QM Document

    bench execute microsynth.qms.doctype.qm_computerised_system.qm_computerised_system.import_qm_computerised_systems --kwargs "{'file_path': '/mnt/erp_share/Migration/QM_Computerised_Systems/260911_QM_CS_Template_v01.csv', 'expected_line_length': 14, 'verbose': True, 'dry_run': True}"
    """
    def clean(value):
        if value is None:
            return None
        value = value.strip()
        if not value or value.upper() == "NA":
            return None
        return value

    def get_allowed_select_values(meta, fieldname):
        field = meta.get_field(fieldname)
        if not field or not field.options:
            return set()
        return {option.strip() for option in field.options.split("\n") if option.strip()}

    def resolve_qm_process(raw_value):
        value = clean(raw_value)
        if not value:
            return None, "QM Process is mandatory."
        if frappe.db.exists("QM Process", value):
            return value, None
        return None, f"QM Process '{value}' does not exist."

    def resolve_qm_document(raw_value):
        value = clean(raw_value)
        if not value:
            return None, None

        candidates = []
        candidates.append(value)
        candidates.append(value.replace("  ", " "))
        candidates.append(value.replace(" ", "-"))
        candidates = [c.strip() for c in candidates if c and c.strip()]

        # 1) Exact match first.
        for candidate in candidates:
            if frappe.db.exists("QM Document", candidate):
                return candidate, None

        # 2) Try get_valid_version on likely base names.
        for candidate in candidates:
            valid_doc = get_valid_version(candidate)
            if valid_doc and valid_doc.get("name"):
                return valid_doc.get("name"), None

        # 3) Fallback: use latest valid version by prefix.
        for candidate in candidates:
            valid_rows = frappe.get_all(
                "QM Document",
                filters=[
                    ["name", "like", f"{candidate}%"],
                    ["status", "=", "Valid"]
                ],
                fields=["name", "version"],
                order_by="version DESC"
            )
            if valid_rows:
                return valid_rows[0]["name"], None

        return None, f"QM Document '{value}' could not be resolved."


    qmcs_meta = frappe.get_meta("QM Computerised System")
    allowed_types = get_allowed_select_values(qmcs_meta, "cs_type")
    allowed_gamp5_classes = get_allowed_select_values(qmcs_meta, "gamp5_class")
    allowed_regulatory_classification = get_allowed_select_values(qmcs_meta, "regulatory_classification")
    allowed_version_control_methods = get_allowed_select_values(qmcs_meta, "primary_version_control_method")
    allowed_statuses = get_allowed_select_values(qmcs_meta, "status")
    allowed_sources = get_allowed_select_values(qmcs_meta, "cs_source")
    existing_companies = {row["name"] for row in frappe.get_all("Company", fields=["name"])}
    existing_users = {row["name"].lower() for row in frappe.get_all("User", fields=["name"])}
    imported_count = 0
    skipped_count = 0
    line_counter = 0
    created_names = []
    errors = []

    with open(file_path, newline="") as f:
        raw_content = f.read().replace("\0", "")
        if not raw_content.strip():
            print(f"ERROR: Input file is empty: '{file_path}'")
            return {
                "imported": 0,
                "skipped": 0,
                "lines_processed": 0,
                "created_names": [],
                "errors": ["Input file is empty."]
            }
        try:
            dialect = csv.Sniffer().sniff(raw_content[:4096], delimiters=";,\t")
            delimiter = dialect.delimiter
        except Exception:
            delimiter = ";"

        reader = csv.reader(raw_content.splitlines(), delimiter=delimiter)

        try:
            next(reader)  # skip header
        except StopIteration:
            print(f"ERROR: Input file only contains header: '{file_path}'")
            return {
                "imported": 0,
                "skipped": 0,
                "lines_processed": 0,
                "created_names": [],
                "errors": ["Input file only contains header."]
            }
        for line in reader:
            line_counter += 1

            if len(line) != expected_line_length:
                msg = f"Line {line_counter} has length {len(line)}, but expected {expected_line_length}. Skipping line: {line}"
                print(f"ERROR: {msg}")
                errors.append(msg)
                skipped_count += 1
                continue

            # Ignore ID column (index 0)
            cs_name = clean(line[1])
            cs_type = clean(line[2])
            gamp5_class = clean(line[3])
            regulatory_classification = clean(line[4])
            primary_version_control_method = clean(line[5])
            qm_process_raw = line[6]
            status = clean(line[7])
            description = clean(line[8])
            atr_frequency_raw = clean(line[9])
            cs_source = clean(line[10])
            company = clean(line[11])
            responsible_user = clean(line[12])
            qm_document_raw = line[13] if len(line) > 13 else None

            mandatory_fields = {
                "Name": cs_name,
                "Type": cs_type,
                "GAMP5 Class": gamp5_class,
                "Regulatory Classification": regulatory_classification,
                "Version Control": primary_version_control_method,
                "QM Process": clean(qm_process_raw),
                "Status": status,
                "Description": description
            }
            missing = [k for k, v in mandatory_fields.items() if not v]
            if missing:
                msg = f"Line {line_counter} is missing mandatory values: {missing}."
                print(f"ERROR: {msg}")
                errors.append(msg)
                skipped_count += 1
                continue

            if cs_type not in allowed_types:
                msg = f"Line {line_counter} has invalid Type '{cs_type}'. Allowed: {sorted(allowed_types)}."
                print(f"ERROR: {msg}")
                errors.append(msg)
                skipped_count += 1
                continue

            if gamp5_class not in allowed_gamp5_classes:
                msg = f"Line {line_counter} has invalid GAMP5 Class '{gamp5_class}'. Allowed: {sorted(allowed_gamp5_classes)}."
                print(f"ERROR: {msg}")
                errors.append(msg)
                skipped_count += 1
                continue

            if regulatory_classification not in allowed_regulatory_classification:
                msg = (f"Line {line_counter} has invalid Regulatory Classification '{regulatory_classification}'. Allowed: {sorted(allowed_regulatory_classification)}.")
                print(f"ERROR: {msg}")
                errors.append(msg)
                skipped_count += 1
                continue

            if primary_version_control_method not in allowed_version_control_methods:
                msg = (f"Line {line_counter} has invalid Version Control '{primary_version_control_method}'. Allowed: {sorted(allowed_version_control_methods)}.")
                print(f"ERROR: {msg}")
                errors.append(msg)
                skipped_count += 1
                continue

            if status not in allowed_statuses:
                msg = f"Line {line_counter} has invalid Status '{status}'. Allowed: {sorted(allowed_statuses)}."
                print(f"ERROR: {msg}")
                errors.append(msg)
                skipped_count += 1
                continue

            if cs_source and cs_source not in allowed_sources:
                msg = f"Line {line_counter} has invalid Source '{cs_source}'. Allowed: {sorted(allowed_sources)}."
                print(f"ERROR: {msg}")
                errors.append(msg)
                skipped_count += 1
                continue

            qm_process, process_error = resolve_qm_process(qm_process_raw)
            if process_error:
                msg = f"Line {line_counter}: {process_error}"
                print(f"ERROR: {msg}")
                errors.append(msg)
                skipped_count += 1
                continue

            if company and company not in existing_companies:
                msg = f"Line {line_counter}: Company '{company}' does not exist."
                print(f"ERROR: {msg}")
                errors.append(msg)
                skipped_count += 1
                continue

            if responsible_user:
                responsible_user_lc = responsible_user.lower()
                if responsible_user_lc not in existing_users:
                    msg = f"Line {line_counter}: Responsible Person '{responsible_user}' does not exist."
                    print(f"ERROR: {msg}")
                    errors.append(msg)
                    skipped_count += 1
                    continue
                responsible_user = responsible_user_lc

            qm_document, qm_document_error = resolve_qm_document(qm_document_raw)
            if qm_document_error:
                msg = f"Line {line_counter}: {qm_document_error}"
                print(f"ERROR: {msg}")
                errors.append(msg)
                skipped_count += 1
                continue

            atr_frequency = 0
            if atr_frequency_raw is not None:
                try:
                    atr_frequency = int(atr_frequency_raw)
                    if atr_frequency < 0:
                        raise ValueError("negative value")
                except Exception:
                    msg = f"Line {line_counter} has invalid ATR frequency '{atr_frequency_raw}'. Expected integer >= 0."
                    print(f"ERROR: {msg}")
                    errors.append(msg)
                    skipped_count += 1
                    continue

            duplicate_filters = {
                "cs_name": cs_name,
                "qm_process": qm_process,
                "status": ["!=", "Decommissioned"]
            }
            if company:
                duplicate_filters["company"] = company

            existing_duplicate = frappe.get_all(
                "QM Computerised System",
                filters=duplicate_filters,
                fields=["name"],
                limit=1
            )
            if existing_duplicate:
                msg = f"Line {line_counter}: Possible duplicate found (existing QMCS {existing_duplicate[0]['name']}). Skipping."
                print(f"ERROR: {msg}")
                errors.append(msg)
                skipped_count += 1
                continue

            payload = {
                "doctype": "QM Computerised System",
                "cs_name": cs_name,
                "cs_type": cs_type,
                "gamp5_class": gamp5_class,
                "regulatory_classification": regulatory_classification,
                "primary_version_control_method": primary_version_control_method,
                "qm_process": qm_process,
                "status": status,
                "description": description,
                "atr_frequency": atr_frequency,
                "cs_source": cs_source,
                "company": company,
                "responsible_user": responsible_user
            }
            if verbose:
                print(f"INFO: Prepared QMCS payload for line {line_counter}: {payload}")
            if dry_run:
                imported_count += 1
                continue
            try:
                qmcs = frappe.get_doc(payload)
                qmcs.insert()
                if qm_document:
                    qmcs.append("qm_documents", {"qm_document": qm_document})
                    qmcs.save()
                created_names.append(qmcs.name)
                imported_count += 1
                if verbose:
                    print(f"INFO: Created QM Computerised System '{qmcs.name}' from line {line_counter}.")
            except Exception as err:
                frappe.db.rollback()
                msg = f"Line {line_counter}: Unable to create QM Computerised System: {err}"
                print(f"ERROR: {msg}")
                errors.append(msg)
                skipped_count += 1
                continue

    if not dry_run:
        frappe.db.commit()

    print(f"Done. Processed {line_counter} line(s), imported {imported_count}, skipped {skipped_count}, dry_run={dry_run}.")

    return {
        "imported": imported_count,
        "skipped": skipped_count,
        "lines_processed": line_counter,
        "created_names": created_names,
        "errors": errors,
        "dry_run": dry_run
    }
