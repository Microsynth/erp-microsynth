# -*- coding: utf-8 -*-
# Copyright (c) 2025, Microsynth, libracore and contributors and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document
import csv


class QMDevice(Document):
    pass


def import_qm_devices(input_filepath, company='Microsynth AG', expected_line_length=18):
    """
    bench execute microsynth.qms.doctype.qm_device.qm_device.import_qm_devices --kwargs "{'input_filepath': '/mnt/erp_share/JPe/2025-07-25_Geraeteliste.csv'}"
    """
    group_mapping = {
        '3.1 DNA/RNA Synthese': '3.1 DNA/RNA Synthesis',
        '3.2 Balgach': '3.2 Sequencing',
        '3.2 Lyon': '3.2 Sequencing',
        '3.2 Seqlab': '3.2 Sequencing',
        '3.2 Wien': '3.2 Sequencing',
        '3.3 DNA/RNA Isolation': '3.3 Isolation',
        '3.4 Genotyping': '3.4 Genotyping',
        '3.5 Real Time PCR': '3.5 PCR',
        '3.6 Library Prep': 'TODO',
        '3.7 NGS': '3.6 NGS',
        '5.1 Instrumente': '5.1 Instruments',
    }
    with open(input_filepath) as file:
        print(f"INFO: Parsing devices from '{input_filepath}' ...")
        csv_reader = csv.reader((l.replace('\0', '') for l in file), delimiter=";")  # replace NULL bytes (throwing an error)
        next(csv_reader)  # skip header
        for line in csv_reader:
            if len(line) != expected_line_length:
                print(f"ERROR: Line '{line}' has length {len(line)}, but expected length {expected_line_length}. Going to continue.")
                continue
            # parse values
            device_id = line[0].strip()  # remove leading and trailing whitespaces
            device_name = line[1].strip()
            acquisition_date = line[2].strip()
            serial_number = line[3].strip()
            critical_parameters = line[4].strip()
            location = line[5].strip()
            maintenance_instructions = line[6].strip()
            manufacturer = line[7].strip()
            supplier_name = line[8].strip()
            function_control = line[9].strip()
            process = line[10].strip()
            price_chf = line[11].strip()
            price_eur = line[12].strip()
            price_usd = line[13].strip()
            device_classification = line[14].strip()
            requalification_date = line[15].strip()
            quattek_nr = line[16].strip()
            is_archived = line[17].strip()
            # validation
            if not device_id:
                print(f"ERROR: No 'GeräteNr.' in the following line: {line}")
                continue
            if not device_name:
                print(f"ERROR: No 'Gerätename' in the following line: {line}")
                continue
            if not location or len(location) < 2:
                print(f"ERROR: No 'Standort' in the following line: {line}")
                continue
            if not process or len(process) < 2:
                print(f"ERROR: No 'Gruppe' in the following line: {line}")
                continue
            if process not in group_mapping:
                print(f"ERROR: Unknown 'Gruppe' '{process}' in the following line: {line}")
                continue
            if not device_classification:
                print(f"ERROR: No 'ABC_Kundeneinteilung' in the following line: {line}")
                continue
