# -*- coding: utf-8 -*-
# Copyright (c) 2025, Microsynth, libracore and contributors
# For license information, please see license.txt

import csv
from datetime import datetime, timedelta
import frappe
from frappe.utils import get_url_to_form, getdate
from frappe.model.document import Document
from microsynth.qms.doctype.qm_document.qm_document import get_valid_version
from microsynth.microsynth.purchasing import get_location_path_string, get_or_create_single_location


class QMInstrument(Document):

    def validate(self):
        if self.status != 'Unapproved':
            if not self.instrument_class:
                frappe.throw("Instrument Class is mandatory if status is not 'Unapproved'.")
            if not self.regulatory_classification:
                frappe.throw("Regulatory Classification is mandatory if status is not 'Unapproved'.")
            if not self.has_service_contract:
                frappe.throw("Has Service Contract is mandatory if status is not 'Unapproved'.")
            if (self.instrument_class.startswith('A') or self.instrument_class.startswith('B')) and not self.instrument_manager:
                frappe.throw("Instrument Manager is mandatory for Instrument Class A and B if status is not 'Unapproved'.")
        self.validate_subcategory()
        self.validate_site_location()

    def validate_subcategory(self):
        if self.subcategory:
            allowed_subcategories = get_allowed_subcategory_for_category(
                doctype="QM Instrument",
                txt=self.subcategory,
                searchfield="name",
                start=0,
                page_len=20,
                filters={'category': self.category}
            )
            if len(allowed_subcategories) == 0:
                frappe.throw("Invalid value in 'Subcategory'. Please select from the available values.", "Validation")

    def validate_site_location(self):
        if self.site and self.site not in ['Balgach', 'Göttingen', 'Lyon', 'Wien']:
            frappe.throw("Invalid value in 'Site'. Please select from the available values.", "Validation")

        site_abbreviations = {
            "Balgach": "BAL",
            "Göttingen": "GOE",
            "Lyon": "LYO",
            "Wien": "WIE"
        }
        if self.site and self.location:
            location_path = get_location_path_string(self.location)
            if location_path and not location_path.startswith(site_abbreviations.get(self.site, "")):
                frappe.throw(f"The selected Location '{location_path}' does not match the selected Site '{self.site}'. Please select a Location that is within the selected Site")

    def get_advanced_dashboard(self):
        html = frappe.render_template("microsynth/qms/doctype/qm_instrument/advanced_dashboard.html",
            {
                'doc': self,
                'changes': self.get_qm_changes(),
                'qm_documents': self.get_qm_documents()
            })
        return html

    def get_qm_documents(self):
        """
        Fetch a list of all QM Documents that are linked on this QM Instrument.
        If the linked QM Document has status "Valid", it is added to the list.
        If the linked QM Document does not have status "Valid", the method tries to find a valid version of this document by looking for documents with the same name without the version number at the end.
        If there is exactly one valid version, this version is added to the list.
        If there are multiple valid versions, an error is logged.
        If there are no valid versions, the method looks for all versions of this document with docstatus 1 and adds the one with the highest version number to the list (if there are any).
        If there are no versions with docstatus 1, nothing is added to the list.
        """
        relating_docs = []
        for doc in self.qm_documents:
            if frappe.get_value("QM Document", doc.qm_document, "status") == "Valid":
                relating_docs.append(doc.qm_document)
            else:
                # try to find the valid version
                without_version = doc.qm_document.split("-")[0]
                valid_docs = frappe.db.sql(f"""
                    SELECT `tabQM Document`.`name`
                    FROM `tabQM Document`
                    WHERE `tabQM Document`.`name` LIKE '{without_version}%'
                        AND `tabQM Document`.`status` = 'Valid';
                    """, as_dict=True)
                if len(valid_docs) == 1:
                    relating_docs.append(valid_docs[0]['name'])
                elif len(valid_docs) > 1:
                    frappe.log_error(f"There seem to be {len(valid_docs)} Valid versions of QM Document LIKE '{without_version}%'.", "qm_document.get_overview")
                else:
                    # no valid version -> take the highest version
                    all_versions = frappe.db.sql(f"""
                    SELECT `tabQM Document`.`name`
                    FROM `tabQM Document`
                    WHERE `tabQM Document`.`name` LIKE '{without_version}%'
                        AND `tabQM Document`.`docstatus` = 1
                    ORDER BY `tabQM Document`.`version` DESC;
                    """, as_dict=True)
                    if len(all_versions) > 0:
                        relating_docs.append(all_versions[0]['name'])
                    else:
                        #frappe.log_error(f"There seem to be no QM Documents LIKE '{without_version}%' with docstatus 1.", "qm_document.get_overview")
                        continue
        return relating_docs

    def get_qm_changes(self):
        """
        Fetch a list of all QM Changes that are not cancelled and that link to the given instrument_id using the table "QM Instrument Link"
        """
        changes = frappe.db.sql(f"""
            SELECT `tabQM Change`.`name`, `tabQM Change`.`cc_type`, `tabQM Change`.`title`, `tabQM Change`.`status`, `tabQM Change`.`creation`
            FROM `tabQM Change`
            JOIN `tabQM Instrument Link` ON `tabQM Instrument Link`.`parent` = `tabQM Change`.`name` AND `tabQM Instrument Link`.`parenttype` = "QM Change"
            WHERE `tabQM Instrument Link`.`qm_instrument` = "{self.name}"
                AND `tabQM Change`.`status` != "Cancelled"
            ORDER BY `tabQM Change`.`creation` DESC;
        """, as_dict=True)
        return changes

    def print_due_label(self):
        """
        Print a label for the due qualifications/verification/calibrations of this instrument to stick on the instrument.
        """
        due_events = get_due_qualifications(self.name, self.instrument_class, self.acquisition_date)
        label = f"QM Instrument: {self.instrument_name} ({self.name})\n"
        for event in due_events:
            label += f"{event['qualification_type']} due: {event['due_date']}\n"
        # TODO: print the label
        return label


def get_allowed_category(doctype, txt, searchfield, start, page_len, filters):
    """
    Return all QM Instrument Categories that are not linked on another QM Instrument Category via QM Instrument Category Link, i.e. that are not used as subcategory in another category.
    """
    return frappe.db.sql("""
        SELECT `name`
        FROM `tabQM Instrument Category`
        WHERE `name` LIKE "%{txt}%"
            AND `name` NOT IN (
                SELECT `category`
                FROM `tabQM Instrument Category Link`
                WHERE `parenttype` = "QM Instrument Category"
            )
        """.format(txt=txt)
    )


def get_allowed_subcategory_for_category(doctype, txt, searchfield, start, page_len, filters):
    """
    bench execute microsynth.qms.doctype.qm_instrument.qm_instrument.get_allowed_subcategory_for_category --kwargs "{'doctype': 'QM Instrument', 'txt': '', 'searchfield': 'name', 'start': 0, 'page_len': 20, 'filters': {'category': 'Sequencing'}}"
    """
    return frappe.db.sql("""
        SELECT `tabQM Instrument Category Link`.`category` AS `name`
        FROM `tabQM Instrument Category Link`
        WHERE `tabQM Instrument Category Link`.`parent` = "{category}"
            AND `tabQM Instrument Category Link`.`parenttype` = "QM Instrument Category"
            AND `tabQM Instrument Category Link`.`category` LIKE "%{txt}%"
        """.format(category=filters.get('category'), txt=txt)
    )


@frappe.whitelist()
def get_qm_process_owner(qm_process, company):
    """
    Returns the process owner (user) for a given QM Process and Company.

    bench execute microsynth.qms.doctype.qm_instrument.qm_instrument.get_qm_process_owner --kwargs "{'qm_process': '3.2 Sequencing', 'company': 'Microsynth AG'}"
    """
    owners = frappe.db.get_all(
        "QM Process Owner",
        filters={"qm_process": qm_process, "company": company},
        fields=["process_owner"]
    )
    return [owner["process_owner"] for owner in owners]


@frappe.whitelist()
def get_due_qualifications(instrument_name, instrument_class, acquisition_date):
    """
    Returns a list of due qualification/verification/calibration events for the given instrument.
    Each item: {qualification_type, due_date}
    """
    def get_last_entry_date(entry_type):
        return frappe.db.get_value(
            "QM Log Book",
            {
                "document_type": "QM Instrument",
                "document_name": instrument_name,
                "entry_type": entry_type,
                "docstatus": 1
            },
            "date",
            order_by="date desc"
        )

    def to_date(value):
        return getdate(value) if value else None

    def get_due_date(entry_type, interval_days):
        last_date = get_last_entry_date(entry_type)
        base_date = to_date(last_date) or acquisition_date
        return (base_date + timedelta(days=interval_days)).strftime("%Y-%m-%d")

    # ensure acquisition_date is a date object
    acquisition_date = to_date(acquisition_date)
    iclass = instrument_class[0] if instrument_class else None

    rules = {
        'A': [("(Re-)Qualification", 2 * 365)],
        'P': [("Verification", 365), ("Calibration", 5 * 365)],
        'T': [("Verification", 365)],
        'W': [("Verification", 365)],
    }
    return [
        {
            "qualification_type": entry_type,
            "due_date": get_due_date(entry_type, days)
        }
        for entry_type, days in rules.get(iclass, [])
    ]


@frappe.whitelist()
def is_gmp(qm_instrument):
    """
    Returns True if the given QM Instrument is GMP relevant, i.e. if it has regulatory classification "GMP" and is not disposed.
    """
    result = frappe.db.get_value("QM Instrument", qm_instrument, ["regulatory_classification"])
    if result:
        return result == "GMP"
    return False


def get_or_create_location(site, floor, room, fridge_freezer):
    """
    Returns the final Location ID/name (creates any missing lower-level locations except site).

    Hierarchy: All Locations → Site → Floor → Room → Fridge/Freezer
    """
    if not site:
        frappe.throw("Site is required to determine location.")

    # Site (must exist)
    site_location = frappe.db.exists("Location", {"location_name": site})
    if not site_location:
        frappe.throw(f"Site location '{site}' not found under 'All Locations'.")

    if not floor:
        return site_location

    # Floor (create if missing)
    floor_location = get_or_create_single_location(
        location_name=floor,
        parent_location=site_location,
        is_group=True
    )
    if not room:
        return floor_location

    # Room (create if missing)
    room_location = get_or_create_single_location(
        location_name=room,
        parent_location=floor_location,
        is_group=True
    )
    if not fridge_freezer:
        return room_location

    # Fridge / Freezer (create if missing, leaf node)
    fridge_freezer_location = get_or_create_single_location(
        location_name=fridge_freezer,
        parent_location=room_location,
        is_group=False
    )
    return fridge_freezer_location


@frappe.whitelist()
def create_logbook_entry(qm_instrument, entry_type, description, date):
    """
    Creates a QM Log Book entry for a given QM Instrument.

    :param qm_instrument: Name of the QM Instrument
    :param entry_type: Type of the logbook entry (e.g. "Requalification")
    :param description: Description of the logbook entry
    :param date: Date of the logbook entry (in format "YYYY-MM-DD")
    """
    logbook_entry = frappe.get_doc({
        'doctype': "QM Log Book",
        'document_type': "QM Instrument",
        'document_name': qm_instrument,
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


def import_qm_instruments(input_filepath, expected_line_length=23):
    """
    bench execute microsynth.qms.doctype.qm_instrument.qm_instrument.import_qm_instruments --kwargs "{'input_filepath': '/mnt/erp_share/JPe/260414_TestImport_Instruments.csv'}"
    """
    def parse_date(value):
        try:
            return datetime.strptime(value, "%d.%m.%Y").strftime("%Y-%m-%d")
        except Exception:
            return None

    def clean(value, lower=False):
        if not value:
            return None
        value = value.strip()
        if not value or value.lower() == "na":
            return None
        return value.lower() if lower else value

    site_company_mapping = {
        'Lyon': 'Microsynth France SAS',
        'Göttingen': 'Microsynth Seqlab GmbH',
        'Wien': 'Microsynth Austria GmbH',
        'Balgach': 'Microsynth AG'
    }
    instrument_class_mapping = {
        'A': 'A – Complex or computerised instrument',
        'B': 'B – Standard device with straightforward measurement',
        'C': 'C – Instrument without measuring function',
        'F': 'F – Freezer or Fridge',
        'P': 'P – Pipette',
        'R': 'R – Measuring reference',
        'T': 'T – Thermometer',
        'W': 'W – Balance or Scale'
    }
    qm_processes = {p['name'] for p in frappe.db.get_all("QM Process", fields=["name"])}
    users = {u['name'].lower() for u in frappe.db.get_all("User", fields=["name"])}
    suppliers = {s['name'] for s in frappe.db.get_all("Supplier", fields=["name"])}
    raw_categories = get_allowed_category(doctype="QM Instrument", txt="", searchfield="name", start=0, page_len=100, filters={})
    allowed_categories = {row[0] for row in raw_categories}
    subcategory_cache = {}

    imported_counter = 0

    with open(input_filepath) as file:
        print(f"INFO: Parsing devices from '{input_filepath}' ...")
        csv_reader = csv.reader((l.replace('\0', '') for l in file), delimiter=";")  # replace NULL bytes (throwing an error)
        next(csv_reader)  # skip header
        for line in csv_reader:
            if len(line) != expected_line_length:
                print(f"ERROR: Line '{line}' has length {len(line)}, but expected length {expected_line_length}. Going to continue.")
                continue

            # parse values
            instrument_id = clean(line[0])
            instrument_name = clean(line[1])
            category = clean(line[2])
            subcategory = clean(line[3])
            process = clean(line[4])
            site = clean(line[5])
            floor = clean(line[6])
            room = clean(line[7])
            freezer_fridge = clean(line[8])
            instrument_class = clean(line[9])
            regulatory_classification = clean(line[10])
            status = clean(line[11])
            instrument_manager = clean(line[12], lower=True)
            deputy_instrument_manager = clean(line[13], lower=True)
            serial_number = clean(line[14])
            manufacturer = clean(line[15])
            supplier = clean(line[16])
            acquisition_date = clean(line[17])
            software_version = clean(line[18])
            has_service_contract = clean(line[19])
            instrument_sop = clean(line[20])
            last_requalification_date = clean(line[21])
            logbook_description = clean(line[22])

            # validation
            mandatory_fields = {
                "instrument_id": instrument_id,
                "instrument_name": instrument_name,
                "site": site,
                "process": process,
                "instrument_class": instrument_class,
                "regulatory_classification": regulatory_classification,
                "status": status,
                "instrument_manager": instrument_manager,
                "acquisition_date": acquisition_date
            }
            # check that all mandatory fields have a non-empty value
            invalid_fields = [name for name, value in mandatory_fields.items() if not value]

            if invalid_fields:
                print(f"ERROR: Missing/invalid fields {invalid_fields} in line: {line}")
                continue

            try:
                name = f"QMI-{int(instrument_id):05d}"
            except Exception:
                print(f"ERROR: Invalid instrument_id '{instrument_id}' in line: {line}")
                continue
            if frappe.db.exists("QM Instrument", name):
                print(f"ERROR: QM Instrument {name} already exists, going to skip the following line: {line}")
                continue

            if subcategory:
                if not category:
                    print(f"ERROR: Subcategory is provided but Category is missing for the following line: {line}.")
                    continue
                else:
                    if category not in allowed_categories:
                        print(f"ERROR: Category '{category}' is not a valid category in the following line: {line}.")
                        continue
                    if category not in subcategory_cache:
                        subcategory_cache[category] = [
                            sub[0] for sub in get_allowed_subcategory_for_category(
                                doctype="QM Instrument",
                                txt="",
                                searchfield="name",
                                start=0,
                                page_len=20,
                                filters={'category': category}
                            )
                        ]
                    if subcategory not in subcategory_cache[category]:
                        print(f"ERROR: Subcategory '{subcategory}' is not a valid subcategory for Category '{category}' in the following line: {line}.")
                        continue

            if process not in qm_processes:
                print(f"ERROR: QM Process '{process}' does not exist in the system for the following line: {line}.")
                continue

            if site not in site_company_mapping:
                print(f"ERROR: Invalid Site '{site}' in the following line: {line}.")
                continue

            if freezer_fridge and not room:
                print(f"ERROR: Freezer/Fridge is provided but Room is missing for the following line: {line}.")
                continue
            if room and (not floor):
                print(f"ERROR: Room is provided but Floor is missing for the following line: {line}.")
                continue

            if instrument_class not in instrument_class_mapping:
                print(f"ERROR: Invalid Instrument Classification '{instrument_class}' in the following line: {line}")
                continue

            if regulatory_classification not in ['GMP', 'non-GMP']:
                print(f"ERROR: Invalid Regulatory Classification '{regulatory_classification}' in the following line: {line}")
                continue

            if status not in ['Unapproved', 'Active', 'Blocked', 'Decommissioned', 'Disposed']:
                print(f"ERROR: Invalid Status '{status}' in the following line: {line}")
                continue

            if instrument_manager not in users:
                print(f"ERROR: Instrument Manager '{instrument_manager}' does not exist in the system for the following line: {line}.")
                continue
            if deputy_instrument_manager and deputy_instrument_manager not in users:
                print(f"ERROR: Deputy Instrument Manager '{deputy_instrument_manager}' does not exist in the system for the following line: {line}.")
                continue

            if supplier and supplier not in suppliers:
                print(f"ERROR: Supplier '{supplier}' does not exist in the system for the following line: {line}.")
                continue

            if instrument_sop and not last_requalification_date:
                print(f"ERROR: Instrument SOP is provided but Last Requalification Date is missing for the following line: {line}.")
                continue

            if last_requalification_date and not instrument_sop:
                print(f"ERROR: Last Requalification Date is provided but Instrument SOP is missing for the following line: {line}.")
                continue

            # get or create location
            location = None
            if site:
                try:
                    location = get_or_create_location(site, floor, room, freezer_fridge)
                except Exception as e:
                    print(f"ERROR: Failed to get or create location for the following line: {line}. Exception: {e}")
                    continue

            # reformat dates from dd.mm.yyyy to yyyy-mm-dd
            acquisition_date = parse_date(acquisition_date)
            if not acquisition_date:
                print(f"ERROR: Invalid acquisition date in the following line: {line}.")
                continue
            last_requalification_date = parse_date(last_requalification_date) if last_requalification_date else None

            # create QM Instrument
            qm_instrument = frappe.get_doc({
                'doctype': "QM Instrument",
                'instrument_name': instrument_name,
                'category': category,
                'subcategory': subcategory,
                'qm_process': process,
                'site': site,
                'location': location,
                'instrument_class': instrument_class_mapping[instrument_class],
                'regulatory_classification': regulatory_classification,
                'status': status,
                'instrument_manager': instrument_manager,
                'deputy_instrument_manager': deputy_instrument_manager,
                'serial_no': serial_number,
                'manufacturer': manufacturer,
                'supplier': supplier,
                'acquisition_date': acquisition_date,
                'software_version': software_version,
                'has_service_contract': 'Yes' if has_service_contract and has_service_contract.lower() in {'yes','y','true','1'} else 'No'
            })
            qm_instrument.name = name
            # disable automatic name generation
            qm_instrument.flags.name_set = True
            qm_instrument.insert()

            if instrument_sop:
                # try to find valid version of the SOP
                valid_sop_version = get_valid_version(instrument_sop)
                if valid_sop_version:
                    qm_instrument.append("qm_documents", {
                        "qm_document": valid_sop_version.get('name'),
                        "title": valid_sop_version.get('title') or instrument_sop
                    })
                else:
                    print(f"WARNING: No valid version found for Instrument SOP '{instrument_sop}' in the following line: {line}. Going to link the provided SOP without checking for its validity.")
                    qm_instrument.append("qm_documents", {
                        "qm_document": instrument_sop,
                        "title": frappe.get_value("QM Document", instrument_sop, "title") or instrument_sop
                    })
                qm_instrument.save()

            if last_requalification_date and logbook_description:
                create_logbook_entry(
                    qm_instrument=qm_instrument.name,
                    entry_type="(Re-)Qualification",
                    description=logbook_description,
                    date=last_requalification_date
                )
            imported_counter += 1
            print(f"Successfully imported QM Instrument '{qm_instrument.name}' from the following line: {line}.")

    print(f"Successfully imported {imported_counter} QM Instruments.")
